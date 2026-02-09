"""Tests for blocks_to_workoutkit converter (AMA-243, AMA-260)."""
import pytest
from backend.adapters.blocks_to_workoutkit import (
    exercise_to_step,
    block_to_intervals,
    to_workoutkit,
    parse_exercise_name,
)
from backend.adapters.workoutkit_schemas import RestStep, TimeStep, RepsStep


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
class TestRestStepSerialization:
    """Tests for explicit RestStep kind (AMA-260)."""

    def test_rest_step_has_kind_rest(self):
        """RestStep should serialize with kind='rest'."""
        rest = RestStep(kind="rest", seconds=60)
        data = rest.model_dump()

        assert data["kind"] == "rest"
        assert data["seconds"] == 60

    def test_rest_step_allows_none_seconds(self):
        """RestStep with seconds=None indicates manual rest ('tap when ready')."""
        rest = RestStep(kind="rest", seconds=None)
        data = rest.model_dump()

        assert data["kind"] == "rest"
        assert data["seconds"] is None


@pytest.mark.unit
class TestRestStepInIntervalBlock:
    """Tests for RestStep emission in interval blocks (AMA-260)."""

    def test_interval_block_emits_rest_step(self):
        """Interval blocks should emit RestStep (kind='rest') for rest periods."""
        block = {
            "time_work_sec": 60,
            "exercises": [
                {"name": "Skier", "duration_sec": 60, "rest_sec": 90}
            ],
        }
        intervals = block_to_intervals(block)

        # With 1 round, steps are returned directly (no RepeatInterval wrap)
        assert len(intervals) == 2
        work_step = intervals[0]
        rest_step = intervals[1]

        assert work_step.kind == "time"
        assert rest_step.kind == "rest"
        assert rest_step.seconds == 90

    def test_interval_block_multiple_rounds_emits_rest_step(self):
        """Interval blocks with multiple rounds wrap in RepeatInterval with RestStep."""
        block = {
            "structure": "3 ROUNDS",
            "time_work_sec": 60,
            "exercises": [
                {"name": "Skier", "duration_sec": 60, "rest_sec": 90}
            ],
        }
        intervals = block_to_intervals(block)

        # Should be a single RepeatInterval wrapping work + rest
        assert len(intervals) == 1
        repeat = intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 3

        # Inside should be work + rest
        assert len(repeat.intervals) == 2
        work_step = repeat.intervals[0]
        rest_step = repeat.intervals[1]

        assert work_step.kind == "time"
        assert rest_step.kind == "rest"
        assert rest_step.seconds == 90

    def test_interval_block_without_rest(self):
        """Interval blocks without rest should not emit RestStep."""
        block = {
            "time_work_sec": 60,
            "exercises": [
                {"name": "Plank", "duration_sec": 60}
            ],
        }
        intervals = block_to_intervals(block)

        # Should just be the time step (no repeat since 1 round)
        assert len(intervals) == 1
        assert intervals[0].kind == "time"


@pytest.mark.unit
class TestRestStepInStrengthExercises:
    """Tests for RestStep in strength training exercises (AMA-260)."""

    def test_exercise_with_sets_emits_rest_step(self):
        """Exercises with multiple sets should emit RestStep between sets."""
        block = {
            "exercises": [
                {"name": "Pushups", "reps": 10, "sets": 3, "rest_sec": 60}
            ]
        }
        intervals = block_to_intervals(block)

        # Should be a RepeatInterval wrapping exercise + rest
        assert len(intervals) == 1
        repeat = intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 3

        # Inside: exercise step + rest step
        assert len(repeat.intervals) == 2
        exercise_step = repeat.intervals[0]
        rest_step = repeat.intervals[1]

        assert exercise_step.kind == "reps"
        assert rest_step.kind == "rest"
        assert rest_step.seconds == 60

    def test_exercise_without_sets_no_rest_step(self):
        """Single exercises without sets should not emit separate RestStep."""
        block = {
            "exercises": [
                {"name": "Plank", "duration_sec": 60}
            ]
        }
        intervals = block_to_intervals(block)

        # Should just be the time step
        assert len(intervals) == 1
        assert intervals[0].kind == "time"


@pytest.mark.unit
class TestRestStepInSupersets:
    """Tests for RestStep in superset blocks (AMA-260)."""

    def test_superset_with_rest_between_exercises(self):
        """Supersets should emit RestStep between exercises."""
        block = {
            "supersets": [
                {
                    "exercises": [
                        {"name": "Pushups", "reps": 10},
                        {"name": "Rows", "reps": 10}
                    ],
                    "rest_between_sec": 30
                }
            ]
        }
        intervals = block_to_intervals(block)

        # Should have: pushups, rest, rows (no rest after last)
        assert len(intervals) == 3
        assert intervals[0].kind == "reps"
        assert intervals[1].kind == "rest"
        assert intervals[1].seconds == 30
        assert intervals[2].kind == "reps"

    def test_multiple_supersets_with_rest_between(self):
        """Multiple supersets should emit RestStep between them."""
        block = {
            "rest_between_sec": 90,
            "supersets": [
                {
                    "exercises": [{"name": "Pushups", "reps": 10}]
                },
                {
                    "exercises": [{"name": "Squats", "reps": 10}]
                }
            ]
        }
        intervals = block_to_intervals(block)

        # Should have: pushups, rest, squats (rest between supersets)
        assert len(intervals) == 3
        assert intervals[0].kind == "reps"
        assert intervals[1].kind == "rest"
        assert intervals[1].seconds == 90
        assert intervals[2].kind == "reps"


@pytest.mark.unit
class TestRestStepWithDefaultRest:
    """Tests for RestStep with default rest settings (AMA-260)."""

    def test_default_rest_timed_creates_rest_step(self):
        """Default timed rest should create RestStep in exercises with sets."""
        block = {
            "exercises": [
                {"name": "Curls", "reps": 10, "sets": 3}
            ]
        }
        # Simulate default_rest_sec from settings
        intervals = block_to_intervals(block, default_rest_sec=45)

        assert len(intervals) == 1
        repeat = intervals[0]
        assert repeat.kind == "repeat"

        # Should have rest step using default
        rest_step = repeat.intervals[1]
        assert rest_step.kind == "rest"
        assert rest_step.seconds == 45


@pytest.mark.unit
class TestSupersetStructureAware:
    """Tests for structure-aware superset/circuit handling in block_to_intervals."""

    def test_superset_block_creates_single_repeat_interval(self):
        """Block with structure='superset' groups exercises into one RepeatInterval."""
        block = {
            "structure": "superset",
            "rounds": 4,
            "exercises": [
                {"name": "Pull-ups", "reps": 8},
                {"name": "Z Press", "reps": 8},
            ],
            "rest_between_sec": 60,
        }
        intervals = block_to_intervals(block)

        assert len(intervals) == 1
        repeat = intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 4
        # Should contain both exercises + rest after the pair
        exercise_steps = [s for s in repeat.intervals if s.kind == "reps"]
        rest_steps = [s for s in repeat.intervals if s.kind == "rest"]
        assert len(exercise_steps) == 2
        assert exercise_steps[0].name is not None
        assert exercise_steps[1].name is not None
        assert len(rest_steps) == 1
        assert rest_steps[0].seconds == 60

    def test_superset_rounds_from_block_level(self):
        """RepeatInterval reps come from block-level rounds field."""
        block = {
            "structure": "superset",
            "rounds": 3,
            "exercises": [
                {"name": "A", "reps": 10, "sets": 5},
                {"name": "B", "reps": 10, "sets": 5},
            ],
        }
        intervals = block_to_intervals(block)

        assert len(intervals) == 1
        # Block-level rounds=3 takes priority over exercise sets=5
        assert intervals[0].reps == 3

    def test_superset_rounds_fallback_to_exercise_sets(self):
        """When block has no rounds, fall back to first exercise's sets."""
        block = {
            "structure": "superset",
            "exercises": [
                {"name": "Pull-ups", "reps": 8, "sets": 4},
                {"name": "Z Press", "reps": 8, "sets": 4},
            ],
        }
        intervals = block_to_intervals(block)

        assert len(intervals) == 1
        assert intervals[0].reps == 4

    def test_superset_no_rest_between_exercises(self):
        """Superset exercises have no rest between them — rest only after the pair."""
        block = {
            "structure": "superset",
            "rounds": 4,
            "exercises": [
                {"name": "Pull-ups", "reps": 8},
                {"name": "Z Press", "reps": 8},
            ],
            "rest_between_sec": 90,
        }
        intervals = block_to_intervals(block)

        repeat = intervals[0]
        # Order should be: exercise, exercise, rest
        assert repeat.intervals[0].kind == "reps"
        assert repeat.intervals[1].kind == "reps"
        assert repeat.intervals[2].kind == "rest"
        assert repeat.intervals[2].seconds == 90

    def test_circuit_block_creates_single_repeat_interval(self):
        """Block with structure='circuit' also groups exercises into one RepeatInterval."""
        block = {
            "structure": "circuit",
            "rounds": 3,
            "exercises": [
                {"name": "Burpees", "reps": 10},
                {"name": "Jump Squats", "reps": 15},
                {"name": "Push-ups", "reps": 20},
            ],
            "rest_between_sec": 60,
        }
        intervals = block_to_intervals(block)

        assert len(intervals) == 1
        repeat = intervals[0]
        assert repeat.kind == "repeat"
        assert repeat.reps == 3
        exercise_steps = [s for s in repeat.intervals if s.kind == "reps"]
        assert len(exercise_steps) == 3

    def test_superset_without_rest(self):
        """Superset with no rest_between_sec omits rest step."""
        block = {
            "structure": "superset",
            "rounds": 4,
            "exercises": [
                {"name": "Pull-ups", "reps": 8},
                {"name": "Z Press", "reps": 8},
            ],
        }
        intervals = block_to_intervals(block)

        repeat = intervals[0]
        # Should only have exercise steps, no rest
        assert all(s.kind == "reps" for s in repeat.intervals)
        assert len(repeat.intervals) == 2
