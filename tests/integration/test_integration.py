import pytest
import json
from shared.schemas.cir import CIR
from backend.adapters.ingest_to_cir import to_cir
from backend.core.canonicalize import canonicalize
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
import yaml


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the full pipeline."""

    def test_full_pipeline(self):
        """Test the complete pipeline from ingest JSON to Garmin YAML."""
        ingest = {
            "title": "Upper Body Push",
            "exercises": [
                {
                    "name": "DB Bench Press",
                    "sets": 3,
                    "reps": "8-10",
                    "rest": 60,
                    "equipment": ["dumbbell"],
                    "modifiers": ["flat"]
                },
                {
                    "name": "Incline DB Flye",
                    "sets": 3,
                    "reps": 12,
                    "rest": 75,
                    "equipment": ["dumbbell"],
                    "modifiers": ["incline"]
                },
                {
                    "name": "Push-ups",
                    "sets": 3,
                    "reps": 15,
                    "rest": 0
                }
            ]
        }

        # Step 1: Convert to CIR
        cir = to_cir(ingest)
        assert isinstance(cir, CIR)
        assert len(cir.workout.blocks[0].items) == 3

        # Step 2: Canonicalize
        cir = canonicalize(cir)
        assert cir.workout.blocks[0].items[0].canonical_name is not None
        assert cir.workout.blocks[0].items[1].canonical_name is not None
        assert cir.workout.blocks[0].items[2].canonical_name is not None

        # Step 3: Convert to Garmin YAML
        yaml_str = to_garmin_yaml(cir)
        assert isinstance(yaml_str, str)

        # Validate YAML can be parsed
        doc = yaml.safe_load(yaml_str)
        assert "workout" in doc
        assert doc["workout"]["name"] == "Upper Body Push"
        assert len(doc["workout"]["steps"]) == 3

    def test_pipeline_with_sample_file(self):
        """Test pipeline using the sample OCR JSON file."""
        import pathlib

        sample_file = pathlib.Path(__file__).parents[1] / "sample" / "ocr.json"

        if sample_file.exists():
            with open(sample_file) as f:
                ingest = json.load(f)

            # Run full pipeline
            cir = to_cir(ingest)
            cir = canonicalize(cir)
            yaml_str = to_garmin_yaml(cir)

            # Validate output
            assert len(yaml_str) > 0
            doc = yaml.safe_load(yaml_str)
            assert "workout" in doc

            # Verify exercises were canonicalized
            canonical_names = [
                ex.canonical_name
                for block in cir.workout.blocks
                for ex in block.items
            ]
            assert all(name is not None for name in canonical_names)

    def test_pipeline_with_unknown_exercise(self):
        """Test pipeline with an exercise that doesn't match catalog."""
        ingest = {
            "title": "Test",
            "exercises": [
                {
                    "name": "Completely Unknown Exercise XYZ123",
                    "sets": 3,
                    "reps": 10
                }
            ]
        }

        cir = to_cir(ingest)
        cir = canonicalize(cir)

        # Should not crash even with unknown exercise
        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)

        assert "workout" in doc
        assert len(doc["workout"]["steps"]) > 0
        # Should have custom exercise name
        step = doc["workout"]["steps"][0]
        assert "Custom:" in step.get("exerciseName", "")

    def test_pipeline_preserves_metadata(self):
        """Test that workout metadata is preserved through pipeline."""
        ingest = {
            "title": "Custom Title",
            "notes": "Test notes",
            "tags": ["tag1", "tag2"],
            "exercises": [{"name": "Exercise 1"}]
        }

        cir = to_cir(ingest)
        assert cir.workout.title == "Custom Title"
        assert cir.workout.notes == "Test notes"
        assert cir.workout.tags == ["tag1", "tag2"]

        cir = canonicalize(cir)
        assert cir.workout.title == "Custom Title"

        yaml_str = to_garmin_yaml(cir)
        doc = yaml.safe_load(yaml_str)
        assert doc["workout"]["name"] == "Custom Title"
        assert doc["workout"]["notes"] == "Test notes"
