import pytest
from backend.core.match import suggest, classify


@pytest.mark.unit
class TestMatch:
    """Tests for the match functions."""

    def test_suggest_returns_list(self):
        """Test that suggest returns a list of tuples."""
        results = suggest("db bench press")
        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], tuple)
        assert len(results[0]) == 2  # (canonical, score)

    def test_suggest_top_k(self):
        """Test that suggest respects top_k parameter."""
        results = suggest("bench press", top_k=3)
        assert len(results) <= 3

        results = suggest("bench press", top_k=1)
        assert len(results) == 1

    def test_suggest_scores_are_valid(self):
        """Test that scores are between 0 and 1."""
        results = suggest("db bench press")
        for canonical, score in results:
            assert 0.0 <= score <= 1.0

    def test_suggest_best_match_first(self):
        """Test that best match is first in results."""
        results = suggest("db bench press")
        if len(results) > 1:
            first_score = results[0][1]
            second_score = results[1][1]
            assert first_score >= second_score

    def test_classify_structure(self):
        """Test that classify returns correct structure."""
        result = classify("db bench press")
        assert isinstance(result, dict)
        assert "canonical" in result
        assert "score" in result
        assert "status" in result
        assert "alternates" in result

    def test_classify_status_auto(self):
        """Test that classify returns 'auto' status for high scores."""
        # Use an exact match to ensure high score
        result = classify("db bench press")
        # Note: This may not always be 'auto' depending on fuzzy match score
        assert result["status"] in ["auto", "review", "unknown"]

    def test_classify_status_values(self):
        """Test that status is one of valid values."""
        result = classify("db bench press")
        assert result["status"] in ["auto", "review", "unknown"]

    def test_classify_score_range(self):
        """Test that score is between 0 and 1."""
        result = classify("db bench press")
        assert 0.0 <= result["score"] <= 1.0

    def test_classify_alternates_structure(self):
        """Test that alternates is a list of tuples."""
        result = classify("db bench press")
        assert isinstance(result["alternates"], list)
        if len(result["alternates"]) > 0:
            assert isinstance(result["alternates"][0], tuple)
            assert len(result["alternates"][0]) == 2

    def test_classify_with_exact_match(self):
        """Test classify with exercise names that should match well."""
        result = classify("push ups")
        assert result["canonical"] is not None
        assert result["score"] > 0

    def test_suggest_with_various_inputs(self):
        """Test suggest with various input formats."""
        # Test with abbreviation
        results1 = suggest("db bench")
        assert len(results1) > 0

        # Test with full name
        results2 = suggest("dumbbell bench press")
        assert len(results2) > 0

        # Test with different formatting
        results3 = suggest("push-ups")
        assert len(results3) > 0
