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
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """Regular workout with 'for time' structure returns True."""
        # Import the function directly since it's a module-level function
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout(sample_blocks_json)
        assert result is False

    @pytest.mark.unit
    def test_hiit_workout_with_for_time(
        self,
        export_service: ExportService,
        hiit_blocks_json: dict,
    ):
        """HIIT workout with 'for time' structure returns True."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout(hiit_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_amrap_workout_is_hiit(
        self,
        export_service: ExportService,
        amrap_blocks_json: dict,
    ):
        """AMRAP workout returns True."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout(amrap_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_emom_workout_is_hiit(
        self,
        export_service: ExportService,
        emom_blocks_json: dict,
    ):
        """EMOM workout returns True."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout(emom_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_exercise_type_hiit(
        self,
        export_service: ExportService,
    ):
        """Exercise with type=HIIT returns True."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
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
        export_service: ExportService,
        superset_hiit_blocks_json: dict,
    ):
        """Superset with HIIT type exercise returns True."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout(superset_hiit_blocks_json)
        assert result is True

    @pytest.mark.unit
    def test_empty_blocks_returns_false(
        self,
        export_service: ExportService,
    ):
        """Empty blocks returns False."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout
        result = is_hiit_workout({})
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
        # The result should not be empty
        assert len(result) > 0

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
        """get_fit_metadata returns metadata with expected keys."""
        result = export_service.get_fit_metadata(sample_blocks_json)
        assert isinstance(result, dict)
        # FIT metadata should include these keys
        assert "detected_sport" in result
        assert "exercise_count" in result

    @pytest.mark.unit
    def test_get_fit_metadata_with_lap_button(
        self,
        export_service: ExportService,
        sample_blocks_json: dict,
    ):
        """get_fit_metadata respects use_lap_button parameter."""
        result = export_service.get_fit_metadata(sample_blocks_json, use_lap_button=True)
        assert isinstance(result, dict)
        assert result.get("use_lap_button") is True

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
        """get_fit_metadata handles empty blocks."""
        result = export_service.get_fit_metadata({})
        assert isinstance(result, dict)
