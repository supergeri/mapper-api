import pytest
from shared.schemas.cir import CIR, Workout, Block, Exercise
from backend.core.canonicalize import canonicalize


class TestCanonicalize:
    """Tests for the canonicalize function."""

    def test_canonicalize_sets_canonical_names(self):
        """Test that canonicalize sets canonical_name on exercises."""
        exercise = Exercise(name="db bench press")
        block = Block(items=[exercise])
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)
        
        result = canonicalize(cir)
        
        assert result.workout.blocks[0].items[0].canonical_name is not None

    def test_canonicalize_with_known_exercises(self):
        """Test canonicalize with exercises that should match."""
        exercises = [
            Exercise(name="db bench press"),
            Exercise(name="push ups"),
            Exercise(name="incline db flye")
        ]
        block = Block(items=exercises)
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)
        
        result = canonicalize(cir)
        
        # All should have canonical names set
        for ex in result.workout.blocks[0].items:
            assert ex.canonical_name is not None

    def test_canonicalize_with_resolver(self):
        """Test canonicalize with a custom resolver function."""
        exercise = Exercise(name="some exercise")
        block = Block(items=[exercise])
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)
        
        def resolver(norm):
            if norm == "some exercise":
                return "custom_canonical"
            return None
        
        result = canonicalize(cir, resolver=resolver)
        
        assert result.workout.blocks[0].items[0].canonical_name == "custom_canonical"

    def test_canonicalize_multiple_blocks(self):
        """Test canonicalize with multiple blocks."""
        block1 = Block(items=[Exercise(name="db bench press")])
        block2 = Block(items=[Exercise(name="push ups")])
        workout = Workout(title="Test", blocks=[block1, block2])
        cir = CIR(workout=workout)
        
        result = canonicalize(cir)
        
        assert len(result.workout.blocks) == 2
        assert result.workout.blocks[0].items[0].canonical_name is not None
        assert result.workout.blocks[1].items[0].canonical_name is not None

    def test_canonicalize_unknown_exercise(self):
        """Test canonicalize with an exercise that doesn't match."""
        exercise = Exercise(name="completely unknown exercise xyz")
        block = Block(items=[exercise])
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)
        
        result = canonicalize(cir)
        
        # Should return CIR (not crash), canonical_name might be None
        assert isinstance(result, CIR)
        
        canonical_name = result.workout.blocks[0].items[0].canonical_name
        # May be None if score is too low, or may have a fallback match
        assert canonical_name is None or isinstance(canonical_name, str)

    def test_canonicalize_returns_same_cir(self):
        """Test that canonicalize returns the same CIR object (in-place modification)."""
        exercise = Exercise(name="db bench press")
        block = Block(items=[exercise])
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)
        
        result = canonicalize(cir)
        
        # Should modify in place, so result is same object
        assert result is cir
        assert result.workout.blocks[0].items[0].canonical_name is not None


