"""
Unit tests for ExerciseRepository new methods.

Part of AMA-472: Exercise Database Integration for Program Generation

Tests the new repository methods:
- get_similar_exercises
- validate_exercise_name
"""

import pytest

from tests.fakes import FakeExerciseRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo():
    """Create a fake exercise repository with default exercises."""
    repo = FakeExerciseRepository()
    repo.seed_default_exercises()
    return repo


@pytest.fixture
def repo_with_aliases():
    """Create a repository with exercises that have aliases."""
    repo = FakeExerciseRepository()
    repo.seed([
        {
            "id": "bench-press",
            "name": "Barbell Bench Press",
            "primary_muscles": ["chest"],
            "secondary_muscles": ["triceps", "anterior_deltoid"],
            "equipment": ["barbell", "bench"],
            "category": "compound",
            "movement_pattern": "push",
            "supports_1rm": True,
            "aliases": ["Flat Bench", "BB Bench", "chest press"],
        },
        {
            "id": "squat",
            "name": "Barbell Back Squat",
            "primary_muscles": ["quadriceps", "glutes"],
            "secondary_muscles": ["hamstrings"],
            "equipment": ["barbell", "squat_rack"],
            "category": "compound",
            "movement_pattern": "squat",
            "supports_1rm": True,
            "aliases": ["Back Squat", "BB Squat"],
        },
    ])
    return repo


# ---------------------------------------------------------------------------
# get_similar_exercises Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetSimilarExercises:
    """Tests for get_similar_exercises method."""

    def test_returns_similar_exercises(self, repo):
        """Returns exercises with same movement pattern and overlapping muscles."""
        similar = repo.get_similar_exercises("barbell-bench-press", limit=5)

        assert len(similar) > 0
        for ex in similar:
            assert ex["id"] != "barbell-bench-press"
            # Should have same movement pattern
            assert ex.get("movement_pattern") == "push"

    def test_returns_empty_for_unknown_exercise(self, repo):
        """Returns empty list for unknown exercise ID."""
        similar = repo.get_similar_exercises("nonexistent-exercise")

        assert similar == []

    def test_respects_limit(self, repo):
        """Respects the limit parameter."""
        similar = repo.get_similar_exercises("barbell-bench-press", limit=2)

        assert len(similar) <= 2

    def test_excludes_source_exercise(self, repo):
        """Does not include the source exercise in results."""
        similar = repo.get_similar_exercises("barbell-bench-press", limit=10)

        ids = [ex["id"] for ex in similar]
        assert "barbell-bench-press" not in ids

    def test_prioritizes_muscle_overlap(self, repo):
        """Exercises with more muscle overlap score higher."""
        # Barbell bench targets chest primarily
        similar = repo.get_similar_exercises("barbell-bench-press", limit=3)

        # First result should also target chest
        if similar:
            first = similar[0]
            assert "chest" in first.get("primary_muscles", [])

    def test_considers_category(self, repo):
        """Exercises with same category score higher."""
        similar = repo.get_similar_exercises("barbell-bench-press", limit=5)

        # Should prefer compounds over isolation for bench press alternatives
        categories = [ex.get("category") for ex in similar]
        if "compound" in categories:
            # Compound should appear before isolation
            compound_idx = categories.index("compound")
            isolation_indices = [i for i, c in enumerate(categories) if c == "isolation"]
            if isolation_indices:
                assert compound_idx < max(isolation_indices)

    def test_handles_exercise_without_pattern(self, repo):
        """Handles edge case of exercise without movement pattern."""
        # Seed an exercise without movement pattern
        repo.seed([{
            "id": "test-no-pattern",
            "name": "Test Exercise",
            "primary_muscles": ["chest"],
            "equipment": ["barbell"],
        }])

        similar = repo.get_similar_exercises("test-no-pattern")

        assert similar == []


# ---------------------------------------------------------------------------
# validate_exercise_name Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestValidateExerciseName:
    """Tests for validate_exercise_name method."""

    def test_finds_exact_match(self, repo):
        """Finds exercise by exact name."""
        result = repo.validate_exercise_name("Barbell Bench Press")

        assert result is not None
        assert result["id"] == "barbell-bench-press"

    def test_case_insensitive_match(self, repo):
        """Finds exercise with case-insensitive name match."""
        result = repo.validate_exercise_name("BARBELL BENCH PRESS")

        assert result is not None
        assert result["id"] == "barbell-bench-press"

    def test_finds_by_alias(self, repo_with_aliases):
        """Finds exercise by alias."""
        result = repo_with_aliases.validate_exercise_name("Flat Bench")

        assert result is not None
        assert result["id"] == "bench-press"

    def test_case_insensitive_alias(self, repo_with_aliases):
        """Finds exercise by alias case-insensitively."""
        result = repo_with_aliases.validate_exercise_name("bb squat")

        assert result is not None
        assert result["id"] == "squat"

    def test_returns_none_for_unknown(self, repo):
        """Returns None for unknown exercise name."""
        result = repo.validate_exercise_name("Nonexistent Exercise")

        assert result is None

    def test_returns_none_for_empty_string(self, repo):
        """Returns None for empty string."""
        result = repo.validate_exercise_name("")

        assert result is None

    def test_prefers_exact_name_over_alias(self, repo_with_aliases):
        """Prefers exact name match over alias match."""
        # "Barbell Bench Press" is the exact name
        result = repo_with_aliases.validate_exercise_name("Barbell Bench Press")

        assert result is not None
        assert result["id"] == "bench-press"
        assert result["name"] == "Barbell Bench Press"


# ---------------------------------------------------------------------------
# Existing Method Regression Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExistingMethods:
    """Regression tests to ensure existing methods still work."""

    def test_get_by_id(self, repo):
        """get_by_id still works."""
        result = repo.get_by_id("barbell-bench-press")

        assert result is not None
        assert result["id"] == "barbell-bench-press"

    def test_get_by_name(self, repo):
        """get_by_name still works (exact match)."""
        result = repo.get_by_name("Barbell Bench Press")

        assert result is not None
        assert result["id"] == "barbell-bench-press"

    def test_search_by_alias(self, repo_with_aliases):
        """search_by_alias still works."""
        results = repo_with_aliases.search_by_alias("Flat Bench")

        assert len(results) == 1
        assert results[0]["id"] == "bench-press"

    def test_get_by_muscle_groups(self, repo):
        """get_by_muscle_groups still works."""
        results = repo.get_by_muscle_groups(["chest"])

        assert len(results) > 0
        for ex in results:
            assert "chest" in ex.get("primary_muscles", [])

    def test_get_by_equipment(self, repo):
        """get_by_equipment still works."""
        results = repo.get_by_equipment(["barbell"])

        assert len(results) > 0
        for ex in results:
            equipment = ex.get("equipment", [])
            # Either bodyweight or has barbell
            if equipment:
                assert "barbell" in equipment

    def test_search_combined(self, repo):
        """search with multiple criteria still works."""
        results = repo.search(
            muscle_groups=["chest"],
            equipment=["barbell"],
            movement_pattern="push",
            limit=10,
        )

        assert len(results) > 0
        for ex in results:
            assert ex.get("movement_pattern") == "push"
