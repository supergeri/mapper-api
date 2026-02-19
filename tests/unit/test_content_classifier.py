"""
Unit tests for ContentClassifier service (AMA-171)

Tests the keyword-based pre-filter and LLM classification fallback.
"""

import pytest
from unittest.mock import patch, AsyncMock

from backend.services.content_classifier import (
    ContentClassifier,
    ContentCategory,
    ClassificationConfidence,
    clear_classification_cache,
)


# Test settings override to avoid requiring real settings
class TestSettings:
    openai_api_key = None  # No API key for tests
    content_classifier_model = "gpt-4o-mini"
    content_classifier_cache_ttl = 86400


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear classification cache before each test."""
    clear_classification_cache()
    yield
    clear_classification_cache()


class TestKeywordFilter:
    """Tests for the keyword-based pre-filter."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance with test settings."""
        return ContentClassifier(settings=TestSettings())

    def test_workout_keywords_high_confidence(self, classifier):
        """Test that workout keywords result in high confidence workout classification."""
        title = "30 Minute Full Body HIIT Workout | No Equipment"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.WORKOUT
        assert confidence == ClassificationConfidence.HIGH
        assert len(keywords) > 0
        assert "workout" in keywords

    def test_non_workout_keywords_high_confidence(self, classifier):
        """Test that non-workout keywords result in high confidence non-workout classification."""
        title = "Taylor Swift - Anti-Hero (Official Music Video)"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        assert confidence == ClassificationConfidence.HIGH
        assert len(keywords) > 0
        assert "music video" in [k.lower() for k in keywords]

    def test_gaming_content_rejected(self, classifier):
        """Test that gaming content is rejected."""
        title = "Minecraft Let's Play - Episode 1"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_vlog_content_rejected(self, classifier):
        """Test that vlog content is rejected."""
        title = "Day in My Life: My Morning Routine"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        # "routine" is also a workout keyword, so confidence is medium due to mixed signals
        assert confidence in [ClassificationConfidence.HIGH, ClassificationConfidence.MEDIUM]

    def test_cooking_content_rejected(self, classifier):
        """Test that cooking content is rejected."""
        title = "How to Make Perfect Pasta - Italian Recipe"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_news_content_rejected(self, classifier):
        """Test that news content is rejected."""
        title = "Breaking News: Latest Updates"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_yoga_workout_accepted(self, classifier):
        """Test that yoga content is accepted."""
        title = "Morning Yoga Flow - 20 Minutes for Beginners"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_strength_training_accepted(self, classifier):
        """Test that strength training content is accepted."""
        title = "Full Body Strength Training with Dumbbells"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_no_keywords_uncertain(self, classifier):
        """Test that content with no keywords returns uncertain."""
        title = "Random Video Title 12345"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.UNCERTAIN
        assert confidence == ClassificationConfidence.LOW
        assert len(keywords) == 0

    def test_mixed_keywords_favors_workout(self, classifier):
        """Test that when keywords are mixed, workout keywords win if more."""
        # Add more workout keywords to description
        title = "Music Video"
        description = "workout exercise fitness training cardio strength yoga"

        category, confidence, keywords, reason = classifier._keyword_filter(title, description)

        # Should be workout because more workout keywords
        assert category == ContentCategory.WORKOUT

    def test_description_used_for_classification(self, classifier):
        """Test that description is used for classification when title is ambiguous."""
        title = "Video"
        description = "Follow along with this 30 minute HIIT cardio session"

        category, confidence, keywords, reason = classifier._keyword_filter(title, description)

        assert category == ContentCategory.WORKOUT
        assert confidence == ClassificationConfidence.HIGH


class TestClassificationFlow:
    """Tests for the full classification flow with caching."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance with test settings."""
        return ContentClassifier(settings=TestSettings())

    @pytest.mark.asyncio
    async def test_classify_uses_cache(self, classifier):
        """Test that classification uses cache when available."""
        video_id = "test123"

        # First classification
        result1 = await classifier.classify(
            video_id=video_id,
            platform="youtube",
            title="HIIT Workout"
        )

        assert result1.category == ContentCategory.WORKOUT
        assert result1.cached == False

        # Second classification should use cache
        result2 = await classifier.classify(
            video_id=video_id,
            platform="youtube",
            title="Different Title"  # Different title, but should still use cache
        )

        assert result2.cached == True
        assert result2.category == result1.category

    @pytest.mark.asyncio
    async def test_different_video_ids_not_cached(self, classifier):
        """Test that different video IDs have separate cache entries."""
        # First video
        result1 = await classifier.classify(
            video_id="video1",
            platform="youtube",
            title="HIIT Workout"
        )

        # Different video ID
        result2 = await classifier.classify(
            video_id="video2",
            platform="youtube",
            title="HIIT Workout"
        )

        assert result1.cached == False
        assert result2.cached == False


class TestContentClassifierEdgeCases:
    """Tests for edge cases in content classification."""

    @pytest.fixture
    def classifier(self):
        """Create classifier instance with test settings."""
        return ContentClassifier(settings=TestSettings())

    def test_empty_title_and_description(self, classifier):
        """Test classification with empty title and description."""
        category, confidence, keywords, reason = classifier._keyword_filter(None, None)

        assert category == ContentCategory.UNCERTAIN
        assert confidence == ClassificationConfidence.LOW

    def test_case_insensitive_keywords(self, classifier):
        """Test that keywords are matched case-insensitively."""
        title = "MORNING YOGA FLOW - 20 MINUTES"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.WORKOUT
        assert confidence == ClassificationConfidence.HIGH

    def test_partial_word_matching(self, classifier):
        """Test that partial words are not matched (word boundary)."""
        # "arm" should not match "farm" or "alarm"
        title = "Farm equipment review"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        assert category == ContentCategory.NON_WORKOUT
        # Should not match "arms" keyword from workout keywords

    def test_workout_with_music_keyword(self, classifier):
        """Test that workout videos with 'music' in title are still classified as workout."""
        # Music in context of workout (workout with music) should not trigger non-workout
        title = "Workout Music - Best Hip Hop for Exercise"

        category, confidence, keywords, reason = classifier._keyword_filter(title, None)

        # This tests the logic - "workout" keyword should outweigh "music"
        assert category == ContentCategory.WORKOUT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
