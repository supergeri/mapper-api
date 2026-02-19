"""Retry utilities for AI API calls with exponential backoff."""
import logging
from typing import Any, Callable, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)


logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default retry configuration
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MIN_WAIT_SECONDS = 1
DEFAULT_MAX_WAIT_SECONDS = 10


# Exception types for more robust error classification
class RateLimitError(Exception):
    """Rate limit exceeded error."""
    pass


class ServerError(Exception):
    """Server error (5xx)."""
    pass


class TimeoutError(Exception):
    """Timeout error."""
    pass


class ConnectionError(Exception):
    """Connection error."""
    pass


class AuthenticationError(Exception):
    """Authentication error."""
    pass


class BadRequestError(Exception):
    """Bad request error."""
    pass


def is_retryable_error(exception: BaseException) -> bool:
    """
    Determine if an exception is retryable.

    Uses both exception type checking and string matching for robustness.
    This approach handles cases where:
    - Exception types are properly set by the library
    - Exception messages contain relevant error information

    Retryable errors include:
    - Rate limit errors (429)
    - Server errors (5xx)
    - Timeout errors
    - Connection errors

    Non-retryable errors include:
    - Authentication errors (401)
    - Bad request errors (400)
    - Not found errors (404)
    - Insufficient quota errors
    """
    # Check exception type first (more reliable)
    exception_type = type(exception)

    # Check for retryable exception types
    if issubclass(exception_type, (RateLimitError, ServerError, TimeoutError, ConnectionError)):
        return True

    # Check for non-retryable exception types
    if issubclass(exception_type, (AuthenticationError, BadRequestError)):
        return False

    # Fall back to string matching for libraries that don't use proper exception types
    error_str = str(exception).lower()
    exception_type_str = exception_type.__name__.lower()

    # Check for rate limit (429) - always retry
    if "rate" in error_str and "limit" in error_str:
        return True
    if "429" in error_str:
        return True

    # Check for server errors (5xx) - retry
    if any(code in error_str for code in ["500", "502", "503", "504"]):
        return True

    # Check for timeout errors - retry
    if "timeout" in error_str or "timed out" in error_str:
        return True
    if "timeout" in exception_type_str:
        return True

    # Check for connection errors - retry
    if "connection" in error_str or "connect" in exception_type_str:
        return True

    # Check for DNS resolution failures - retry (transient network issue)
    if "name or service not known" in error_str:
        return True
    if "nodename nor servname provided" in error_str:
        return True
    if "getaddrinfo failed" in error_str:
        return True
    if "dns" in error_str and ("failed" in error_str or "error" in error_str):
        return True
    if "temporary failure in name resolution" in error_str:
        return True

    # Check for non-retryable errors
    if any(code in error_str for code in ["400", "401", "403", "404"]):
        return False
    if "authentication" in error_str or "unauthorized" in error_str:
        return False
    if "invalid" in error_str and "key" in error_str:
        return False
    if "quota" in error_str and "exceeded" in error_str:
        return False

    # Default: don't retry unknown errors
    return False


def _validate_retry_params(
    max_attempts: int,
    min_wait_seconds: float,
    max_wait_seconds: float,
) -> None:
    """
    Validate retry parameters.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait_seconds: Minimum wait time between retries
        max_wait_seconds: Maximum wait time between retries

    Raises:
        ValueError: If any parameter is invalid
    """
    if max_attempts < 1:
        raise ValueError(
            f"max_attempts must be >= 1, got {max_attempts}. "
            "If max_attempts <= 0, the retry loop will never execute."
        )
    if min_wait_seconds <= 0:
        raise ValueError(
            f"min_wait_seconds must be positive, got {min_wait_seconds}"
        )
    if max_wait_seconds <= 0:
        raise ValueError(
            f"max_wait_seconds must be positive, got {max_wait_seconds}"
        )
    if min_wait_seconds > max_wait_seconds:
        raise ValueError(
            f"min_wait_seconds ({min_wait_seconds}) cannot exceed "
            f"max_wait_seconds ({max_wait_seconds})"
        )


def create_retry_decorator(
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait_seconds: float = DEFAULT_MIN_WAIT_SECONDS,
    max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Create a retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait_seconds: Minimum wait time between retries
        max_wait_seconds: Maximum wait time between retries

    Returns:
        A retry decorator configured with the specified parameters

    Raises:
        ValueError: If parameters are invalid
    """
    _validate_retry_params(max_attempts, min_wait_seconds, max_wait_seconds)

    return retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=1,
            min=min_wait_seconds,
            max=max_wait_seconds,
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# Pre-configured retry decorator for AI API calls
ai_retry = create_retry_decorator()


async def retry_async_call(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait_seconds: float = DEFAULT_MIN_WAIT_SECONDS,
    max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    **kwargs: Any,
) -> T:
    """
    Execute an async function with retry logic.

    Args:
        func: Async function to execute
        *args: Positional arguments for the function
        max_attempts: Maximum number of retry attempts
        min_wait_seconds: Minimum wait time between retries
        max_wait_seconds: Maximum wait time between retries
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        RetryError: If all retry attempts fail
        ValueError: If parameters are invalid
    """
    import asyncio

    _validate_retry_params(max_attempts, min_wait_seconds, max_wait_seconds)

    last_exception: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error encountered: {e}")
                raise

            if attempt < max_attempts:
                wait_time = min(
                    min_wait_seconds * (2 ** (attempt - 1)),
                    max_wait_seconds,
                )
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_attempts} attempts failed. Last error: {e}")

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state: no result and no exception")


def retry_sync_call(
    func: Callable[..., T],
    *args: Any,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    min_wait_seconds: float = DEFAULT_MIN_WAIT_SECONDS,
    max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    **kwargs: Any,
) -> T:
    """
    Execute a sync function with retry logic.

    Args:
        func: Sync function to execute
        *args: Positional arguments for the function
        max_attempts: Maximum number of retry attempts
        min_wait_seconds: Minimum wait time between retries
        max_wait_seconds: Maximum wait time between retries
        **kwargs: Keyword arguments for the function

    Returns:
        Result of the function call

    Raises:
        Exception: If all retry attempts fail
        ValueError: If parameters are invalid
    """
    import time

    _validate_retry_params(max_attempts, min_wait_seconds, max_wait_seconds)

    last_exception: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e

            if not is_retryable_error(e):
                logger.warning(f"Non-retryable error encountered: {e}")
                raise

            if attempt < max_attempts:
                wait_time = min(
                    min_wait_seconds * (2 ** (attempt - 1)),
                    max_wait_seconds,
                )
                logger.warning(
                    f"Attempt {attempt}/{max_attempts} failed: {e}. "
                    f"Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_attempts} attempts failed. Last error: {e}")

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state: no result and no exception")
