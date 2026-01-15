"""
Unit tests for MapWorkoutUseCase.

Part of AMA-391: Create MapWorkout use case
Phase 3 - Canonical Model + Use Cases

Tests for:
- MapWorkoutUseCase with mocked dependencies
- Success path with exercise mapping
- Error handling paths
- User mapping priority over fuzzy matching
"""

import pytest

from application.use_cases import MapWorkoutResult, MapWorkoutUseCase
from backend.parsers.models import ParsedExercise, ParsedWorkout
from domain.models import BlockType, WorkoutSource
from tests.fakes.mapping_repository import (
    FakeExerciseMatchRepository,
    FakeUserMappingRepository,
)
from tests.fakes.workout_repository import FakeWorkoutRepository


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def workout_repo() -> FakeWorkoutRepository:
    """Create a fresh fake workout repository."""
    return FakeWorkoutRepository()


@pytest.fixture
def user_mapping_repo() -> FakeUserMappingRepository:
    """Create a fresh fake user mapping repository."""
    return FakeUserMappingRepository(user_id="test-user-123")


@pytest.fixture
def exercise_match_repo() -> FakeExerciseMatchRepository:
    """Create a fake exercise match repository with common matches."""
    repo = FakeExerciseMatchRepository()
    repo.seed_matches(
        {
            "squat": ("Barbell Back Squat", 0.95),
            "bench press": ("Barbell Bench Press", 0.92),
            "deadlift": ("Barbell Deadlift", 0.98),
            "pull-up": ("Pull Up", 0.90),
            "push-up": ("Push Up", 0.88),
            "plank": ("Plank", 0.95),
            "dumbbell curl": ("Dumbbell Biceps Curl", 0.85),
            "lat pulldown": ("Lat Pull Down", 0.82),
            "shoulder press": ("Overhead Press", 0.75),
        }
    )
    return repo


@pytest.fixture
def use_case(
    workout_repo: FakeWorkoutRepository,
    user_mapping_repo: FakeUserMappingRepository,
    exercise_match_repo: FakeExerciseMatchRepository,
) -> MapWorkoutUseCase:
    """Create MapWorkoutUseCase with fake dependencies."""
    return MapWorkoutUseCase(
        exercise_match_repo=exercise_match_repo,
        user_mapping_repo=user_mapping_repo,
        workout_repo=workout_repo,
    )


@pytest.fixture
def basic_parsed_workout() -> ParsedWorkout:
    """Simple parsed workout for testing."""
    return ParsedWorkout(
        name="Test Workout",
        exercises=[
            ParsedExercise(raw_name="Squat", sets=3, reps="10"),
            ParsedExercise(raw_name="Bench Press", sets=3, reps="8"),
            ParsedExercise(raw_name="Deadlift", sets=3, reps="5"),
        ],
    )


@pytest.fixture
def superset_parsed_workout() -> ParsedWorkout:
    """Parsed workout with supersets for testing."""
    return ParsedWorkout(
        name="Superset Workout",
        exercises=[
            ParsedExercise(raw_name="Squat", sets=4, reps="8"),
            ParsedExercise(
                raw_name="Bench Press",
                sets=3,
                reps="10",
                superset_group="A",
            ),
            ParsedExercise(
                raw_name="Pull-up",
                sets=3,
                reps="8",
                superset_group="A",
            ),
        ],
    )


# =============================================================================
# Success Path Tests
# =============================================================================


class TestMapWorkoutUseCaseSuccess:
    """Tests for successful MapWorkoutUseCase execution."""

    @pytest.mark.unit
    def test_execute_basic_workout(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Execute with basic workout creates domain model and saves."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        assert result.success is True
        assert result.workout is not None
        assert result.workout.title == "Test Workout"
        assert result.workout.total_exercises == 3
        assert result.workout_id is not None
        assert result.exercises_mapped == 3
        assert result.exercises_unmapped == 0

    @pytest.mark.unit
    def test_execute_maps_exercise_names(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
    ):
        """Exercises are mapped to canonical names."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        workout = result.workout
        exercise_names = []
        canonical_names = []

        for block in workout.blocks:
            for ex in block.exercises:
                exercise_names.append(ex.name)
                canonical_names.append(ex.canonical_name)

        # Original names preserved
        assert "Squat" in exercise_names
        assert "Bench Press" in exercise_names
        assert "Deadlift" in exercise_names

        # Canonical names set
        assert "Barbell Back Squat" in canonical_names
        assert "Barbell Bench Press" in canonical_names
        assert "Barbell Deadlift" in canonical_names

    @pytest.mark.unit
    def test_execute_preserves_sets_and_reps(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
    ):
        """Sets and reps are preserved in domain model."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        workout = result.workout
        exercises = workout.blocks[0].exercises

        assert exercises[0].sets == 3
        assert exercises[0].reps == 10
        assert exercises[1].sets == 3
        assert exercises[1].reps == 8

    @pytest.mark.unit
    def test_execute_with_supersets(
        self,
        use_case: MapWorkoutUseCase,
        superset_parsed_workout: ParsedWorkout,
    ):
        """Superset structure is preserved."""
        result = use_case.execute(
            parsed_workout=superset_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        workout = result.workout
        assert len(workout.blocks) == 2  # One straight, one superset

        # First block is straight (single exercise)
        assert workout.blocks[0].type == BlockType.STRAIGHT
        assert len(workout.blocks[0].exercises) == 1

        # Second block is superset
        assert workout.blocks[1].type == BlockType.SUPERSET
        assert len(workout.blocks[1].exercises) == 2

    @pytest.mark.unit
    def test_execute_saves_to_repository(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Workout is saved to repository with correct data."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        # Verify saved in repository
        saved_workouts = workout_repo.get_all()
        assert len(saved_workouts) == 1

        saved = saved_workouts[0]
        assert saved["profile_id"] == "test-user-123"
        assert saved["device"] == "garmin"
        assert saved["title"] == "Test Workout"
        assert WorkoutSource.AI.value in saved["sources"]

    @pytest.mark.unit
    def test_execute_without_save(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Can execute without saving to repository."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        assert result.success is True
        assert result.workout is not None
        assert result.workout_id is None  # Not saved

        # Repository should be empty
        assert len(workout_repo.get_all()) == 0

    @pytest.mark.unit
    def test_execute_returns_workout_id(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
        workout_repo: FakeWorkoutRepository,
    ):
        """Returns the ID of the saved workout."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device="garmin",
        )

        assert result.workout_id is not None

        # Can retrieve by ID
        saved = workout_repo.get(result.workout_id, "test-user-123")
        assert saved is not None
        assert saved["id"] == result.workout_id


# =============================================================================
# User Mapping Priority Tests
# =============================================================================


class TestUserMappingPriority:
    """Tests for user mapping priority over fuzzy matching."""

    @pytest.mark.unit
    def test_user_mapping_takes_priority(
        self,
        use_case: MapWorkoutUseCase,
        user_mapping_repo: FakeUserMappingRepository,
    ):
        """User-defined mappings override fuzzy matching."""
        # Set up user mapping that overrides the fuzzy match
        user_mapping_repo.add("squat", "Goblet Squat")

        parsed = ParsedWorkout(
            name="Custom Mapping Test",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10"),
            ],
        )

        result = use_case.execute(
            parsed_workout=parsed,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        # Should use user mapping, not fuzzy match
        exercise = result.workout.blocks[0].exercises[0]
        assert exercise.canonical_name == "Goblet Squat"

    @pytest.mark.unit
    def test_falls_back_to_fuzzy_match(
        self,
        use_case: MapWorkoutUseCase,
        user_mapping_repo: FakeUserMappingRepository,
    ):
        """Falls back to fuzzy matching when no user mapping exists."""
        # No user mapping for squat
        assert user_mapping_repo.get("squat") is None

        parsed = ParsedWorkout(
            name="Fuzzy Match Test",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10"),
            ],
        )

        result = use_case.execute(
            parsed_workout=parsed,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        # Should use fuzzy match
        exercise = result.workout.blocks[0].exercises[0]
        assert exercise.canonical_name == "Barbell Back Squat"


# =============================================================================
# Unmapped Exercise Tests
# =============================================================================


class TestUnmappedExercises:
    """Tests for handling unmapped exercises."""

    @pytest.mark.unit
    def test_unmapped_exercise_count(
        self,
        use_case: MapWorkoutUseCase,
    ):
        """Tracks count of unmapped exercises."""
        parsed = ParsedWorkout(
            name="Unknown Exercises",
            exercises=[
                ParsedExercise(raw_name="Squat", sets=3, reps="10"),  # Known
                ParsedExercise(raw_name="Zorpflinger Press", sets=3, reps="8"),  # Unknown
            ],
        )

        result = use_case.execute(
            parsed_workout=parsed,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        assert result.exercises_mapped == 1
        assert result.exercises_unmapped == 1

    @pytest.mark.unit
    def test_unmapped_exercise_preserves_name(
        self,
        use_case: MapWorkoutUseCase,
    ):
        """Unmapped exercises preserve original name."""
        parsed = ParsedWorkout(
            name="Unknown Exercise",
            exercises=[
                ParsedExercise(raw_name="Zorpflinger Press", sets=3, reps="8"),
            ],
        )

        result = use_case.execute(
            parsed_workout=parsed,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        exercise = result.workout.blocks[0].exercises[0]
        assert exercise.name == "Zorpflinger Press"
        assert exercise.canonical_name is None


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestMapWorkoutUseCaseErrors:
    """Tests for error handling in MapWorkoutUseCase."""

    @pytest.mark.unit
    def test_empty_workout_still_succeeds(
        self,
        use_case: MapWorkoutUseCase,
    ):
        """Empty workout (no exercises) still processes without error."""
        parsed = ParsedWorkout(
            name="Empty Workout",
            exercises=[],
        )

        # This should raise an error from ingest_to_workout due to min 1 block
        result = use_case.execute(
            parsed_workout=parsed,
            user_id="test-user-123",
            device="garmin",
            save=False,
        )

        # Should fail gracefully
        assert result.success is False
        assert result.error is not None


# =============================================================================
# Result Object Tests
# =============================================================================


class TestMapWorkoutResult:
    """Tests for MapWorkoutResult dataclass."""

    @pytest.mark.unit
    def test_success_result(self):
        """Success result has expected fields."""
        result = MapWorkoutResult(
            success=True,
            workout_id="w-123",
            exercises_mapped=5,
            exercises_unmapped=1,
        )

        assert result.success is True
        assert result.workout_id == "w-123"
        assert result.exercises_mapped == 5
        assert result.exercises_unmapped == 1
        assert result.error is None

    @pytest.mark.unit
    def test_failure_result(self):
        """Failure result has error field."""
        result = MapWorkoutResult(
            success=False,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.workout is None
        assert result.workout_id is None


# =============================================================================
# Device Type Tests
# =============================================================================


class TestDeviceTypes:
    """Tests for different device types."""

    @pytest.mark.unit
    @pytest.mark.parametrize("device", ["garmin", "apple", "ios_companion"])
    def test_saves_with_device_type(
        self,
        use_case: MapWorkoutUseCase,
        basic_parsed_workout: ParsedWorkout,
        workout_repo: FakeWorkoutRepository,
        device: str,
    ):
        """Workout is saved with correct device type."""
        result = use_case.execute(
            parsed_workout=basic_parsed_workout,
            user_id="test-user-123",
            device=device,
        )

        saved = workout_repo.get_all()[0]
        assert saved["device"] == device
