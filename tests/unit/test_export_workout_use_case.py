"""
Unit tests for ExportWorkoutUseCase.

Part of AMA-392: Create ExportWorkout use case
Phase 3 - Canonical Model + Use Cases

Tests for:
- ExportWorkoutUseCase with mocked dependencies
- Each export format path (yaml, hiit, zwo, workoutkit, fit_metadata)
- Error handling (workout not found, invalid format)
"""

import pytest

from application.use_cases import ExportFormat, ExportWorkoutResult, ExportWorkoutUseCase
from domain.models import Block, BlockType, Exercise, Workout, WorkoutMetadata, WorkoutSource
from tests.fakes.workout_repository import FakeWorkoutRepository


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def workout_repo() -> FakeWorkoutRepository:
    """Create a fresh fake workout repository."""
    return FakeWorkoutRepository()


@pytest.fixture
def use_case(workout_repo: FakeWorkoutRepository) -> ExportWorkoutUseCase:
    """Create ExportWorkoutUseCase with fake dependencies."""
    return ExportWorkoutUseCase(workout_repo=workout_repo)


@pytest.fixture
def sample_workout_data() -> dict:
    """Sample workout data in the format stored in DB."""
    return {
        "title": "Test Workout",
        "blocks": [
            {
                "exercises": [
                    {"name": "Squat", "sets": 3, "reps": 10},
                    {"name": "Bench Press", "sets": 3, "reps": 8},
                ]
            }
        ],
    }


@pytest.fixture
def seeded_workout_repo(
    workout_repo: FakeWorkoutRepository, sample_workout_data: dict
) -> FakeWorkoutRepository:
    """Repository seeded with a test workout."""
    workout_repo.seed(
        [
            {
                "id": "workout-123",
                "profile_id": "user-456",
                "title": "Test Workout",
                "workout_data": sample_workout_data,
                "sources": ["ai"],
                "device": "garmin",
                "is_exported": False,
            }
        ]
    )
    return workout_repo


@pytest.fixture
def use_case_with_data(
    seeded_workout_repo: FakeWorkoutRepository,
) -> ExportWorkoutUseCase:
    """ExportWorkoutUseCase with seeded workout data."""
    return ExportWorkoutUseCase(workout_repo=seeded_workout_repo)


@pytest.fixture
def sample_workout() -> Workout:
    """Sample domain Workout for direct export tests."""
    return Workout(
        id="workout-789",
        title="Domain Workout",
        blocks=[
            Block(
                type=BlockType.STRAIGHT,
                exercises=[
                    Exercise(name="Deadlift", sets=3, reps=5),
                    Exercise(name="Pull-up", sets=3, reps=8),
                ],
            )
        ],
        metadata=WorkoutMetadata(sources=[WorkoutSource.AI]),
    )


# =============================================================================
# Success Path Tests
# =============================================================================


class TestExportWorkoutUseCaseSuccess:
    """Tests for successful ExportWorkoutUseCase execution."""

    @pytest.mark.unit
    def test_export_yaml_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export workout to YAML format succeeds."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="yaml",
        )

        assert result.success is True
        assert result.export_format == "yaml"
        assert result.export_data is not None
        assert isinstance(result.export_data, str)
        assert result.workout_id == "workout-123"
        assert result.workout_title == "Test Workout"

    @pytest.mark.unit
    def test_export_hiit_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export workout to HIIT YAML format succeeds."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="hiit",
        )

        assert result.success is True
        assert result.export_format == "hiit"
        assert result.export_data is not None
        assert isinstance(result.export_data, str)

    @pytest.mark.unit
    def test_export_zwo_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export workout to ZWO XML format succeeds."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="zwo",
        )

        assert result.success is True
        assert result.export_format == "zwo"
        assert result.export_data is not None
        assert isinstance(result.export_data, str)
        # Should be XML
        assert "<?xml" in result.export_data or "<workout_file" in result.export_data

    @pytest.mark.unit
    def test_export_zwo_with_sport_option(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export to ZWO respects sport option."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="zwo",
            sport="run",
        )

        assert result.success is True
        assert result.export_format == "zwo"

    @pytest.mark.unit
    def test_export_workoutkit_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export workout to WorkoutKit DTO format succeeds."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="workoutkit",
        )

        assert result.success is True
        assert result.export_format == "workoutkit"
        assert result.export_data is not None
        assert isinstance(result.export_data, dict)

    @pytest.mark.unit
    def test_export_fit_metadata_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export workout FIT metadata succeeds."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="fit_metadata",
        )

        assert result.success is True
        assert result.export_format == "fit_metadata"
        assert result.export_data is not None
        assert isinstance(result.export_data, dict)

    @pytest.mark.unit
    def test_export_format_case_insensitive(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Export format is case insensitive."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="YAML",
        )

        assert result.success is True
        assert result.export_format == "yaml"


# =============================================================================
# Direct Workout Export Tests
# =============================================================================


class TestExportFromWorkout:
    """Tests for exporting directly from domain Workout model."""

    @pytest.mark.unit
    def test_export_from_workout_yaml(
        self,
        use_case: ExportWorkoutUseCase,
        sample_workout: Workout,
    ):
        """Export domain Workout directly to YAML."""
        result = use_case.execute_from_workout(
            workout=sample_workout,
            export_format="yaml",
        )

        assert result.success is True
        assert result.export_format == "yaml"
        assert result.workout_id == "workout-789"
        assert result.workout_title == "Domain Workout"

    @pytest.mark.unit
    def test_export_from_workout_workoutkit(
        self,
        use_case: ExportWorkoutUseCase,
        sample_workout: Workout,
    ):
        """Export domain Workout directly to WorkoutKit."""
        result = use_case.execute_from_workout(
            workout=sample_workout,
            export_format="workoutkit",
        )

        assert result.success is True
        assert result.export_format == "workoutkit"
        assert isinstance(result.export_data, dict)


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestExportWorkoutUseCaseErrors:
    """Tests for error handling in ExportWorkoutUseCase."""

    @pytest.mark.unit
    def test_workout_not_found(
        self,
        use_case: ExportWorkoutUseCase,
    ):
        """Returns error when workout not found."""
        result = use_case.execute(
            workout_id="nonexistent",
            profile_id="user-456",
            export_format="yaml",
        )

        assert result.success is False
        assert result.error == "Workout not found"
        assert result.workout_id == "nonexistent"

    @pytest.mark.unit
    def test_invalid_format(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Returns error for invalid export format."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="invalid_format",
        )

        assert result.success is False
        assert "Unknown export format" in result.error
        assert "valid formats" in result.error.lower()

    @pytest.mark.unit
    def test_wrong_user_cannot_export(
        self,
        use_case_with_data: ExportWorkoutUseCase,
    ):
        """Cannot export workout belonging to different user."""
        result = use_case_with_data.execute(
            workout_id="workout-123",
            profile_id="different-user",  # Not the owner
            export_format="yaml",
        )

        assert result.success is False
        assert result.error == "Workout not found"


# =============================================================================
# Export Status Update Tests
# =============================================================================


class TestExportStatusUpdate:
    """Tests for export status tracking."""

    @pytest.mark.unit
    def test_updates_export_status_when_requested(
        self,
        seeded_workout_repo: FakeWorkoutRepository,
    ):
        """Export status is updated when requested."""
        use_case = ExportWorkoutUseCase(workout_repo=seeded_workout_repo)

        result = use_case.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="yaml",
            update_export_status=True,
        )

        assert result.success is True

        # Check workout was marked as exported
        workout = seeded_workout_repo.get("workout-123", "user-456")
        assert workout["is_exported"] is True

    @pytest.mark.unit
    def test_does_not_update_export_status_by_default(
        self,
        seeded_workout_repo: FakeWorkoutRepository,
    ):
        """Export status is NOT updated by default."""
        use_case = ExportWorkoutUseCase(workout_repo=seeded_workout_repo)

        result = use_case.execute(
            workout_id="workout-123",
            profile_id="user-456",
            export_format="yaml",
        )

        assert result.success is True

        # Check workout was NOT marked as exported
        workout = seeded_workout_repo.get("workout-123", "user-456")
        assert workout["is_exported"] is False


# =============================================================================
# Result Object Tests
# =============================================================================


class TestExportWorkoutResult:
    """Tests for ExportWorkoutResult dataclass."""

    @pytest.mark.unit
    def test_success_result(self):
        """Success result has expected fields."""
        result = ExportWorkoutResult(
            success=True,
            export_format="yaml",
            export_data="yaml: content",
            workout_id="w-123",
            workout_title="Test",
        )

        assert result.success is True
        assert result.export_format == "yaml"
        assert result.export_data == "yaml: content"
        assert result.error is None
        assert result.warnings == []

    @pytest.mark.unit
    def test_failure_result(self):
        """Failure result has error field."""
        result = ExportWorkoutResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.export_data is None

    @pytest.mark.unit
    def test_result_with_warnings(self):
        """Result can include warnings."""
        result = ExportWorkoutResult(
            success=True,
            export_format="yaml",
            export_data="content",
            warnings=["Warning 1", "Warning 2"],
        )

        assert result.success is True
        assert len(result.warnings) == 2


# =============================================================================
# ExportFormat Enum Tests
# =============================================================================


class TestExportFormat:
    """Tests for ExportFormat enum."""

    @pytest.mark.unit
    def test_all_formats(self):
        """All expected formats are defined."""
        assert ExportFormat.YAML.value == "yaml"
        assert ExportFormat.HIIT.value == "hiit"
        assert ExportFormat.ZWO.value == "zwo"
        assert ExportFormat.WORKOUTKIT.value == "workoutkit"
        assert ExportFormat.FIT_METADATA.value == "fit_metadata"

    @pytest.mark.unit
    def test_format_from_string(self):
        """Can create format from string."""
        fmt = ExportFormat("yaml")
        assert fmt == ExportFormat.YAML

    @pytest.mark.unit
    def test_invalid_format_raises(self):
        """Invalid format string raises ValueError."""
        with pytest.raises(ValueError):
            ExportFormat("invalid")
