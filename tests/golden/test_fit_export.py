"""
Golden tests for FIT (Garmin) metadata export adapter.

Part of AMA-399: Add golden fixtures for FIT metadata export
Phase 4 - Testing Overhaul

Tests FIT metadata and step generation against saved fixtures to detect unintended changes.
Covers:
- Sport type auto-detection (strength, cardio, running)
- Exercise step generation with categories
- Rest step handling (timed vs button)
- Repeat/set structure
- Warmup step generation
"""

import json

import pytest

from tests.golden import assert_golden
from backend.adapters.blocks_to_fit import (
    get_fit_metadata,
    blocks_to_steps,
)


# =============================================================================
# Test Data Factories
# =============================================================================


def create_strength_workout() -> dict:
    """Create a basic strength workout (no cardio)."""
    return {
        "title": "Upper Body Strength",
        "blocks": [
            {
                "structure": "3 rounds",
                "rest_between_sec": 60,
                "exercises": [
                    {
                        "name": "Bench Press",
                        "reps": 8,
                        "sets": 3,
                        "rest_sec": 90,
                    },
                    {
                        "name": "Barbell Row",
                        "reps": 10,
                        "sets": 3,
                        "rest_sec": 60,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_cardio_workout() -> dict:
    """Create a workout with cardio exercises."""
    return {
        "title": "Cardio Conditioning",
        "blocks": [
            {
                "exercises": [
                    {
                        "name": "Ski Erg",
                        "distance_m": 500,
                    },
                    {
                        "name": "Assault Bike",
                        "duration_sec": 60,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_running_workout() -> dict:
    """Create a running-only workout."""
    return {
        "title": "Track Intervals",
        "blocks": [
            {
                "structure": "4 rounds",
                "exercises": [
                    {
                        "name": "400m Run",
                        "distance_m": 400,
                        "rest_sec": 90,
                        "sets": 4,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_mixed_hyrox_workout() -> dict:
    """Create a HYROX-style mixed workout (strength + cardio)."""
    return {
        "title": "HYROX Training",
        "blocks": [
            {
                "structure": "1 round",
                "exercises": [
                    {
                        "name": "Ski Erg",
                        "distance_m": 1000,
                    },
                ],
                "supersets": [],
            },
            {
                "structure": "1 round",
                "exercises": [
                    {
                        "name": "Wall Ball",
                        "reps": 75,
                    },
                ],
                "supersets": [],
            },
            {
                "structure": "1 round",
                "exercises": [
                    {
                        "name": "Indoor Row",
                        "distance_m": 1000,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_superset_workout() -> dict:
    """Create a workout with supersets."""
    return {
        "title": "Push Pull Supersets",
        "blocks": [
            {
                "structure": "3 rounds",
                "rest_between_sec": 90,
                "exercises": [],
                "supersets": [
                    {
                        "exercises": [
                            {
                                "name": "Push Up",
                                "reps": 12,
                            },
                            {
                                "name": "Pull Up",
                                "reps": 8,
                            },
                        ],
                        "rest_between_sec": 30,
                    },
                ],
            },
        ],
    }


def create_timed_workout() -> dict:
    """Create a workout with time-based exercises."""
    return {
        "title": "Timed Holds",
        "blocks": [
            {
                "exercises": [
                    {
                        "name": "Plank",
                        "duration_sec": 60,
                    },
                    {
                        "name": "Wall Sit",
                        "duration_sec": 45,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_button_rest_workout() -> dict:
    """Create a workout with button-press rest (lap button)."""
    return {
        "title": "Button Rest Workout",
        "blocks": [
            {
                "rest_type": "button",
                "exercises": [
                    {
                        "name": "Goblet Squat",
                        "reps": 10,
                        "sets": 3,
                        "rest_type": "button",
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_warmup_exercise_workout() -> dict:
    """Create a workout with warmup sets on exercises."""
    return {
        "title": "Warmup Sets Workout",
        "blocks": [
            {
                "exercises": [
                    {
                        "name": "Back Squat",
                        "reps": 5,
                        "sets": 3,
                        "warmup_sets": 2,
                        "warmup_reps": 8,
                        "rest_sec": 120,
                    },
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_fit_metadata(metadata: dict) -> str:
    """
    Normalize FIT metadata for stable golden comparisons.

    - Sorts category_ids for deterministic output
    """
    # Sort category_ids list for consistent ordering
    if "category_ids" in metadata:
        metadata["category_ids"] = sorted(metadata["category_ids"])
    return json.dumps(metadata, indent=2, sort_keys=True)


def normalize_fit_steps(steps: list) -> str:
    """
    Normalize FIT steps list for stable golden comparisons.

    Removes internal markers that vary per run.
    """
    # Create clean copies without internal markers
    clean_steps = []
    for step in steps:
        clean_step = {k: v for k, v in step.items() if not k.startswith('_')}
        clean_steps.append(clean_step)
    return json.dumps(clean_steps, indent=2, sort_keys=True)


# =============================================================================
# Metadata Golden Tests
# =============================================================================


class TestFitMetadataExport:
    """Golden tests for FIT metadata generation."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_strength_workout_metadata(self):
        """Strength workout metadata detects strength sport type."""
        blocks = create_strength_workout()
        metadata = get_fit_metadata(blocks)
        normalized = normalize_fit_metadata(metadata)
        assert_golden(normalized, "fit/strength_metadata.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_cardio_workout_metadata(self):
        """Cardio workout metadata detects cardio sport type."""
        blocks = create_cardio_workout()
        metadata = get_fit_metadata(blocks)
        normalized = normalize_fit_metadata(metadata)
        assert_golden(normalized, "fit/cardio_metadata.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_running_workout_metadata(self):
        """Running workout metadata detects running sport type."""
        blocks = create_running_workout()
        metadata = get_fit_metadata(blocks)
        normalized = normalize_fit_metadata(metadata)
        assert_golden(normalized, "fit/running_metadata.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_mixed_hyrox_metadata(self):
        """HYROX-style mixed workout detects cardio sport type."""
        blocks = create_mixed_hyrox_workout()
        metadata = get_fit_metadata(blocks)
        normalized = normalize_fit_metadata(metadata)
        assert_golden(normalized, "fit/hyrox_metadata.json")


# =============================================================================
# Step Generation Golden Tests
# =============================================================================


class TestFitStepGeneration:
    """Golden tests for FIT workout step generation."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_strength_workout_steps(self):
        """Strength workout generates correct step structure."""
        blocks = create_strength_workout()
        steps, _ = blocks_to_steps(blocks)
        normalized = normalize_fit_steps(steps)
        assert_golden(normalized, "fit/strength_steps.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_superset_workout_steps(self):
        """Superset workout generates correct step structure."""
        blocks = create_superset_workout()
        steps, _ = blocks_to_steps(blocks)
        normalized = normalize_fit_steps(steps)
        assert_golden(normalized, "fit/superset_steps.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_timed_workout_steps(self):
        """Time-based workout generates correct step structure."""
        blocks = create_timed_workout()
        steps, _ = blocks_to_steps(blocks)
        normalized = normalize_fit_steps(steps)
        assert_golden(normalized, "fit/timed_steps.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_button_rest_steps(self):
        """Button-press rest generates OPEN duration type."""
        blocks = create_button_rest_workout()
        steps, _ = blocks_to_steps(blocks)
        normalized = normalize_fit_steps(steps)
        assert_golden(normalized, "fit/button_rest_steps.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_warmup_sets_steps(self):
        """Warmup sets generate additional warmup steps."""
        blocks = create_warmup_exercise_workout()
        steps, _ = blocks_to_steps(blocks)
        normalized = normalize_fit_steps(steps)
        assert_golden(normalized, "fit/warmup_sets_steps.json")


# =============================================================================
# Integration Tests
# =============================================================================


class TestFitExportIntegration:
    """Integration tests for FIT export."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_sport_type_detection_strength(self):
        """Pure strength workout detects as strength."""
        blocks = create_strength_workout()
        metadata = get_fit_metadata(blocks)

        assert metadata["detected_sport"] == "strength"
        assert metadata["detected_sport_id"] == 10  # training
        assert metadata["detected_sub_sport_id"] == 20  # strength_training
        assert metadata["has_strength"] is True
        assert metadata["has_cardio"] is False
        assert metadata["has_running"] is False

    @pytest.mark.golden
    @pytest.mark.unit
    def test_sport_type_detection_cardio(self):
        """Cardio workout detects as cardio."""
        blocks = create_cardio_workout()
        metadata = get_fit_metadata(blocks)

        assert metadata["detected_sport"] == "cardio"
        assert metadata["detected_sport_id"] == 10  # training
        assert metadata["detected_sub_sport_id"] == 26  # cardio_training
        assert metadata["has_cardio"] is True

    @pytest.mark.golden
    @pytest.mark.unit
    def test_sport_type_detection_running(self):
        """Running-style workout detects category correctly."""
        blocks = create_running_workout()
        metadata = get_fit_metadata(blocks)

        # "400m Run" maps to Cardio category (2), not Run (32)
        # This is because it's distance-based and maps via builtin keywords
        assert metadata["has_cardio"] is True
        assert metadata["has_strength"] is False

    @pytest.mark.golden
    @pytest.mark.unit
    def test_mixed_workout_prefers_cardio(self):
        """Mixed workout with cardio prefers cardio sport type."""
        blocks = create_mixed_hyrox_workout()
        metadata = get_fit_metadata(blocks)

        # HYROX has both strength and cardio - should prefer cardio
        assert metadata["detected_sport"] == "cardio"
        assert metadata["has_cardio"] is True

    @pytest.mark.golden
    @pytest.mark.unit
    def test_steps_include_warmup(self):
        """All workouts start with a warmup step."""
        blocks = create_strength_workout()
        steps, _ = blocks_to_steps(blocks)

        # First step should be warmup
        assert steps[0]["type"] == "warmup"
        assert steps[0]["display_name"] == "Warm-Up"

    @pytest.mark.golden
    @pytest.mark.unit
    def test_repeat_structure_for_sets(self):
        """Exercises with sets > 1 generate repeat steps."""
        blocks = create_strength_workout()
        steps, _ = blocks_to_steps(blocks)

        # Find repeat steps
        repeat_steps = [s for s in steps if s["type"] == "repeat"]
        assert len(repeat_steps) > 0

        # Check repeat structure
        first_repeat = repeat_steps[0]
        assert "repeat_count" in first_repeat
        assert "duration_step" in first_repeat

    @pytest.mark.golden
    @pytest.mark.unit
    def test_rest_steps_timed_vs_button(self):
        """Rest steps have correct duration type for timed vs button."""
        # Timed rest workout
        timed_blocks = create_strength_workout()
        timed_steps, _ = blocks_to_steps(timed_blocks)
        timed_rest = [s for s in timed_steps if s["type"] == "rest"]
        assert any(s["duration_type"] == 0 for s in timed_rest)  # TIME type

        # Button rest workout
        button_blocks = create_button_rest_workout()
        button_steps, _ = blocks_to_steps(button_blocks)
        button_rest = [s for s in button_steps if s["type"] == "rest"]
        assert any(s["duration_type"] == 5 for s in button_rest)  # OPEN type

    @pytest.mark.golden
    @pytest.mark.unit
    def test_lap_button_mode(self):
        """Lap button mode creates OPEN duration type for exercises."""
        blocks = create_strength_workout()
        steps, _ = blocks_to_steps(blocks, use_lap_button=True)

        # Find exercise steps
        exercise_steps = [s for s in steps if s["type"] == "exercise"]
        # All exercises should have OPEN duration type
        assert all(s["duration_type"] == 5 for s in exercise_steps)
