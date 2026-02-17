import pytest
from shared.schemas.cir import CIR
from backend.adapters.ingest_to_cir import to_cir


@pytest.mark.unit
class TestIngestToCIR:
    """Tests for the to_cir function."""

    def test_basic_conversion(self):
        """Test basic conversion from ingest JSON to CIR."""
        ingest = {
            "title": "Test Workout",
            "exercises": [
                {
                    "name": "Bench Press",
                    "sets": 3,
                    "reps": 10
                }
            ]
        }
        
        result = to_cir(ingest)
        
        assert isinstance(result, CIR)
        assert result.workout.title == "Test Workout"
        assert len(result.workout.blocks) == 1
        assert len(result.workout.blocks[0].items) == 1
        assert result.workout.blocks[0].items[0].name == "Bench Press"

    def test_default_title(self):
        """Test that default title is used when not provided."""
        ingest = {
            "exercises": []
        }
        
        result = to_cir(ingest)
        
        assert result.workout.title == "Imported Workout"

    def test_all_exercise_fields(self):
        """Test that all exercise fields are converted."""
        ingest = {
            "exercises": [
                {
                    "name": "Test Exercise",
                    "sets": 3,
                    "reps": "8-10",
                    "duration_seconds": 60,
                    "rest": 90,
                    "equipment": ["dumbbell", "bench"],
                    "modifiers": ["flat"],
                    "tempo": "2-1-2"
                }
            ]
        }
        
        result = to_cir(ingest)
        
        ex = result.workout.blocks[0].items[0]
        assert ex.name == "Test Exercise"
        assert ex.sets == 3
        assert ex.reps == "8-10"
        assert ex.duration_seconds == 60
        assert ex.rest_seconds == 90
        assert ex.equipment == ["dumbbell", "bench"]
        assert ex.modifiers == ["flat"]
        assert ex.tempo == "2-1-2"

    def test_multiple_exercises(self):
        """Test conversion with multiple exercises."""
        ingest = {
            "exercises": [
                {"name": "Exercise 1", "sets": 3},
                {"name": "Exercise 2", "sets": 4},
                {"name": "Exercise 3", "sets": 5}
            ]
        }
        
        result = to_cir(ingest)
        
        assert len(result.workout.blocks[0].items) == 3
        assert result.workout.blocks[0].items[0].name == "Exercise 1"
        assert result.workout.blocks[0].items[1].name == "Exercise 2"
        assert result.workout.blocks[0].items[2].name == "Exercise 3"

    def test_optional_fields(self):
        """Test that optional fields default correctly."""
        ingest = {
            "exercises": [
                {"name": "Exercise"}
            ]
        }
        
        result = to_cir(ingest)
        
        ex = result.workout.blocks[0].items[0]
        assert ex.name == "Exercise"
        assert ex.sets is None
        assert ex.reps is None
        assert ex.rest_seconds is None
        assert ex.equipment == []
        assert ex.modifiers == []

    def test_workout_metadata(self):
        """Test workout metadata fields."""
        ingest = {
            "title": "My Workout",
            "notes": "Test notes",
            "tags": ["chest", "push"],
            "exercises": []
        }
        
        result = to_cir(ingest)
        
        assert result.workout.title == "My Workout"
        assert result.workout.notes == "Test notes"
        assert result.workout.tags == ["chest", "push"]

    def test_block_type_and_rounds(self):
        """Test that block type and rounds are set correctly."""
        ingest = {
            "exercises": [{"name": "Exercise"}]
        }

        result = to_cir(ingest)

        block = result.workout.blocks[0]
        assert block.type == "straight"
        assert block.rounds == 1


@pytest.mark.unit
class TestIngestToCIRBlocks:
    """Tests for block-aware conversion in to_cir."""

    def test_blocks_with_superset_structure(self):
        """Input with blocks[].structure='superset' creates superset CIR blocks."""
        ingest = {
            "title": "Superset Workout",
            "blocks": [
                {
                    "structure": "superset",
                    "rounds": 4,
                    "exercises": [
                        {"name": "Pull-ups", "reps": 8},
                        {"name": "Z Press", "reps": 8},
                    ]
                },
                {
                    "structure": "superset",
                    "rounds": 4,
                    "exercises": [
                        {"name": "SA cable row", "reps": 12},
                        {"name": "SA DB press", "reps": 8},
                    ]
                },
                {
                    "exercises": [
                        {"name": "Seated sled pull", "sets": 5, "reps": 10},
                    ]
                }
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 3
        # Superset A
        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].rounds == 4
        assert len(result.workout.blocks[0].items) == 2
        assert result.workout.blocks[0].items[0].name == "Pull-ups"
        assert result.workout.blocks[0].items[1].name == "Z Press"
        # Superset B
        assert result.workout.blocks[1].type == "superset"
        assert result.workout.blocks[1].rounds == 4
        assert len(result.workout.blocks[1].items) == 2
        # Standalone
        assert result.workout.blocks[2].type == "straight"
        assert result.workout.blocks[2].items[0].name == "Seated sled pull"

    def test_blocks_with_circuit_structure(self):
        """Input with blocks[].structure='circuit' creates circuit CIR blocks."""
        ingest = {
            "title": "Circuit Workout",
            "blocks": [
                {
                    "structure": "circuit",
                    "rounds": 3,
                    "exercises": [
                        {"name": "Burpees", "reps": 10},
                        {"name": "Jump Squats", "reps": 15},
                        {"name": "Push-ups", "reps": 20},
                    ]
                }
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "circuit"
        assert result.workout.blocks[0].rounds == 3
        assert len(result.workout.blocks[0].items) == 3

    def test_blocks_with_timed_round_structures(self):
        """Tabata/EMOM/AMRAP map to timed_round BlockType."""
        for structure in ["tabata", "emom", "amrap", "for-time"]:
            ingest = {
                "blocks": [
                    {
                        "structure": structure,
                        "exercises": [{"name": "Exercise"}]
                    }
                ]
            }
            result = to_cir(ingest)
            assert result.workout.blocks[0].type == "timed_round", f"Failed for structure={structure}"

    def test_unknown_structure_defaults_to_straight(self):
        """Unknown structure values fall through to straight."""
        ingest = {
            "blocks": [
                {
                    "structure": "some_future_type",
                    "exercises": [{"name": "Exercise"}]
                }
            ]
        }

        result = to_cir(ingest)

        assert result.workout.blocks[0].type == "straight"

    def test_superset_rounds_fallback_to_exercise_sets(self):
        """When block has no rounds, use first exercise's sets as rounds."""
        ingest = {
            "blocks": [
                {
                    "structure": "superset",
                    "exercises": [
                        {"name": "Pull-ups", "sets": 4, "reps": 8},
                        {"name": "Z Press", "sets": 4, "reps": 8},
                    ]
                }
            ]
        }

        result = to_cir(ingest)

        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].rounds == 4

    def test_backward_compat_flat_exercises_no_labels(self):
        """Flat exercises with no superset indicators produce single straight block."""
        ingest = {
            "exercises": [
                {"name": "Bench Press", "sets": 3, "reps": 10},
                {"name": "Rows", "sets": 3, "reps": 10},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "straight"
        assert len(result.workout.blocks[0].items) == 2


@pytest.mark.unit
class TestDetectSupersetGroups:
    """Tests for the superset detection heuristic on flat exercise lists."""

    def test_detect_superset_label_field(self):
        """Exercises with superset_label field are grouped."""
        ingest = {
            "exercises": [
                {"name": "Pull-ups", "reps": 8, "sets": 4, "superset_label": "A"},
                {"name": "Z Press", "reps": 8, "sets": 4, "superset_label": "A"},
                {"name": "SA cable row", "reps": 12, "sets": 4, "superset_label": "B"},
                {"name": "SA DB press", "reps": 8, "sets": 4, "superset_label": "B"},
                {"name": "Seated sled pull", "reps": 10, "sets": 5},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 3
        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].rounds == 4
        assert len(result.workout.blocks[0].items) == 2
        assert result.workout.blocks[0].items[0].name == "Pull-ups"
        assert result.workout.blocks[0].items[1].name == "Z Press"
        assert result.workout.blocks[1].type == "superset"
        assert result.workout.blocks[1].rounds == 4
        assert len(result.workout.blocks[1].items) == 2
        assert result.workout.blocks[2].type == "straight"
        assert result.workout.blocks[2].items[0].name == "Seated sled pull"

    def test_detect_parenthesized_superset_labels(self):
        """Exercises with '(superset A)' in name are grouped."""
        ingest = {
            "exercises": [
                {"name": "Pull-ups (superset A)", "reps": 8, "sets": 4},
                {"name": "Z Press (superset A)", "reps": 8, "sets": 4},
                {"name": "Rows (superset B)", "reps": 12, "sets": 4},
                {"name": "DB press (superset B)", "reps": 8, "sets": 4},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 2
        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].items[0].name == "Pull-ups"
        assert result.workout.blocks[0].items[1].name == "Z Press"
        assert result.workout.blocks[1].type == "superset"

    def test_detect_letter_prefix_groups(self):
        """Exercises with A1:/A2:/B1:/B2: prefixes are grouped."""
        ingest = {
            "exercises": [
                {"name": "A1: Pull-ups", "reps": 8, "sets": 4},
                {"name": "A2: Z Press", "reps": 8, "sets": 4},
                {"name": "B1: Rows", "reps": 12, "sets": 3},
                {"name": "B2: DB press", "reps": 8, "sets": 3},
                {"name": "Sled pull", "reps": 10, "sets": 5},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 3
        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].items[0].name == "A1: Pull-ups"
        assert result.workout.blocks[0].items[1].name == "A2: Z Press"
        assert result.workout.blocks[1].type == "superset"
        assert result.workout.blocks[2].type == "straight"

    def test_mixed_superset_and_standalone(self):
        """Mix of superset-labeled and unlabeled exercises creates correct blocks."""
        ingest = {
            "exercises": [
                {"name": "Warmup jog", "duration_seconds": 300},
                {"name": "Pull-ups", "reps": 8, "sets": 4, "superset_label": "A"},
                {"name": "Z Press", "reps": 8, "sets": 4, "superset_label": "A"},
                {"name": "Cooldown stretch", "duration_seconds": 180},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 3
        assert result.workout.blocks[0].type == "straight"
        assert result.workout.blocks[0].items[0].name == "Warmup jog"
        assert result.workout.blocks[1].type == "superset"
        assert len(result.workout.blocks[1].items) == 2
        assert result.workout.blocks[2].type == "straight"
        assert result.workout.blocks[2].items[0].name == "Cooldown stretch"


@pytest.mark.unit
class TestDetectCircuitGroups:
    """Tests for circuit detection in the flat exercise path (AMA-648)."""

    def test_circuit_label_field(self):
        """3+ exercises with circuit_label field produce a circuit block."""
        ingest = {
            "exercises": [
                {"name": "Ski Erg", "sets": 5, "circuit_label": "A"},
                {"name": "Sled Pull", "sets": 5, "circuit_label": "A"},
                {"name": "Bike Erg", "sets": 5, "circuit_label": "A"},
                {"name": "Wall Balls", "sets": 5, "circuit_label": "A"},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "circuit"
        assert result.workout.blocks[0].rounds == 5
        assert len(result.workout.blocks[0].items) == 4
        assert result.workout.blocks[0].items[0].name == "Ski Erg"
        assert result.workout.blocks[0].items[3].name == "Wall Balls"

    def test_parenthesized_circuit_labels(self):
        """Exercises with '(circuit A)' in name produce circuit block."""
        ingest = {
            "exercises": [
                {"name": "Burpees (circuit A)", "reps": 10, "sets": 3},
                {"name": "Jump Squats (circuit A)", "reps": 15, "sets": 3},
                {"name": "Push-ups (circuit A)", "reps": 20, "sets": 3},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "circuit"
        assert result.workout.blocks[0].rounds == 3
        # Labels should be cleaned from names
        assert result.workout.blocks[0].items[0].name == "Burpees"
        assert result.workout.blocks[0].items[1].name == "Jump Squats"
        assert result.workout.blocks[0].items[2].name == "Push-ups"

    def test_letter_prefix_three_plus_is_circuit(self):
        """3+ exercises with same letter prefix (A1:, A2:, A3:) = circuit, not superset."""
        ingest = {
            "exercises": [
                {"name": "A1: Ski Erg", "sets": 4},
                {"name": "A2: Sled Pull", "sets": 4},
                {"name": "A3: Bike Erg", "sets": 4},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "circuit"
        assert result.workout.blocks[0].rounds == 4

    def test_mixed_circuit_superset_standalone(self):
        """Mixed circuit (3+) + superset (2) + standalone in one flat list."""
        ingest = {
            "exercises": [
                # Circuit: 3 exercises with label A
                {"name": "Burpees", "reps": 10, "sets": 3, "circuit_label": "A"},
                {"name": "Jump Squats", "reps": 15, "sets": 3, "circuit_label": "A"},
                {"name": "Push-ups", "reps": 20, "sets": 3, "circuit_label": "A"},
                # Superset: 2 exercises with label B
                {"name": "Pull-ups", "reps": 8, "sets": 4, "superset_label": "B"},
                {"name": "Dips", "reps": 10, "sets": 4, "superset_label": "B"},
                # Standalone
                {"name": "Plank", "duration_seconds": 60},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 3
        assert result.workout.blocks[0].type == "circuit"
        assert result.workout.blocks[0].rounds == 3
        assert len(result.workout.blocks[0].items) == 3
        assert result.workout.blocks[1].type == "superset"
        assert result.workout.blocks[1].rounds == 4
        assert len(result.workout.blocks[1].items) == 2
        assert result.workout.blocks[2].type == "straight"
        assert result.workout.blocks[2].items[0].name == "Plank"

    def test_hyrox_style_circuit_with_rounds(self):
        """HYROX-style circuit: 4 exercises, 5 rounds, rounds from exercise sets."""
        ingest = {
            "exercises": [
                {"name": "Ski Erg", "sets": 5, "circuit_label": "A"},
                {"name": "Sled Pull", "sets": 5, "circuit_label": "A"},
                {"name": "Bike Erg", "sets": 5, "circuit_label": "A"},
                {"name": "Wall Balls", "reps": 20, "sets": 5, "circuit_label": "A"},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        block = result.workout.blocks[0]
        assert block.type == "circuit"
        assert block.rounds == 5
        assert len(block.items) == 4

    def test_two_exercises_with_circuit_label_become_superset(self):
        """Only 2 exercises sharing a circuit_label fall back to superset (count < 3)."""
        ingest = {
            "exercises": [
                {"name": "Pull-ups", "sets": 4, "circuit_label": "A"},
                {"name": "Dips", "sets": 4, "circuit_label": "A"},
            ]
        }

        result = to_cir(ingest)

        assert len(result.workout.blocks) == 1
        assert result.workout.blocks[0].type == "superset"
        assert result.workout.blocks[0].rounds == 4
        assert len(result.workout.blocks[0].items) == 2


