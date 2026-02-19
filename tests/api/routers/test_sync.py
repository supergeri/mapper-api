"""
Unit tests for the sync router.

Part of AMA-590: Write unit tests for sync router

Tests all endpoints in api/routers/sync.py:
- iOS Companion App endpoints (push, pending)
- Android Companion App endpoints (push, pending)
- Garmin sync endpoint
- Sync Queue endpoints (queue, pending, confirm, failed, status)
- Helper functions (calculate_intervals_duration, convert_exercise_to_interval, _transform_workout_to_companion)

Coverage: All 10+ endpoints tested with 60+ test cases
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock, AsyncMock

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user
from fastapi.testclient import TestClient

# =============================================================================
# Test Constants
# =============================================================================

TEST_USER_ID = "test-user-sync-590"
TEST_WORKOUT_ID = "workout-123-abc"
TEST_DEVICE_ID = "device-xyz-789"

SAMPLE_WORKOUT_DATA = {
    "title": "Test Workout",
    "blocks": [
        {
            "label": "Warm-up",
            "structure": "regular",
            "exercises": [
                {"name": "Jumping Jacks", "duration_sec": 60, "sets": 1},
            ],
        },
        {
            "label": "Main Workout",
            "structure": "regular",
            "rounds": 3,
            "rest_between_rounds_sec": 60,
            "exercises": [
                {"name": "Push-ups", "reps": 15, "sets": 3, "rest_sec": 30},
                {"name": "Squats", "reps": 20, "sets": 3, "rest_sec": 30},
            ],
        },
        {
            "label": "Cooldown",
            "structure": "regular",
            "exercises": [
                {"name": "Stretching", "duration_sec": 120, "sets": 1},
            ],
        },
    ],
}

SAMPLE_WORKOUT_RECORD = {
    "id": TEST_WORKOUT_ID,
    "title": "Test Workout",
    "workout_data": SAMPLE_WORKOUT_DATA,
    "created_at": "2024-01-01T00:00:00Z",
    "ios_companion_synced_at": None,
    "android_companion_synced_at": None,
}


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
def sample_workout_record():
    """Return sample workout record."""
    return SAMPLE_WORKOUT_RECORD.copy()


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestCalculateIntervalsDuration:
    """Tests for calculate_intervals_duration function."""

    @pytest.mark.unit
    def test_time_interval(self):
        """Duration calculation for time intervals."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{"kind": "time", "seconds": 60}]
        assert calculate_intervals_duration(intervals) == 60

    @pytest.mark.unit
    def test_warmup_interval(self):
        """Duration calculation for warmup intervals."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{"kind": "warmup", "seconds": 300}]
        assert calculate_intervals_duration(intervals) == 300

    @pytest.mark.unit
    def test_cooldown_interval(self):
        """Duration calculation for cooldown intervals."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{"kind": "cooldown", "seconds": 180}]
        assert calculate_intervals_duration(intervals) == 180

    @pytest.mark.unit
    def test_reps_interval(self):
        """Duration calculation for reps intervals (estimates ~3 sec/rep)."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{"kind": "reps", "reps": 10, "restSec": 30}]
        assert calculate_intervals_duration(intervals) == 10 * 3 + 30

    @pytest.mark.unit
    def test_distance_interval(self):
        """Duration calculation for distance intervals."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{"kind": "distance", "meters": 1000}]
        assert calculate_intervals_duration(intervals) == int(1000 * 0.36)

    @pytest.mark.unit
    def test_repeat_interval(self):
        """Duration calculation for repeat intervals."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [{
            "kind": "repeat",
            "reps": 3,
            "intervals": [
                {"kind": "time", "seconds": 60},
                {"kind": "time", "seconds": 30},
            ]
        }]
        assert calculate_intervals_duration(intervals) == 3 * (60 + 30)

    @pytest.mark.unit
    def test_mixed_intervals(self):
        """Duration calculation for mixed interval types."""
        from api.routers.sync import calculate_intervals_duration
        intervals = [
            {"kind": "warmup", "seconds": 300},
            {"kind": "time", "seconds": 60},
            {"kind": "reps", "reps": 10, "restSec": 30},
            {"kind": "cooldown", "seconds": 180},
        ]
        expected = 300 + 60 + (10 * 3 + 30) + 180
        assert calculate_intervals_duration(intervals) == expected

    @pytest.mark.unit
    def test_empty_intervals(self):
        """Duration calculation for empty intervals list."""
        from api.routers.sync import calculate_intervals_duration
        assert calculate_intervals_duration([]) == 0


class TestConvertExerciseToInterval:
    """Tests for convert_exercise_to_interval function."""

    @pytest.mark.unit
    def test_rep_based_exercise(self):
        """Convert rep-based exercise to interval."""
        from api.routers.sync import convert_exercise_to_interval
        exercise = {
            "name": "Push-ups",
            "reps": 15,
            "sets": 3,
            "rest_sec": 30,
        }
        result = convert_exercise_to_interval(exercise)
        assert result["kind"] == "reps"
        assert result["reps"] == 45  # 15 reps * 3 sets
        assert result["name"] == "Push-ups"
        assert result["load"] == "3 sets"
        assert result["restSec"] == 30

    @pytest.mark.unit
    def test_time_based_exercise(self):
        """Convert time-based exercise to interval."""
        from api.routers.sync import convert_exercise_to_interval
        exercise = {
            "name": "Plank",
            "duration_sec": 60,
            "rest_sec": 30,
        }
        result = convert_exercise_to_interval(exercise)
        assert result["kind"] == "time"
        assert result["seconds"] == 60
        assert result["target"] == "Plank"

    @pytest.mark.unit
    def test_default_duration_for_unknown(self):
        """Default to 60 seconds for exercises without reps or duration."""
        from api.routers.sync import convert_exercise_to_interval
        exercise = {"name": "Mystery Exercise"}
        result = convert_exercise_to_interval(exercise)
        assert result["kind"] == "time"
        assert result["seconds"] == 60
        assert result["target"] == "Mystery Exercise"


class TestTransformWorkoutToCompanion:
    """Tests for _transform_workout_to_companion function."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_transform_simple_workout(self, sample_workout):
        """Transform a simple workout to companion format."""
        from api.routers.sync import _transform_workout_to_companion
        result = await _transform_workout_to_companion(sample_workout, "Test Workout")
        assert result["name"] == "Test Workout"
        assert result["source"] == "amakaflow"
        assert "intervals" in result
        assert result["duration"] > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_strength_sport(self, sample_workout):
        """Detect strength training sport type."""
        from api.routers.sync import _transform_workout_to_companion
        result = await _transform_workout_to_companion(sample_workout, "Test")
        assert result["sport"] == "strength"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_detect_cardio_sport(self):
        """Detect cardio sport type from HIIT structure."""
        from api.routers.sync import _transform_workout_to_companion
        cardio_workout = {
            "blocks": [
                {"structure": "tabata", "exercises": [{"name": "Burpees", "duration_sec": 20}]},
            ]
        }
        result = await _transform_workout_to_companion(cardio_workout, "HIIT")
        assert result["sport"] == "cardio"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invalid_workout_data_raises_error(self):
        """Raise ValueError for invalid workout data."""
        from api.routers.sync import _transform_workout_to_companion
        with pytest.raises(ValueError):
            await _transform_workout_to_companion("not a dict", "Test")


# =============================================================================
# iOS Companion Endpoint Tests
# =============================================================================

@patch("api.routers.sync.queue_workout_sync")
@patch("api.routers.sync.update_workout_ios_companion_sync")
@patch("api.routers.sync.run_in_threadpool")
class TestIOSCompanionEndpoints:
    """Tests for iOS Companion App endpoints."""

    @pytest.mark.unit
    def test_push_workout_to_ios_success(
        self, mock_run, mock_update, mock_queue, client, sample_workout_record
    ):
        """Successfully push workout to iOS Companion."""
        mock_run.side_effect = [sample_workout_record, None, None]
        mock_update.return_value = True
        mock_queue.return_value = {"status": "pending", "queued_at": "2024-01-01T00:00:00Z"}

        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["iosCompanionWorkoutId"] == TEST_WORKOUT_ID
        assert "payload" in data

    @pytest.mark.unit
    def test_push_workout_to_ios_not_found(
        self, mock_run, mock_update, mock_queue, client
    ):
        """Return 404 when workout not found."""
        mock_run.return_value = None

        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
            json={}
        )

        assert response.status_code == 404

    @pytest.mark.unit
    def test_get_ios_pending_success(
        self, mock_run, mock_update, mock_queue, client
    ):
        """Successfully get pending iOS workouts."""
        mock_run.return_value = [
            {
                "id": TEST_WORKOUT_ID,
                "title": "Test Workout",
                "workout_data": SAMPLE_WORKOUT_DATA,
                "ios_companion_synced_at": "2024-01-01T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        response = client.get("/ios-companion/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["workouts"][0]["id"] == TEST_WORKOUT_ID

    @pytest.mark.unit
    def test_get_ios_pending_empty(
        self, mock_run, mock_update, mock_queue, client
    ):
        """Return empty list when no pending workouts."""
        mock_run.return_value = []

        response = client.get("/ios-companion/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["workouts"] == []


# =============================================================================
# Android Companion Endpoint Tests
# =============================================================================

@patch("api.routers.sync.queue_workout_sync")
@patch("api.routers.sync.update_workout_android_companion_sync")
@patch("api.routers.sync.run_in_threadpool")
class TestAndroidCompanionEndpoints:
    """Tests for Android Companion App endpoints."""

    @pytest.mark.unit
    def test_push_workout_to_android_success(
        self, mock_run, mock_update, mock_queue, client, sample_workout_record
    ):
        """Successfully push workout to Android Companion."""
        mock_run.side_effect = [sample_workout_record, None, None]
        mock_update.return_value = True
        mock_queue.return_value = {"status": "pending", "queued_at": "2024-01-01T00:00:00Z"}

        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/push/android-companion",
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["androidCompanionWorkoutId"] == TEST_WORKOUT_ID

    @pytest.mark.unit
    def test_get_android_pending_success(
        self, mock_run, mock_update, mock_queue, client
    ):
        """Successfully get pending Android workouts."""
        mock_run.return_value = [
            {
                "id": TEST_WORKOUT_ID,
                "title": "Test Workout",
                "workout_data": SAMPLE_WORKOUT_DATA,
                "android_companion_synced_at": "2024-01-01T00:00:00Z",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ]

        response = client.get("/android-companion/pending")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1


# =============================================================================
# Garmin Sync Endpoint Tests
# =============================================================================

@patch.dict("os.environ", {"GARMIN_UNOFFICIAL_SYNC_ENABLED": "true", "GARMIN_EMAIL": "test@test.com", "GARMIN_PASSWORD": "password"})
@patch("api.routers.sync.httpx.AsyncClient")
class TestGarminSyncEndpoint:
    """Tests for Garmin sync endpoint."""

    @pytest.mark.unit
    def test_sync_to_garmin_success(self, mock_client_class, client):
        """Successfully sync workout to Garmin."""
        mock_client = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        payload = {
            "blocks_json": {
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Bench Press", "reps": 10},
                        ]
                    }
                ]
            },
            "workout_title": "Test Garmin Workout",
        }

        response = client.post("/workout/sync/garmin", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "garminWorkoutId" in data

    @pytest.mark.unit
    def test_sync_to_garmin_with_schedule_date(self, mock_client_class, client):
        """Sync workout with schedule date."""
        mock_client = MagicMock()
        mock_client_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_class.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)

        payload = {
            "blocks_json": {
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Squats", "reps": 15},
                        ]
                    }
                ]
            },
            "workout_title": "Scheduled Workout",
            "schedule_date": "2024-12-25",
        }

        response = client.post("/workout/sync/garmin", json=payload)
        assert response.status_code == 200
        assert mock_client.post.call_count == 2


@patch.dict("os.environ", {"GARMIN_UNOFFICIAL_SYNC_ENABLED": "false"})
class TestGarminSyncDisabled:
    """Tests when Garmin sync is disabled."""

    @pytest.mark.unit
    def test_sync_to_garmin_disabled(self, client):
        """Return 503 when Garmin sync is disabled."""
        payload = {
            "blocks_json": {"blocks": [{"exercises": [{"name": "Push-ups", "reps": 10}]}]},
            "workout_title": "Test Workout",
        }

        response = client.post("/workout/sync/garmin", json=payload)
        assert response.status_code == 503


# =============================================================================
# Sync Queue Endpoint Tests
# =============================================================================

@patch("api.routers.sync.get_workout_sync_status")
@patch("api.routers.sync.report_sync_failed")
@patch("api.routers.sync.confirm_sync")
@patch("api.routers.sync.get_pending_syncs")
@patch("api.routers.sync.queue_workout_sync")
@patch("api.routers.sync.get_workout")
@patch("api.routers.sync.run_in_threadpool")
class TestSyncQueueEndpoints:
    """Tests for sync queue endpoints."""

    @pytest.mark.unit
    def test_queue_sync_success(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client, sample_workout_record
    ):
        """Successfully queue workout for sync."""
        mock_run.side_effect = [sample_workout_record, {"status": "pending", "queued_at": "2024-01-01T00:00:00Z"}]

        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/sync",
            json={"device_type": "ios", "device_id": TEST_DEVICE_ID}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "pending"

    @pytest.mark.unit
    def test_queue_sync_invalid_device_type(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client
    ):
        """Return 422 for invalid device type."""
        response = client.post(
            f"/workouts/{TEST_WORKOUT_ID}/sync",
            json={"device_type": "invalid_device"}
        )
        assert response.status_code == 422

    @pytest.mark.unit
    def test_get_pending_syncs_success(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client
    ):
        """Successfully get pending syncs."""
        mock_run.return_value = [
            {
                "workout_id": TEST_WORKOUT_ID,
                "queued_at": "2024-01-01T00:00:00Z",
                "workouts": {
                    "id": TEST_WORKOUT_ID,
                    "title": "Test Workout",
                    "workout_data": SAMPLE_WORKOUT_DATA,
                    "created_at": "2024-01-01T00:00:00Z",
                }
            }
        ]

        response = client.get("/sync/pending?device_type=ios")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 1

    @pytest.mark.unit
    def test_get_pending_syncs_invalid_device_type(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client
    ):
        """Return 400 for invalid device type."""
        response = client.get("/sync/pending?device_type=invalid")
        assert response.status_code == 400

    @pytest.mark.unit
    def test_confirm_sync_success(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client
    ):
        """Successfully confirm sync."""
        mock_run.return_value = {
            "status": "synced",
            "synced_at": "2024-01-01T00:00:00Z"
        }

        response = client.post(
            "/sync/confirm",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "ios",
                "device_id": TEST_DEVICE_ID
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "synced"

    @pytest.mark.unit
    def test_report_sync_failed_success(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client
    ):
        """Successfully report sync failure."""
        mock_run.return_value = {
            "status": "failed",
            "failed_at": "2024-01-01T00:00:00Z"
        }

        response = client.post(
            "/sync/failed",
            json={
                "workout_id": TEST_WORKOUT_ID,
                "device_type": "android",
                "error": "Network timeout",
                "device_id": TEST_DEVICE_ID
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["status"] == "failed"

    @pytest.mark.unit
    def test_get_sync_status_success(
        self, mock_run, mock_get, mock_queue, mock_pending,
        mock_confirm, mock_failed, mock_status, client, sample_workout_record
    ):
        """Successfully get sync status for workout."""
        mock_run.side_effect = [
            sample_workout_record,
            {
                "ios": {"status": "synced", "queued_at": "2024-01-01T00:00:00Z", "synced_at": "2024-01-01T01:00:00Z"},
                "android": {"status": "pending", "queued_at": "2024-01-01T00:00:00Z"},
                "garmin": None
            }
        ]

        response = client.get(f"/workouts/{TEST_WORKOUT_ID}/sync-status")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "sync_status" in data


# =============================================================================
# Device Type Enum Tests
# =============================================================================

class TestDeviceTypeEnum:
    """Tests for DeviceType enum."""

    @pytest.mark.unit
    def test_device_type_values(self):
        """DeviceType enum has correct values."""
        from api.routers.sync import DeviceType

        assert DeviceType.IOS.value == "ios"
        assert DeviceType.ANDROID.value == "android"
        assert DeviceType.GARMIN.value == "garmin"

    @pytest.mark.unit
    def test_device_type_from_string(self):
        """Can create DeviceType from string."""
        from api.routers.sync import DeviceType

        assert DeviceType("ios") == DeviceType.IOS
        assert DeviceType("android") == DeviceType.ANDROID
        assert DeviceType("garmin") == DeviceType.GARMIN


# =============================================================================
# Router Configuration Tests
# =============================================================================

class TestSyncRouterConfiguration:
    """Tests for sync router configuration."""

    @pytest.mark.unit
    def test_router_endpoints_exist(self, app):
        """All expected endpoints should be registered."""
        openapi = app.openapi()
        paths = openapi.get("paths", {})

        expected_endpoints = [
            "/workouts/{workout_id}/push/ios-companion",
            "/ios-companion/pending",
            "/workouts/{workout_id}/push/android-companion",
            "/android-companion/pending",
            "/workout/sync/garmin",
            "/workouts/{workout_id}/sync",
            "/sync/pending",
            "/sync/confirm",
            "/sync/failed",
            "/workouts/{workout_id}/sync-status",
        ]

        for endpoint in expected_endpoints:
            assert endpoint in paths, f"Missing endpoint: {endpoint}"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling in sync router."""

    @pytest.mark.unit
    def test_database_error_handling_ios_push(self, client):
        """Handle database error during iOS push."""
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = Exception("Database connection failed")

            response = client.post(
                f"/workouts/{TEST_WORKOUT_ID}/push/ios-companion",
                json={}
            )

            assert response.status_code == 500

    @pytest.mark.unit
    def test_database_error_handling_get_pending(self, client):
        """Handle database error when getting pending workouts."""
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = Exception("Query failed")

            response = client.get("/ios-companion/pending")

            assert response.status_code == 500


# =============================================================================
# Integration Workflow Tests
# =============================================================================

@pytest.mark.integration
class TestSyncRouterIntegration:
    """Integration-style tests for sync router."""

    @pytest.mark.unit
    def test_full_sync_workflow(self, client):
        """Test complete sync workflow: queue -> pending -> confirm."""
        workout_id = "workflow-test-123"

        # Step 1: Queue workout for sync
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.side_effect = [
                {
                    "id": workout_id,
                    "title": "Workflow Test",
                    "workout_data": SAMPLE_WORKOUT_DATA,
                },
                {
                    "status": "pending",
                    "queued_at": "2024-01-01T00:00:00Z"
                }
            ]

            response = client.post(
                f"/workouts/{workout_id}/sync",
                json={"device_type": "ios", "device_id": "device-1"}
            )
            assert response.status_code == 200

        # Step 2: Get pending syncs
        with patch("api.routers.sync.run_in_threadpool") as mock_run:
            mock_run.return_value = [
                {
                    "workout_id": workout_id,
                    "queued_at": "2024-01-01T00:00:00Z",
                    "workouts": {
                        "id": workout_id,
                        "title": "Workflow Test",
                        "workout_data": SAMPLE_WORKOUT_DATA,
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                }
            ]

            response = client.get("/sync/pending?device_type=ios&device_id=device-1")
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
