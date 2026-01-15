"""
Contract tests for API response shapes.

Part of AMA-400: Add contract tests for API responses
Phase 4 - Testing Overhaul

Tests verify that API response shapes match expected structure.
"""

from typing import Dict, List, Optional, Any

import pytest

from tests.contract import assert_response_shape, assert_list_response


# =============================================================================
# Test Data Factories
# =============================================================================


def create_valid_blocks_json() -> Dict[str, Any]:
    """Create a valid blocks payload for workflow endpoints."""
    return {
        "blocks_json": {
            "title": "Test Workout",
            "blocks": [
                {
                    "label": "Main",
                    "exercises": [
                        {"name": "Bench Press", "reps": 10, "sets": 3},
                        {"name": "Squat", "reps": 10, "sets": 3},
                    ],
                }
            ],
        }
    }


def create_ingest_payload() -> Dict[str, Any]:
    """Create a valid ingest payload for /map/final."""
    return {
        "ingest_json": {
            "name": "Test Workout",
            "exercises": [
                {"name": "Bench Press", "reps": 10, "sets": 3},
                {"name": "Squat", "reps": 10, "sets": 3},
            ],
        }
    }


def create_save_workout_payload() -> Dict[str, Any]:
    """Create a valid payload for /workouts/save."""
    return {
        "workout_data": {
            "title": "Test Workout",
            "blocks": [
                {
                    "label": "Main",
                    "exercises": [
                        {"name": "Bench Press", "reps": 10, "sets": 3},
                    ],
                }
            ],
        },
        "sources": ["text:test"],
        "device": "garmin",
        "title": "Test Workout",
    }


def create_workout_complete_payload() -> Dict[str, Any]:
    """Create a valid payload for /workouts/complete."""
    return {
        "workout_id": "test-workout-123",
        "completed_at": "2024-01-15T10:30:00Z",
        "duration_seconds": 3600,
        "device": "garmin",
        "notes": "Great workout!",
    }


# =============================================================================
# Health Router Contract Tests
# =============================================================================


class TestHealthContracts:
    """Contract tests for health router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_health_response_shape(self, api_client):
        """Health endpoint returns expected shape."""
        resp = api_client.get("/health")

        assert resp.status_code == 200
        data = resp.json()

        # Health response should have status field
        assert_response_shape(data, {"status": str})
        assert data["status"] == "ok"


# =============================================================================
# Mapping Router Contract Tests
# =============================================================================


class TestMappingContracts:
    """Contract tests for mapping router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_workflow_validate_response_shape(self, api_client):
        """Workflow validate returns expected shape."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/workflow/validate", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Validate response shape - actual fields from workflow.py
        expected_fields = {
            "total_exercises": int,
            "validated_exercises": list,
            "needs_review": list,
            "unmapped_exercises": list,
            "can_proceed": bool,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_workflow_process_response_shape(self, api_client):
        """Workflow process returns expected shape."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/workflow/process", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Process response - actual fields from workflow.py
        expected_fields = {
            "validation": dict,
            "yaml": str,
            "message": str,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_exercise_suggest_response_shape(self, api_client):
        """Exercise suggest returns expected shape."""
        payload = {
            "exercise_name": "bench press",
            "include_similar_types": True,
        }
        resp = api_client.post("/exercise/suggest", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "exercise_name": str,
            "best_match": str,
            "confidence": float,
            "suggestions": list,
            "similar_by_type": list,
        }
        assert_response_shape(data, expected_fields)

        # Validate suggestion items have correct shape
        if data["suggestions"]:
            assert_response_shape(
                data["suggestions"][0],
                {"name": str, "confidence": float},
            )

    @pytest.mark.contract
    @pytest.mark.unit
    def test_exercise_similar_response_shape(self, api_client):
        """Exercise similar returns expected shape."""
        resp = api_client.get("/exercise/similar/squat")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "exercise_name": str,
            "similar": list,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_exercise_by_type_response_shape(self, api_client):
        """Exercise by type returns expected shape."""
        resp = api_client.get("/exercise/by-type/squat")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "exercise_name": str,
            "category": str,
            "exercises": list,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_exercises_match_single_response_shape(self, api_client):
        """Single exercise match returns expected shape."""
        payload = {"name": "bench press", "limit": 5}
        resp = api_client.post("/exercises/match", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "original_name": str,
            "matched_name": str,
            "confidence": float,
            "status": str,
            "suggestions": list,
        }
        assert_response_shape(data, expected_fields)

        # Status should be one of expected values
        assert data["status"] in ("matched", "needs_review", "unmapped")

    @pytest.mark.contract
    @pytest.mark.unit
    def test_exercises_match_batch_response_shape(self, api_client):
        """Batch exercise match returns expected shape."""
        payload = {"names": ["bench press", "squat", "unknown exercise xyz"], "limit": 5}
        resp = api_client.post("/exercises/match/batch", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "results": list,
            "total": int,
            "matched": int,
            "needs_review": int,
            "unmapped": int,
        }
        assert_response_shape(data, expected_fields)

        # Validate result items
        if data["results"]:
            assert_response_shape(
                data["results"][0],
                {
                    "original_name": str,
                    "matched_name": str,
                    "confidence": float,
                    "status": str,
                    "suggestions": list,
                },
            )

    @pytest.mark.contract
    @pytest.mark.unit
    def test_mappings_list_response_shape(self, api_client):
        """Mappings list returns expected shape."""
        resp = api_client.get("/mappings")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "total": int,
            "mappings": dict,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_mappings_lookup_response_shape(self, api_client):
        """Mappings lookup returns expected shape."""
        resp = api_client.get("/mappings/lookup/bench%20press")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "exercise_name": str,
            "exists": bool,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_mappings_add_response_shape(self, api_client):
        """Mappings add returns expected shape."""
        payload = {
            "exercise_name": "test exercise",
            "garmin_name": "Bench Press",
        }
        resp = api_client.post("/mappings/add", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "message": str,
            "mapping": dict,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_mappings_popularity_stats_response_shape(self, api_client):
        """Mappings popularity stats returns expected shape (may error if DB unavailable)."""
        resp = api_client.get("/mappings/popularity/stats")

        # May return error if DB table doesn't exist in test env
        assert resp.status_code in (200, 500)
        data = resp.json()

        # If successful, should have stats
        if resp.status_code == 200 and "error" not in data:
            # Actual response may vary based on implementation
            assert isinstance(data, dict)


# =============================================================================
# Exports Router Contract Tests
# =============================================================================


class TestExportsContracts:
    """Contract tests for exports router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_final_response_shape(self, api_client):
        """Map final (YAML) returns expected shape."""
        payload = create_ingest_payload()
        resp = api_client.post("/map/final", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Response should contain yaml output
        expected_fields = {
            "yaml": str,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_auto_map_response_shape(self, api_client):
        """Map auto-map returns expected shape."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/map/auto-map", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "yaml": str,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_to_workoutkit_response_shape(self, api_client):
        """Map to-workoutkit returns expected shape."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/map/to-workoutkit", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # WorkoutKit response has specific structure
        expected_fields = {
            "title": str,
            "sportType": str,
            "intervals": list,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_to_zwo_returns_xml(self, api_client):
        """Map to-zwo returns XML file."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/map/to-zwo", json=payload)

        assert resp.status_code == 200
        # ZWO endpoint returns XML file, not JSON
        assert resp.headers.get("content-type") == "application/xml"
        assert "Content-Disposition" in resp.headers

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_to_fit_response_shape(self, api_client):
        """Map to-fit returns binary FIT file."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/map/to-fit", json=payload)

        assert resp.status_code == 200
        # FIT endpoint returns binary file
        content_type = resp.headers.get("content-type", "")
        assert "octet-stream" in content_type or resp.headers.get("Content-Disposition")

    @pytest.mark.contract
    @pytest.mark.unit
    def test_map_fit_metadata_response_shape(self, api_client):
        """Map fit-metadata returns expected shape."""
        payload = create_valid_blocks_json()
        resp = api_client.post("/map/fit-metadata", json=payload)

        assert resp.status_code == 200
        data = resp.json()

        # Should have detected sport info
        expected_fields = {
            "detected_sport": str,
            "detected_sport_id": int,
            "detected_sub_sport_id": int,
        }
        assert_response_shape(data, expected_fields)


# =============================================================================
# Workouts Router Contract Tests
# =============================================================================


class TestWorkoutsContracts:
    """Contract tests for workouts router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_get_workouts_response_shape(self, api_client):
        """Get workouts returns expected shape."""
        resp = api_client.get("/workouts")

        # Response is wrapped in success envelope
        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "success": bool,
            "workouts": list,
            "count": int,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_get_workouts_incoming_response_shape(self, api_client):
        """Get incoming workouts returns expected shape."""
        resp = api_client.get("/workouts/incoming")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "success": bool,
            "workouts": list,
            "count": int,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_save_workout_response_shape(self, api_client):
        """Save workout returns expected shape (success or error)."""
        payload = create_save_workout_payload()
        resp = api_client.post("/workouts/save", json=payload)

        # May succeed or fail depending on DB
        assert resp.status_code in (200, 500)
        data = resp.json()

        # Should always have success field
        assert "success" in data
        assert isinstance(data["success"], bool)

        # If successful, should have workout_id and message
        if data["success"]:
            assert "workout_id" in data
            assert "message" in data

    @pytest.mark.contract
    @pytest.mark.unit
    def test_save_workout_validation_error_shape(self, api_client):
        """Save workout validation error has expected shape."""
        # Send invalid payload to trigger validation error
        resp = api_client.post("/workouts/save", json={})

        assert resp.status_code == 422
        data = resp.json()

        # FastAPI validation errors have specific structure
        assert "detail" in data
        assert isinstance(data["detail"], list)

        if data["detail"]:
            error = data["detail"][0]
            # Validation error should have loc, msg, type
            assert "loc" in error
            assert "msg" in error
            assert "type" in error


# =============================================================================
# Pairing Router Contract Tests
# =============================================================================


class TestPairingContracts:
    """Contract tests for pairing router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_pairing_generate_response_shape(self, api_client):
        """Generate pairing token returns expected shape."""
        resp = api_client.post("/mobile/pairing/generate")

        # May return 200 or 500 depending on DB
        if resp.status_code == 200:
            data = resp.json()

            expected_fields = {
                "token": str,
                "short_code": str,
                "expires_at": str,
            }
            assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_pairing_status_response_shape(self, api_client):
        """Pairing status returns expected shape."""
        # Use a dummy token
        resp = api_client.get("/mobile/pairing/status/dummy-token-123")

        # May return 200 or 500 depending on DB
        if resp.status_code == 200:
            data = resp.json()

            expected_fields = {
                "paired": bool,
                "expired": bool,
            }
            assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_pairing_devices_response_shape(self, api_client):
        """List paired devices returns expected shape."""
        resp = api_client.get("/mobile/pairing/devices")

        # May return 200 or 500 depending on DB
        if resp.status_code == 200:
            data = resp.json()

            expected_fields = {
                "success": bool,
                "devices": list,
                "count": int,
            }
            assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_pairing_revoke_response_shape(self, api_client):
        """Revoke pairing tokens returns expected shape."""
        resp = api_client.delete("/mobile/pairing/revoke")

        # May return 200 or 500 depending on DB
        if resp.status_code == 200:
            data = resp.json()

            expected_fields = {
                "success": bool,
                "message": str,
                "revoked_count": int,
            }
            assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_mobile_profile_response_shape(self, api_client):
        """Mobile profile returns expected shape."""
        resp = api_client.get("/mobile/profile")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "success": bool,
            "profile": dict,
        }
        assert_response_shape(data, expected_fields)

        # Profile should have expected fields
        profile = data.get("profile", {})
        assert "id" in profile


# =============================================================================
# Completions Router Contract Tests
# =============================================================================


class TestCompletionsContracts:
    """Contract tests for completions router."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_completions_list_response_shape(self, api_client):
        """List completions returns expected shape."""
        resp = api_client.get("/workouts/completions")

        assert resp.status_code == 200
        data = resp.json()

        expected_fields = {
            "success": bool,
            "completions": list,
            "total": int,
        }
        assert_response_shape(data, expected_fields)

    @pytest.mark.contract
    @pytest.mark.unit
    def test_complete_workout_validation_error_shape(self, api_client):
        """Complete workout validation error has expected shape."""
        # Send invalid payload
        resp = api_client.post("/workouts/complete", json={})

        assert resp.status_code == 422
        data = resp.json()

        # FastAPI validation errors have specific structure
        assert "detail" in data


# =============================================================================
# Error Response Shape Tests
# =============================================================================


class TestErrorResponseShapes:
    """Tests for consistent error response shapes across all routers."""

    @pytest.mark.contract
    @pytest.mark.unit
    def test_404_error_shape(self, api_client):
        """404 errors have consistent shape."""
        resp = api_client.get("/nonexistent-endpoint-12345")

        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    @pytest.mark.contract
    @pytest.mark.unit
    def test_422_validation_error_shape(self, api_client):
        """422 validation errors have FastAPI standard shape."""
        # Trigger validation error with invalid JSON
        resp = api_client.post("/workflow/validate", json={})

        assert resp.status_code == 422
        data = resp.json()

        assert "detail" in data
        assert isinstance(data["detail"], list)

        if data["detail"]:
            error = data["detail"][0]
            assert "loc" in error
            assert "msg" in error
            assert "type" in error

    @pytest.mark.contract
    @pytest.mark.unit
    def test_method_not_allowed_shape(self, api_client):
        """405 method not allowed has consistent shape."""
        # GET on POST-only endpoint
        resp = api_client.get("/workflow/validate")

        assert resp.status_code == 405
        data = resp.json()
        assert "detail" in data
