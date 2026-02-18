"""
Unit tests for ExportService.

Part of AMA-601: Write unit tests for ExportService

Tests for:
- is_hiit_workout method
- to_workoutkit returns dict
- get_fit_metadata returns dict
"""

import pytest
from backend.services.export_service import ExportService
from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def export_service() -> ExportService:
    """Create ExportService instance."""
    return ExportService()


@pytest.fixture
def sample_blocks_json() -> dict:
    """Sample blocks JSON for testing."""
    return {
        "title": "Test Workout",
        "blocks": [
            {
                "structure": "3 sets",
                "exercises": [
                    {"name": "Squat", "sets": 3, "reps": 10},
                    {"name": "Bench Press", "sets": 3, "reps": 8},
                ],
            }
        ],
    }


@pytest.fixture
def hiit_blocks_json() -> dict:
    """Sample HIIT blocks JSON for testing."""
    return {
        "title": "HIIT Workout",
        "blocks": [
            {
                "structure": "5 rounds for time",
                "exercises": [
                    {"name": "Burpees", "type": "HIIT"},
                    {"name": "Mountain Climbers", "type": "HIIT"},
                ],
            }
        ],
    }


@pytest.fixture
def amrap_blocks_json() -> dict:
    """Sample AMRAP blocks JSON for testing."""
    return {
        "title": "AMRAP Workout",
        "blocks": [
            {
                "structure": "AMRAP 20 min",
                "exercises": [
                    {"name": "Pull-ups", "sets": 3, "reps": 10},
                ],
            }
        ],
    }


@pytest.fixture
def emom_blocks_json() -> dict:
    """Sample EMOM blocks JSON for testing."""
    return {
        "title": "EMOM Workout",
        "blocks": [
            {
                "structure": "EMOM 10 min",
                "exercises": [
                    {"name": "Deadlift", "sets": 5, "reps": 5},
                ],
            }
        ],
    }


@pytest.fixture
def superset_hiit_blocks_json() -> dict:
    """Sample blocks JSON with HIIT superset."""
    return {
        "title": "Superset HIIT",
        "blocks": [
            {
                "structure": "3 sets",
                "supersets": [
                    {
                        "exercises": [
                            {"name": "Push-ups", "type": "HIIT"},
                            {"name": "Squats", "type": "HIIT"},
                        ]
                    }
                ],
            }
        ],
    }


# =============================================================================
# is_hiit_workout Tests
# =============================================================================


class TestIsHiitWorkout:
    """Tests for is_hiit_workout method."""

    @pytest.mark.unit
    def test_regular_workout_is_not_hiit(
        self,
        sample_blocks_json: dict,
    ):
        """Regular workout with 3-set structure returns False."""
        result = is_hiit_workout(sample_blocks_json)
        assert result is False

    @pytest.mark.unit
    def test_hiit_workout_with_for_time(
        self,
        hiit_blocks_json: dict,
    ):
        """HIIT workout with 'for time' structure returns True."""
        result = is_hiit_workout(hiit_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_amrap_workout_is_hiit(
        self,
        amrap_blocks_json: dict,
    ):
        """AMRAP workout returns True."""
        result = is_hiit_workout(amrap_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_emom_workout_is_hiit(
        self,
        emom_blocks_json: dict,
    ):
        """EMOM workout returns True."""
        result = is_hiit_workout(emom_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_exercise_type_hiit(
        self,
    ):
        """Exercise with type=HIIT returns True."""
        blocks = {
            "title": "Type HIIT",
            "blocks": [
                {
                    "structure": "3 sets",
                    "exercises": [
                        {"name": "Squat", "sets": 3, "reps": 10, "type": "HIIT"},
                    ],
                }
            ],
        }
        result = is_hiit_workout(blocks)
        assert result is True

    @pytest.mark.unit
    def test_superset_with_hiit_exercise(
        self,
        superset_hiit_blocks_json: dict,
    ):
        """Superset with HIIT type exercise returns True."""
        result = is_hiit_workout(superset_hiit_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_empty_blocks_returns_false(
        self,
    ):
        """Empty blocks returns False."""
        result = is_hiit_workout({})
        assert result is False

    @pytest.mark.unit
    def test_none_input_returns_false(
        self,
    ):
        """None input returns False."""
        result = is_hiit_workout(None)
        assert result is False

    @pytest.mark.unit
    def test_missing_blocks_key_returns_false(
        self):
        """Missing 'blocks' key returns False."""
        result = is_hiit_workout({"title": "No blocks"})
        assert result is False

    @pytest.mark.unit
    def test_malformed_json_returns_false(
        self):
        """Malformed input (non-dict) returns False."""
        result = is_hiit_workout("not a dict")
        assert result is False


# =============================================================================
# to_workoutkit Tests
# =============================================================================


class TestMapToWorkoutkit:
    """Tests for map_to_workoutkit method."""

    @pytest.mark.unit
    def test_to_workoutkit_returns_dict(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """map_to_workoutkit returns a dictionary."""
        result = export_service.map_to_workoutkit(sample_blocks_json)
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_to_workoutkit_returns_valid_dict(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """map_to_workoutkit returns a valid dictionary with expected keys."""
        result = export_service.map_to_workoutkit(sample_blocks_json)
        # WorkoutKit DTO should have specific structure
        assert isinstance(result, dict)
        # Validate required keys for WorkoutKit DTO
        assert "title" in result or "name" in result, "Result should have title or name key"
        assert "intervals" in result or "exercises" in result or "workout" in result, \
            "Result should have intervals, exercises, or workout key"

    @pytest.mark.unit
    def test_to_workoutkit_with_hiit_workout(
        self,
        export_service: ExportService,
        hiit_blocks_json: dict,
    ):
        """map_to_workoutkit handles HIIT workout."""
        result = export_service.map_to_workoutkit(hiit_blocks_json)
        assert isinstance(result, dict)


# =============================================================================
# get_fit_metadata Tests
# =============================================================================


class TestGetFitMetadata:
    """Tests for get_fit_metadata method."""

    @pytest.mark.unit
    def test_get_fit_metadata_returns_dict(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """get_fit_metadata returns a dictionary."""
        result = export_service.get_fit_metadata(sample_blocks_json)
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_get_fit_metadata_returns_valid_metadata(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """get_fit_metadata returns metadata with expected keys and valid values."""
        result = export_service.get_fit_metadata(sample_blocks_json)
        assert isinstance(result, dict)
        # FIT metadata should include these keys
        assert "detected_sport" in result
        assert "exercise_count" in result
        # Validate reasonable values
        assert result["exercise_count"] is None or isinstance(result["exercise_count"], int), \
            "exercise_count should be an integer or None"
        # detected_sport should be a valid sport string or None
        if result.get("detected_sport") is not None:
            assert isinstance(result["detected_sport"], str), "detected_sport should be a string"

    @pytest.mark.unit
    def test_get_fit_metadata_with_lap_button(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """get_fit_metadata respects use_lap_button parameter and affects output."""
        result_with_lap = export_service.get_fit_metadata(sample_blocks_json, use_lap_button=True)
        result_without_lap = export_service.get_fit_metadata(sample_blocks_json, use_lap_button=False)

        assert isinstance(result_with_lap, dict)
        assert result_with_lap.get("use_lap_button") is True
        assert isinstance(result_without_lap, dict)
        assert result_without_lap.get("use_lap_button") is False

        # Verify actual behavior change
        assert result_with_lap.get("use_lap_button") != result_without_lap.get("use_lap_button"), \
            "use_lap_button parameter should cause measurable behavior change"

    @pytest.mark.unit
    def test_get_fit_metadata_hiit_workout(
        self,
        export_service: ExportService,
        hiit_blocks_json: dict,
    ):
        """get_fit_metadata handles HIIT workout."""
        result = export_service.get_fit_metadata(hiit_blocks_json)
        assert isinstance(result, dict)
        assert "detected_sport" in result

    @pytest.mark.unit
    def test_get_fit_metadata_empty_blocks(
        self,
        export_service: ExportService,
    ):
        """get_fit_metadata handles empty blocks - returns dict with default/empty values."""
        result = export_service.get_fit_metadata({})
        assert isinstance(result, dict)
        # Empty blocks should result in zero exercise count or defaults
        assert "exercise_count" in result
        assert result["exercise_count"] == 0 or result["exercise_count"] is None
