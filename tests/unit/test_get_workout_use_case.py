"""
Tests for GetWorkoutUseCase.

Part of AMA-370: Refactor routers to call use-cases
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from application.use_cases.get_workout import (
    GetWorkoutUseCase,
    GetWorkoutResult,
    ListWorkoutsResult,
    GetIncomingWorkoutsResult,
)


class TestGetWorkoutUseCase:
    """Tests for GetWorkoutUseCase."""

    @pytest.fixture
    def mock_workout_repo(self):
        """Create a mock workout repository."""
        return MagicMock()

    @pytest.fixture
    def use_case(self, mock_workout_repo):
        """Create use case with mock dependencies."""
        return GetWorkoutUseCase(workout_repo=mock_workout_repo)

    def test_get_workout_success(self, use_case, mock_workout_repo):
        """Test getting a workout successfully."""
        mock_workout_repo.get.return_value = {
            "id": "workout-123",
            "title": "Test Workout",
            "workout_data": {}
        }
        mock_workout_repo.get_sync_status.return_value = {"ios": True, "android": False, "garmin": None}

        result = use_case.get_workout("workout-123", "user-123")

        assert result.success is True
        assert result.workout is not None
        assert result.workout["id"] == "workout-123"
        assert "sync_status" in result.workout
        mock_workout_repo.get.assert_called_once_with("workout-123", "user-123")

    def test_get_workout_not_found(self, use_case, mock_workout_repo):
        """Test getting a non-existent workout."""
        mock_workout_repo.get.return_value = None

        result = use_case.get_workout("nonexistent", "user-123")

        assert result.success is False
        assert result.error == "Workout not found or not owned by user"
        assert result.workout is None

    def test_list_workouts(self, use_case, mock_workout_repo):
        """Test listing workouts."""
        mock_workout_repo.get_list.return_value = [
            {"id": "w1", "title": "Workout 1"},
            {"id": "w2", "title": "Workout 2"},
        ]
        mock_workout_repo.batch_get_sync_status.return_value = {
            "w1": {"ios": True, "android": False, "garmin": None},
            "w2": {"ios": False, "android": True, "garmin": None},
        }

        result = use_case.list_workouts("user-123", limit=10)

        assert result.success is True
        assert result.count == 2
        assert len(result.workouts) == 2
        mock_workout_repo.get_list.assert_called_once()

    def test_get_incoming_workouts(self, use_case, mock_workout_repo):
        """Test getting incoming workouts."""
        mock_workout_repo.get_incoming.return_value = [
            {"id": "w1", "title": "Incoming 1"},
        ]

        result = use_case.get_incoming_workouts("user-123", limit=5)

        assert result.success is True
        assert result.count == 1
        assert len(result.workouts) == 1
        mock_workout_repo.get_incoming.assert_called_once_with("user-123", limit=5)

    def test_delete_workout(self, use_case, mock_workout_repo):
        """Test deleting a workout."""
        mock_workout_repo.delete.return_value = True

        result = use_case.delete_workout("workout-123", "user-123")

        assert result is True
        mock_workout_repo.delete.assert_called_once_with("workout-123", "user-123")

    def test_update_export_status(self, use_case, mock_workout_repo):
        """Test updating export status."""
        mock_workout_repo.update_export_status.return_value = True

        result = use_case.update_export_status("workout-123", "user-123", True, "garmin")

        assert result is True
        mock_workout_repo.update_export_status.assert_called_once()

    def test_toggle_favorite(self, use_case, mock_workout_repo):
        """Test toggling favorite status."""
        mock_workout_repo.toggle_favorite.return_value = {"id": "w1", "is_favorite": True}

        result = use_case.toggle_favorite("w1", "user-123", True)

        assert result is not None
        assert result["is_favorite"] is True

    def test_track_usage(self, use_case, mock_workout_repo):
        """Test tracking workout usage."""
        mock_workout_repo.track_usage.return_value = {"id": "w1", "times_completed": 1}

        result = use_case.track_usage("w1", "user-123")

        assert result is not None
        mock_workout_repo.track_usage.assert_called_once()

    def test_update_tags(self, use_case, mock_workout_repo):
        """Test updating workout tags."""
        mock_workout_repo.update_tags.return_value = {"id": "w1", "tags": ["tag1", "tag2"]}

        result = use_case.update_tags("w1", "user-123", ["tag1", "tag2"])

        assert result is not None
        mock_workout_repo.update_tags.assert_called_once()
