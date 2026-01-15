"""
Unit tests for domain models.

Part of AMA-389: Define canonical Workout domain model

These tests verify:
- Model validation
- Model serialization/deserialization
- Computed properties
- Domain methods
"""

import json
import pytest
from datetime import datetime


@pytest.mark.unit
class TestLoadModel:
    """Tests for the Load value object."""

    def test_load_creation(self):
        """Load can be created with valid values."""
        from domain.models import Load

        load = Load(value=135, unit="lb")
        assert load.value == 135
        assert load.unit == "lb"
        assert load.per_side is False

    def test_load_per_side(self):
        """Load can be marked as per-side (e.g., dumbbells)."""
        from domain.models import Load

        load = Load(value=20, unit="kg", per_side=True)
        assert load.per_side is True

    def test_load_conversion_lb_to_kg(self):
        """Load converts from lb to kg correctly."""
        from domain.models import Load

        load = Load(value=100, unit="lb")
        assert abs(load.to_kg() - 45.36) < 0.01

    def test_load_conversion_kg_to_lb(self):
        """Load converts from kg to lb correctly."""
        from domain.models import Load

        load = Load(value=100, unit="kg")
        assert abs(load.to_lb() - 220.46) < 0.01

    def test_load_total_with_per_side(self):
        """Total load doubles when per_side is True."""
        from domain.models import Load

        load = Load(value=20, unit="kg", per_side=True)
        assert load.total_load_kg() == 40.0

    def test_load_validation_positive(self):
        """Load value must be positive."""
        from domain.models import Load

        with pytest.raises(ValueError):
            Load(value=0, unit="lb")

        with pytest.raises(ValueError):
            Load(value=-10, unit="kg")

    def test_load_validation_max(self):
        """Load value has a reasonable maximum."""
        from domain.models import Load

        with pytest.raises(ValueError):
            Load(value=5000, unit="lb")

    def test_load_serialization(self):
        """Load can be serialized to JSON."""
        from domain.models import Load

        load = Load(value=135, unit="lb", per_side=False)
        json_str = load.model_dump_json()
        data = json.loads(json_str)

        assert data["value"] == 135
        assert data["unit"] == "lb"
        assert data["per_side"] is False

    def test_load_deserialization(self):
        """Load can be deserialized from JSON."""
        from domain.models import Load

        json_str = '{"value": 100, "unit": "kg", "per_side": true}'
        load = Load.model_validate_json(json_str)

        assert load.value == 100
        assert load.unit == "kg"
        assert load.per_side is True

    def test_load_immutability(self):
        """Load is immutable (frozen)."""
        from domain.models import Load

        load = Load(value=135, unit="lb")
        with pytest.raises(Exception):  # ValidationError for frozen model
            load.value = 225


@pytest.mark.unit
class TestExerciseModel:
    """Tests for the Exercise value object."""

    def test_exercise_creation_basic(self):
        """Exercise can be created with basic fields."""
        from domain.models import Exercise

        exercise = Exercise(name="Squat", sets=5, reps=5)
        assert exercise.name == "Squat"
        assert exercise.sets == 5
        assert exercise.reps == 5

    def test_exercise_with_load(self):
        """Exercise can include a Load."""
        from domain.models import Exercise, Load

        exercise = Exercise(
            name="Bench Press",
            sets=4,
            reps=8,
            load=Load(value=135, unit="lb"),
        )
        assert exercise.load is not None
        assert exercise.load.value == 135
        assert exercise.has_load is True

    def test_exercise_timed(self):
        """Exercise can be time-based."""
        from domain.models import Exercise

        exercise = Exercise(name="Plank", sets=3, duration_seconds=60)
        assert exercise.is_timed is True
        assert exercise.is_rep_based is False

    def test_exercise_rep_based(self):
        """Exercise can be rep-based."""
        from domain.models import Exercise

        exercise = Exercise(name="Pull-up", sets=4, reps=10)
        assert exercise.is_rep_based is True
        assert exercise.is_timed is False

    def test_exercise_complex_reps(self):
        """Exercise supports complex rep schemes as strings."""
        from domain.models import Exercise

        exercise = Exercise(name="Pause Squat", sets=5, reps="3+1")
        assert exercise.reps == "3+1"
        assert exercise.total_reps is None  # Can't compute for complex schemes

    def test_exercise_total_reps(self):
        """Exercise computes total reps when possible."""
        from domain.models import Exercise

        exercise = Exercise(name="Curl", sets=3, reps=12)
        assert exercise.total_reps == 36

    def test_exercise_total_duration(self):
        """Exercise computes total duration when possible."""
        from domain.models import Exercise

        exercise = Exercise(name="Plank", sets=3, duration_seconds=60)
        assert exercise.total_duration_seconds == 180

    def test_exercise_with_modifiers(self):
        """Exercise can have equipment and modifiers."""
        from domain.models import Exercise

        exercise = Exercise(
            name="Bench Press",
            equipment=["barbell", "bench"],
            modifiers=["incline", "pause"],
            tempo="3010",
        )
        assert "barbell" in exercise.equipment
        assert "pause" in exercise.modifiers
        assert exercise.tempo == "3010"

    def test_exercise_side_specification(self):
        """Exercise can specify side for unilateral movements."""
        from domain.models import Exercise

        exercise = Exercise(name="Single Leg RDL", sets=3, reps=10, side="left")
        assert exercise.side == "left"

    def test_exercise_serialization(self):
        """Exercise can be serialized to JSON."""
        from domain.models import Exercise, Load

        exercise = Exercise(
            name="Squat",
            sets=5,
            reps=5,
            load=Load(value=225, unit="lb"),
            rest_seconds=180,
        )
        json_str = exercise.model_dump_json()
        data = json.loads(json_str)

        assert data["name"] == "Squat"
        assert data["sets"] == 5
        assert data["load"]["value"] == 225

    def test_exercise_deserialization(self):
        """Exercise can be deserialized from JSON."""
        from domain.models import Exercise

        json_str = '{"name": "Deadlift", "sets": 3, "reps": 5}'
        exercise = Exercise.model_validate_json(json_str)

        assert exercise.name == "Deadlift"
        assert exercise.sets == 3
        assert exercise.reps == 5


@pytest.mark.unit
class TestBlockModel:
    """Tests for the Block value object."""

    def test_block_creation(self):
        """Block can be created with exercises."""
        from domain.models import Block, Exercise

        block = Block(
            label="Main Lifts",
            exercises=[
                Exercise(name="Squat", sets=5, reps=5),
                Exercise(name="Bench", sets=5, reps=5),
            ],
        )
        assert block.label == "Main Lifts"
        assert block.exercise_count == 2

    def test_block_type_default(self):
        """Block defaults to STRAIGHT type."""
        from domain.models import Block, BlockType, Exercise

        block = Block(exercises=[Exercise(name="Curl", sets=3, reps=12)])
        assert block.type == BlockType.STRAIGHT

    def test_block_superset(self):
        """Block can be a superset."""
        from domain.models import Block, BlockType, Exercise

        block = Block(
            type=BlockType.SUPERSET,
            rounds=3,
            exercises=[
                Exercise(name="Bicep Curl", reps=12),
                Exercise(name="Tricep Pushdown", reps=12),
            ],
            rest_between_seconds=60,
        )
        assert block.is_superset is True
        assert block.rounds == 3

    def test_block_circuit(self):
        """Block can be a circuit."""
        from domain.models import Block, BlockType, Exercise

        block = Block(
            type=BlockType.CIRCUIT,
            rounds=4,
            exercises=[
                Exercise(name="Burpees", reps=10),
                Exercise(name="Mountain Climbers", duration_seconds=30),
                Exercise(name="Jump Squats", reps=15),
            ],
        )
        assert block.is_circuit is True

    def test_block_total_sets_straight(self):
        """Block computes total sets for straight sets."""
        from domain.models import Block, Exercise

        block = Block(
            exercises=[
                Exercise(name="Squat", sets=5, reps=5),
                Exercise(name="Bench", sets=4, reps=8),
            ]
        )
        assert block.total_sets == 9  # 5 + 4

    def test_block_total_sets_superset(self):
        """Block computes total sets for supersets."""
        from domain.models import Block, BlockType, Exercise

        block = Block(
            type=BlockType.SUPERSET,
            rounds=3,
            exercises=[
                Exercise(name="Curl", reps=12),
                Exercise(name="Extension", reps=12),
            ],
        )
        assert block.total_sets == 6  # 3 rounds * 2 exercises

    def test_block_exercise_names(self):
        """Block returns exercise names."""
        from domain.models import Block, Exercise

        block = Block(
            exercises=[
                Exercise(name="Squat", sets=5, reps=5),
                Exercise(name="Bench", sets=5, reps=5),
            ]
        )
        assert block.exercise_names == ["Squat", "Bench"]

    def test_block_validation_empty(self):
        """Block must have at least one exercise."""
        from domain.models import Block

        with pytest.raises(ValueError):
            Block(exercises=[])

    def test_block_serialization(self):
        """Block can be serialized to JSON."""
        from domain.models import Block, BlockType, Exercise

        block = Block(
            label="Superset A",
            type=BlockType.SUPERSET,
            rounds=3,
            exercises=[Exercise(name="Curl", reps=12)],
        )
        json_str = block.model_dump_json()
        data = json.loads(json_str)

        assert data["label"] == "Superset A"
        assert data["type"] == "superset"
        assert data["rounds"] == 3


@pytest.mark.unit
class TestWorkoutMetadataModel:
    """Tests for the WorkoutMetadata value object."""

    def test_metadata_creation(self):
        """WorkoutMetadata can be created."""
        from domain.models import WorkoutMetadata, WorkoutSource

        metadata = WorkoutMetadata(
            sources=[WorkoutSource.AI],
            platform="ios_companion",
        )
        assert WorkoutSource.AI in metadata.sources
        assert metadata.platform == "ios_companion"

    def test_metadata_ai_generated(self):
        """WorkoutMetadata detects AI-generated workouts."""
        from domain.models import WorkoutMetadata, WorkoutSource

        metadata = WorkoutMetadata(sources=[WorkoutSource.AI])
        assert metadata.is_ai_generated is True

    def test_metadata_imported(self):
        """WorkoutMetadata detects imported workouts."""
        from domain.models import WorkoutMetadata, WorkoutSource

        metadata = WorkoutMetadata(sources=[WorkoutSource.YOUTUBE])
        assert metadata.is_imported is True

    def test_metadata_export_tracking(self):
        """WorkoutMetadata tracks export status."""
        from domain.models import WorkoutMetadata

        metadata = WorkoutMetadata(
            is_exported=True,
            exported_to_device="garmin-123",
        )
        assert metadata.is_exported is True
        assert metadata.is_synced is True

    def test_metadata_serialization(self):
        """WorkoutMetadata can be serialized to JSON."""
        from domain.models import WorkoutMetadata, WorkoutSource

        metadata = WorkoutMetadata(
            sources=[WorkoutSource.AI, WorkoutSource.MANUAL],
            platform="garmin",
        )
        json_str = metadata.model_dump_json()
        data = json.loads(json_str)

        assert "ai" in data["sources"]
        assert data["platform"] == "garmin"


@pytest.mark.unit
class TestWorkoutModel:
    """Tests for the Workout aggregate root."""

    def test_workout_creation(self):
        """Workout can be created with basic fields."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Full Body",
            blocks=[
                Block(exercises=[Exercise(name="Squat", sets=5, reps=5)])
            ],
        )
        assert workout.title == "Full Body"
        assert workout.block_count == 1

    def test_workout_with_id(self):
        """Workout can have an ID."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            id="550e8400-e29b-41d4-a716-446655440000",
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
        )
        assert workout.id is not None
        assert workout.is_new is False

    def test_workout_is_new(self):
        """Workout without ID is new."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
        )
        assert workout.is_new is True

    def test_workout_total_exercises(self):
        """Workout computes total exercises."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[
                Block(exercises=[
                    Exercise(name="Squat"),
                    Exercise(name="Bench"),
                ]),
                Block(exercises=[
                    Exercise(name="Deadlift"),
                ]),
            ],
        )
        assert workout.total_exercises == 3

    def test_workout_total_sets(self):
        """Workout computes total sets."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[
                Block(exercises=[
                    Exercise(name="Squat", sets=5),
                    Exercise(name="Bench", sets=4),
                ]),
            ],
        )
        assert workout.total_sets == 9

    def test_workout_exercise_names(self):
        """Workout returns all exercise names."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[
                Block(exercises=[Exercise(name="Squat"), Exercise(name="Bench")]),
                Block(exercises=[Exercise(name="Deadlift")]),
            ],
        )
        assert workout.exercise_names == ["Squat", "Bench", "Deadlift"]

    def test_workout_unique_exercise_names(self):
        """Workout returns unique exercise names."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[
                Block(exercises=[Exercise(name="Squat"), Exercise(name="Bench")]),
                Block(exercises=[Exercise(name="Squat")]),  # Duplicate
            ],
        )
        assert workout.unique_exercise_names == ["Squat", "Bench"]

    def test_workout_tags_normalization(self):
        """Workout normalizes tags to lowercase."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
            tags=["STRENGTH", "Full-Body", "strength"],  # Duplicate after lowercase
        )
        assert "strength" in workout.tags
        assert "full-body" in workout.tags
        assert len(workout.tags) == 2  # Deduped

    def test_workout_with_id_method(self):
        """Workout.with_id returns new instance with ID."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
        )
        new_workout = workout.with_id("new-id-123")

        assert workout.id is None  # Original unchanged
        assert new_workout.id == "new-id-123"

    def test_workout_toggle_favorite(self):
        """Workout.toggle_favorite returns new instance with toggled status."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
            is_favorite=False,
        )
        new_workout = workout.toggle_favorite()

        assert workout.is_favorite is False  # Original unchanged
        assert new_workout.is_favorite is True

    def test_workout_record_completion(self):
        """Workout.record_completion increments counter."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
            times_completed=5,
        )
        new_workout = workout.record_completion()

        assert workout.times_completed == 5  # Original unchanged
        assert new_workout.times_completed == 6
        assert new_workout.last_used_at is not None

    def test_workout_add_tag(self):
        """Workout.add_tag returns new instance with added tag."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
            tags=["strength"],
        )
        new_workout = workout.add_tag("leg-day")

        assert "leg-day" not in workout.tags  # Original unchanged
        assert "leg-day" in new_workout.tags

    def test_workout_remove_tag(self):
        """Workout.remove_tag returns new instance without the tag."""
        from domain.models import Workout, Block, Exercise

        workout = Workout(
            title="Test",
            blocks=[Block(exercises=[Exercise(name="Squat")])],
            tags=["strength", "full-body"],
        )
        new_workout = workout.remove_tag("strength")

        assert "strength" in workout.tags  # Original unchanged
        assert "strength" not in new_workout.tags

    def test_workout_validation_empty_blocks(self):
        """Workout must have at least one block."""
        from domain.models import Workout

        with pytest.raises(ValueError):
            Workout(title="Test", blocks=[])

    def test_workout_validation_title_empty(self):
        """Workout title cannot be empty."""
        from domain.models import Workout, Block, Exercise

        with pytest.raises(ValueError):
            Workout(
                title="",
                blocks=[Block(exercises=[Exercise(name="Squat")])],
            )

    def test_workout_serialization(self):
        """Workout can be serialized to JSON."""
        from domain.models import Workout, Block, Exercise, Load

        workout = Workout(
            id="123",
            title="Full Body Strength",
            blocks=[
                Block(
                    label="Main Lifts",
                    exercises=[
                        Exercise(
                            name="Squat",
                            sets=5,
                            reps=5,
                            load=Load(value=225, unit="lb"),
                        )
                    ],
                )
            ],
            tags=["strength"],
        )
        json_str = workout.model_dump_json()
        data = json.loads(json_str)

        assert data["title"] == "Full Body Strength"
        assert data["blocks"][0]["label"] == "Main Lifts"
        assert data["blocks"][0]["exercises"][0]["name"] == "Squat"

    def test_workout_deserialization(self):
        """Workout can be deserialized from JSON."""
        from domain.models import Workout

        json_str = """
        {
            "title": "Test Workout",
            "blocks": [
                {
                    "exercises": [
                        {"name": "Squat", "sets": 5, "reps": 5}
                    ]
                }
            ]
        }
        """
        workout = Workout.model_validate_json(json_str)

        assert workout.title == "Test Workout"
        assert workout.blocks[0].exercises[0].name == "Squat"

    def test_workout_roundtrip_serialization(self):
        """Workout survives serialization roundtrip."""
        from domain.models import Workout, Block, Exercise, Load, WorkoutMetadata, WorkoutSource

        original = Workout(
            id="test-id",
            title="Full Body",
            description="A complete workout",
            blocks=[
                Block(
                    label="Main",
                    exercises=[
                        Exercise(
                            name="Squat",
                            sets=5,
                            reps=5,
                            load=Load(value=225, unit="lb"),
                        ),
                        Exercise(name="Plank", duration_seconds=60),
                    ],
                )
            ],
            metadata=WorkoutMetadata(
                sources=[WorkoutSource.AI],
                platform="ios_companion",
            ),
            tags=["strength", "full-body"],
            is_favorite=True,
            times_completed=10,
        )

        # Serialize to JSON
        json_str = original.model_dump_json()

        # Deserialize back
        restored = Workout.model_validate_json(json_str)

        # Verify all fields match
        assert restored.id == original.id
        assert restored.title == original.title
        assert restored.description == original.description
        assert len(restored.blocks) == len(original.blocks)
        assert restored.blocks[0].exercises[0].name == "Squat"
        assert restored.metadata.platform == "ios_companion"
        assert restored.tags == original.tags
        assert restored.is_favorite == original.is_favorite
        assert restored.times_completed == original.times_completed


@pytest.mark.unit
class TestNoInfrastructureImports:
    """Tests to verify domain models have no infrastructure dependencies."""

    def test_load_imports(self):
        """Load module has no infrastructure imports."""
        import domain.models.load as load_module

        # Check module doesn't import infrastructure
        module_imports = dir(load_module)
        infrastructure_patterns = ["supabase", "fastapi", "sqlalchemy", "requests", "httpx"]

        for pattern in infrastructure_patterns:
            assert pattern not in str(module_imports).lower()

    def test_exercise_imports(self):
        """Exercise module has no infrastructure imports."""
        import domain.models.exercise as exercise_module

        module_imports = dir(exercise_module)
        infrastructure_patterns = ["supabase", "fastapi", "sqlalchemy", "requests", "httpx"]

        for pattern in infrastructure_patterns:
            assert pattern not in str(module_imports).lower()

    def test_workout_imports(self):
        """Workout module has no infrastructure imports."""
        import domain.models.workout as workout_module

        module_imports = dir(workout_module)
        infrastructure_patterns = ["supabase", "fastapi", "sqlalchemy", "requests", "httpx"]

        for pattern in infrastructure_patterns:
            assert pattern not in str(module_imports).lower()
