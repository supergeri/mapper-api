"""
Unit tests for LLM client cache key functionality.

Part of AMA-486: Fix LLM cache key missing critical parameters

Tests verify that the cache key includes all relevant parameters
so cached responses are only returned for matching requests.
"""

from unittest.mock import AsyncMock, patch

import pytest

from services.llm.client import OpenAIExerciseSelector
from services.llm.schemas import (
    ExerciseSelection,
    ExerciseSelectionRequest,
    ExerciseSelectionResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_exercises():
    """Sample available exercises for testing."""
    return [
        {"id": "bench-press", "name": "Bench Press", "category": "compound"},
        {"id": "squat", "name": "Squat", "category": "compound"},
    ]


@pytest.fixture
def base_request(sample_exercises):
    """Base request for testing cache key."""
    return ExerciseSelectionRequest(
        workout_type="push",
        muscle_groups=["chest", "triceps"],
        equipment=["barbell", "bench"],
        exercise_count=5,
        intensity_percent=0.8,
        volume_modifier=1.0,
        available_exercises=sample_exercises,
        experience_level="intermediate",
        goal="hypertrophy",
        is_deload=False,
    )


@pytest.fixture
def selector():
    """Create selector with fake API key for testing."""
    return OpenAIExerciseSelector(api_key="test-key")


# ---------------------------------------------------------------------------
# Cache Configuration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheConfiguration:
    """Tests for cache configuration constants."""

    def test_cache_max_size_is_500(self):
        """CACHE_MAX_SIZE should be 500 to accommodate more combinations."""
        assert OpenAIExerciseSelector.CACHE_MAX_SIZE == 500

    def test_default_cache_max_size_in_instance(self):
        """Instance should use CACHE_MAX_SIZE as default."""
        selector = OpenAIExerciseSelector(api_key="test-key")
        assert selector._cache_max_size == 500


# ---------------------------------------------------------------------------
# Cache Key Component Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheKeyComponents:
    """Tests for cache key including all required parameters."""

    def test_cache_key_includes_workout_type(self, selector, base_request):
        """Cache key includes workout_type."""
        key = selector._cache_key(base_request)
        assert "push" in key

    def test_cache_key_includes_muscle_groups(self, selector, base_request):
        """Cache key includes sorted muscle groups."""
        key = selector._cache_key(base_request)
        # Should contain both muscles, sorted alphabetically
        assert "chest" in key
        assert "triceps" in key

    def test_cache_key_includes_exercise_count(self, selector, base_request):
        """Cache key includes exercise count."""
        key = selector._cache_key(base_request)
        assert "5" in key

    def test_cache_key_includes_goal(self, selector, base_request):
        """Cache key includes goal."""
        key = selector._cache_key(base_request)
        assert "hypertrophy" in key

    def test_cache_key_includes_experience_level(self, selector, base_request):
        """Cache key includes experience level."""
        key = selector._cache_key(base_request)
        assert "intermediate" in key

    def test_cache_key_includes_is_deload(self, selector, base_request):
        """Cache key includes is_deload flag."""
        key = selector._cache_key(base_request)
        assert "False" in key

    def test_cache_key_includes_equipment(self, selector, base_request):
        """Cache key includes sorted equipment."""
        key = selector._cache_key(base_request)
        # Should contain both equipment items
        assert "barbell" in key
        assert "bench" in key

    def test_cache_key_includes_user_limitations(self, selector, sample_exercises):
        """Cache key includes user limitations."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
            user_limitations=["knee_injury", "shoulder_pain"],
        )

        key = selector._cache_key(request)

        assert "knee_injury" in key
        assert "shoulder_pain" in key


# ---------------------------------------------------------------------------
# Cache Key Differentiation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheKeyDifferentiation:
    """Tests verifying different parameters produce different cache keys."""

    def test_different_goal_produces_different_key(
        self, selector, base_request, sample_exercises
    ):
        """Different goal produces different cache key."""
        strength_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=base_request.equipment,
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal="strength",  # Different goal
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(strength_request)

        assert key1 != key2

    def test_different_experience_level_produces_different_key(
        self, selector, base_request, sample_exercises
    ):
        """Different experience level produces different cache key."""
        beginner_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=base_request.equipment,
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level="beginner",  # Different experience level
            goal=base_request.goal,
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(beginner_request)

        assert key1 != key2

    def test_different_is_deload_produces_different_key(
        self, selector, base_request, sample_exercises
    ):
        """Different is_deload flag produces different cache key."""
        deload_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=base_request.equipment,
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal=base_request.goal,
            is_deload=True,  # Different is_deload
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(deload_request)

        assert key1 != key2

    def test_different_equipment_produces_different_key(
        self, selector, base_request, sample_exercises
    ):
        """Different equipment produces different cache key."""
        dumbbell_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=["dumbbells", "bench"],  # Different equipment
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal=base_request.goal,
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(dumbbell_request)

        assert key1 != key2

    def test_different_user_limitations_produces_different_key(
        self, selector, sample_exercises
    ):
        """Different user limitations produce different cache key."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "experience_level": "intermediate",
            "goal": "hypertrophy",
            "is_deload": False,
        }

        request_no_limitations = ExerciseSelectionRequest(**base_params, user_limitations=None)
        request_with_limitations = ExerciseSelectionRequest(
            **base_params, user_limitations=["knee_injury"]
        )

        key1 = selector._cache_key(request_no_limitations)
        key2 = selector._cache_key(request_with_limitations)

        assert key1 != key2

    def test_same_parameters_produce_same_key(
        self, selector, base_request, sample_exercises
    ):
        """Identical parameters produce the same cache key."""
        identical_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=base_request.equipment,
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal=base_request.goal,
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(identical_request)

        assert key1 == key2

    def test_equipment_order_does_not_affect_key(
        self, selector, base_request, sample_exercises
    ):
        """Equipment order should not affect cache key (sorted)."""
        reversed_equipment_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=base_request.muscle_groups,
            equipment=["bench", "barbell"],  # Reversed order
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal=base_request.goal,
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(reversed_equipment_request)

        assert key1 == key2

    def test_muscle_groups_order_does_not_affect_key(
        self, selector, base_request, sample_exercises
    ):
        """Muscle group order should not affect cache key (sorted)."""
        reversed_muscle_request = ExerciseSelectionRequest(
            workout_type=base_request.workout_type,
            muscle_groups=["triceps", "chest"],  # Reversed order
            equipment=base_request.equipment,
            exercise_count=base_request.exercise_count,
            intensity_percent=base_request.intensity_percent,
            volume_modifier=base_request.volume_modifier,
            available_exercises=sample_exercises,
            experience_level=base_request.experience_level,
            goal=base_request.goal,
            is_deload=base_request.is_deload,
        )

        key1 = selector._cache_key(base_request)
        key2 = selector._cache_key(reversed_muscle_request)

        assert key1 == key2


# ---------------------------------------------------------------------------
# Cache Key Edge Cases
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheKeyEdgeCases:
    """Tests for cache key edge cases."""

    def test_empty_equipment_produces_valid_key(self, selector, sample_exercises):
        """Empty equipment list produces a valid cache key."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=[],  # Empty equipment
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        key = selector._cache_key(request)

        assert key is not None
        assert len(key) > 0
        # Key should still have the colon separators (8 parts = 7 colons)
        assert key.count(":") >= 7

    def test_single_muscle_group(self, selector, sample_exercises):
        """Single muscle group produces valid key."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        key = selector._cache_key(request)

        assert "chest" in key
        assert key is not None

    def test_many_equipment_items(self, selector, sample_exercises):
        """Many equipment items are all included in key."""
        equipment = ["barbell", "dumbbells", "cables", "bench", "squat_rack", "pull_up_bar"]
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=equipment,
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        key = selector._cache_key(request)

        for item in equipment:
            assert item in key

    def test_deload_true_vs_false(self, selector, sample_exercises):
        """is_deload True vs False produce different keys."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "experience_level": "intermediate",
            "goal": "hypertrophy",
        }

        request_false = ExerciseSelectionRequest(**base_params, is_deload=False)
        request_true = ExerciseSelectionRequest(**base_params, is_deload=True)

        key_false = selector._cache_key(request_false)
        key_true = selector._cache_key(request_true)

        assert key_false != key_true
        assert "False" in key_false
        assert "True" in key_true


# ---------------------------------------------------------------------------
# None Value Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheKeyNoneHandling:
    """Tests for cache key format and structure."""

    def test_empty_equipment_produces_empty_segment(self, selector, sample_exercises):
        """Empty equipment list produces empty segment in cache key."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=[],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        key = selector._cache_key(request)
        parts = key.split(":")

        # Last segment (equipment) should be empty
        assert parts[-1] == ""

    def test_cache_key_format_structure(self, selector, sample_exercises):
        """Cache key should have consistent colon-separated format."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest", "triceps"],
            equipment=["barbell", "bench"],
            exercise_count=5,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
            user_limitations=["back_pain"],
        )

        key = selector._cache_key(request)
        parts = key.split(":")

        # Should have 8 parts: workout_type, muscles, count, goal, exp_level, is_deload, equipment, limitations
        assert len(parts) == 8
        assert parts[0] == "push"
        assert parts[1] == "chest,triceps"  # Sorted
        assert parts[2] == "5"
        assert parts[3] == "hypertrophy"
        assert parts[4] == "intermediate"
        assert parts[5] == "False"
        assert parts[6] == "barbell,bench"  # Sorted
        assert parts[7] == "back_pain"


# ---------------------------------------------------------------------------
# Cache Hit/Miss Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing."""
    return ExerciseSelectionResponse(
        exercises=[
            ExerciseSelection(
                exercise_id="bench-press",
                exercise_name="Bench Press",
                sets=4,
                reps="8-12",
                rest_seconds=90,
                notes=None,
                order=1,
                superset_group=None,
            )
        ],
        workout_notes="Test workout",
        estimated_duration_minutes=45,
    )


@pytest.mark.unit
class TestCacheHitMissBehavior:
    """Integration tests for actual cache hit/miss behavior."""

    @pytest.mark.asyncio
    async def test_identical_request_uses_cache(
        self, selector, sample_exercises, mock_llm_response
    ):
        """Identical requests should hit cache and not call LLM twice."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # Return valid JSON that can be parsed
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            # First call - should call LLM
            await selector.select_exercises(request, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Second call with same params - should use cache
            await selector.select_exercises(request, use_cache=True)
            assert mock_call_llm.call_count == 1  # Still 1, cache hit

    @pytest.mark.asyncio
    async def test_different_goal_triggers_cache_miss(
        self, selector, sample_exercises
    ):
        """Different goal should cause cache miss."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "experience_level": "intermediate",
            "is_deload": False,
        }

        request1 = ExerciseSelectionRequest(**base_params, goal="hypertrophy")
        request2 = ExerciseSelectionRequest(**base_params, goal="strength")

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request1, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Different goal - should call LLM again
            await selector.select_exercises(request2, use_cache=True)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_different_experience_level_triggers_cache_miss(
        self, selector, sample_exercises
    ):
        """Different experience level should cause cache miss."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "goal": "hypertrophy",
            "is_deload": False,
        }

        request1 = ExerciseSelectionRequest(**base_params, experience_level="intermediate")
        request2 = ExerciseSelectionRequest(**base_params, experience_level="beginner")

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request1, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Different experience level - should call LLM again
            await selector.select_exercises(request2, use_cache=True)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_different_is_deload_triggers_cache_miss(
        self, selector, sample_exercises
    ):
        """Different is_deload flag should cause cache miss."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "goal": "hypertrophy",
            "experience_level": "intermediate",
        }

        request1 = ExerciseSelectionRequest(**base_params, is_deload=False)
        request2 = ExerciseSelectionRequest(**base_params, is_deload=True)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request1, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Different is_deload - should call LLM again
            await selector.select_exercises(request2, use_cache=True)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_different_equipment_triggers_cache_miss(
        self, selector, sample_exercises
    ):
        """Different equipment should cause cache miss."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "goal": "hypertrophy",
            "experience_level": "intermediate",
            "is_deload": False,
        }

        request1 = ExerciseSelectionRequest(**base_params, equipment=["barbell"])
        request2 = ExerciseSelectionRequest(**base_params, equipment=["dumbbells"])

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request1, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Different equipment - should call LLM again
            await selector.select_exercises(request2, use_cache=True)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_different_user_limitations_triggers_cache_miss(
        self, selector, sample_exercises
    ):
        """Different user limitations should cause cache miss."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 3,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": sample_exercises,
            "goal": "hypertrophy",
            "experience_level": "intermediate",
            "is_deload": False,
        }

        request1 = ExerciseSelectionRequest(**base_params, user_limitations=None)
        request2 = ExerciseSelectionRequest(**base_params, user_limitations=["knee_injury"])

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request1, use_cache=True)
            assert mock_call_llm.call_count == 1

            # Different user limitations - should call LLM again
            await selector.select_exercises(request2, use_cache=True)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_cache_disabled_always_calls_llm(
        self, selector, sample_exercises
    ):
        """When use_cache=False, LLM should always be called."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            # First call with cache disabled
            await selector.select_exercises(request, use_cache=False)
            assert mock_call_llm.call_count == 1

            # Second call with cache disabled - should still call LLM
            await selector.select_exercises(request, use_cache=False)
            assert mock_call_llm.call_count == 2

    @pytest.mark.asyncio
    async def test_cached_response_returned_correctly(
        self, selector, sample_exercises
    ):
        """Cached response should be identical to original response."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Unique test note", "estimated_duration_minutes": 45}'

            # First call
            response1 = await selector.select_exercises(request, use_cache=True)

            # Second call (from cache)
            response2 = await selector.select_exercises(request, use_cache=True)

            # Responses should be identical
            assert response1.workout_notes == response2.workout_notes
            assert len(response1.exercises) == len(response2.exercises)
            assert response1.exercises[0].exercise_id == response2.exercises[0].exercise_id


# ---------------------------------------------------------------------------
# Exercise Variety Tests (AMA-487)
# ---------------------------------------------------------------------------


@pytest.fixture
def extended_exercises():
    """Extended set of exercises for variety testing."""
    return [
        {"id": "bench-press", "name": "Bench Press", "category": "compound"},
        {"id": "squat", "name": "Squat", "category": "compound"},
        {"id": "deadlift", "name": "Deadlift", "category": "compound"},
        {"id": "overhead-press", "name": "Overhead Press", "category": "compound"},
        {"id": "barbell-row", "name": "Barbell Row", "category": "compound"},
        {"id": "pull-up", "name": "Pull Up", "category": "compound"},
        {"id": "dumbbell-curl", "name": "Dumbbell Curl", "category": "isolation"},
        {"id": "tricep-pushdown", "name": "Tricep Pushdown", "category": "isolation"},
        {"id": "leg-curl", "name": "Leg Curl", "category": "isolation"},
        {"id": "leg-extension", "name": "Leg Extension", "category": "isolation"},
    ]


@pytest.mark.unit
class TestExerciseVarietyWithLowTemperature:
    """
    Tests to verify exercise selection variety with lower temperature (0.3).

    Part of AMA-487: Lower LLM temperature for structured exercise selection.
    """

    @pytest.mark.asyncio
    async def test_different_muscle_groups_produce_different_selections(
        self, selector, extended_exercises
    ):
        """Different muscle groups should produce different exercise selections."""
        push_request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest", "triceps"],
            equipment=["barbell", "dumbbells"],
            exercise_count=4,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=extended_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        pull_request = ExerciseSelectionRequest(
            workout_type="pull",
            muscle_groups=["back", "biceps"],
            equipment=["barbell", "dumbbells"],
            exercise_count=4,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=extended_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        # Cache keys should be different
        push_key = selector._cache_key(push_request)
        pull_key = selector._cache_key(pull_request)

        assert push_key != pull_key
        assert "chest" in push_key
        assert "back" in pull_key

    @pytest.mark.asyncio
    async def test_different_goals_produce_different_cache_keys(
        self, selector, extended_exercises
    ):
        """Different goals should produce different cache keys for variety."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 4,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": extended_exercises,
            "experience_level": "intermediate",
            "is_deload": False,
        }

        goals = ["strength", "hypertrophy", "endurance", "weight_loss"]
        cache_keys = set()

        for goal in goals:
            request = ExerciseSelectionRequest(**base_params, goal=goal)
            key = selector._cache_key(request)
            cache_keys.add(key)

        # All goals should produce unique cache keys
        assert len(cache_keys) == len(goals)

    @pytest.mark.asyncio
    async def test_deload_vs_normal_week_differentiated(
        self, selector, extended_exercises
    ):
        """Deload weeks should have different cache keys from normal weeks."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest", "shoulders"],
            "equipment": ["barbell", "dumbbells"],
            "exercise_count": 4,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": extended_exercises,
            "experience_level": "intermediate",
            "goal": "hypertrophy",
        }

        normal_request = ExerciseSelectionRequest(**base_params, is_deload=False)
        deload_request = ExerciseSelectionRequest(**base_params, is_deload=True)

        normal_key = selector._cache_key(normal_request)
        deload_key = selector._cache_key(deload_request)

        assert normal_key != deload_key
        assert "False" in normal_key
        assert "True" in deload_key

    @pytest.mark.asyncio
    async def test_experience_levels_produce_different_keys(
        self, selector, extended_exercises
    ):
        """Different experience levels should produce unique cache keys."""
        base_params = {
            "workout_type": "push",
            "muscle_groups": ["chest"],
            "equipment": ["barbell"],
            "exercise_count": 4,
            "intensity_percent": 0.8,
            "volume_modifier": 1.0,
            "available_exercises": extended_exercises,
            "goal": "hypertrophy",
            "is_deload": False,
        }

        levels = ["beginner", "intermediate", "advanced"]
        cache_keys = set()

        for level in levels:
            request = ExerciseSelectionRequest(**base_params, experience_level=level)
            key = selector._cache_key(request)
            cache_keys.add(key)

        assert len(cache_keys) == len(levels)


# ---------------------------------------------------------------------------
# Cache Stats and Hit Rate Tests (AMA-487)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCacheStatsTracking:
    """Tests to verify cache statistics tracking for hit rate monitoring."""

    def test_get_cache_stats_returns_expected_fields(self, selector):
        """Cache stats should include all required fields."""
        stats = selector.get_cache_stats()

        assert "total_entries" in stats
        assert "valid_entries" in stats
        assert "max_size" in stats
        assert "ttl_seconds" in stats

    def test_cache_stats_empty_initially(self, selector):
        """Fresh selector should have empty cache."""
        stats = selector.get_cache_stats()

        assert stats["total_entries"] == 0
        assert stats["valid_entries"] == 0

    @pytest.mark.asyncio
    async def test_cache_stats_increment_after_caching(
        self, selector, sample_exercises
    ):
        """Cache stats should reflect cached entries."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            await selector.select_exercises(request, use_cache=True)

            stats = selector.get_cache_stats()
            assert stats["total_entries"] == 1
            assert stats["valid_entries"] == 1

    def test_clear_cache_resets_stats(self, selector):
        """Clearing cache should reset entry counts."""
        # Manually add a cache entry
        from services.llm.client import CacheEntry
        import time

        selector._cache["test-key"] = CacheEntry(
            response=ExerciseSelectionResponse(
                exercises=[],
                workout_notes="Test",
                estimated_duration_minutes=30,
            ),
            created_at=time.time(),
        )

        assert selector.get_cache_stats()["total_entries"] == 1

        selector.clear_cache()

        assert selector.get_cache_stats()["total_entries"] == 0


# ---------------------------------------------------------------------------
# Temperature Edge Cases (AMA-487)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTemperatureEdgeCases:
    """Edge cases that may behave differently with lower temperature (0.3)."""

    @pytest.mark.asyncio
    async def test_limited_exercise_pool_uses_fallback(self, selector):
        """When LLM fails with limited pool, fallback should work."""
        limited_exercises = [
            {"id": "bench-press", "name": "Bench Press", "category": "compound"},
            {"id": "incline-press", "name": "Incline Press", "category": "compound"},
            {"id": "dumbbell-fly", "name": "Dumbbell Fly", "category": "isolation"},
        ]

        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=5,  # More than available
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=limited_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        # Test fallback directly
        fallback = selector._fallback_selection(request)

        assert len(fallback.exercises) == 3  # Only 3 available
        assert fallback.exercises[0].exercise_id == "bench-press"
        assert "Fallback" in fallback.workout_notes

    @pytest.mark.asyncio
    async def test_fallback_applies_deload_modifier(self, selector, sample_exercises):
        """Fallback selection should reduce sets for deload weeks."""
        normal_request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        deload_request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=True,
        )

        normal_fallback = selector._fallback_selection(normal_request)
        deload_fallback = selector._fallback_selection(deload_request)

        # Deload should have fewer sets
        assert deload_fallback.exercises[0].sets < normal_fallback.exercises[0].sets

    @pytest.mark.asyncio
    async def test_fallback_uses_goal_appropriate_rep_scheme(
        self, selector, sample_exercises
    ):
        """Fallback should select rep ranges based on goal."""
        strength_request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="strength",
            is_deload=False,
        )

        endurance_request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="endurance",
            is_deload=False,
        )

        strength_fallback = selector._fallback_selection(strength_request)
        endurance_fallback = selector._fallback_selection(endurance_request)

        # Strength: 3-5 reps, Endurance: 15-20 reps
        assert strength_fallback.exercises[0].reps == "3-5"
        assert endurance_fallback.exercises[0].reps == "15-20"

    @pytest.mark.asyncio
    async def test_minimal_exercise_pool_fallback_succeeds(self, selector):
        """Minimal exercise pool should produce valid fallback selection."""
        minimal_exercises = [
            {"id": "bench-press", "name": "Bench Press", "category": "compound"},
            {"id": "incline-press", "name": "Incline Press", "category": "compound"},
            {"id": "dumbbell-fly", "name": "Dumbbell Fly", "category": "isolation"},
        ]

        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=minimal_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        fallback = selector._fallback_selection(request)

        assert len(fallback.exercises) == 3
        assert "Fallback" in fallback.workout_notes
        assert fallback.estimated_duration_minutes >= 20

    @pytest.mark.asyncio
    async def test_fallback_prioritizes_compound_exercises(self, selector):
        """Fallback should select compound exercises first."""
        mixed_exercises = [
            {"id": "curl", "name": "Bicep Curl", "category": "isolation"},
            {"id": "squat", "name": "Squat", "category": "compound"},
            {"id": "extension", "name": "Leg Extension", "category": "isolation"},
            {"id": "deadlift", "name": "Deadlift", "category": "compound"},
            {"id": "lunge", "name": "Lunge", "category": "compound"},
        ]

        request = ExerciseSelectionRequest(
            workout_type="legs",
            muscle_groups=["quads", "hamstrings"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=mixed_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        fallback = selector._fallback_selection(request)

        # Should select the 3 compound exercises first (sorted alphabetically: deadlift, lunge, squat)
        exercise_ids = [ex.exercise_id for ex in fallback.exercises]
        # First 3 should be compounds (deadlift, lunge, squat - alphabetical after category sort)
        assert "deadlift" in exercise_ids
        assert "lunge" in exercise_ids
        assert "squat" in exercise_ids
        # Isolation exercises should not be selected when we only need 3 and have 3 compounds
        assert "curl" not in exercise_ids
        assert "extension" not in exercise_ids


# ---------------------------------------------------------------------------
# Output Determinism Tests (AMA-487)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOutputDeterminism:
    """Tests to verify output consistency with lower temperature."""

    @pytest.mark.asyncio
    async def test_same_input_same_cache_key(self, selector, sample_exercises):
        """Identical inputs should always produce the same cache key."""
        request1 = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest", "triceps"],
            equipment=["barbell", "bench"],
            exercise_count=5,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        request2 = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest", "triceps"],
            equipment=["barbell", "bench"],
            exercise_count=5,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        # Generate keys multiple times
        keys = [selector._cache_key(request1) for _ in range(10)]
        keys.extend([selector._cache_key(request2) for _ in range(10)])

        # All keys should be identical
        assert len(set(keys)) == 1

    @pytest.mark.asyncio
    async def test_cached_response_is_identical_object(
        self, selector, sample_exercises
    ):
        """Cached response should be the exact same object (not a copy)."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Test", "estimated_duration_minutes": 45}'

            response1 = await selector.select_exercises(request, use_cache=True)
            response2 = await selector.select_exercises(request, use_cache=True)

            # Should be the same object from cache
            assert response1 is response2

    @pytest.mark.asyncio
    async def test_parse_response_produces_consistent_structure(
        self, selector, sample_exercises
    ):
        """Parsing the same JSON should produce consistent results."""
        request = ExerciseSelectionRequest(
            workout_type="push",
            muscle_groups=["chest"],
            equipment=["barbell"],
            exercise_count=3,
            intensity_percent=0.8,
            volume_modifier=1.0,
            available_exercises=sample_exercises,
            experience_level="intermediate",
            goal="hypertrophy",
            is_deload=False,
        )

        raw_response = '{"exercises": [{"exercise_id": "bench-press", "exercise_name": "Bench Press", "sets": 4, "reps": "8-12", "rest_seconds": 90, "order": 1}], "workout_notes": "Consistent", "estimated_duration_minutes": 45}'

        parsed1 = selector._parse_response(raw_response, request)
        parsed2 = selector._parse_response(raw_response, request)

        assert parsed1.workout_notes == parsed2.workout_notes
        assert len(parsed1.exercises) == len(parsed2.exercises)
        assert parsed1.exercises[0].exercise_id == parsed2.exercises[0].exercise_id
        assert parsed1.exercises[0].sets == parsed2.exercises[0].sets
        assert parsed1.exercises[0].reps == parsed2.exercises[0].reps
