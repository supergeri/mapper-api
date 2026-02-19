"""
Content Classifier Service (AMA-171)

Hybrid approach to classify video content as workout or non-workout:
1. Keyword pre-filter (free, instant) - skips obvious non-workout content
2. LLM classification on title + description for ambiguous cases
3. Proceed with flag if still uncertain

Cache classification by video ID to avoid re-classifying same URLs.
"""

import asyncio
import re
import hashlib
import logging
import time
from functools import lru_cache
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from enum import Enum

import httpx

from backend.settings import get_settings

logger = logging.getLogger(__name__)


class ContentCategory(str, Enum):
    """Classification categories for video content."""
    WORKOUT = "workout"
    NON_WORKOUT = "non_workout"
    UNCERTAIN = "uncertain"


class ClassificationConfidence(str, Enum):
    """Confidence levels for classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ClassificationResult:
    """Result of content classification."""
    category: ContentCategory
    confidence: ClassificationConfidence
    reason: str
    keywords_matched: List[str] = field(default_factory=list)
    used_llm: bool = False
    cached: bool = False


# Simple in-memory cache with size limit to prevent unbounded growth
MAX_CACHE_SIZE = 1000  # Maximum number of cached entries
_classification_cache: Dict[str, Tuple[ClassificationResult, float]] = {}


class ContentClassifier:
    """
    Hybrid content classifier using keyword filtering + LLM fallback.

    Flow:
    1. Keyword pre-filter - fast, free, catches obvious non-workout content
    2. If uncertain, use LLM to classify based on title + description
    3. Cache results by video ID to avoid re-classification
    """

    # Keywords that indicate NON-workout content
    # These are phrases commonly found in non-workout videos
    NON_WORKOUT_KEYWORDS = [
        # Music/Music Videos
        "music video", "official video", "lyric video", "visualizer",
        "album", "single", "ep", "mixtape", "concert", "live performance",
        "music", "song", "track", "audio", "spotify", "apple music",

        # Entertainment/Movies/TV
        "movie", "film", "trailer", "scene", "episode", "season",
        "netflix", "hulu", "disney", "prime video", "hbo",
        "comedy", "drama", "action", "thriller", "horror",

        # Gaming
        "gaming", "gameplay", "let's play", "walkthrough", "stream",
        "twitch", "minecraft", "fortnite", "cod", "call of duty",

        # Vlogs/Lifestyle (non-workout)
        "vlog", "day in my life", "get ready with me", "haul",
        "travel", "vacation", "wedding", "birthday", "party",
        "cooking", "recipe", "baking", "food", "restaurant",
        "makeup", "beauty", "fashion", "clothing", "outfit",

        # News/Politics
        "news", "politics", "interview", "documentary", "report",
        "breaking", "update", "latest", "announcement",

        # Tutorials/Education (non-fitness)
        "tutorial", "how to", "learn", "course", "class",
        "coding", "programming", "math", "science", "language",

        # Kids/Animation
        "cartoon", "animation", "anime", "kids", "children",
        "toy", "playground", "nursery rhyme",

        # Other non-workout categories
        "unboxing", "review", "vs", "comparison", "challenge",
        "prank", "funny", "compilation", "montage",
    ]

    # Keywords that indicate WORKOUT content
    # These are strong indicators that the content is fitness-related
    WORKOUT_KEYWORDS = [
        # Workout types
        "workout", "exercise", "fitness", "training", "cardio",
        "strength", "hiit", "yoga", "pilates", "stretching",
        "warm up", "warmup", "cool down", "cooldown",

        # Body parts
        "abs", "core", "arms", "legs", "glutes", "back",
        "chest", "shoulders", "biceps", "triceps", "quads",

        # Fitness goals
        "weight loss", "fat burn", "toning", "bulking", "sculpt",
        "muscle", "lose weight", "get fit", "in shape",

        # Equipment
        "dumbbell", "kettlebell", "barbell", "resistance band",
        "pull up", "pull-up", "push up", "push-up", "squat",

        # Programs
        "challenge", "30 day", "60 day", "90 day", "program",
        "routine", "session", "class", "guided",

        # Specific workouts
        "bootcamp", "circuit", "Tabata", "EMOM", "AMRAP",
        "crossfit", "bodyweight", "full body", "upper body", "lower body",
    ]

    def __init__(self, settings: Optional[Any] = None):
        """Initialize the classifier with optional settings override."""
        self._settings = settings or get_settings()
        self._llm_client: Optional[httpx.AsyncClient] = None

        # Compile keyword patterns for efficiency
        self._non_workout_pattern = self._compile_keywords(self.NON_WORKOUT_KEYWORDS)
        self._workout_pattern = self._compile_keywords(self.WORKOUT_KEYWORDS)

    def _compile_keywords(self, keywords: List[str]) -> re.Pattern:
        """Compile keywords into a single case-insensitive regex pattern."""
        escaped = [re.escape(kw) for kw in keywords]
        pattern = r'\b(' + '|'.join(escaped) + r')\b'
        return re.compile(pattern, re.IGNORECASE)

    def _get_cache_key(self, video_id: str, platform: str) -> str:
        """Generate cache key for a video."""
        return f"{platform}:{video_id}"

    def _get_from_cache(self, video_id: str, platform: str) -> Optional[ClassificationResult]:
        """Get cached classification result if still valid."""
        cache_key = self._get_cache_key(video_id, platform)
        if cache_key in _classification_cache:
            result, cached_at = _classification_cache[cache_key]
            ttl = self._settings.content_classifier_cache_ttl
            if time.time() - cached_at < ttl:
                result.cached = True
                return result
            else:
                # Cache expired
                del _classification_cache[cache_key]
        return None

    def _save_to_cache(self, video_id: str, platform: str, result: ClassificationResult) -> None:
        """Save classification result to cache with size limit."""
        cache_key = self._get_cache_key(video_id, platform)

        # If cache is full, remove oldest entries (first 10% of entries)
        if len(_classification_cache) >= MAX_CACHE_SIZE:
            # Sort by timestamp (oldest first) and remove oldest 10%
            sorted_items = sorted(_classification_cache.items(), key=lambda x: x[1][1])
            for key, _ in sorted_items[:MAX_CACHE_SIZE // 10]:
                del _classification_cache[key]
            logger.info(f"Cache full, evicted {MAX_CACHE_SIZE // 10} oldest entries")

        _classification_cache[cache_key] = (result, time.time())

    def _keyword_filter(
        self,
        title: Optional[str],
        description: Optional[str]
    ) -> Tuple[ContentCategory, ClassificationConfidence, List[str], str]:
        """
        Keyword-based pre-filter for content classification.

        Returns:
            Tuple of (category, confidence, matched_keywords, reason)
        """
        text = f"{title or ''} {description or ''}".lower()

        # Check for non-workout keywords
        non_workout_matches = self._non_workout_pattern.findall(text)

        # Check for workout keywords
        workout_matches = self._workout_pattern.findall(text)

        # Decision logic
        if non_workout_matches and not workout_matches:
            # Strong non-workout signal
            return (
                ContentCategory.NON_WORKOUT,
                ClassificationConfidence.HIGH,
                list(set(non_workout_matches)),
                f"Contains non-workout keywords: {', '.join(set(non_workout_matches[:3]))}"
            )

        if workout_matches and not non_workout_matches:
            # Strong workout signal
            return (
                ContentCategory.WORKOUT,
                ClassificationConfidence.HIGH,
                list(set(workout_matches)),
                f"Contains workout keywords: {', '.join(set(workout_matches[:3]))}"
            )

        if workout_matches and non_workout_matches:
            # Mixed signals - more workout keywords = likely workout
            if len(workout_matches) > len(non_workout_matches):
                return (
                    ContentCategory.WORKOUT,
                    ClassificationConfidence.MEDIUM,
                    list(set(workout_matches)),
                    "Contains more workout keywords than non-workout"
                )
            else:
                return (
                    ContentCategory.NON_WORKOUT,
                    ClassificationConfidence.MEDIUM,
                    list(set(non_workout_matches)),
                    "Contains more non-workout keywords than workout"
                )

        # No keywords matched - need LLM
        return (
            ContentCategory.UNCERTAIN,
            ClassificationConfidence.LOW,
            [],
            "No keywords matched - requires LLM classification"
        )

    async def _llm_classify(
        self,
        title: Optional[str],
        description: Optional[str],
        platform: str
    ) -> ClassificationResult:
        """
        Use LLM to classify content when keywords are inconclusive.

        Uses gpt-4o-mini (cheap and fast) via OpenAI API.
        """
        if not self._settings.openai_api_key:
            # No API key - return uncertain with low confidence
            return ClassificationResult(
                category=ContentCategory.UNCERTAIN,
                confidence=ClassificationConfidence.LOW,
                reason="No LLM API key configured - cannot classify",
                used_llm=False
            )

        # Prepare prompt
        prompt = f"""Classify this video content as either "workout" or "non_workout".

Title: {title or 'N/A'}
Description: {description or 'N/A'}
Platform: {platform}

A "workout" video contains exercise, fitness training, yoga, cardio, strength training, etc.
A "non_workout" video is entertainment, music, gaming, cooking, vlogs, news, etc.

Respond with ONLY one word: "workout" or "non_workout"
"""

        try:
            from openai import AsyncOpenAI
            from openai import APIError, RateLimitError, APIConnectionError, APITimeoutError

            client = AsyncOpenAI(api_key=self._settings.openai_api_key)

            response = await client.chat.completions.create(
                model=self._settings.content_classifier_model,
                messages=[
                    {"role": "system", "content": "You are a content classifier. Respond with only 'workout' or 'non_workout'."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10,
                temperature=0,
                timeout=30.0  # Add timeout to prevent hanging requests
            )

            # Validate response format before parsing
            if not response.choices or not response.choices[0].message.content:
                logger.warning("LLM returned empty response")
                return ClassificationResult(
                    category=ContentCategory.UNCERTAIN,
                    confidence=ClassificationConfidence.LOW,
                    reason="LLM returned empty response",
                    used_llm=True
                )

            result = response.choices[0].message.content.strip().lower()

            # Validate response contains expected keywords
            if "workout" not in result and "non_workout" not in result:
                logger.warning(f"LLM returned unexpected response: {result}")
                return ClassificationResult(
                    category=ContentCategory.UNCERTAIN,
                    confidence=ClassificationConfidence.LOW,
                    reason=f"LLM returned unexpected response format: {result}",
                    used_llm=True
                )

            if "workout" in result:
                return ClassificationResult(
                    category=ContentCategory.WORKOUT,
                    confidence=ClassificationConfidence.MEDIUM,
                    reason="LLM classified as workout",
                    used_llm=True
                )
            else:
                return ClassificationResult(
                    category=ContentCategory.NON_WORKOUT,
                    confidence=ClassificationConfidence.MEDIUM,
                    reason="LLM classified as non-workout",
                    used_llm=True
                )

        except (APIError, RateLimitError, APIConnectionError, APITimeoutError, asyncio.TimeoutError, ValueError) as e:
            logger.error(f"LLM classification failed: {e}")
            return ClassificationResult(
                category=ContentCategory.UNCERTAIN,
                confidence=ClassificationConfidence.LOW,
                reason=f"LLM classification failed: {str(e)}",
                used_llm=True
            )

    async def classify(
        self,
        video_id: str,
        platform: str,
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> ClassificationResult:
        """
        Classify video content using hybrid approach.

        Args:
            video_id: Unique identifier for the video
            platform: Platform (youtube, instagram, tiktok)
            title: Video title
            description: Video description

        Returns:
            ClassificationResult with category, confidence, and reason
        """
        # Check cache first
        cached = self._get_from_cache(video_id, platform)
        if cached:
            logger.info(f"Using cached classification for {platform}:{video_id}")
            return cached

        # Step 1: Keyword pre-filter
        category, confidence, keywords, reason = self._keyword_filter(title, description)

        # If high confidence from keywords, return immediately
        if confidence == ClassificationConfidence.HIGH:
            result = ClassificationResult(
                category=category,
                confidence=confidence,
                reason=reason,
                keywords_matched=keywords,
                used_llm=False
            )
            self._save_to_cache(video_id, platform, result)
            return result

        # Step 2: If uncertain or medium confidence, use LLM
        if category == ContentCategory.UNCERTAIN or confidence == ClassificationConfidence.MEDIUM:
            llm_result = await self._llm_classify(title, description, platform)

            # Use LLM result if it's higher confidence
            if llm_result.confidence in [ClassificationConfidence.HIGH, ClassificationConfidence.MEDIUM]:
                result = ClassificationResult(
                    category=llm_result.category,
                    confidence=llm_result.confidence,
                    reason=llm_result.reason,
                    keywords_matched=keywords,
                    used_llm=True
                )
                self._save_to_cache(video_id, platform, result)
                return result

        # Fallback: return keyword-based result
        result = ClassificationResult(
            category=category,
            confidence=confidence,
            reason=reason,
            keywords_matched=keywords,
            used_llm=False
        )
        self._save_to_cache(video_id, platform, result)
        return result


# Module-level instance for convenience
_classifier: Optional[ContentClassifier] = None


def get_classifier() -> ContentClassifier:
    """Get or create the global content classifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = ContentClassifier()
    return _classifier


async def classify_content(
    video_id: str,
    platform: str,
    title: Optional[str] = None,
    description: Optional[str] = None
) -> ClassificationResult:
    """
    Convenience function to classify content.

    Args:
        video_id: Unique identifier for the video
        platform: Platform (youtube, instagram, tiktok)
        title: Video title
        description: Video description

    Returns:
        ClassificationResult with category, confidence, and reason
    """
    classifier = get_classifier()
    return await classifier.classify(video_id, platform, title, description)


def clear_classification_cache() -> None:
    """Clear the classification cache (useful for testing)."""
    global _classification_cache
    _classification_cache.clear()
