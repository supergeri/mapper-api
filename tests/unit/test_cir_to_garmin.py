import pytest
import yaml
from shared.schemas.cir import CIR, Workout, Block, Exercise
from backend.adapters.cir_to_garmin_yaml import step_from_ex, to_garmin_yaml


@pytest.mark.unit
class TestCIRToGarmin:
    """Tests for the CIR to Garmin YAML conversion."""

    def test_step_from_ex_with_mapping(self):
        """Test step_from_ex with a mapped exercise."""
        ex = Exercise(
            name="Test Exercise",
            canonical_name="dumbbell_bench_press_flat",
            sets=3,
            reps=10,
            rest_seconds=60
        )

        result = step_from_ex(ex)

        assert result["type"] == "exercise"
        assert result["exerciseName"] == "Dumbbell Bench Press"
        assert result["sets"] == 3
        assert result["repetitionValue"] == 10
        assert result["rest"] == 60

    def test_step_from_ex_without_mapping(self):
        """Test step_from_ex with an unmapped exercise."""
        ex = Exercise(
            name="Unknown Exercise",
            canonical_name="unknown_exercise",
            sets=3,
            reps=10,
            rest_seconds=60
        )

        result = step_from_ex(ex)

        assert result["type"] == "exercise"
        assert "Custom: unknown_exercise" in result["exerciseName"]
        assert result["sets"] == 3
        assert result["repetitionValue"] == 10
        assert result["rest"] == 60

    def test_step_from_ex_with_no_canonical(self):
        """Test step_from_ex with no canonical name."""
        ex = Exercise(
            name="Original Name",
            canonical_name=None,
            sets=3,
            reps=10,
            rest_seconds=60
        )

        result = step_from_ex(ex)

        assert "Custom: Original Name" in result["exerciseName"]

    def test_step_from_ex_incline_modifier(self):
        """Test step_from_ex with incline modifier."""
        ex = Exercise(
            name="Test Flye",
            canonical_name="dumbbell_flye_incline",
            sets=3,
            reps=12,
            modifiers=["incline"]
        )

        result = step_from_ex(ex)

        assert result["position"] == "Incline"

    def test_to_garmin_yaml_straight_block(self):
        """Test to_garmin_yaml with a straight block."""
        exercises = [
            Exercise(name="Exercise 1", sets=3, reps=10),
            Exercise(name="Exercise 2", sets=4, reps=12)
        ]
        block = Block(type="straight", rounds=1, items=exercises)
        workout = Workout(title="Test Workout", blocks=[block])
        cir = CIR(workout=workout)

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert "workout" in doc
        assert doc["workout"]["name"] == "Test Workout"
        assert doc["workout"]["sport"] == "strength"
        assert len(doc["workout"]["steps"]) == 2
        assert doc["workout"]["steps"][0]["type"] == "exercise"

    def test_to_garmin_yaml_circuit_block(self):
        """Test to_garmin_yaml with a circuit block."""
        exercises = [
            Exercise(name="Exercise 1", sets=3, reps=10),
            Exercise(name="Exercise 2", sets=4, reps=12)
        ]
        block = Block(type="circuit", rounds=3, items=exercises)
        workout = Workout(title="Circuit Workout", blocks=[block])
        cir = CIR(workout=workout)

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert len(doc["workout"]["steps"]) == 1
        assert doc["workout"]["steps"][0]["type"] == "circuit"
        assert doc["workout"]["steps"][0]["rounds"] == 3
        assert len(doc["workout"]["steps"][0]["steps"]) == 2

    def test_to_garmin_yaml_superset_block(self):
        """Test to_garmin_yaml with a superset block."""
        exercises = [
            Exercise(name="Exercise 1", sets=3, reps=10),
            Exercise(name="Exercise 2", sets=4, reps=12)
        ]
        block = Block(type="superset", rounds=2, items=exercises)
        workout = Workout(title="Superset Workout", blocks=[block])
        cir = CIR(workout=workout)

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert doc["workout"]["steps"][0]["type"] == "circuit"
        assert doc["workout"]["steps"][0]["rounds"] == 2

    def test_to_garmin_yaml_with_notes(self):
        """Test to_garmin_yaml includes workout notes."""
        block = Block(items=[Exercise(name="Exercise 1")])
        workout = Workout(title="Test", notes="Test notes", blocks=[block])
        cir = CIR(workout=workout)

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert doc["workout"]["notes"] == "Test notes"

    def test_to_garmin_yaml_no_notes(self):
        """Test to_garmin_yaml handles missing notes."""
        block = Block(items=[Exercise(name="Exercise 1")])
        workout = Workout(title="Test", blocks=[block])
        cir = CIR(workout=workout)

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert doc["workout"]["notes"] is None
