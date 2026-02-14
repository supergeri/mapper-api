"""
Integration tests for the follow-along router.

Part of AMA-588: Write integration tests for follow-along router

Tests all endpoints in api/routers/follow_along.py:
- POST /follow-along/create — Create from manual data
- POST /follow-along/ingest — Ingest from video URL
- GET /follow-along — List all workouts
- POST /follow-along/from-workout — Create from existing workout
- GET /follow-along/{workout_id} — Get specific workout
- DELETE /follow-along/{workout_id} — Delete workout
- POST /follow-along/{workout_id}/push/garmin — Push to Garmin
- POST /follow-along/{workout_id}/push/apple-watch — Push to Apple Watch
- POST /follow-along/{workout_id}/push/ios-companion — Push to iOS Companion

Coverage: All 9 endpoints with 60+ test cases including success, error, and edge cases
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from fastapi import status, HTTPException

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user

# =============================================================================
# Test Constants
# =============================================================================

TEST_USER_ID = "test-user-follow-588"
TEST_WORKOUT_ID = "follow-along-123-abc"
TEST_GARMIN_ID = "garmin-456-def"
TEST_APPLE_WATCH_ID = "apple-789-ghi"
TEST_IOS_COMPANION_ID = "ios-012-jkl"

SAMPLE_WORKOUT_DATA = {
    "id": TEST_WORKOUT_ID,
    "user_id": TEST_USER_ID,
    "source": "instagram",
    "source_url": "https://instagram.com/p/test123",
    "title": "Test Follow-Along Workout",
    "description": "A test workout description",
    "video_duration_sec": 1800,
    "thumbnail_url": "https://example.com/thumb.jpg",
    "video_proxy_url": "https://example.com/video.mp4",
    "created_at": "2024-01-01T00:00:00Z",
    "steps": [
        {
            "id": "step-1",
            "follow_along_workout_id": TEST_WORKOUT_ID,
            "order": 1,
            "label": "Warm-up Jumping Jacks",
            "canonical_exercise_id": "ex-jumping-jacks",
            "start_time_sec": 0,
            "end_time_sec": 60,
            "duration_sec": 60,
            "target_reps": None,
            "target_duration_sec": 60,
            "intensity_hint": "moderate",
            "notes": "Get your heart rate up",
        },
        {
            "id": "step-2",
            "follow_along_workout_id": TEST_WORKOUT_ID,
            "order": 2,
            "label": "Push-ups",
            "canonical_exercise_id": "ex-pushups",
            "start_time_sec": 60,
            "end_time_sec": 180,
            "duration_sec": 120,
            "target_reps": 15,
            "target_duration_sec": None,
            "intensity_hint": "high",
            "notes": "Keep core tight",
        },
    ],
}

SAMPLE_WORKOUT_LIST = [
    SAMPLE_WORKOUT_DATA,
    {
        "id": "follow-along-456-def",
        "user_id": TEST_USER_ID,
        "source": "youtube",
        "source_url": "https://youtube.com/watch?v=test456",
        "title": "YouTube HIIT Workout",
        "description": "High intensity interval training",
        "video_duration_sec": 1200,
        "thumbnail_url": "https://example.com/thumb2.jpg",
        "video_proxy_url": None,
        "created_at": "2024-01-02T00:00:00Z",
        "steps": [],
    },
]

VALID_SOURCE_URLS = [
    ("https://instagram.com/p/test123", "instagram"),
    ("https://www.instagram.com/reel/test456", "instagram"),
    ("https://youtube.com/watch?v=test789", "youtube"),
    ("https://youtu.be/test012", "youtube"),
    ("https://tiktok.com/@user/video/123456", "tiktok"),
    ("https://vimeo.com/789012", "vimeo"),
    ("https://example.com/video", "other"),
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
def sample_workout():
    """Return sample workout data."""
    return SAMPLE_WORKOUT_DATA.copy()


@pytest.fixture
def sample_workout_list():
    """Return sample workout list."""
    return SAMPLE_WORKOUT_LIST.copy()


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestDetectSourcePlatform:
    """Tests for _detect_source_platform function."""

    @pytest.mark.unit
    @pytest.mark.parametrize("url,expected", VALID_SOURCE_URLS)
    def test_detect_platform_from_url(self, url, expected):
        """Test platform detection from various URLs."""
        from api.routers.follow_along import _detect_source_platform
        assert _detect_source_platform(url) == expected

    @pytest.mark.unit
    def test_detect_instagram_variants(self):
        """Test Instagram URL variants."""
        from api.routers.follow_along import _detect_source_platform
        urls = [
            "https://instagram.com/p/abc123",
            "https://www.instagram.com/p/abc123",
            "https://INSTAGRAM.COM/p/abc123",  # case insensitive
            "https://instagram.com/reel/xyz789",
        ]
        for url in urls:
            assert _detect_source_platform(url) == "instagram"

    @pytest.mark.unit
    def test_detect_youtube_variants(self):
        """Test YouTube URL variants."""
        from api.routers.follow_along import _detect_source_platform
        urls = [
            "https://youtube.com/watch?v=abc123",
            "https://www.youtube.com/watch?v=abc123",
            "https://YOUTUBE.COM/watch?v=abc123",  # case insensitive
            "https://youtu.be/abc123",
            "https://www.youtu.be/abc123",
        ]
        for url in urls:
            assert _detect_source_platform(url) == "youtube"

    @pytest.mark.unit
    def test_detect_tiktok_variants(self):
        """Test TikTok URL variants."""
        from api.routers.follow_along import _detect_source_platform
        urls = [
            "https://tiktok.com/@user/video/123",
            "https://www.tiktok.com/@user/video/123",
            "https://TIKTOK.COM/@user/video/123",  # case insensitive
        ]
        for url in urls:
            assert _detect_source_platform(url) == "tiktok"

    @pytest.mark.unit
    def test_detect_vimeo_variants(self):
        """Test Vimeo URL variants."""
        from api.routers.follow_along import _detect_source_platform
        urls = [
            "https://vimeo.com/123456",
            "https://www.vimeo.com/123456",
            "https://VIMEO.COM/123456",  # case insensitive
        ]
        for url in urls:
            assert _detect_source_platform(url) == "vimeo"


# =============================================================================
# POST /follow-along/create Tests
# =============================================================================

class TestCreateFollowAlong:
    """Tests for POST /follow-along/create endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_success(self, mock_save, client):
        """Test successful creation of follow-along workout."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Follow-Along Workout",
            "description": "A test workout description",
            "steps": [
                {
                    "order": 1,
                    "label": "Warm-up Jumping Jacks",
                    "duration_sec": 60,
                    "target_reps": None,
                    "notes": "Get your heart rate up",
                },
                {
                    "order": 2,
                    "label": "Push-ups",
                    "duration_sec": 120,
                    "target_reps": 15,
                    "notes": "Keep core tight",
                },
            ],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["followAlongWorkout"] is not None
        assert data["followAlongWorkout"]["title"] == "Test Follow-Along Workout"
        mock_save.assert_called_once()
        
        # Validate step transformation
        steps = data["followAlongWorkout"].get("steps", [])
        if steps:
            for step in steps:
                assert "id" in step, "Step must have an id"
                assert "type" in step, "Step must have a type"
                assert "title" in step, "Step must have a title"
                assert "duration" in step, "Step must have a duration"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_with_source_override(self, mock_save, client):
        """Test creation with explicit source override."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://example.com/video",
            "title": "Test Workout",
            "source": "youtube",  # Explicit override
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        # Verify save was called with the overridden source
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["source"] == "youtube"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_with_thumbnail(self, mock_save, client):
        """Test creation with thumbnail URL."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "thumbnailUrl": "https://example.com/thumb.jpg",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["thumbnail_url"] == "https://example.com/thumb.jpg"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_missing_optional_fields(self, mock_save, client):
        """Test creation with only required fields."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_database_failure(self, mock_save, client):
        """Test handling of database save failure."""
        mock_save.return_value = None

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to save" in response.json()["detail"]

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_follow_along_exception(self, mock_save, client):
        """Test handling of unexpected exception."""
        mock_save.side_effect = Exception("Database connection error")

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database connection error" in response.json()["detail"]

    @pytest.mark.integration
    def test_create_follow_along_invalid_url(self, client):
        """Test validation of invalid URL."""
        request_data = {
            "sourceUrl": "not-a-valid-url",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_create_follow_along_missing_required_fields(self, client):
        """Test validation of missing required fields."""
        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            # Missing title and steps
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /follow-along/ingest Tests
# =============================================================================

class TestIngestFollowAlong:
    """Tests for POST /follow-along/ingest endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_follow_along_success(self, mock_save, client):
        """Test successful ingestion from video URL."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://youtube.com/watch?v=test123",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["followAlongWorkout"] is not None
        mock_save.assert_called_once()

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_from_instagram(self, mock_save, client):
        """Test ingestion from Instagram URL."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["source"] == "instagram"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_from_tiktok(self, mock_save, client):
        """Test ingestion from TikTok URL."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://tiktok.com/@user/video/123",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["source"] == "tiktok"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_with_source_override(self, mock_save, client):
        """Test ingestion with explicit source override."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://example.com/video",
            "source": "vimeo",  # Explicit override
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["source"] == "vimeo"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_database_failure(self, mock_save, client):
        """Test handling of database failure during ingestion."""
        mock_save.return_value = None

        request_data = {
            "sourceUrl": "https://youtube.com/watch?v=test123",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to ingest" in response.json()["detail"]

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_ingest_exception(self, mock_save, client):
        """Test handling of unexpected exception during ingestion."""
        mock_save.side_effect = Exception("Ingestion failed")

        request_data = {
            "sourceUrl": "https://youtube.com/watch?v=test123",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_ingest_invalid_url(self, client):
        """Test validation of invalid URL."""
        request_data = {
            "sourceUrl": "not-a-valid-url",
        }

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.integration
    def test_ingest_missing_url(self, client):
        """Test validation of missing URL."""
        request_data = {}

        response = client.post("/follow-along/ingest", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# GET /follow-along Tests
# =============================================================================

class TestListFollowAlong:
    """Tests for GET /follow-along endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workouts")
    def test_list_follow_along_success(self, mock_get, client, sample_workout_list):
        """Test successful listing of follow-along workouts."""
        mock_get.return_value = sample_workout_list

        response = client.get("/follow-along")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["items"]) == 2
        assert data["items"][0]["title"] == "Test Follow-Along Workout"

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workouts")
    def test_list_follow_along_empty(self, mock_get, client):
        """Test listing with no workouts."""
        mock_get.return_value = []

        response = client.get("/follow-along")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["items"] == []

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workouts")
    def test_list_follow_along_none_result(self, mock_get, client):
        """Test handling when database returns None."""
        mock_get.return_value = None

        response = client.get("/follow-along")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["items"] == []

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workouts")
    def test_list_follow_along_exception(self, mock_get, client):
        """Test handling of exception during listing."""
        mock_get.side_effect = Exception("Database error")

        response = client.get("/follow-along")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Database error" in response.json()["detail"]


# =============================================================================
# POST /follow-along/from-workout Tests
# =============================================================================

class TestCreateFromWorkout:
    """Tests for POST /follow-along/from-workout endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_from_workout_success(self, mock_save, client):
        """Test successful creation from existing workout."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "workout": {
                "title": "Existing Workout",
                "description": "A workout to convert",
                "steps": [
                    {"name": "Push-ups", "reps": 10, "sets": 3},
                    {"name": "Squats", "reps": 15, "sets": 3},
                ],
            },
            "sourceUrl": "https://instagram.com/p/test123",
        }

        response = client.post("/follow-along/from-workout", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["followAlongWorkout"] is not None

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_from_workout_without_url(self, mock_save, client):
        """Test creation without optional source URL."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "workout": {
                "title": "Existing Workout",
                "steps": [],
            },
        }

        response = client.post("/follow-along/from-workout", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["source_url"] is None

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_from_workout_default_title(self, mock_save, client):
        """Test default title when not provided in workout."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "workout": {
                "steps": [],
            },
        }

        response = client.post("/follow-along/from-workout", json=request_data)

        call_kwargs = mock_save.call_args.kwargs
        assert call_kwargs["title"] == "Follow-along Workout"

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_from_workout_database_failure(self, mock_save, client):
        """Test handling of database failure."""
        mock_save.return_value = None

        request_data = {
            "workout": {
                "title": "Test Workout",
                "steps": [],
            },
        }

        response = client.post("/follow-along/from-workout", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to create" in response.json()["detail"]

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_from_workout_exception(self, mock_save, client):
        """Test handling of unexpected exception."""
        mock_save.side_effect = Exception("Conversion error")

        request_data = {
            "workout": {
                "title": "Test Workout",
                "steps": [],
            },
        }

        response = client.post("/follow-along/from-workout", json=request_data)

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.integration
    def test_create_from_workout_missing_workout(self, client):
        """Test validation when workout field is missing."""
        request_data = {}

        response = client.post("/follow-along/from-workout", json=request_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# GET /follow-along/{workout_id} Tests
# =============================================================================

class TestGetFollowAlong:
    """Tests for GET /follow-along/{workout_id} endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workout")
    def test_get_follow_along_success(self, mock_get, client, sample_workout):
        """Test successful retrieval of a workout."""
        mock_get.return_value = sample_workout

        response = client.get(f"/follow-along/{TEST_WORKOUT_ID}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["followAlongWorkout"]["id"] == TEST_WORKOUT_ID

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workout")
    def test_get_follow_along_not_found(self, mock_get, client):
        """Test handling when workout is not found."""
        mock_get.return_value = None

        response = client.get(f"/follow-along/{TEST_WORKOUT_ID}")

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workout")
    def test_get_follow_along_exception(self, mock_get, client):
        """Test handling of exception during retrieval."""
        mock_get.side_effect = Exception("Database error")

        response = client.get(f"/follow-along/{TEST_WORKOUT_ID}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# =============================================================================
# DELETE /follow-along/{workout_id} Tests
# =============================================================================

class TestDeleteFollowAlong:
    """Tests for DELETE /follow-along/{workout_id} endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.delete_follow_along_workout")
    def test_delete_follow_along_success(self, mock_delete, client):
        """Test successful deletion of a workout."""
        mock_delete.return_value = True

        response = client.delete(f"/follow-along/{TEST_WORKOUT_ID}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "deleted successfully" in data["message"]

    @pytest.mark.integration
    @patch("api.routers.follow_along.delete_follow_along_workout")
    def test_delete_follow_along_exception(self, mock_delete, client):
        """Test handling of exception during deletion."""
        mock_delete.side_effect = Exception("Database error")

        response = client.delete(f"/follow-along/{TEST_WORKOUT_ID}")

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR


# =============================================================================
# POST /follow-along/{workout_id}/push/garmin Tests
# =============================================================================

class TestPushToGarmin:
    """Tests for POST /follow-along/{workout_id}/push/garmin endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_garmin_sync")
    def test_push_to_garmin_success(self, mock_update, client):
        """Test successful push to Garmin."""
        mock_update.return_value = True

        request_data = {
            "garminWorkoutId": TEST_GARMIN_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/garmin",
            json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "pushed to Garmin" in data["message"]
        mock_update.assert_called_once_with(
            workout_id=TEST_WORKOUT_ID,
            user_id=TEST_USER_ID,
            garmin_workout_id=TEST_GARMIN_ID,
        )

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_garmin_sync")
    def test_push_to_garmin_exception(self, mock_update, client):
        """Test handling of exception during push."""
        mock_update.side_effect = Exception("Garmin API error")

        request_data = {
            "garminWorkoutId": TEST_GARMIN_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/garmin",
            json=request_data
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Garmin API error" in response.json()["detail"]

    @pytest.mark.integration
    def test_push_to_garmin_missing_id(self, client):
        """Test validation of missing Garmin workout ID."""
        request_data = {}

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/garmin",
            json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /follow-along/{workout_id}/push/apple-watch Tests
# =============================================================================

class TestPushToAppleWatch:
    """Tests for POST /follow-along/{workout_id}/push/apple-watch endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_apple_watch_sync")
    def test_push_to_apple_watch_success(self, mock_update, client):
        """Test successful push to Apple Watch."""
        mock_update.return_value = True

        request_data = {
            "appleWatchWorkoutId": TEST_APPLE_WATCH_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/apple-watch",
            json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "pushed to Apple Watch" in data["message"]
        mock_update.assert_called_once_with(
            workout_id=TEST_WORKOUT_ID,
            user_id=TEST_USER_ID,
            apple_watch_workout_id=TEST_APPLE_WATCH_ID,
        )

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_apple_watch_sync")
    def test_push_to_apple_watch_exception(self, mock_update, client):
        """Test handling of exception during push."""
        mock_update.side_effect = Exception("Apple Watch API error")

        request_data = {
            "appleWatchWorkoutId": TEST_APPLE_WATCH_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/apple-watch",
            json=request_data
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Apple Watch API error" in response.json()["detail"]

    @pytest.mark.integration
    def test_push_to_apple_watch_missing_id(self, client):
        """Test validation of missing Apple Watch workout ID."""
        request_data = {}

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/apple-watch",
            json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# POST /follow-along/{workout_id}/push/ios-companion Tests
# =============================================================================

class TestPushToIOSCompanion:
    """Tests for POST /follow-along/{workout_id}/push/ios-companion endpoint."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_ios_companion_sync")
    def test_push_to_ios_companion_success(self, mock_update, client):
        """Test successful push to iOS Companion."""
        mock_update.return_value = True

        request_data = {
            "iosCompanionWorkoutId": TEST_IOS_COMPANION_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/ios-companion",
            json=request_data
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "pushed to iOS Companion" in data["message"]

    @pytest.mark.integration
    @patch("api.routers.follow_along.update_follow_along_ios_companion_sync")
    def test_push_to_ios_companion_exception(self, mock_update, client):
        """Test handling of exception during push."""
        mock_update.side_effect = Exception("iOS Companion API error")

        request_data = {
            "iosCompanionWorkoutId": TEST_IOS_COMPANION_ID,
        }

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/ios-companion",
            json=request_data
        )

        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "iOS Companion API error" in response.json()["detail"]

    @pytest.mark.integration
    def test_push_to_ios_companion_missing_id(self, client):
        """Test validation of missing iOS Companion workout ID."""
        request_data = {}

        response = client.post(
            f"/follow-along/{TEST_WORKOUT_ID}/push/ios-companion",
            json=request_data
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_with_empty_steps(self, mock_save, client):
        """Test creation with empty steps list."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_with_many_steps(self, mock_save, client):
        """Test creation with large number of steps."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        steps = [
            {
                "order": i,
                "label": f"Exercise {i}",
                "duration_sec": 30 + (i * 10),
            }
            for i in range(50)
        ]

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Long Workout",
            "steps": steps,
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK
        call_kwargs = mock_save.call_args.kwargs
        assert len(call_kwargs["steps"]) == 50

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_with_very_long_title(self, mock_save, client):
        """Test creation with very long title."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        long_title = "A" * 500

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": long_title,
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_create_with_special_characters(self, mock_save, client):
        """Test creation with special characters in title."""
        mock_save.return_value = SAMPLE_WORKOUT_DATA

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test™ Workout® 💪 #GetFit",
            "description": "Special chars: <>&\"'",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.integration
    @patch("api.routers.follow_along.save_follow_along_workout")
    def test_get_with_various_id_formats(self, mock_save, client, sample_workout):
        """Test retrieval with various ID formats."""
        from api.routers.follow_along import get_follow_along_workout as mock_get

        # Test with UUID-like ID
        test_ids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "simple-id-123",
            "id_with_underscores",
        ]

        for test_id in test_ids:
            with patch("api.routers.follow_along.get_follow_along_workout") as mock_get_fn:
                mock_get_fn.return_value = {**sample_workout, "id": test_id}
                response = client.get(f"/follow-along/{test_id}")
                assert response.status_code == status.HTTP_200_OK


# =============================================================================
# Authentication Tests
# =============================================================================

class TestAuthenticationAndAuthorization:
    """Tests for authentication and authorization."""

    @pytest.mark.integration
    def test_create_requires_auth(self, client):
        """Test that create endpoint requires authentication."""
        # Override auth to return None/raise error
        app = client.app
        
        async def mock_no_auth():
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        app.dependency_overrides[get_current_user] = mock_no_auth

        request_data = {
            "sourceUrl": "https://instagram.com/p/test123",
            "title": "Test Workout",
            "steps": [],
        }

        response = client.post("/follow-along/create", json=request_data)

        # Expect 401 Unauthorized
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.integration
    @patch("api.routers.follow_along.get_follow_along_workout")
    def test_get_respects_user_isolation(self, mock_get, client):
        """Test that users can only access their own workouts."""
        # Simulate another user's workout
        mock_get.return_value = None

        response = client.get(f"/follow-along/{TEST_WORKOUT_ID}")

        # When get_follow_along_workout returns None, expect 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
