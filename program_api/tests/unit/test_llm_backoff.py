"""
Unit tests for LLM client exponential backoff functionality.

Part of AMA-490: Add exponential backoff for LLM retries

Tests verify that:
- Exponential backoff is applied between retries
- Jitter is added to prevent thundering herd
- Rate limit errors (429) trigger longer backoff
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import RateLimitError, APIConnectionError, APIStatusError

from services.llm.client import OpenAIExerciseSelector
from services.llm.schemas import ExerciseSelectionRequest


def create_rate_limit_error():
    """Create a mock RateLimitError for testing."""
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {"retry-after": "1"}
    mock_request = MagicMock()
    mock_response.request = mock_request
    return RateLimitError(
        message="Rate limit exceeded",
        response=mock_response,
        body={"error": {"message": "Rate limit exceeded"}},
    )


def create_api_status_error(status_code: int = 500):
    """Create a mock APIStatusError for testing server errors."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_request = MagicMock()
    mock_response.request = mock_request
    return APIStatusError(
        message=f"Server error {status_code}",
        response=mock_response,
        body={"error": {"message": f"Server error {status_code}"}},
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
    """Base request for testing."""
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
# Backoff Configuration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackoffConfiguration:
    """Tests for backoff configuration constants."""

    def test_base_backoff_is_1_second(self):
        """BASE_BACKOFF_SECONDS should be 1.0 for standard retries."""
        assert OpenAIExerciseSelector.BASE_BACKOFF_SECONDS == 1.0

    def test_rate_limit_backoff_is_5_seconds(self):
        """RATE_LIMIT_BACKOFF_SECONDS should be 5.0 for rate limit errors."""
        assert OpenAIExerciseSelector.RATE_LIMIT_BACKOFF_SECONDS == 5.0

    def test_max_retries_is_2(self):
        """MAX_RETRIES should be 2."""
        assert OpenAIExerciseSelector.MAX_RETRIES == 2


# ---------------------------------------------------------------------------
# Backoff Calculation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackoffCalculation:
    """Tests for the _calculate_backoff method."""

    def test_first_attempt_base_delay(self, selector):
        """First attempt (0) should have base delay + jitter."""
        with patch("services.llm.client.random.uniform", return_value=0.5):
            delay = selector._calculate_backoff(attempt=0, base_delay=1.0)
            # 2^0 * 1.0 + 0.5 = 1.5
            assert delay == 1.5

    def test_second_attempt_doubles_delay(self, selector):
        """Second attempt (1) should double the delay."""
        with patch("services.llm.client.random.uniform", return_value=0.5):
            delay = selector._calculate_backoff(attempt=1, base_delay=1.0)
            # 2^1 * 1.0 + 0.5 = 2.5
            assert delay == 2.5

    def test_third_attempt_quadruples_delay(self, selector):
        """Third attempt (2) should quadruple the delay."""
        with patch("services.llm.client.random.uniform", return_value=0.5):
            delay = selector._calculate_backoff(attempt=2, base_delay=1.0)
            # 2^2 * 1.0 + 0.5 = 4.5
            assert delay == 4.5

    def test_rate_limit_backoff_uses_higher_base(self, selector):
        """Rate limit backoff should use higher base delay."""
        with patch("services.llm.client.random.uniform", return_value=0.0):
            normal_delay = selector._calculate_backoff(
                attempt=0, base_delay=selector.BASE_BACKOFF_SECONDS
            )
            rate_limit_delay = selector._calculate_backoff(
                attempt=0, base_delay=selector.RATE_LIMIT_BACKOFF_SECONDS
            )
            # Rate limit should have 5x the base delay
            assert rate_limit_delay == 5 * normal_delay

    def test_jitter_is_between_0_and_1(self, selector):
        """Jitter should add random value between 0 and 1."""
        delays = []
        for _ in range(100):
            delay = selector._calculate_backoff(attempt=0, base_delay=1.0)
            delays.append(delay)

        # Base delay for attempt 0 is 2^0 * 1.0 = 1.0
        # With jitter, delay should be between 1.0 and 2.0
        assert all(1.0 <= d <= 2.0 for d in delays)

    def test_jitter_varies_between_calls(self, selector):
        """Jitter should vary between calls (not deterministic)."""
        delays = set()
        for _ in range(10):
            delay = selector._calculate_backoff(attempt=0, base_delay=1.0)
            delays.add(delay)

        # With 10 calls, we should have multiple unique values due to jitter
        # (probability of all 10 being identical is essentially 0)
        assert len(delays) > 1


# ---------------------------------------------------------------------------
# Retry Backoff Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRetryBackoff:
    """Tests for retry backoff behavior in select_exercises."""

    @pytest.mark.asyncio
    async def test_backoff_applied_between_retries(
        self, selector, base_request
    ):
        """Backoff should be applied between retry attempts."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # Fail twice, then succeed
            mock_call_llm.side_effect = [
                Exception("Error 1"),
                Exception("Error 2"),
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should have slept twice (after first and second failures)
            assert len(sleep_calls) == 2
            # First backoff: 2^0 * 1.0 + 0.5 = 1.5
            assert sleep_calls[0] == 1.5
            # Second backoff: 2^1 * 1.0 + 0.5 = 2.5
            assert sleep_calls[1] == 2.5

    @pytest.mark.asyncio
    async def test_no_backoff_after_final_attempt(
        self, selector, base_request
    ):
        """No backoff should be applied after the final attempt."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # Fail all attempts
            mock_call_llm.side_effect = [
                Exception("Error 1"),
                Exception("Error 2"),
                Exception("Error 3"),
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                # Should use fallback after all retries fail
                response = await selector.select_exercises(
                    base_request, use_cache=False
                )

            # Only 2 sleeps (between attempts 0-1 and 1-2, not after final)
            assert len(sleep_calls) == 2
            # Should have fallen back
            assert "Fallback" in response.workout_notes

    @pytest.mark.asyncio
    async def test_no_backoff_on_success(self, selector, base_request):
        """No backoff should be applied when first attempt succeeds."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.return_value = (
                '{"exercises": [], "workout_notes": "Success", '
                '"estimated_duration_minutes": 45}'
            )

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                await selector.select_exercises(base_request, use_cache=False)

            # Should not have slept at all
            assert len(sleep_calls) == 0


# ---------------------------------------------------------------------------
# Rate Limit Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRateLimitHandling:
    """Tests for rate limit error (429) handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_triggers_longer_backoff(
        self, selector, base_request
    ):
        """Rate limit errors should trigger longer backoff delay."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        rate_limit_error = create_rate_limit_error()

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # First call hits rate limit, second succeeds
            mock_call_llm.side_effect = [
                rate_limit_error,
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should have slept once with rate limit backoff
            assert len(sleep_calls) == 1
            # Rate limit backoff: 2^0 * 5.0 + 0.5 = 5.5
            assert sleep_calls[0] == 5.5

    @pytest.mark.asyncio
    async def test_rate_limit_backoff_exponential(
        self, selector, base_request
    ):
        """Rate limit backoff should also be exponential."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        rate_limit_error = create_rate_limit_error()

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # Two rate limit errors, then success
            mock_call_llm.side_effect = [
                rate_limit_error,
                rate_limit_error,
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should have slept twice
            assert len(sleep_calls) == 2
            # First rate limit backoff: 2^0 * 5.0 + 0.5 = 5.5
            assert sleep_calls[0] == 5.5
            # Second rate limit backoff: 2^1 * 5.0 + 0.5 = 10.5
            assert sleep_calls[1] == 10.5

    @pytest.mark.asyncio
    async def test_rate_limit_falls_back_after_max_retries(
        self, selector, base_request
    ):
        """Rate limit errors should fall back after max retries."""
        rate_limit_error = create_rate_limit_error()

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # All attempts hit rate limit
            mock_call_llm.side_effect = [
                rate_limit_error,
                rate_limit_error,
                rate_limit_error,
            ]

            with patch("services.llm.client.asyncio.sleep", new_callable=AsyncMock):
                response = await selector.select_exercises(
                    base_request, use_cache=False
                )

            # Should have fallen back
            assert "Fallback" in response.workout_notes

    @pytest.mark.asyncio
    async def test_mixed_errors_use_appropriate_backoff(
        self, selector, base_request
    ):
        """Mixed error types should use appropriate backoff delays."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        rate_limit_error = create_rate_limit_error()

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # First call: regular error, second: rate limit, third: success
            mock_call_llm.side_effect = [
                Exception("Network error"),
                rate_limit_error,
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should have slept twice with different backoff types
            assert len(sleep_calls) == 2
            # First: regular backoff for network error: 2^0 * 1.0 + 0.5 = 1.5
            assert sleep_calls[0] == 1.5
            # Second: rate limit backoff: 2^1 * 5.0 + 0.5 = 10.5
            assert sleep_calls[1] == 10.5


# ---------------------------------------------------------------------------
# JSON Parse Error Backoff Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestJsonParseErrorBackoff:
    """Tests for JSON parse error backoff behavior."""

    @pytest.mark.asyncio
    async def test_json_error_triggers_standard_backoff(
        self, selector, base_request
    ):
        """JSON parse errors should trigger standard backoff."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            # Return invalid JSON, then valid
            mock_call_llm.side_effect = [
                "not valid json",
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should have slept once with standard backoff
            assert len(sleep_calls) == 1
            # Standard backoff: 2^0 * 1.0 + 0.5 = 1.5
            assert sleep_calls[0] == 1.5


# ---------------------------------------------------------------------------
# Server Error Handling Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestServerErrorHandling:
    """Tests for server error (500, 503) handling."""

    @pytest.mark.asyncio
    async def test_server_500_error_triggers_standard_backoff(
        self, selector, base_request
    ):
        """Server 500 errors should trigger standard backoff (not rate limit)."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        server_error = create_api_status_error(500)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.side_effect = [
                server_error,
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            # Should use standard backoff, not rate limit backoff
            assert len(sleep_calls) == 1
            # Standard backoff: 2^0 * 1.0 + 0.5 = 1.5
            assert sleep_calls[0] == 1.5

    @pytest.mark.asyncio
    async def test_server_503_error_triggers_standard_backoff(
        self, selector, base_request
    ):
        """Server 503 errors should trigger standard backoff."""
        sleep_calls = []

        async def mock_sleep(delay):
            sleep_calls.append(delay)

        server_error = create_api_status_error(503)

        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.side_effect = [
                server_error,
                '{"exercises": [], "workout_notes": "Test", "estimated_duration_minutes": 45}',
            ]

            with patch("services.llm.client.asyncio.sleep", side_effect=mock_sleep):
                with patch("services.llm.client.random.uniform", return_value=0.5):
                    await selector.select_exercises(base_request, use_cache=False)

            assert len(sleep_calls) == 1
            assert sleep_calls[0] == 1.5


# ---------------------------------------------------------------------------
# Edge Cases and Boundary Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackoffEdgeCases:
    """Edge case tests for backoff behavior."""

    def test_zero_base_delay_only_returns_jitter(self, selector):
        """Zero base delay should only return jitter component."""
        with patch("services.llm.client.random.uniform", return_value=0.75):
            delay = selector._calculate_backoff(attempt=0, base_delay=0.0)
            # 2^0 * 0.0 + 0.75 = 0.75
            assert delay == 0.75

    def test_high_attempt_number_exponential_growth(self, selector):
        """High attempt numbers should still calculate correctly."""
        with patch("services.llm.client.random.uniform", return_value=0.0):
            delay = selector._calculate_backoff(attempt=5, base_delay=1.0)
            # 2^5 * 1.0 + 0.0 = 32.0
            assert delay == 32.0

    @pytest.mark.asyncio
    async def test_all_retries_exhausted_returns_fallback(
        self, selector, base_request
    ):
        """Exhausting all retries should return fallback, not raise."""
        with patch.object(
            selector, "_call_llm", new_callable=AsyncMock
        ) as mock_call_llm:
            mock_call_llm.side_effect = Exception("Persistent failure")

            with patch("services.llm.client.asyncio.sleep", new_callable=AsyncMock):
                response = await selector.select_exercises(
                    base_request, use_cache=False
                )

            # Should return fallback response, not raise
            assert response is not None
            assert "Fallback" in response.workout_notes
            # Should have tried MAX_RETRIES + 1 times
            assert mock_call_llm.call_count == 3
