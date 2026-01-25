"""
OpenAI client wrapper for exercise selection.

Part of AMA-462: Implement ProgramGenerator Service

Provides the OpenAIExerciseSelector class for LLM-powered exercise selection.
"""

import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from openai import AsyncOpenAI

from services.llm.prompts import (
    EXERCISE_SELECTION_SYSTEM_PROMPT,
    build_exercise_selection_prompt,
)
from services.llm.schemas import (
    ExerciseSelection,
    ExerciseSelectionRequest,
    ExerciseSelectionResponse,
)

logger = logging.getLogger(__name__)


class ExerciseSelectorError(Exception):
    """Error during exercise selection."""

    pass


@dataclass
class CacheEntry:
    """Cache entry with TTL support."""

    response: "ExerciseSelectionResponse"
    created_at: float


class OpenAIExerciseSelector:
    """
    OpenAI-powered exercise selector for program generation.

    Uses GPT-4o-mini for cost-effective exercise selection based on
    workout type, muscle groups, equipment, and user parameters.
    """

    # Use gpt-4o-mini for cost efficiency
    DEFAULT_MODEL = "gpt-4o-mini"
    MAX_RETRIES = 2

    # Cache configuration
    CACHE_MAX_SIZE = 100  # Maximum cache entries
    CACHE_TTL_SECONDS = 3600  # 1 hour TTL

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        cache_max_size: int = CACHE_MAX_SIZE,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        """
        Initialize the exercise selector.

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4o-mini)
            cache_max_size: Maximum number of cached responses (default: 100)
            cache_ttl_seconds: Cache TTL in seconds (default: 3600)
        """
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._cache: dict[str, CacheEntry] = {}
        self._cache_max_size = cache_max_size
        self._cache_ttl = cache_ttl_seconds

    def _cache_key(self, request: ExerciseSelectionRequest) -> str:
        """Generate cache key for a request."""
        return f"{request.workout_type}:{','.join(sorted(request.muscle_groups))}:{request.exercise_count}"

    async def select_exercises(
        self,
        request: ExerciseSelectionRequest,
        use_cache: bool = True,
    ) -> ExerciseSelectionResponse:
        """
        Select exercises for a workout using the LLM.

        Args:
            request: Exercise selection request parameters
            use_cache: Whether to use cached responses

        Returns:
            ExerciseSelectionResponse with selected exercises

        Raises:
            ExerciseSelectorError: If selection fails after retries
        """
        # Check cache
        cache_key = self._cache_key(request)
        if use_cache:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                logger.debug(f"Using cached response for {cache_key}")
                return cached

        # Build prompt
        user_prompt = build_exercise_selection_prompt(
            workout_type=request.workout_type,
            muscle_groups=request.muscle_groups,
            equipment=request.equipment,
            exercise_count=request.exercise_count,
            available_exercises=request.available_exercises,
            goal=request.goal,
            experience_level=request.experience_level,
            intensity_percent=request.intensity_percent,
            volume_modifier=request.volume_modifier,
            is_deload=request.is_deload,
            limitations=request.user_limitations,
        )

        # Call LLM with retries
        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = await self._call_llm(user_prompt)
                parsed = self._parse_response(response, request)

                # Cache successful response
                if use_cache:
                    self._add_to_cache(cache_key, parsed)

                return parsed

            except json.JSONDecodeError as e:
                last_error = e
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call error on attempt {attempt + 1}: {e}")

        # All retries failed - use fallback
        logger.error(f"All LLM attempts failed, using fallback selection")
        return self._fallback_selection(request)

    async def _call_llm(self, user_prompt: str) -> str:
        """
        Call the OpenAI API.

        Args:
            user_prompt: The user prompt

        Returns:
            Raw response content

        Raises:
            Exception: On API errors
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": EXERCISE_SELECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            raise ExerciseSelectorError("Empty response from LLM")

        return content

    def _parse_response(
        self,
        raw_response: str,
        request: ExerciseSelectionRequest,
    ) -> ExerciseSelectionResponse:
        """
        Parse and validate LLM response.

        Args:
            raw_response: Raw JSON string from LLM
            request: Original request for validation

        Returns:
            Validated ExerciseSelectionResponse

        Raises:
            json.JSONDecodeError: If JSON is invalid
            ValueError: If validation fails
        """
        data = json.loads(raw_response)

        # Validate exercise IDs are from available list
        available_ids = {ex["id"] for ex in request.available_exercises}
        exercises = []

        for ex_data in data.get("exercises", []):
            ex_id = ex_data.get("exercise_id", "")

            # Skip invalid exercises
            if ex_id not in available_ids:
                logger.warning(f"LLM selected invalid exercise ID: {ex_id}")
                continue

            exercises.append(
                ExerciseSelection(
                    exercise_id=ex_id,
                    exercise_name=ex_data.get("exercise_name", ex_id),
                    sets=ex_data.get("sets", 3),
                    reps=str(ex_data.get("reps", "8-12")),
                    rest_seconds=ex_data.get("rest_seconds", 90),
                    notes=ex_data.get("notes"),
                    order=ex_data.get("order", len(exercises) + 1),
                    superset_group=ex_data.get("superset_group"),
                )
            )

        return ExerciseSelectionResponse(
            exercises=exercises,
            workout_notes=data.get("workout_notes"),
            estimated_duration_minutes=data.get("estimated_duration_minutes", 45),
        )

    def _fallback_selection(
        self,
        request: ExerciseSelectionRequest,
    ) -> ExerciseSelectionResponse:
        """
        Deterministic fallback when LLM fails.

        Selects exercises based on simple heuristics:
        1. Prefer compound exercises
        2. Match muscle groups
        3. Vary rep ranges based on goal

        Args:
            request: Original request

        Returns:
            ExerciseSelectionResponse with fallback selections
        """
        # Sort by category (compounds first), then by name
        sorted_exercises = sorted(
            request.available_exercises,
            key=lambda x: (
                0 if x.get("category") == "compound" else 1,
                x.get("name", ""),
            ),
        )

        # Select up to requested count
        selected = sorted_exercises[: request.exercise_count]

        # Determine rep scheme based on goal
        rep_schemes = {
            "strength": ("3-5", 4, 150),
            "hypertrophy": ("8-12", 4, 90),
            "endurance": ("15-20", 3, 60),
            "weight_loss": ("12-15", 3, 45),
            "general_fitness": ("10-15", 3, 60),
            "sport_specific": ("6-10", 4, 90),
        }

        reps, base_sets, rest = rep_schemes.get(
            request.goal, ("8-12", 3, 60)
        )

        # Apply deload modifier
        sets = base_sets if not request.is_deload else max(2, base_sets - 1)

        exercises = []
        for i, ex in enumerate(selected, 1):
            exercises.append(
                ExerciseSelection(
                    exercise_id=ex["id"],
                    exercise_name=ex.get("name", ex["id"]),
                    sets=sets,
                    reps=reps,
                    rest_seconds=rest,
                    notes=None,
                    order=i,
                    superset_group=None,
                )
            )

        return ExerciseSelectionResponse(
            exercises=exercises,
            workout_notes="Fallback selection due to LLM unavailability",
            estimated_duration_minutes=len(exercises) * 8 + 10,
        )

    def _get_from_cache(self, key: str) -> Optional[ExerciseSelectionResponse]:
        """
        Get a response from cache if valid.

        Args:
            key: Cache key

        Returns:
            Cached response if valid and not expired, None otherwise
        """
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check TTL
        if time.time() - entry.created_at > self._cache_ttl:
            # Entry expired, remove it
            del self._cache[key]
            return None

        return entry.response

    def _add_to_cache(self, key: str, response: ExerciseSelectionResponse) -> None:
        """
        Add a response to cache with size limit enforcement.

        Args:
            key: Cache key
            response: Response to cache
        """
        # Evict oldest entries if cache is full
        if len(self._cache) >= self._cache_max_size:
            self._evict_oldest_entries()

        self._cache[key] = CacheEntry(
            response=response,
            created_at=time.time()
        )

    def _evict_oldest_entries(self) -> None:
        """Evict oldest entries to make room for new ones."""
        if not self._cache:
            return

        # Remove expired entries first
        current_time = time.time()
        expired_keys = [
            k for k, v in self._cache.items()
            if current_time - v.created_at > self._cache_ttl
        ]
        for key in expired_keys:
            del self._cache[key]

        # If still over limit, remove oldest entries (LRU approximation)
        if len(self._cache) >= self._cache_max_size:
            # Sort by creation time and remove oldest 20%
            entries = sorted(self._cache.items(), key=lambda x: x[1].created_at)
            num_to_remove = max(1, len(entries) // 5)
            for key, _ in entries[:num_to_remove]:
                del self._cache[key]

    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()

    def get_cache_stats(self) -> dict:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache stats
        """
        current_time = time.time()
        valid_entries = sum(
            1 for entry in self._cache.values()
            if current_time - entry.created_at <= self._cache_ttl
        )
        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_entries,
            "max_size": self._cache_max_size,
            "ttl_seconds": self._cache_ttl,
        }
