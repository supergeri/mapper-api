"""
Integration tests for ContentClassifier LLM fallback.

Part of AMA-171: Detect and reject non-workout video content

Tests LLM classification when keyword filter returns ambiguous results.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.services.content_classifier import (
    ContentClassifier,
    ContentCategory,
    ClassificationConfidence,
)


class TestLLMClassification:
    """Tests for LLM-based content classification."""

    @pytest.mark.unit
    def test_ambiguous_content_needs_llm(self):
        """Ambiguous content should return None from keyword filter (needs LLM)."""
        classifier = ContentClassifier()

        # Test with ambiguous content
        category, confidence, keywords, reason = classifier._keyword_filter(
            title="My Active Lifestyle Journey",
            description="Movement and activities throughout the day",
        )

        # This should be ambiguous and need LLM
        assert category == ContentCategory.UNCERTAIN


class TestEndToEndClassification:
    """End-to-end tests for full classification pipeline."""

    @pytest.mark.integration
    def test_classify_with_clear_workout_keywords(self):
        """Clear workout content should be classified without LLM."""
        classifier = ContentClassifier()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            classifier.classify(
                video_id="test123",
                platform="youtube",
                title="30 Min HIIT Workout - No Equipment",
                description="Full body cardio and strength training",
            )
        )

        assert result.category == ContentCategory.WORKOUT
        assert result.confidence == ClassificationConfidence.HIGH

    @pytest.mark.integration
    def test_classify_with_clear_non_workout_keywords(self):
        """Clear non-workout content should be classified without LLM."""
        classifier = ContentClassifier()

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            classifier.classify(
                video_id="test456",
                platform="youtube",
                title="Taylor Swift Anti-Hero Official Music Video VEVO",
                description="Official music video vevo",
            )
        )

        assert result.category == ContentCategory.NON_WORKOUT
        assert result.confidence == ClassificationConfidence.HIGH
