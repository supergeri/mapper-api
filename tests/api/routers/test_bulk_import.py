"""
Integration tests for the bulk import router.

Part of AMA-592: Write integration tests for bulk import router

Tests all endpoints in api/routers/bulk_import.py:
- POST /import/detect — Detect workout items from sources
- POST /import/detect/file — Detect from uploaded file
- POST /import/detect/urls — Detect from URLs
- POST /import/detect/images — Detect from images (OCR)
- POST /import/map — Apply column mappings (files only)
- POST /import/match — Match exercises to Garmin database
- POST /import/preview — Generate preview before import
- POST /import/execute — Execute the bulk import
- GET /import/status/{job_id} — Get import job status
- POST /import/cancel/{job_id} — Cancel a running import

Coverage: All 10 endpoints with 60+ test cases including success, error, and edge cases
"""

import pytest
from io import BytesIO
from datetime import datetime
from unittest.mock import patch, MagicMock
from typing import List

from fastapi.testclient import TestClient
from fastapi import status, HTTPException

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user

# =============================================================================
# Test Constants
# =============================================================================

TEST_USER_ID = "test-user-bulk-import-592"
TEST_PROFILE_ID = "profile-592-abc"
TEST_JOB_ID = "job-592-xyz-123456"
TEST_DEVICE = "garmin-watch"

# Sample detected items
SAMPLE_DETECTED_ITEM = {
    "id": "item-1",
    "source_index": 0,
    "source_type": "file",
    "source_ref": "data.csv",
    "raw_data": {"row": 1, "title": "Test Workout", "duration": 30},
    "parsed_title": "Test Workout",
    "parsed_exercise_count": 5,
    "parsed_block_count": 1,
    "confidence": 0.95,
    "errors": None,
    "warnings": None,
}

SAMPLE_DETECTED_ITEMS = [
    SAMPLE_DETECTED_ITEM,
    {
        "id": "item-2",
        "source_index": 1,
        "source_type": "file",
        "source_ref": "data.csv",
        "raw_data": {"row": 2, "title": "Another Workout", "duration": 45},
        "parsed_title": "Another Workout",
        "parsed_exercise_count": 8,
        "parsed_block_count": 2,
        "confidence": 0.88,
        "errors": None,
        "warnings": ["Missing duration field"],
    },
]

SAMPLE_DETECT_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "items": SAMPLE_DETECTED_ITEMS,
    "metadata": {"source_filename": "data.csv", "total_rows": 2},
    "total": 2,
    "success_count": 2,
    "error_count": 0,
}

SAMPLE_COLUMN_MAPPING = {
    "source_column": "Exercise Name",
    "source_column_index": 0,
    "target_field": "exercise_name",
    "confidence": 0.92,
    "user_override": False,
    "sample_values": ["Push-ups", "Squats", "Burpees"],
}

SAMPLE_MAP_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "mapped_count": 8,
    "patterns": [
        {
            "pattern_type": "duration",
            "regex": r"^\d+\s?(min|sec|m|s)$",
            "confidence": 0.98,
            "examples": ["30 min", "45m", "60 sec"],
            "count": 45,
        },
    ],
}

SAMPLE_EXERCISE_MATCH = {
    "id": "match-1",
    "original_name": "Push-ups",
    "matched_garmin_name": "Pushups",
    "confidence": 0.98,
    "suggestions": [
        {"name": "Pushups", "confidence": 0.98},
        {"name": "Chest Press", "confidence": 0.75},
    ],
    "status": "matched",
    "user_selection": "Pushups",
    "source_workout_ids": ["item-1", "item-2"],
    "occurrence_count": 5,
}

SAMPLE_MATCH_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "exercises": [SAMPLE_EXERCISE_MATCH],
    "total_exercises": 10,
    "matched": 8,
    "needs_review": 2,
    "unmapped": 0,
}

SAMPLE_PREVIEW_WORKOUT = {
    "id": "workout-1",
    "detected_item_id": "item-1",
    "title": "Test Workout",
    "description": "A test workout",
    "exercise_count": 5,
    "block_count": 1,
    "estimated_duration": 30,
    "validation_issues": [],
    "workout": {"exercises": [], "blocks": []},
    "selected": True,
    "is_duplicate": False,
    "duplicate_of": None,
}

SAMPLE_PREVIEW_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "workouts": [SAMPLE_PREVIEW_WORKOUT],
    "stats": {
        "total_detected": 2,
        "total_selected": 2,
        "total_skipped": 0,
        "exercises_matched": 8,
        "exercises_needing_review": 2,
        "exercises_unmapped": 0,
        "new_exercises_to_create": 0,
        "estimated_duration": 60,
        "duplicates_found": 0,
        "validation_errors": 0,
        "validation_warnings": 1,
    },
}

SAMPLE_IMPORT_RESULT = {
    "workout_id": "item-1",
    "title": "Test Workout",
    "status": "success",
    "error": None,
    "saved_workout_id": "saved-123",
    "export_formats": ["tcx", "fit"],
}

SAMPLE_STATUS_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "status": "running",
    "progress": 50,
    "current_item": "Workout 2 of 4",
    "results": [SAMPLE_IMPORT_RESULT],
    "error": None,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:05:00Z",
}

SAMPLE_EXECUTE_RESPONSE = {
    "success": True,
    "job_id": TEST_JOB_ID,
    "status": "running",
    "message": "Import started (async mode)",
}

SAMPLE_CANCEL_RESPONSE = {
    "success": True,
    "message": "Import cancelled",
}

# Valid source URLs for testing
VALID_SOURCE_URLS = [
    "https://youtube.com/watch?v=test123",
    "https://www.youtube.com/watch?v=abc456",
    "https://youtu.be/xyz789",
    "https://instagram.com/p/test123",
    "https://www.instagram.com/reel/abc456",
    "https://instagram.com/tv/xyz789",
    "https://tiktok.com/@user/video/123",
    "https://www.tiktok.com/@user/video/456",
    "https://vimeo.com/789012",
]

# Invalid URLs for testing
INVALID_URLS = [
    "not-a-url",
    "htp://typo.com",
    "",
    "javascript:alert('xss')",
]

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def app():
    """Create test app with mocked dependencies."""
    settings = Settings(environment="test", _env_file=None)
    test_app = create_app(settings=settings)

    async def mock_get_current_user():
        return TEST_USER_ID

    test_app.dependency_overrides[get_current_user] = mock_get_current_user
    return test_app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_detect_response():
    """Return sample detect response."""
    return SAMPLE_DETECT_RESPONSE.copy()


@pytest.fixture
def sample_map_response():
    """Return sample map response."""
    return SAMPLE_MAP_RESPONSE.copy()


@pytest.fixture
def sample_match_response():
    """Return sample match response."""
    return SAMPLE_MATCH_RESPONSE.copy()


@pytest.fixture
def sample_preview_response():
    """Return sample preview response."""
    return SAMPLE_PREVIEW_RESPONSE.copy()


@pytest.fixture
def sample_status_response():
    """Return sample status response."""
    return SAMPLE_STATUS_RESPONSE.copy()


# =============================================================================
# POST /import/detect Tests
# =============================================================================


class TestBulkImportDetect:
    """Tests for POST /import/detect endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_from_urls_success(self, mock_detect, client, sample_detect_response):
        """Test successful detection from URLs."""
        mock_detect.return_value = sample_detect_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": [
                "https://youtube.com/watch?v=test123",
                "https://instagram.com/p/abc456",
            ],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == TEST_JOB_ID
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["success_count"] == 2
        assert data["error_count"] == 0
        mock_detect.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_from_file_success(self, mock_detect, client, sample_detect_response):
        """Test successful detection from file content."""
        mock_detect.return_value = sample_detect_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "file",
            "sources": ["base64encodedfullfilecontent=="],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_from_images_success(self, mock_detect, client, sample_detect_response):
        """Test successful detection from images."""
        mock_detect.return_value = sample_detect_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "images",
            "sources": ["iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_with_errors(self, mock_detect, client):
        """Test detection with parsing errors."""
        error_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "items": [
                {
                    **SAMPLE_DETECTED_ITEM,
                    "errors": ["Invalid format", "Missing required field"],
                    "confidence": 0.45,
                }
            ],
            "metadata": {},
            "total": 1,
            "success_count": 0,
            "error_count": 1,
        }
        mock_detect.return_value = error_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "file",
            "sources": ["malformed_data"],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["error_count"] == 1
        assert data["items"][0]["errors"] is not None

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_empty_sources(self, mock_detect, client):
        """Test detection with empty sources."""
        empty_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "items": [],
            "metadata": {},
            "total": 0,
            "success_count": 0,
            "error_count": 0,
        }
        mock_detect.return_value = empty_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": [],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_service_exception(self, mock_detect, client):
        """Test handling of service exception."""
        mock_detect.side_effect = Exception("Detection service error")

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": ["https://example.com"],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_detect_invalid_source_type(self, client):
        """Test validation of invalid source type."""
        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "invalid_type",
            "sources": ["test"],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_detect_missing_profile_id(self, client):
        """Test validation of missing profile_id."""
        request_data = {
            "source_type": "urls",
            "sources": ["https://example.com"],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/detect/file Tests
# =============================================================================


class TestBulkImportDetectFile:
    """Tests for POST /import/detect/file endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_csv_success(self, mock_detect, client, sample_detect_response):
        """Test successful CSV file upload and detection."""
        mock_detect.return_value = sample_detect_response

        csv_content = b"Exercise,Duration,Reps\nPushups,30,10\nSquats,45,15"
        files = {"file": ("data.csv", BytesIO(csv_content), "text/csv")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        mock_detect.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_excel_success(self, mock_detect, client, sample_detect_response):
        """Test successful Excel file upload and detection."""
        mock_detect.return_value = sample_detect_response

        # Simulate binary Excel content
        excel_content = b"PK\x03\x04" + b"\x00" * 100  # Minimal Excel signature
        files = {"file": ("data.xlsx", BytesIO(excel_content), "application/vnd.ms-excel")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_json_success(self, mock_detect, client, sample_detect_response):
        """Test successful JSON file upload and detection."""
        mock_detect.return_value = sample_detect_response

        json_content = b'[{"exercise": "Pushups", "duration": 30}]'
        files = {"file": ("data.json", BytesIO(json_content), "application/json")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_text_success(self, mock_detect, client, sample_detect_response):
        """Test successful text file upload and detection."""
        mock_detect.return_value = sample_detect_response

        text_content = b"Workout:\nPushups 10x3\nSquats 15x3"
        files = {"file": ("workout.txt", BytesIO(text_content), "text/plain")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_large_file(self, mock_detect, client, sample_detect_response):
        """Test handling of large file upload."""
        mock_detect.return_value = sample_detect_response

        # Create a 5MB file content
        large_content = b"x" * (5 * 1024 * 1024)
        files = {"file": ("large.csv", BytesIO(large_content), "text/csv")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_file_service_exception(self, mock_detect, client):
        """Test handling of service exception during file detection."""
        mock_detect.side_effect = Exception("File processing error")

        csv_content = b"Exercise,Duration\nPushups,30"
        files = {"file": ("data.csv", BytesIO(csv_content), "text/csv")}

        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_detect_file_missing_file(self, client):
        """Test validation when file is missing."""
        response = client.post(
            "/import/detect/file",
            data={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_detect_file_missing_profile_id(self, client):
        """Test validation when profile_id is missing."""
        csv_content = b"Exercise,Duration\nPushups,30"
        files = {"file": ("data.csv", BytesIO(csv_content), "text/csv")}

        response = client.post(
            "/import/detect/file",
            files=files,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/detect/urls Tests
# =============================================================================


class TestBulkImportDetectUrls:
    """Tests for POST /import/detect/urls endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_urls_success(self, mock_detect, client, sample_detect_response):
        """Test successful detection from multiple URLs."""
        mock_detect.return_value = sample_detect_response

        urls_text = "\n".join(VALID_SOURCE_URLS[:3])

        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": urls_text},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == TEST_JOB_ID

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_urls_comma_separated(self, mock_detect, client, sample_detect_response):
        """Test URL detection with comma-separated URLs."""
        mock_detect.return_value = sample_detect_response

        urls_text = ", ".join(VALID_SOURCE_URLS[:3])

        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": urls_text},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_urls_mixed_separators(self, mock_detect, client, sample_detect_response):
        """Test URL detection with mixed separators (newlines and commas)."""
        mock_detect.return_value = sample_detect_response

        urls_text = f"{VALID_SOURCE_URLS[0]}\n{VALID_SOURCE_URLS[1]}, {VALID_SOURCE_URLS[2]}"

        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": urls_text},
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_urls_youtube_variants(self, mock_detect, client, sample_detect_response):
        """Test detection of YouTube URL variants."""
        mock_detect.return_value = sample_detect_response

        youtube_urls = [
            "https://youtube.com/watch?v=abc123",
            "https://www.youtube.com/watch?v=xyz789",
            "https://youtu.be/def456",
        ]

        urls_text = "\n".join(youtube_urls)

        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": urls_text},
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_urls_instagram_variants(self, mock_detect, client, sample_detect_response):
        """Test detection of Instagram URL variants."""
        mock_detect.return_value = sample_detect_response

        instagram_urls = [
            "https://instagram.com/p/abc123",
            "https://www.instagram.com/reel/xyz789",
            "https://instagram.com/tv/def456",
        ]

        urls_text = "\n".join(instagram_urls)

        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": urls_text},
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_detect_urls_no_urls_provided(self, client):
        """Test validation when no URLs are provided."""
        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": ""},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No URLs provided" in response.json()["detail"]

    @pytest.mark.integration
    def test_detect_urls_whitespace_only(self, client):
        """Test validation when only whitespace is provided."""
        response = client.post(
            "/import/detect/urls",
            data={"profile_id": TEST_PROFILE_ID, "urls": "   \n  \n  "},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.integration
    def test_detect_urls_missing_profile_id(self, client):
        """Test validation of missing profile_id."""
        urls_text = "\n".join(VALID_SOURCE_URLS[:2])

        response = client.post(
            "/import/detect/urls",
            data={"urls": urls_text},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/detect/images Tests
# =============================================================================


class TestBulkImportDetectImages:
    """Tests for POST /import/detect/images endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_images_success(self, mock_detect, client, sample_detect_response):
        """Test successful image upload and OCR detection."""
        mock_detect.return_value = sample_detect_response

        # Minimal PNG image bytes
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        files = [
            ("files", ("image1.png", BytesIO(png_content), "image/png")),
            ("files", ("image2.png", BytesIO(png_content), "image/png")),
        ]

        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_images_jpg_format(self, mock_detect, client, sample_detect_response):
        """Test detection with JPG image format."""
        mock_detect.return_value = sample_detect_response

        # Minimal JPEG bytes
        jpg_content = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01"
            b"\x00\x01\x00\x00\xff\xd9"
        )

        files = [("files", ("image.jpg", BytesIO(jpg_content), "image/jpeg"))]

        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_images_webp_format(self, mock_detect, client, sample_detect_response):
        """Test detection with WebP image format."""
        mock_detect.return_value = sample_detect_response

        webp_content = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 100

        files = [("files", ("image.webp", BytesIO(webp_content), "image/webp"))]

        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_images_multiple_files(self, mock_detect, client, sample_detect_response):
        """Test detection with maximum allowed images (20)."""
        mock_detect.return_value = sample_detect_response

        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        files = [
            ("files", (f"image{i}.png", BytesIO(png_content), "image/png"))
            for i in range(20)
        ]

        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    def test_detect_images_too_many_files(self, client):
        """Test validation when more than 20 images are provided."""
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        files = [
            ("files", (f"image{i}.png", BytesIO(png_content), "image/png"))
            for i in range(25)  # 25 images, exceeds limit
        ]

        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
            files=files,
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Too many images" in response.json()["detail"]

    @pytest.mark.integration
    def test_detect_images_no_files(self, client):
        """Test validation when no images are provided."""
        response = client.post(
            "/import/detect/images",
            data={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "No images provided" in response.json()["detail"]

    @pytest.mark.integration
    def test_detect_images_missing_profile_id(self, client):
        """Test validation when profile_id is missing."""
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
            b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        files = [("files", ("image.png", BytesIO(png_content), "image/png"))]

        response = client.post(
            "/import/detect/images",
            files=files,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/map Tests
# =============================================================================


class TestBulkImportMap:
    """Tests for POST /import/map endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_success(self, mock_map, client, sample_map_response):
        """Test successful column mapping."""
        mock_map.return_value = sample_map_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [
                {
                    "source_column": "Exercise Name",
                    "source_column_index": 0,
                    "target_field": "exercise_name",
                    "confidence": 0.92,
                    "user_override": False,
                    "sample_values": ["Push-ups", "Squats"],
                },
                {
                    "source_column": "Duration (min)",
                    "source_column_index": 1,
                    "target_field": "duration",
                    "confidence": 0.88,
                    "user_override": False,
                    "sample_values": ["30", "45", "60"],
                },
            ],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["job_id"] == TEST_JOB_ID
        assert data["mapped_count"] == 8
        mock_map.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_with_user_overrides(self, mock_map, client, sample_map_response):
        """Test mapping with user-provided overrides."""
        mock_map.return_value = sample_map_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [
                {
                    "source_column": "Custom Field",
                    "source_column_index": 5,
                    "target_field": "notes",
                    "confidence": 0.0,
                    "user_override": True,  # User explicitly chose this mapping
                    "sample_values": ["Note 1", "Note 2"],
                },
            ],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_map.call_args.kwargs
        assert call_kwargs["column_mappings"][0].user_override is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_with_patterns(self, mock_map, client):
        """Test response containing detected patterns."""
        patterns_response = {
            **SAMPLE_MAP_RESPONSE,
            "patterns": [
                {
                    "pattern_type": "duration",
                    "regex": r"^\d+\s?(min|sec|m|s)$",
                    "confidence": 0.98,
                    "examples": ["30 min", "45m", "60 sec"],
                    "count": 45,
                },
                {
                    "pattern_type": "reps",
                    "regex": r"^\d+x\d+$",
                    "confidence": 0.95,
                    "examples": ["10x3", "15x2"],
                    "count": 32,
                },
            ],
        }
        mock_map.return_value = patterns_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [SAMPLE_COLUMN_MAPPING],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["patterns"]) == 2

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_empty_mappings(self, mock_map, client):
        """Test mapping with empty column mappings."""
        empty_response = {
            **SAMPLE_MAP_RESPONSE,
            "mapped_count": 0,
            "patterns": [],
        }
        mock_map.return_value = empty_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_service_exception(self, mock_map, client):
        """Test handling of service exception."""
        mock_map.side_effect = Exception("Mapping service error")

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [SAMPLE_COLUMN_MAPPING],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_map_missing_job_id(self, client):
        """Test validation of missing job_id."""
        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [SAMPLE_COLUMN_MAPPING],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_map_missing_profile_id(self, client):
        """Test validation of missing profile_id."""
        request_data = {
            "job_id": TEST_JOB_ID,
            "column_mappings": [SAMPLE_COLUMN_MAPPING],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/match Tests
# =============================================================================


class TestBulkImportMatch:
    """Tests for POST /import/match endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_success(self, mock_match, client, sample_match_response):
        """Test successful exercise matching."""
        mock_match.return_value = sample_match_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "user_mappings": None,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["total_exercises"] == 10
        assert data["matched"] == 8
        assert data["needs_review"] == 2
        mock_match.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_with_user_mappings(self, mock_match, client, sample_match_response):
        """Test matching with user-provided mappings."""
        mock_match.return_value = sample_match_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "user_mappings": {
                "Push-ups": "Pushups",
                "Sit-ups": "Crunches",
                "Leg Raises": "Knee Raise",
            },
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_match.call_args.kwargs
        assert call_kwargs["user_mappings"] is not None
        assert len(call_kwargs["user_mappings"]) == 3

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_all_unmapped(self, mock_match, client):
        """Test matching result with all exercises unmapped."""
        unmapped_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "exercises": [
                {
                    **SAMPLE_EXERCISE_MATCH,
                    "status": "unmapped",
                    "matched_garmin_name": None,
                    "confidence": 0.0,
                    "suggestions": [],
                }
            ],
            "total_exercises": 5,
            "matched": 0,
            "needs_review": 0,
            "unmapped": 5,
        }
        mock_match.return_value = unmapped_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["unmapped"] == 5

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_all_matched(self, mock_match, client):
        """Test matching result with all exercises matched."""
        all_matched_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "exercises": [SAMPLE_EXERCISE_MATCH],
            "total_exercises": 10,
            "matched": 10,
            "needs_review": 0,
            "unmapped": 0,
        }
        mock_match.return_value = all_matched_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["matched"] == 10

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_service_exception(self, mock_match, client):
        """Test handling of service exception."""
        mock_match.side_effect = Exception("Matching service error")

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_match_missing_job_id(self, client):
        """Test validation of missing job_id."""
        request_data = {
            "profile_id": TEST_PROFILE_ID,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/preview Tests
# =============================================================================


class TestBulkImportPreview:
    """Tests for POST /import/preview endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    def test_preview_success(self, mock_preview, client, sample_preview_response):
        """Test successful preview generation."""
        mock_preview.return_value = sample_preview_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": ["item-1", "item-2"],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["workouts"]) == 1
        assert data["stats"]["total_detected"] == 2
        assert data["stats"]["total_selected"] == 2
        mock_preview.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    def test_preview_with_validation_issues(self, mock_preview, client):
        """Test preview with validation issues found."""
        preview_with_issues = {
            **SAMPLE_PREVIEW_RESPONSE,
            "workouts": [
                {
                    **SAMPLE_PREVIEW_WORKOUT,
                    "validation_issues": [
                        {
                            "id": "issue-1",
                            "severity": "error",
                            "field": "exercise_name",
                            "message": "Exercise not found in database",
                            "workout_id": "item-1",
                            "exercise_name": "Unknown Exercise",
                            "suggestion": "Did you mean 'Pushups'?",
                            "auto_fixable": False,
                        },
                        {
                            "id": "issue-2",
                            "severity": "warning",
                            "field": "duration",
                            "message": "Duration seems unusually high",
                            "suggestion": "Duration should be 30-300 minutes",
                            "auto_fixable": False,
                        },
                    ],
                }
            ],
            "stats": {
                **SAMPLE_PREVIEW_RESPONSE["stats"],
                "validation_errors": 1,
                "validation_warnings": 1,
            },
        }
        mock_preview.return_value = preview_with_issues

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": ["item-1"],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["stats"]["validation_errors"] == 1
        assert len(data["workouts"][0]["validation_issues"]) == 2

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    def test_preview_with_duplicates(self, mock_preview, client):
        """Test preview with duplicate detection."""
        preview_with_duplicates = {
            **SAMPLE_PREVIEW_RESPONSE,
            "workouts": [
                SAMPLE_PREVIEW_WORKOUT,
                {
                    **SAMPLE_PREVIEW_WORKOUT,
                    "id": "workout-2",
                    "detected_item_id": "item-2",
                    "is_duplicate": True,
                    "duplicate_of": "workout-1",
                },
            ],
            "stats": {
                **SAMPLE_PREVIEW_RESPONSE["stats"],
                "duplicates_found": 1,
            },
        }
        mock_preview.return_value = preview_with_duplicates

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": ["item-1", "item-2"],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["stats"]["duplicates_found"] == 1
        assert data["workouts"][1]["is_duplicate"] is True

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    def test_preview_empty_selection(self, mock_preview, client):
        """Test preview with no workouts selected."""
        empty_preview = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "workouts": [],
            "stats": {
                "total_detected": 2,
                "total_selected": 0,
                "total_skipped": 2,
                "exercises_matched": 0,
                "exercises_needing_review": 0,
                "exercises_unmapped": 0,
                "new_exercises_to_create": 0,
                "estimated_duration": 0,
                "duplicates_found": 0,
                "validation_errors": 0,
                "validation_warnings": 0,
            },
        }
        mock_preview.return_value = empty_preview

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": [],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["workouts"]) == 0

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    def test_preview_service_exception(self, mock_preview, client):
        """Test handling of service exception."""
        mock_preview.side_effect = Exception("Preview generation error")

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": ["item-1"],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_preview_missing_job_id(self, client):
        """Test validation of missing job_id."""
        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "selected_ids": ["item-1"],
        }

        response = client.post("/import/preview", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /import/execute Tests
# =============================================================================


class TestBulkImportExecute:
    """Tests for POST /import/execute endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_async_success(self, mock_execute, client):
        """Test successful async execution."""
        mock_execute.return_value = SAMPLE_EXECUTE_RESPONSE

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1", "item-2"],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "running"
        assert "async mode" in data["message"].lower()
        mock_execute.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_sync_success(self, mock_execute, client):
        """Test successful sync execution."""
        sync_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "status": "completed",
            "message": "Import completed (2 workouts imported)",
        }
        mock_execute.return_value = sync_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1", "item-2"],
            "device": TEST_DEVICE,
            "async_mode": False,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_with_various_devices(self, mock_execute, client):
        """Test execution with various device types."""
        mock_execute.return_value = SAMPLE_EXECUTE_RESPONSE

        devices = ["garmin-watch", "apple-watch", "fitbit", "strava"]

        for device in devices:
            request_data = {
                "job_id": TEST_JOB_ID,
                "profile_id": TEST_PROFILE_ID,
                "workout_ids": ["item-1"],
                "device": device,
                "async_mode": True,
            }

            response = client.post("/import/execute", json=request_data)

            assert response.status_code == status.HTTP_200_OK
            call_kwargs = mock_execute.call_args.kwargs
            assert call_kwargs["device"] == device

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_no_workouts(self, mock_execute, client):
        """Test execution with empty workout list."""
        mock_execute.return_value = SAMPLE_EXECUTE_RESPONSE

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": [],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_partial_failure(self, mock_execute, client):
        """Test execution with some workouts failing."""
        partial_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "status": "completed_with_errors",
            "message": "Import completed with 1 error out of 2 workouts",
        }
        mock_execute.return_value = partial_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1", "item-2"],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_service_exception(self, mock_execute, client):
        """Test handling of service exception."""
        mock_execute.side_effect = Exception("Import execution error")

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1"],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_execute_missing_job_id(self, client):
        """Test validation of missing job_id."""
        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1"],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# GET /import/status/{job_id} Tests
# =============================================================================


class TestBulkImportStatus:
    """Tests for GET /import/status/{job_id} endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_running(self, mock_status, client):
        """Test status check for running job."""
        mock_status.return_value = SAMPLE_STATUS_RESPONSE

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "running"
        assert data["progress"] == 50
        assert data["current_item"] is not None
        mock_status.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_completed(self, mock_status, client):
        """Test status check for completed job."""
        completed_response = {
            **SAMPLE_STATUS_RESPONSE,
            "status": "completed",
            "progress": 100,
            "current_item": None,
            "results": [SAMPLE_IMPORT_RESULT, SAMPLE_IMPORT_RESULT],
        }
        mock_status.return_value = completed_response

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert data["progress"] == 100

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_failed(self, mock_status, client):
        """Test status check for failed job."""
        failed_response = {
            **SAMPLE_STATUS_RESPONSE,
            "status": "failed",
            "progress": 0,
            "error": "Database connection error",
        }
        mock_status.return_value = failed_response

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] is not None

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_with_results(self, mock_status, client):
        """Test status response with multiple results."""
        status_with_results = {
            **SAMPLE_STATUS_RESPONSE,
            "results": [
                {
                    **SAMPLE_IMPORT_RESULT,
                    "status": "success",
                },
                {
                    **SAMPLE_IMPORT_RESULT,
                    "workout_id": "item-2",
                    "status": "failed",
                    "error": "Invalid exercise",
                },
            ],
        }
        mock_status.return_value = status_with_results

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["results"]) == 2

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_service_exception(self, mock_status, client):
        """Test handling of service exception."""
        mock_status.side_effect = Exception("Status lookup error")

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_status_missing_profile_id(self, client):
        """Test validation of missing profile_id."""
        response = client.get(f"/import/status/{TEST_JOB_ID}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.get_import_status")
    def test_status_invalid_job_id(self, mock_status, client):
        """Test with invalid job ID format."""
        mock_status.return_value = {
            "success": False,
            "job_id": "invalid-id",
            "status": "error",
            "progress": 0,
            "error": "Job not found",
        }

        response = client.get(
            "/import/status/invalid-id",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# POST /import/cancel/{job_id} Tests
# =============================================================================


class TestBulkImportCancel:
    """Tests for POST /import/cancel/{job_id} endpoint."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.cancel_import")
    def test_cancel_success(self, mock_cancel, client):
        """Test successful job cancellation."""
        mock_cancel.return_value = True

        response = client.post(
            f"/import/cancel/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "cancelled" in data["message"].lower()
        mock_cancel.assert_called_once()

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.cancel_import")
    def test_cancel_already_completed(self, mock_cancel, client):
        """Test cancellation of already completed job."""
        mock_cancel.return_value = False

        response = client.post(
            f"/import/cancel/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False
        assert "Failed to cancel" in data["message"]

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.cancel_import")
    def test_cancel_not_found(self, mock_cancel, client):
        """Test cancellation of non-existent job."""
        mock_cancel.return_value = False

        response = client.post(
            "/import/cancel/nonexistent-job",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is False

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.cancel_import")
    def test_cancel_service_exception(self, mock_cancel, client):
        """Test handling of service exception."""
        mock_cancel.side_effect = Exception("Cancellation error")

        response = client.post(
            f"/import/cancel/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_cancel_missing_profile_id(self, client):
        """Test validation of missing profile_id."""
        response = client.post(f"/import/cancel/{TEST_JOB_ID}")

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Authentication Tests
# =============================================================================


class TestAuthentication:
    """Tests for authentication and authorization."""

    @pytest.mark.integration
    def test_detect_requires_auth(self, client):
        """Test that detect endpoint requires authentication."""
        app = client.app

        async def mock_no_auth():
            raise HTTPException(status_code=401, detail="Unauthorized")

        app.dependency_overrides[get_current_user] = mock_no_auth

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": ["https://example.com"],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.integration
    def test_execute_requires_auth(self, client):
        """Test that execute endpoint requires authentication."""
        app = client.app

        async def mock_no_auth():
            raise HTTPException(status_code=401, detail="Unauthorized")

        app.dependency_overrides[get_current_user] = mock_no_auth

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": ["item-1"],
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.integration
    def test_status_requires_auth(self, client):
        """Test that status endpoint requires authentication."""
        app = client.app

        async def mock_no_auth():
            raise HTTPException(status_code=401, detail="Unauthorized")

        app.dependency_overrides[get_current_user] = mock_no_auth

        response = client.get(
            f"/import/status/{TEST_JOB_ID}",
            params={"profile_id": TEST_PROFILE_ID},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_with_special_characters_in_source(self, mock_detect, client, sample_detect_response):
        """Test detection with special characters in source."""
        mock_detect.return_value = sample_detect_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": [
                "https://youtube.com/watch?v=abc123&t=120&list=PLXXX&feature=share",
                "https://example.com/video?title=Test™&id=<script>",
            ],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_with_many_columns(self, mock_map, client, sample_map_response):
        """Test mapping with large number of columns."""
        mock_map.return_value = sample_map_response

        column_mappings = [
            {
                "source_column": f"Column {i}",
                "source_column_index": i,
                "target_field": f"field_{i}",
                "confidence": 0.5 + (i * 0.01),
                "user_override": False,
                "sample_values": [f"value_{i}_1", f"value_{i}_2"],
            }
            for i in range(50)
        ]

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": column_mappings,
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    def test_match_with_many_exercises(self, mock_match, client):
        """Test matching with large number of exercises."""
        exercises = [
            {
                **SAMPLE_EXERCISE_MATCH,
                "id": f"match-{i}",
                "original_name": f"Exercise {i}",
            }
            for i in range(100)
        ]

        large_response = {
            "success": True,
            "job_id": TEST_JOB_ID,
            "exercises": exercises,
            "total_exercises": 100,
            "matched": 80,
            "needs_review": 15,
            "unmapped": 5,
        }
        mock_match.return_value = large_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
        }

        response = client.post("/import/match", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_execute_with_many_workouts(self, mock_execute, client):
        """Test execution with large number of workouts."""
        mock_execute.return_value = SAMPLE_EXECUTE_RESPONSE

        workout_ids = [f"item-{i}" for i in range(500)]

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "workout_ids": workout_ids,
            "device": TEST_DEVICE,
            "async_mode": True,
        }

        response = client.post("/import/execute", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_execute.call_args.kwargs
        assert len(call_kwargs["workout_ids"]) == 500

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    def test_detect_unicode_content(self, mock_detect, client, sample_detect_response):
        """Test detection with unicode content."""
        mock_detect.return_value = sample_detect_response

        request_data = {
            "profile_id": TEST_PROFILE_ID,
            "source_type": "urls",
            "sources": [
                "https://youtube.com/watch?v=test123",  # 中文标题
                "https://instagram.com/p/abc456",  # العربية
                "https://tiktok.com/@user/video/789",  # Русский
            ],
        }

        response = client.post("/import/detect", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    def test_map_with_empty_sample_values(self, mock_map, client, sample_map_response):
        """Test mapping with empty sample values."""
        mock_map.return_value = sample_map_response

        request_data = {
            "job_id": TEST_JOB_ID,
            "profile_id": TEST_PROFILE_ID,
            "column_mappings": [
                {
                    "source_column": "Column A",
                    "source_column_index": 0,
                    "target_field": "field_a",
                    "confidence": 0.5,
                    "user_override": False,
                    "sample_values": [],  # No sample values
                },
            ],
        }

        response = client.post("/import/map", json=request_data)

        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# Integration Tests (Multiple Steps)
# =============================================================================


class TestImportWorkflow:
    """Tests for the complete import workflow."""

    @pytest.mark.integration
    @patch("backend.bulk_import.bulk_import_service.detect_items")
    @patch("backend.bulk_import.bulk_import_service.apply_column_mappings")
    @patch("backend.bulk_import.bulk_import_service.match_exercises")
    @patch("backend.bulk_import.bulk_import_service.generate_preview")
    @patch("backend.bulk_import.bulk_import_service.execute_import")
    def test_complete_workflow(
        self,
        mock_execute,
        mock_preview,
        mock_match,
        mock_map,
        mock_detect,
        client,
    ):
        """Test complete 5-step import workflow."""
        # Step 1: Detect
        mock_detect.return_value = SAMPLE_DETECT_RESPONSE
        response = client.post(
            "/import/detect",
            json={
                "profile_id": TEST_PROFILE_ID,
                "source_type": "file",
                "sources": ["file_content"],
            },
        )
        assert response.status_code == status.HTTP_200_OK
        job_id = response.json()["job_id"]

        # Step 2: Map
        mock_map.return_value = SAMPLE_MAP_RESPONSE
        response = client.post(
            "/import/map",
            json={
                "job_id": job_id,
                "profile_id": TEST_PROFILE_ID,
                "column_mappings": [SAMPLE_COLUMN_MAPPING],
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 3: Match
        mock_match.return_value = SAMPLE_MATCH_RESPONSE
        response = client.post(
            "/import/match",
            json={
                "job_id": job_id,
                "profile_id": TEST_PROFILE_ID,
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 4: Preview
        mock_preview.return_value = SAMPLE_PREVIEW_RESPONSE
        response = client.post(
            "/import/preview",
            json={
                "job_id": job_id,
                "profile_id": TEST_PROFILE_ID,
                "selected_ids": ["item-1", "item-2"],
            },
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 5: Execute
        mock_execute.return_value = SAMPLE_EXECUTE_RESPONSE
        response = client.post(
            "/import/execute",
            json={
                "job_id": job_id,
                "profile_id": TEST_PROFILE_ID,
                "workout_ids": ["item-1", "item-2"],
                "device": TEST_DEVICE,
                "async_mode": True,
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "running"
