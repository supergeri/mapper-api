"""
Unit tests for SaveWorkoutUseCase.

Part of AMA-393: Create SaveWorkout use case
Phase 3 - Canonical Model + Use Cases

Tests for:
- SaveWorkoutUseCase with mocked dependencies
- Create (new workout) and update (existing workout) paths
- Validation error cases
"""

from unittest.mock import PropertyMock, patch

import pytest

from application.use_cases import (
    SaveWorkoutResult,
    SaveWorkoutUseCase,
    WorkoutValidationError,
)
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
def use_case(workout_repo: FakeWorkoutRepository) -> SaveWorkoutUseCase:
    """Create SaveWorkoutUseCase with fake dependencies."""
    return SaveWorkoutUseCase(workout_repo=workout_repo)


@pytest.fixture
def valid_workout() -> Workout:
    """Sample valid workout for testing."""
    return Workout(
        title="Test Workout",
        blocks=[
            Block(
                type=BlockType.STRAIGHT,
                exercises=[
                    Exercise(name="Squat", sets=3, reps=10),
                    Exercise(name="Bench Press", sets=3, reps=8),
                ],
            )
        ],
        metadata=WorkoutMetadata(sources=[WorkoutSource.AI]),
    )


@pytest.fixture
def existing_workout() -> Workout:
    """Sample workout with existing ID for update testing."""
    return Workout(
        id="existing-workout-123",
        title="Existing Workout",
        blocks=[
            Block(
                type=BlockType.STRAIGHT,
                exercises=[
                    Exercise(name="Deadlift", sets=3, reps=5),
                ],
            )
        ],
        metadata=WorkoutMetadata(sources=[WorkoutSource.MANUAL]),
    )


# =============================================================================
# Create Path Tests
# =============================================================================


class TestSaveWorkoutCreate:
    """Tests for creating new workouts."""

    @pytest.mark.unit
    def test_create_new_workout(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Creating a new workout succeeds and assigns ID."""
        result = use_case.execute(
            workout=valid_workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.success is True
        assert result.is_update is False
        assert result.workout_id is not None
        assert result.workout is not None
        assert result.workout.id == result.workout_id

    @pytest.mark.unit
    def test_create_saves_to_repository(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Created workout is saved to repository."""
        result = use_case.execute(
            workout=valid_workout,
            user_id="user-123",
            device="garmin",
        )

        # Verify workout in repository
        saved_workouts = workout_repo.get_all()
        assert len(saved_workouts) == 1
        assert saved_workouts[0]["title"] == "Test Workout"
        assert saved_workouts[0]["profile_id"] == "user-123"

    @pytest.mark.unit
    def test_create_preserves_workout_data(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Created workout preserves all original data."""
        result = use_case.execute(
            workout=valid_workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.workout.title == valid_workout.title
        assert len(result.workout.blocks) == len(valid_workout.blocks)
        assert result.workout.total_exercises == valid_workout.total_exercises

    @pytest.mark.unit
    def test_execute_create_forces_new(
        self,
        use_case: SaveWorkoutUseCase,
        existing_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """execute_create() ignores existing ID and creates new."""
        result = use_case.execute_create(
            workout=existing_workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.success is True
        assert result.is_update is False
        # Should have a new ID, not the existing one
        assert result.workout_id != "existing-workout-123"


# =============================================================================
# Update Path Tests
# =============================================================================


class TestSaveWorkoutUpdate:
    """Tests for updating existing workouts."""

    @pytest.mark.unit
    def test_update_existing_workout(
        self,
        use_case: SaveWorkoutUseCase,
        existing_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Updating an existing workout succeeds."""
        # First seed the repo with existing workout
        workout_repo.seed(
            [
                {
                    "id": "existing-workout-123",
                    "profile_id": "user-123",
                    "title": "Old Title",
                    "workout_data": {},
                    "sources": ["manual"],
                    "device": "garmin",
                }
            ]
        )

        result = use_case.execute(
            workout=existing_workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.success is True
        assert result.is_update is True
        assert result.workout_id == "existing-workout-123"

    @pytest.mark.unit
    def test_execute_update_requires_id(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
    ):
        """execute_update() fails if workout has no ID."""
        result = use_case.execute_update(
            workout=valid_workout,  # Has no ID
            user_id="user-123",
            device="garmin",
        )

        assert result.success is False
        assert "Cannot update workout without ID" in result.error

    @pytest.mark.unit
    def test_execute_update_succeeds_with_id(
        self,
        use_case: SaveWorkoutUseCase,
        existing_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """execute_update() succeeds with workout ID."""
        result = use_case.execute_update(
            workout=existing_workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.success is True
        assert result.is_update is True


# =============================================================================
# Validation Tests
# =============================================================================


class TestSaveWorkoutValidation:
    """Tests for workout validation."""

    @pytest.mark.unit
    def test_validates_empty_title(
        self,
        use_case: SaveWorkoutUseCase,
    ):
        """Validation fails for empty title."""
        workout = Workout(
            title="   ",  # Whitespace only
            blocks=[
                Block(
                    exercises=[Exercise(name="Squat", sets=3, reps=10)],
                )
            ],
        )

        result = use_case.execute(
            workout=workout,
            user_id="user-123",
            device="garmin",
        )

        assert result.success is False
        assert "title" in str(result.validation_errors).lower()

    @pytest.mark.unit
    def test_validates_empty_exercises(
        self,
        use_case: SaveWorkoutUseCase,
    ):
        """Validation fails for blocks with no exercises."""
        # This should fail at Pydantic level due to min_length=1 on exercises
        # But we test through the use case validation
        with pytest.raises(Exception):
            # Pydantic will reject this
            Workout(
                title="Test",
                blocks=[
                    Block(exercises=[]),  # Empty exercises
                ],
            )

    @pytest.mark.unit
    def test_validates_exercise_names(
        self,
        use_case: SaveWorkoutUseCase,
    ):
        """Pydantic validates exercise names cannot be empty."""
        # Pydantic enforces min_length=1 on exercise name
        with pytest.raises(Exception):
            Workout(
                title="Test",
                blocks=[
                    Block(
                        exercises=[Exercise(name="", sets=3, reps=10)],
                    )
                ],
            )

    @pytest.mark.unit
    def test_skip_validation_option(
        self,
        use_case: SaveWorkoutUseCase,
        workout_repo: FakeWorkoutRepository,
    ):
        """Can skip validation with validate=False."""
        workout = Workout(
            title="   ",  # Would fail validation
            blocks=[
                Block(
                    exercises=[Exercise(name="Squat", sets=3, reps=10)],
                )
            ],
        )

        result = use_case.execute(
            workout=workout,
            user_id="user-123",
            device="garmin",
            validate=False,
        )

        # Should succeed because validation was skipped
        assert result.success is True

    @pytest.mark.unit
    def test_rejects_zero_exercises_even_without_validation(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Defense-in-depth: 0 exercises rejected even with validate=False (AMA-561)."""
        with patch.object(
            type(valid_workout), "total_exercises", new_callable=PropertyMock, return_value=0
        ):
            result = use_case.execute(
                workout=valid_workout,
                user_id="user-123",
                device="garmin",
                validate=False,
            )

        assert result.success is False
        assert "at least one exercise" in result.error
        assert "0 exercises" in result.validation_errors[0]
        # Must not have saved anything
        assert len(workout_repo.get_all()) == 0

    @pytest.mark.unit
    def test_rejects_zero_exercises_with_validation(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Defense-in-depth guard fires before regular validation (AMA-561)."""
        with patch.object(
            type(valid_workout), "total_exercises", new_callable=PropertyMock, return_value=0
        ):
            result = use_case.execute(
                workout=valid_workout,
                user_id="user-123",
                device="garmin",
                validate=True,
            )

        assert result.success is False
        assert "at least one exercise" in result.error
        assert len(workout_repo.get_all()) == 0


# =============================================================================
# Device Type Tests
# =============================================================================


class TestDeviceTypes:
    """Tests for different device types."""

    @pytest.mark.unit
    @pytest.mark.parametrize("device", ["garmin", "apple", "ios_companion"])
    def test_saves_with_device_type(
        self,
        use_case: SaveWorkoutUseCase,
        valid_workout: Workout,
        workout_repo: FakeWorkoutRepository,
        device: str,
    ):
        """Workout is saved with correct device type."""
        result = use_case.execute(
            workout=valid_workout,
            user_id="user-123",
            device=device,
        )

        assert result.success is True
        saved = workout_repo.get_all()[0]
        assert saved["device"] == device


# =============================================================================
# Result Object Tests
# =============================================================================


class TestSaveWorkoutResult:
    """Tests for SaveWorkoutResult dataclass."""

    @pytest.mark.unit
    def test_success_result(self):
        """Success result has expected fields."""
        result = SaveWorkoutResult(
            success=True,
            workout_id="w-123",
            is_update=False,
        )

        assert result.success is True
        assert result.workout_id == "w-123"
        assert result.is_update is False
        assert result.error is None
        assert result.validation_errors == []

    @pytest.mark.unit
    def test_failure_result(self):
        """Failure result has error field."""
        result = SaveWorkoutResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.workout is None

    @pytest.mark.unit
    def test_validation_failure_result(self):
        """Validation failure includes error list."""
        result = SaveWorkoutResult(
            success=False,
            error="Validation failed",
            validation_errors=["Title required", "Exercises required"],
        )

        assert result.success is False
        assert len(result.validation_errors) == 2


# =============================================================================
# Exception Tests
# =============================================================================


class TestWorkoutValidationError:
    """Tests for WorkoutValidationError exception."""

    @pytest.mark.unit
    def test_exception_message(self):
        """Exception has message and errors."""
        error = WorkoutValidationError(
            "Validation failed",
            errors=["Error 1", "Error 2"],
        )

        assert str(error) == "Validation failed"
        assert error.message == "Validation failed"
        assert len(error.errors) == 2

    @pytest.mark.unit
    def test_exception_without_errors(self):
        """Exception works without explicit errors list."""
        error = WorkoutValidationError("Simple error")

        assert error.message == "Simple error"
        assert error.errors == []
