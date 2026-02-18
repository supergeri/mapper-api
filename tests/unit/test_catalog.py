import pytest
from backend.core.catalog import all_synonyms, lookup


@pytest.mark.unit
class TestCatalog:
    """Tests for the catalog functions."""

    def test_lookup_existing(self):
        """Test looking up an existing canonical exercise."""
        result = lookup("dumbbell_bench_press_flat")
        assert result is not None
        assert result["canonical"] == "dumbbell_bench_press_flat"
        assert "synonyms" in result
        assert "equipment" in result

    def test_lookup_nonexistent(self):
        """Test looking up a non-existent canonical exercise."""
        result = lookup("nonexistent_exercise")
        assert result is None

    def test_all_synonyms_yields_correctly(self):
        """Test that all_synonyms yields canonical names and synonyms."""
        results = list(all_synonyms())
        assert len(results) > 0

        for canonical, synonyms in results:
            assert isinstance(canonical, str)
            assert isinstance(synonyms, list)
            assert len(synonyms) > 0
            # Canonical name should be in synonyms list
            assert canonical in synonyms

    def test_all_synonyms_contains_expected(self):
        """Test that all_synonyms contains expected exercises."""
        results = dict(all_synonyms())

        # Check that known exercises are present
        assert "dumbbell_bench_press_flat" in results
        assert "push_up" in results
        assert "dumbbell_flye_incline" in results

        # Check that canonical names are in their synonym lists
        assert "dumbbell_bench_press_flat" in results["dumbbell_bench_press_flat"]
        assert "push_up" in results["push_up"]
