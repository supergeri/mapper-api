import pytest
from shared.schemas.cir import CIR
from backend.adapters.ingest_to_cir import to_cir


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


