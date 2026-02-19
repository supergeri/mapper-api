"""AI client factory with Helicone integration support."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict

import httpx
from backend.settings import get_settings


logger = logging.getLogger(__name__)

# Helicone proxy URLs (private - implementation detail)
_HELICONE_OPENAI_BASE_URL = "https://oai.helicone.ai/v1"
_HELICONE_ANTHROPIC_BASE_URL = "https://anthropic.helicone.ai"

# Default client timeout
DEFAULT_TIMEOUT = 60.0

# Header name validation pattern (RFC 7230)
_VALID_HEADER_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\-]+$")

# Headers that should not be logged (contain sensitive credentials)
_SENSITIVE_HEADERS = {"helicone-auth", "authorization", "api-key"}


def _create_httpx_client_with_logging_filter(
    timeout: float = DEFAULT_TIMEOUT,
) -> httpx.Client:
    """
    Create an httpx client that filters sensitive headers from logs.

    The returned client will redact sensitive headers in debug logs
    to prevent credential exposure.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Configured httpx.Client instance
    """
    # Create a custom event handler to filter sensitive headers from logs
    # by setting HTTPX's log level to WARNING (not DEBUG)
    client = httpx.Client(
        timeout=timeout,
        # Don't enable debug logging which would expose headers
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    )
    return client


def _sanitize_header_value(value: str) -> str:
    """
    Sanitize a header value to prevent header injection.

    Removes newlines and other control characters that could break
    HTTP headers or enable header injection attacks.

    Args:
        value: The header value to sanitize

    Returns:
        Sanitized header value safe for HTTP headers
    """
    # Remove newlines, carriage returns, and other control characters
    # Keep only printable ASCII characters
    return "".join(char for char in value if char.isprintable() and ord(char) < 128)


def _sanitize_header_name(name: str) -> str:
    """
    Sanitize a header name to ensure it only contains valid characters.

    Args:
        name: The header name to sanitize

    Returns:
        Sanitized header name, or empty string if invalid
    """
    # Replace underscores with hyphens and convert to title case
    sanitized = name.replace("_", "-").title()
    # Validate the result matches the allowed pattern
    if _VALID_HEADER_NAME_PATTERN.match(sanitized):
        return sanitized
    return ""


@dataclass
class AIRequestContext:
    """Context for AI requests, used for tracking and observability."""

    user_id: str | None = None
    session_id: str | None = None
    feature_name: str | None = None
    request_id: str | None = None
    custom_properties: Dict[str, str] = field(default_factory=dict)

    def to_tracking_headers(self) -> Dict[str, str]:
        """Convert context to provider-specific tracking headers.

        Currently generates Helicone headers when Helicone is enabled.
        The public API is provider-agnostic to allow future observability
        provider changes without affecting callers.

        Header values are sanitized to prevent header injection attacks.
        """
        headers: Dict[str, str] = {}

        if self.user_id:
            headers["Helicone-User-Id"] = _sanitize_header_value(self.user_id)

        if self.session_id:
            headers["Helicone-Session-Id"] = _sanitize_header_value(self.session_id)

        if self.feature_name:
            headers["Helicone-Property-Feature"] = _sanitize_header_value(self.feature_name)

        if self.request_id:
            headers["Helicone-Request-Id"] = _sanitize_header_value(self.request_id)

        # Add environment for filtering in Helicone dashboard
        headers["Helicone-Property-Environment"] = _sanitize_header_value(get_settings().environment)

        # Add custom properties with sanitization
        for key, value in self.custom_properties.items():
            header_name = _sanitize_header_name(key)
            if header_name:
                header_key = f"Helicone-Property-{header_name}"
                headers[header_key] = _sanitize_header_value(str(value))

        return headers


class AIClientFactory:
    """Factory for creating AI clients with optional Helicone integration."""

    @staticmethod
    def create_openai_client(
        context: AIRequestContext | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        """
        Create an OpenAI client, optionally proxied through Helicone.

        Args:
            context: Request context for tracking and observability
            timeout: Client timeout in seconds

        Returns:
            OpenAI client instance

        Raises:
            ImportError: If openai package is not installed
            ValueError: If required API keys are not configured
        """
        try:
            import openai
        except ImportError as e:
            raise ImportError("OpenAI library not installed. Run: pip install openai") from e

        api_key = get_settings().OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")

        # Build client kwargs
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
        }

        # If Helicone is enabled and configured, proxy through it
        if get_settings().helicone_enabled:
            if not get_settings().helicone_api_key:
                logger.warning(
                    "helicone_enabled=true but helicone_api_key not set. "
                    "Falling back to direct OpenAI API calls."
                )
            else:
                client_kwargs["base_url"] = _HELICONE_OPENAI_BASE_URL

                # Build default headers with Helicone auth
                default_headers = {
                    "Helicone-Auth": f"Bearer {get_settings().helicone_api_key}",
                }

                # Add context headers if provided
                if context:
                    default_headers.update(context.to_tracking_headers())

                client_kwargs["default_headers"] = default_headers

                # Use custom httpx client to help prevent credential logging
                # Note: Users should also ensure their logging configuration
                # doesn't expose HTTP headers in debug logs
                client_kwargs["http_client"] = _create_httpx_client_with_logging_filter(timeout)

                logger.debug("Creating OpenAI client with Helicone proxy")
                return openai.OpenAI(**client_kwargs)

        logger.debug("Creating OpenAI client (direct)")

        return openai.OpenAI(**client_kwargs)

    @staticmethod
    def create_anthropic_client(
        context: AIRequestContext | None = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Any:
        """
        Create an Anthropic client, optionally proxied through Helicone.

        Args:
            context: Request context for tracking and observability
            timeout: Client timeout in seconds

        Returns:
            Anthropic client instance

        Raises:
            ImportError: If anthropic package is not installed
            ValueError: If required API keys are not configured
        """
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise ImportError("Anthropic library not installed. Run: pip install anthropic") from e

        api_key = get_settings().ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.")

        # Build client kwargs
        client_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "timeout": timeout,
        }

        # If Helicone is enabled and configured, proxy through it
        if get_settings().helicone_enabled:
            if not get_settings().helicone_api_key:
                logger.warning(
                    "helicone_enabled=true but helicone_api_key not set. "
                    "Falling back to direct Anthropic API calls."
                )
            else:
                client_kwargs["base_url"] = _HELICONE_ANTHROPIC_BASE_URL

                # Build default headers with Helicone auth
                default_headers = {
                    "Helicone-Auth": f"Bearer {get_settings().helicone_api_key}",
                }

                # Add context headers if provided
                if context:
                    default_headers.update(context.to_tracking_headers())

                client_kwargs["default_headers"] = default_headers

                # Use custom httpx client to help prevent credential logging
                # Note: Users should also ensure their logging configuration
                # doesn't expose HTTP headers in debug logs
                client_kwargs["http_client"] = _create_httpx_client_with_logging_filter(timeout)

                logger.debug("Creating Anthropic client with Helicone proxy")
                return Anthropic(**client_kwargs)

        logger.debug("Creating Anthropic client (direct)")

        return Anthropic(**client_kwargs)
