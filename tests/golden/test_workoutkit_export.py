"""
Golden tests for WorkoutKit (Apple Watch) export adapter.

Part of AMA-398: Add golden fixtures for WorkoutKit export
Phase 4 - Testing Overhaul

Tests WorkoutKit JSON export output against saved fixtures to detect unintended changes.
Covers:
- Simple strength workouts
- Workouts with sets (RepeatInterval)
- Superset workouts
- Warmup/cooldown blocks
- Interval/timed workouts
"""

import json

import pytest

from tests.golden import assert_golden
from backend.adapters.blocks_to_workoutkit import to_workoutkit


# =============================================================================
# Test Data Factories
# =============================================================================


def create_simple_strength_workout() -> dict:
    """Create a simple strength workout with basic exercises."""
    return {
        "title": "Upper Body Basics",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 300,
                "exercises": [],
                "supersets": [],
            },
            {
                "label": "Main Set",
                "exercises": [
                    {
                        "name": "Push-Ups",
                        "reps": 15,
                    },
                    {
                        "name": "Dumbbell Rows",
                        "reps": 12,
                    },
                    {
                        "name": "Shoulder Press",
                        "reps": 10,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 180,
                "exercises": [],
                "supersets": [],
            },
        ],
    }


def create_strength_with_sets() -> dict:
    """Create a strength workout with multiple sets per exercise."""
    return {
        "title": "Strength Training - Sets",
        "settings": {
            "defaultRestSec": 60,
            "defaultRestType": "timed",
        },
        "blocks": [
            {
                "label": "Main Workout",
                "exercises": [
                    {
                        "name": "Bench Press",
                        "reps": 8,
                        "sets": 4,
                        "rest_sec": 90,
                    },
                    {
                        "name": "Barbell Squats",
                        "reps": 6,
                        "sets": 3,
                        "rest_sec": 120,
                    },
                    {
                        "name": "Deadlift",
                        "reps": 5,
                        "sets": 3,
                        "rest_sec": 120,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_superset_workout() -> dict:
    """Create a workout with supersets (single round to avoid nested RepeatInterval)."""
    return {
        "title": "Superset Circuit",
        "blocks": [
            {
                "label": "Circuit A",
                "exercises": [],
                "supersets": [
                    {
                        "exercises": [
                            {
                                "name": "Pull-Ups",
                                "reps": 10,
                            },
                            {
                                "name": "Dips",
                                "reps": 12,
                            },
                        ],
                        "rest_between_sec": 30,
                        "sets": 3,
                    },
                ],
            },
        ],
    }


def create_interval_workout() -> dict:
    """Create a timed interval workout (HIIT style)."""
    return {
        "title": "HIIT Intervals",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "Light Jog",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Main",
                "structure": "6 rounds",
                "time_work_sec": 30,
                "rest_between_sec": 30,
                "exercises": [
                    {
                        "name": "Burpees",
                        "duration_sec": 30,
                        "rest_sec": 30,
                        "sets": 6,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 180,
                "exercises": [
                    {
                        "name": "Walking",
                        "duration_sec": 180,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_workout_with_warmup_setting() -> dict:
    """Create a workout with warmup enabled in settings."""
    return {
        "title": "Workout with Settings Warmup",
        "settings": {
            "workoutWarmup": {
                "enabled": True,
                "durationSec": 600,
            },
        },
        "blocks": [
            {
                "label": "Main Set",
                "exercises": [
                    {
                        "name": "Kettlebell Swings",
                        "reps": 20,
                        "sets": 5,
                        "rest_sec": 45,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_distance_workout() -> dict:
    """Create a workout with distance-based exercises."""
    return {
        "title": "Distance Training",
        "blocks": [
            {
                "label": "Main",
                "exercises": [
                    {
                        "name": "Farmer Walk",
                        "distance_m": 50,
                    },
                    {
                        "name": "Sled Push",
                        "distance_m": 30,
                    },
                    {
                        "name": "Lunges",
                        "distance_range": "20-30m",
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_mixed_workout() -> dict:
    """Create a workout mixing reps, time, and distance exercises."""
    return {
        "title": "Mixed Modality",
        "blocks": [
            {
                "label": "Primer",
                "exercises": [
                    {
                        "name": "Jump Rope",
                        "duration_sec": 120,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Strength",
                "exercises": [
                    {
                        "name": "Goblet Squats",
                        "reps": 15,
                        "sets": 3,
                        "rest_sec": 60,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Conditioning",
                "exercises": [
                    {
                        "name": "Row Machine",
                        "distance_m": 500,
                    },
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_workoutkit_json(wk_dto) -> str:
    """
    Normalize WorkoutKit DTO for stable golden comparisons.

    Converts the Pydantic model to a formatted JSON string.
    """
    return json.dumps(wk_dto.model_dump(exclude_none=True), indent=2, sort_keys=True)


# =============================================================================
# Simple Workout Tests
# =============================================================================


class TestSimpleWorkoutKitExport:
    """Golden tests for simple WorkoutKit exports."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_simple_strength_workout(self):
        """Simple strength workout with warmup/cooldown exports correctly."""
        blocks = create_simple_strength_workout()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/simple_strength.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_distance_workout(self):
        """Distance-based workout exports correctly."""
        blocks = create_distance_workout()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/distance_workout.json")


# =============================================================================
# Strength with Sets Tests
# =============================================================================


class TestStrengthSetsWorkoutKitExport:
    """Golden tests for strength workouts with multiple sets."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_strength_with_sets(self):
        """Strength workout with sets creates RepeatIntervals."""
        blocks = create_strength_with_sets()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/strength_sets.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_superset_workout(self):
        """Superset workout exports correctly."""
        blocks = create_superset_workout()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/superset.json")


# =============================================================================
# Interval/HIIT Tests
# =============================================================================


class TestIntervalWorkoutKitExport:
    """Golden tests for interval-style workouts."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_interval_workout(self):
        """HIIT interval workout exports correctly."""
        blocks = create_interval_workout()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/interval_hiit.json")


# =============================================================================
# Settings-Based Tests
# =============================================================================


class TestSettingsWorkoutKitExport:
    """Golden tests for workouts with settings configuration."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_workout_with_warmup_setting(self):
        """Workout with warmup enabled in settings."""
        blocks = create_workout_with_warmup_setting()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/settings_warmup.json")


# =============================================================================
# Mixed Modality Tests
# =============================================================================


class TestMixedWorkoutKitExport:
    """Golden tests for mixed modality workouts."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_mixed_workout(self):
        """Mixed modality workout (reps, time, distance) exports correctly."""
        blocks = create_mixed_workout()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/mixed_modality.json")


# =============================================================================
# Integration Tests
# =============================================================================


class TestWorkoutKitExportIntegration:
    """Integration tests for WorkoutKit export."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_workoutkit_returns_pydantic_model(self):
        """to_workoutkit returns a WKPlanDTO Pydantic model."""
        from backend.adapters.workoutkit_schemas import WKPlanDTO

        blocks = create_simple_strength_workout()
        output = to_workoutkit(blocks)

        assert isinstance(output, WKPlanDTO)
        assert output.title == "Upper Body Basics"
        assert output.sportType == "strengthTraining"
        assert len(output.intervals) > 0

    @pytest.mark.golden
    @pytest.mark.unit
    def test_sets_create_repeat_intervals(self):
        """Exercises with sets > 1 are wrapped in RepeatInterval."""
        from backend.adapters.workoutkit_schemas import RepeatInterval

        blocks = create_strength_with_sets()
        output = to_workoutkit(blocks)

        # Find RepeatIntervals - exercises with sets should create repeats
        repeat_intervals = [i for i in output.intervals if isinstance(i, RepeatInterval)]
        assert len(repeat_intervals) == 3  # Bench Press, Squats, Deadlift

        # Check first repeat has correct structure
        first_repeat = repeat_intervals[0]
        assert first_repeat.reps == 4  # 4 sets of bench press
        assert len(first_repeat.intervals) == 2  # RepsStep + RestStep

    @pytest.mark.golden
    @pytest.mark.unit
    def test_warmup_cooldown_intervals(self):
        """Warmup and cooldown blocks create appropriate intervals."""
        from backend.adapters.workoutkit_schemas import WarmupInterval, CooldownInterval

        blocks = create_simple_strength_workout()
        output = to_workoutkit(blocks)

        # First interval should be warmup
        warmup = output.intervals[0]
        assert isinstance(warmup, WarmupInterval)
        assert warmup.seconds == 300

        # Last interval should be cooldown
        cooldown = output.intervals[-1]
        assert isinstance(cooldown, CooldownInterval)
        assert cooldown.seconds == 180

    @pytest.mark.golden
    @pytest.mark.unit
    def test_json_serialization(self):
        """WorkoutKit DTO can be serialized to JSON."""
        blocks = create_simple_strength_workout()
        output = to_workoutkit(blocks)

        # Should not raise
        json_str = output.model_dump_json()
        assert json_str is not None
        assert "Upper Body Basics" in json_str

        # Should be parseable
        parsed = json.loads(json_str)
        assert parsed["title"] == "Upper Body Basics"
        assert parsed["sportType"] == "strengthTraining"
