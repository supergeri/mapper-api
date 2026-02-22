"""
Tests for the detection endpoint.

Part of AMA-688: Auto-detection endpoint for matching detected exercises
against user's scheduled AmakaFlow workouts.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from backend.schemas.detection import DetectionRequest, DetectionMatch
from application.use_cases.match_workout import MatchWorkoutUseCase


# Shared fixtures
@pytest.fixture
def mock_workout_repo():
    """Create a mock workout repository."""
    return MagicMock()


@pytest.fixture
def use_case(mock_workout_repo):
    """Create a MatchWorkoutUseCase with mock repo."""
    return MatchWorkoutUseCase(workout_repository=mock_workout_repo)


class TestMatchWorkoutUseCase:
    """Test cases for MatchWorkoutUseCase."""

    @pytest.mark.asyncio
    async def test_matched_workout_within_1h_sport_matches_exercise_overlap(
        self, use_case, mock_workout_repo
    ):
        """Test matched: workout within 1h, sport matches, exercise overlap → matched: true, confidence > 0.85"""
        # Setup
        now = datetime.now()
        user_id = "user-123"

        # Workout with perfect exercise overlap (same exercises)
        workout = {
            "id": "workout-1",
            "title": "Full Body Strength",
            "created_at": now - timedelta(minutes=30),
            "workout_data": {
                "type": "strength",
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Squat"},
                            {"name": "Deadlift"},
                        ]
                    }
                ]
            },
        }

        mock_workout_repo.get_list.return_value = [workout]

        request = DetectionRequest(
            user_id=user_id,
            device="apple_watch",
            timestamp=now,
            sport="strength",
            detected_exercises=["squat", "deadlift"],
        )

        # Execute
        result = await use_case.execute(request)

        # Assert
        assert result.matched is True
        assert result.workout_id == "workout-1"
        assert result.workout_name == "Full Body Strength"
        assert result.confidence is not None
        assert result.confidence > 0.85

    @pytest.mark.asyncio
    async def test_no_match_no_workouts_in_window(
        self, use_case, mock_workout_repo
    ):
        """Test no match: no workouts in window → reason: 'no_scheduled_workout'"""
        # Setup
        now = datetime.now()
        user_id = "user-123"

        # No workouts
        mock_workout_repo.get_list.return_value = []

        request = DetectionRequest(
            user_id=user_id,
            device="apple_watch",
            timestamp=now,
            sport="strength",
            detected_exercises=["squat", "deadlift"],
        )

        # Execute
        result = await use_case.execute(request)

        # Assert
        assert result.matched is False
        assert result.reason == "no_scheduled_workout"

    @pytest.mark.asyncio
    async def test_no_match_sport_mismatch(
        self, use_case, mock_workout_repo
    ):
        """Test no match: sport mismatch → reason: 'sport_mismatch'"""
        # Setup
        now = datetime.now()
        user_id = "user-123"

        # Workout with different sport
        workout = {
            "id": "workout-1",
            "title": "Morning Run",
            "created_at": now - timedelta(minutes=30),
            "workout_data": {
                "type": "running",
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Running"},
                        ]
                    }
                ]
            },
        }

        mock_workout_repo.get_list.return_value = [workout]

        request = DetectionRequest(
            user_id=user_id,
            device="apple_watch",
            timestamp=now,
            sport="strength",
            detected_exercises=["squat", "deadlift"],
        )

        # Execute
        result = await use_case.execute(request)

        # Assert
        assert result.matched is False
        assert result.reason == "sport_mismatch"

    @pytest.mark.asyncio
    async def test_no_match_low_confidence(
        self, use_case, mock_workout_repo
    ):
        """Test no match: workouts found but low overlap → reason: 'low_confidence'"""
        # Setup
        now = datetime.now()
        user_id = "user-123"

        # Workout with some overlap but not enough for 0.85 threshold
        workout = {
            "id": "workout-1",
            "title": "Full Body Strength",
            "created_at": now - timedelta(hours=2.5),  # Outside 1h window, closer to 3h
            "workout_data": {
                "type": "strength",
                "blocks": [
                    {
                        "exercises": [
                            {"name": "Squat"},
                            {"name": "Push-up"},
                        ]
                    }
                ]
            },
        }

        mock_workout_repo.get_list.return_value = [workout]

        request = DetectionRequest(
            user_id=user_id,
            device="apple_watch",
            timestamp=now,
            sport="strength",
            detected_exercises=["squat", "deadlift"],  # Only 1 match out of 2
        )

        # Execute
        result = await use_case.execute(request)

        # Assert
        assert result.matched is False
        assert result.reason == "low_confidence"


class TestDetectionSchemas:
    """Test cases for detection schemas."""

    def test_detection_request_valid(self):
        """Test DetectionRequest schema validation."""
        request = DetectionRequest(
            user_id="user-123",
            device="apple_watch",
            timestamp=datetime.now(),
            sport="strength",
            detected_exercises=["squat", "deadlift"],
        )
        assert request.user_id == "user-123"
        assert request.device == "apple_watch"
        assert request.sport == "strength"
        assert request.detected_exercises == ["squat", "deadlift"]

    def test_detection_request_optional_fields(self):
        """Test DetectionRequest with optional fields."""
        request = DetectionRequest(
            user_id="user-123",
            device="garmin",
            timestamp=datetime.now(),
            sport="running",
            detected_exercises=["run"],
            hr_bpm=150.5,
            motion_variance=0.8,
            classifier_confidence=0.9,
        )
        assert request.hr_bpm == 150.5
        assert request.motion_variance == 0.8
        assert request.classifier_confidence == 0.9

    def test_detection_match_matched(self):
        """Test DetectionMatch for matched workout."""
        match = DetectionMatch(
            matched=True,
            workout_id="workout-123",
            workout_name="Full Body",
            confidence=0.92,
            match_reason="Matched 3 exercises with 0.92 confidence",
        )
        assert match.matched is True
        assert match.workout_id == "workout-123"
        assert match.confidence == 0.92

    def test_detection_match_no_match(self):
        """Test DetectionMatch for no match."""
        match = DetectionMatch(
            matched=False,
            reason="no_scheduled_workout",
        )
        assert match.matched is False
        assert match.reason == "no_scheduled_workout"


class TestScheduleProximity:
    """Test schedule proximity calculation."""

    def test_within_1_hour_returns_1(self, use_case):
        """Test that within 1 hour returns 1.0."""
        detection_time = datetime(2024, 1, 1, 10, 0, 0)
        workout_time = datetime(2024, 1, 1, 9, 30, 0)  # 30 min difference

        result = use_case._calculate_schedule_proximity(detection_time, workout_time)
        assert result == 1.0

    def test_at_3_hours_returns_0(self, use_case):
        """Test that at 3 hours returns 0.0."""
        detection_time = datetime(2024, 1, 1, 10, 0, 0)
        workout_time = datetime(2024, 1, 1, 7, 0, 0)  # 3 hours difference

        result = use_case._calculate_schedule_proximity(detection_time, workout_time)
        assert result == 0.0

    def test_linear_decay_at_2_hours(self, use_case):
        """Test linear decay at 2 hours."""
        detection_time = datetime(2024, 1, 1, 10, 0, 0)
        workout_time = datetime(2024, 1, 1, 8, 0, 0)  # 2 hours difference

        result = use_case._calculate_schedule_proximity(detection_time, workout_time)
        # At 2 hours: 1.0 - (2-1)/2 = 1.0 - 0.5 = 0.5
        assert result == 0.5


class TestExerciseOverlap:
    """Test exercise overlap calculation (Jaccard similarity)."""

    def test_perfect_overlap(self, use_case):
        """Test perfect overlap returns 1.0."""
        detected = ["squat", "deadlift"]
        workout = ["squat", "deadlift"]

        result = use_case._calculate_exercise_overlap(detected, workout)
        assert result == 1.0

    def test_partial_overlap(self, use_case):
        """Test partial overlap returns correct Jaccard."""
        detected = ["squat", "deadlift", "bench"]
        workout = ["squat", "deadlift", "pullup"]

        # Intersection: {squat, deadlift} = 2
        # Union: {squat, deadlift, bench, pullup} = 4
        # Jaccard: 2/4 = 0.5

        result = use_case._calculate_exercise_overlap(detected, workout)
        assert result == 0.5

    def test_no_overlap(self, use_case):
        """Test no overlap returns 0.0."""
        detected = ["squat"]
        workout = ["bench"]

        result = use_case._calculate_exercise_overlap(detected, workout)
        assert result == 0.0

    def test_empty_lists(self, use_case):
        """Test empty lists return 0.0."""
        result = use_case._calculate_exercise_overlap([], [])
        assert result == 0.0


class TestScoreFormula:
    """Test the weighted score formula."""

    def test_score_formula(self, use_case):
        """Test score formula: schedule_proximity * 0.35 + exercise_overlap * 0.45 + sport_match * 0.20"""
        workout = {
            "id": "workout-1",
            "created_at": datetime.now() - timedelta(minutes=30),
            "workout_data": {
                "type": "strength",
                "blocks": [
                    {"exercises": [{"name": "squat"}, {"name": "deadlift"}]}
                ]
            },
        }

        # Perfect match: schedule=1.0, exercise=1.0, sport=1.0
        score = use_case._score_workout(
            workout=workout,
            detected_exercises=["squat", "deadlift"],
            sport="strength",
            timestamp=datetime.now()
        )

        # Expected: 1.0*0.35 + 1.0*0.45 + 1.0*0.20 = 1.0
        assert score == 1.0
