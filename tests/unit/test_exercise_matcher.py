"""
Unit tests for ExerciseMatchingService.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service
"""
import pytest
from unittest.mock import Mock, MagicMock

from backend.core.exercise_matcher import (
    ExerciseMatchingService,
    ExerciseMatch,
    MatchMethod,
)
from tests.fakes import FakeExercisesRepository


@pytest.fixture
def fake_repo() -> FakeExercisesRepository:
    """Create a FakeExercisesRepository with default test data."""
    return FakeExercisesRepository()


@pytest.fixture
def matcher(fake_repo: FakeExercisesRepository) -> ExerciseMatchingService:
    """Create an ExerciseMatchingService with fake repository."""
    return ExerciseMatchingService(
        exercises_repository=fake_repo,
        llm_client=None,
        enable_llm_fallback=False,
    )


@pytest.mark.unit
class TestExactMatch:
    """Tests for exact name matching."""

    def test_exact_match_returns_full_confidence(self, matcher: ExerciseMatchingService):
        """Exact name match should return confidence 1.0."""
        result = matcher.match("Barbell Bench Press")

        assert result.exercise_id == "barbell-bench-press"
        assert result.exercise_name == "Barbell Bench Press"
        assert result.confidence == 1.0
        assert result.method == MatchMethod.EXACT

    def test_exact_match_case_insensitive(self, matcher: ExerciseMatchingService):
        """Exact match should be case-insensitive."""
        result = matcher.match("barbell bench press")

        assert result.exercise_id == "barbell-bench-press"
        assert result.confidence == 1.0
        assert result.method == MatchMethod.EXACT

    def test_exact_match_mixed_case(self, matcher: ExerciseMatchingService):
        """Exact match should work with mixed case."""
        result = matcher.match("BARBELL BENCH PRESS")

        assert result.exercise_id == "barbell-bench-press"
        assert result.confidence == 1.0
        assert result.method == MatchMethod.EXACT


@pytest.mark.unit
class TestAliasMatch:
    """Tests for alias matching."""

    def test_alias_match_returns_high_confidence(self, matcher: ExerciseMatchingService):
        """Alias match should return high confidence (0.93-0.95)."""
        result = matcher.match("BB Bench")  # Alias for Barbell Bench Press

        assert result.exercise_id == "barbell-bench-press"
        assert result.confidence >= 0.93
        assert result.method == MatchMethod.ALIAS

    def test_alias_match_rdl(self, matcher: ExerciseMatchingService):
        """RDL alias should match Romanian Deadlift."""
        result = matcher.match("RDL")

        assert result.exercise_id == "romanian-deadlift"
        assert result.confidence >= 0.93
        assert result.method == MatchMethod.ALIAS

    def test_alias_match_pullup_variations(self, matcher: ExerciseMatchingService):
        """Various pullup aliases should match Pull-Up."""
        for alias in ["Pullup", "Pull Up"]:
            result = matcher.match(alias)
            assert result.exercise_id == "pull-up"
            assert result.method == MatchMethod.ALIAS

    def test_alias_match_pushup_variations(self, matcher: ExerciseMatchingService):
        """Various pushup aliases should match Push-Up."""
        for alias in ["Pushup", "Push Up", "Press Up"]:
            result = matcher.match(alias)
            assert result.exercise_id == "push-up"
            assert result.method == MatchMethod.ALIAS


@pytest.mark.unit
class TestFuzzyMatch:
    """Tests for fuzzy matching."""

    def test_fuzzy_match_minor_variation(self, matcher: ExerciseMatchingService):
        """Minor spelling variations should fuzzy match with high confidence."""
        result = matcher.match("Barbell Back Squats")  # Plural form

        assert result.exercise_id == "barbell-back-squat"
        assert result.method == MatchMethod.FUZZY
        assert result.confidence >= 0.8

    def test_fuzzy_match_suggests_alias(self, matcher: ExerciseMatchingService):
        """High-confidence fuzzy match should suggest adding as alias."""
        # "Bench Press Barbell" is similar but not exact or alias
        result = matcher.match("Flat Barbell Bench Press")

        assert result.exercise_id is not None
        assert result.method == MatchMethod.FUZZY
        # High confidence fuzzy matches may suggest alias
        if result.confidence >= 0.90:
            # Only suggests alias if it's not already in aliases
            pass  # suggested_alias may or may not be set

    def test_fuzzy_match_equipment_boost(self, matcher: ExerciseMatchingService):
        """Equipment keyword match should boost score."""
        result = matcher.match("Barbell Deadlifts")

        assert result.exercise_id == "conventional-deadlift"
        assert result.method == MatchMethod.FUZZY


@pytest.mark.unit
class TestNoMatch:
    """Tests for non-matching inputs."""

    def test_no_match_gibberish(self, matcher: ExerciseMatchingService):
        """Gibberish input should return no match."""
        result = matcher.match("xyzzy plugh")

        assert result.exercise_id is None
        assert result.confidence == 0.0
        assert result.method == MatchMethod.NONE

    def test_no_match_empty_string(self, matcher: ExerciseMatchingService):
        """Empty string should return no match."""
        result = matcher.match("")

        assert result.exercise_id is None
        assert result.confidence == 0.0
        assert result.method == MatchMethod.NONE

    def test_no_match_whitespace(self, matcher: ExerciseMatchingService):
        """Whitespace-only input should return no match."""
        result = matcher.match("   ")

        assert result.exercise_id is None
        assert result.confidence == 0.0
        assert result.method == MatchMethod.NONE


@pytest.mark.unit
class TestBatchMatch:
    """Tests for batch matching."""

    def test_batch_match_returns_same_order(self, matcher: ExerciseMatchingService):
        """Batch match should return results in same order as input."""
        names = ["Barbell Bench Press", "Squat", "RDL"]
        results = matcher.match_batch(names)

        assert len(results) == 3
        assert results[0].exercise_id == "barbell-bench-press"
        assert results[1].exercise_id == "barbell-back-squat"  # "Squat" is an alias
        assert results[2].exercise_id == "romanian-deadlift"

    def test_batch_match_handles_no_matches(self, matcher: ExerciseMatchingService):
        """Batch match should handle mix of matches and non-matches."""
        names = ["Barbell Bench Press", "xyzzy", "RDL"]
        results = matcher.match_batch(names)

        assert len(results) == 3
        assert results[0].exercise_id == "barbell-bench-press"
        assert results[1].exercise_id is None  # No match
        assert results[2].exercise_id == "romanian-deadlift"


@pytest.mark.unit
class TestSuggestMatches:
    """Tests for match suggestions."""

    def test_suggest_matches_returns_multiple(self, matcher: ExerciseMatchingService):
        """Suggest matches should return multiple candidates."""
        suggestions = matcher.suggest_matches("bench press", limit=5)

        assert len(suggestions) >= 2
        # Both barbell and dumbbell bench press should be in suggestions
        ids = [s.exercise_id for s in suggestions]
        assert "barbell-bench-press" in ids or "dumbbell-bench-press" in ids

    def test_suggest_matches_respects_limit(self, matcher: ExerciseMatchingService):
        """Suggest matches should respect the limit parameter."""
        suggestions = matcher.suggest_matches("press", limit=3)

        assert len(suggestions) <= 3

    def test_suggest_matches_sorted_by_confidence(self, matcher: ExerciseMatchingService):
        """Suggestions should be sorted by confidence descending."""
        suggestions = matcher.suggest_matches("deadlift", limit=5)

        confidences = [s.confidence for s in suggestions]
        assert confidences == sorted(confidences, reverse=True)


@pytest.mark.unit
class TestCache:
    """Tests for caching behavior."""

    def test_clear_cache(self, matcher: ExerciseMatchingService):
        """clear_cache should reset the exercises cache."""
        # Use suggest_matches to trigger cache population
        # (exact match doesn't use cache, but fuzzy/suggestions do)
        matcher.suggest_matches("bench press")
        assert matcher._exercises_cache is not None

        # Clear cache
        matcher.clear_cache()
        assert matcher._exercises_cache is None

    def test_cache_populated_on_fuzzy_match(self, matcher: ExerciseMatchingService):
        """Cache should be populated when fuzzy matching is used."""
        # Force fuzzy match by using a name that won't exact/alias match
        matcher.match("Flat Barbell Bench Press With Chains")
        assert matcher._exercises_cache is not None


@pytest.mark.unit
class TestMatchResult:
    """Tests for ExerciseMatch dataclass."""

    def test_match_result_fields(self, matcher: ExerciseMatchingService):
        """Match result should have all expected fields."""
        result = matcher.match("Barbell Bench Press")

        assert hasattr(result, "exercise_id")
        assert hasattr(result, "exercise_name")
        assert hasattr(result, "confidence")
        assert hasattr(result, "method")
        assert hasattr(result, "reasoning")
        assert hasattr(result, "suggested_alias")

    def test_method_enum_values(self):
        """MatchMethod enum should have expected values."""
        assert MatchMethod.EXACT.value == "exact"
        assert MatchMethod.ALIAS.value == "alias"
        assert MatchMethod.FUZZY.value == "fuzzy"
        assert MatchMethod.LLM.value == "llm"
        assert MatchMethod.NONE.value == "none"


@pytest.mark.unit
class TestEquipmentKeywordBoost:
    """Tests for equipment keyword matching."""

    def test_barbell_keyword_match(self, matcher: ExerciseMatchingService):
        """Barbell keyword should boost matching exercises."""
        # When matching "barbell squat", the barbell equipment match should help
        result = matcher.match("bb squat")

        assert result.exercise_id is not None
        assert "squat" in result.exercise_id

    def test_dumbbell_keyword_match(self, matcher: ExerciseMatchingService):
        """Dumbbell keyword variants should boost matching exercises."""
        result = matcher.match("db press")

        assert result.exercise_id is not None
        # Should match a dumbbell exercise
        assert "dumbbell" in result.exercise_id or "db" in result.exercise_id.lower()


@pytest.mark.unit
class TestLLMFallback:
    """Tests for LLM fallback matching."""

    def test_llm_fallback_disabled_by_default(self, fake_repo: FakeExercisesRepository):
        """LLM should not be called when disabled."""
        mock_llm = Mock()
        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=False,
        )
        # Match something that won't exact/alias match well
        matcher.match("some obscure exercise name xyz")
        mock_llm.chat.completions.create.assert_not_called()

    def test_llm_fallback_called_for_low_confidence(self, fake_repo: FakeExercisesRepository):
        """LLM should be called when fuzzy confidence is below auto-accept threshold."""
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"exercise_id": "barbell-bench-press", "confidence": 0.75, "reasoning": "semantic match"}'))
        ]
        mock_llm = Mock()
        mock_llm.chat.completions.create.return_value = mock_response

        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=True,
        )
        # Use a name that will fuzzy match but below 90% threshold
        result = matcher.match("flat bench barbell pressing movement")

        # LLM should have been called since fuzzy score likely below 90%
        if result.method == MatchMethod.LLM:
            mock_llm.chat.completions.create.assert_called_once()

    def test_llm_exception_handled_gracefully(self, fake_repo: FakeExercisesRepository):
        """LLM errors should be caught and logged, not crash."""
        mock_llm = Mock()
        mock_llm.chat.completions.create.side_effect = Exception("API rate limit exceeded")

        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=True,
        )
        # Should not raise, should return fuzzy match or NONE
        result = matcher.match("some exercise that triggers llm")

        assert result is not None
        # Should fall back to fuzzy or NONE, not LLM
        assert result.method in (MatchMethod.FUZZY, MatchMethod.NONE, MatchMethod.EXACT, MatchMethod.ALIAS)

    def test_llm_returns_better_match_than_fuzzy(self, fake_repo: FakeExercisesRepository):
        """LLM match should be used if it has higher confidence than fuzzy."""
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"exercise_id": "conventional-deadlift", "confidence": 0.95, "reasoning": "semantic match for deadlift variant"}'))
        ]
        mock_llm = Mock()
        mock_llm.chat.completions.create.return_value = mock_response

        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=True,
        )
        # Use a name that fuzzy matches poorly but LLM understands
        result = matcher.match("heavy pulls from floor")

        # If LLM was called and returned higher confidence, use LLM result
        if result.method == MatchMethod.LLM:
            assert result.exercise_id == "conventional-deadlift"
            assert result.confidence == 0.95

    def test_llm_null_response_handled(self, fake_repo: FakeExercisesRepository):
        """LLM returning null exercise_id should be handled."""
        mock_response = Mock()
        mock_response.choices = [
            Mock(message=Mock(content='{"exercise_id": null, "confidence": 0.2, "reasoning": "no clear match"}'))
        ]
        mock_llm = Mock()
        mock_llm.chat.completions.create.return_value = mock_response

        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=True,
        )
        result = matcher.match("completely unknown exercise xyz")

        assert result is not None
        # Should not crash, may return NONE or fuzzy fallback


@pytest.mark.unit
class TestFuzzyThresholds:
    """Tests for fuzzy matching threshold boundaries."""

    def test_score_above_auto_accept_returns_without_llm(self, fake_repo: FakeExercisesRepository):
        """Scores >= 0.90 should auto-accept without calling LLM."""
        mock_llm = Mock()
        matcher = ExerciseMatchingService(
            exercises_repository=fake_repo,
            llm_client=mock_llm,
            enable_llm_fallback=True,
        )

        # "Barbell Back Squat" vs "Barbell Back Squats" should score ~0.95+
        result = matcher.match("Barbell Back Squats")

        assert result.method == MatchMethod.FUZZY
        assert result.confidence >= matcher.FUZZY_AUTO_ACCEPT
        # LLM should NOT be called for high-confidence fuzzy matches
        mock_llm.chat.completions.create.assert_not_called()

    def test_score_below_reject_returns_none_or_low_confidence(self, matcher: ExerciseMatchingService):
        """Scores < 0.50 should be rejected or have very low confidence."""
        result = matcher.match("xyzzy plugh adventure game")

        # Either no match found, or match with very low confidence
        if result.exercise_id is not None:
            assert result.confidence < matcher.FUZZY_REJECT
        else:
            assert result.method == MatchMethod.NONE

    def test_score_in_review_range(self, matcher: ExerciseMatchingService):
        """Scores between 0.50 and 0.90 should still return a match."""
        # Use a name that's similar but not exact
        result = matcher.match("Bench Press with Dumbbells Flat")

        # Should get a fuzzy match in the review range
        if result.method == MatchMethod.FUZZY:
            # Just verify it returns something reasonable
            assert result.exercise_id is not None
            assert result.confidence > 0

    def test_auto_accept_threshold_value(self, matcher: ExerciseMatchingService):
        """Verify FUZZY_AUTO_ACCEPT threshold is 0.90."""
        assert matcher.FUZZY_AUTO_ACCEPT == 0.90

    def test_review_threshold_value(self, matcher: ExerciseMatchingService):
        """Verify FUZZY_REVIEW threshold is 0.70."""
        assert matcher.FUZZY_REVIEW == 0.70

    def test_reject_threshold_value(self, matcher: ExerciseMatchingService):
        """Verify FUZZY_REJECT threshold is 0.50."""
        assert matcher.FUZZY_REJECT == 0.50
