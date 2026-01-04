"""Tests for blocks_to_workoutkit converter (AMA-243)."""
import pytest
from backend.adapters.blocks_to_workoutkit import (
    exercise_to_step,
    block_to_intervals,
    to_workoutkit,
    parse_exercise_name,
)


class TestParseExerciseName:
    """Tests for exercise name parsing."""

    def test_removes_prefix(self):
        assert parse_exercise_name("A1: Double Bicep Curl") == "Double Bicep Curl"
        assert parse_exercise_name("B2: Hammer Curl") == "Hammer Curl"

    def test_removes_reps_suffix(self):
        assert parse_exercise_name("Bicep Curl X10") == "Bicep Curl"
        assert parse_exercise_name("Hammer Curl X 5") == "Hammer Curl"

    def test_handles_empty_string(self):
        assert parse_exercise_name("") == ""
        assert parse_exercise_name(None) == ""


class TestExerciseToStepTarget:
    """Tests for exercise name in target field (AMA-243)."""

    def test_time_step_has_exercise_name_in_target(self):
        """TimeStep should include exercise name in target field."""
        exercise = {
            "name": "Double Bicep Curl",
            "duration_sec": 30,
        }
        step = exercise_to_step(exercise)

        assert step.kind == "time"
        assert step.seconds == 30
        assert step.target == "Double Bicep Curl"

    def test_time_step_with_prefixed_name(self):
        """TimeStep should clean prefixed exercise names."""
        exercise = {
            "name": "A1: Wrist X Hammer Curl",
            "duration_sec": 45,
        }
        step = exercise_to_step(exercise)

        assert step.kind == "time"
        assert step.target == "Wrist X Hammer Curl"

    def test_distance_step_has_exercise_name_in_target(self):
        """DistanceStep should include exercise name in target field."""
        exercise = {
            "name": "Sprint",
            "distance_m": 100,
        }
        step = exercise_to_step(exercise)

        assert step.kind == "distance"
        assert step.meters == 100
        assert step.target == "Sprint"

    def test_reps_step_has_name_field(self):
        """RepsStep should have exercise name in name field (not target)."""
        exercise = {
            "name": "Pushups",
            "reps": 10,
        }
        step = exercise_to_step(exercise)

        assert step.kind == "reps"
        assert step.reps == 10
        # RepsStep uses Garmin-mapped name (may differ from original)
        assert step.name is not None
        assert len(step.name) > 0

    def test_fallback_time_step_has_exercise_name(self):
        """Fallback TimeStep should include exercise name."""
        exercise = {
            "name": "Plank Hold",
            # No duration, reps, or distance - will fallback to 60s time
        }
        step = exercise_to_step(exercise)

        assert step.kind == "time"
        assert step.seconds == 60
        assert step.target == "Plank Hold"


class TestBlockToIntervalsTarget:
    """Tests for exercise names in block intervals (AMA-243)."""

    def test_interval_block_preserves_exercise_name(self):
        """Interval blocks should preserve exercise name in work step."""
        block = {
            "time_work_sec": 60,
            "exercises": [
                {"name": "Skier", "duration_sec": 60, "rest_sec": 90}
            ],
        }
        intervals = block_to_intervals(block)

        # Should have work step with exercise name
        assert len(intervals) >= 1
        work_step = intervals[0]
        if hasattr(work_step, 'intervals'):
            # It's a RepeatInterval
            work_step = work_step.intervals[0]

        assert work_step.kind == "time"
        assert work_step.target == "Skier"


class TestToWorkoutkitIntegration:
    """Integration tests for full workout conversion."""

    def test_youtube_workout_preserves_exercise_names(self):
        """YouTube-imported workouts should preserve exercise names (AMA-243)."""
        blocks_json = {
            "title": "10 MINUTE DUMBBELL BICEP WORKOUT",
            "blocks": [
                {
                    "label": "Main",
                    "exercises": [
                        {"name": "Double Bicep Curl", "duration_sec": 30},
                        {"name": "Wrist X Hammer Curl", "duration_sec": 30},
                        {"name": "Bicep Curl Negatives", "duration_sec": 30},
                    ]
                }
            ]
        }

        result = to_workoutkit(blocks_json)

        # Check that intervals have exercise names in target
        assert len(result.intervals) == 3
        assert result.intervals[0].target == "Double Bicep Curl"
        assert result.intervals[1].target == "Wrist X Hammer Curl"
        assert result.intervals[2].target == "Bicep Curl Negatives"
