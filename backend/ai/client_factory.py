"""AI client factory with Helicone integration support."""
import logging
from dataclasses import dataclass, field
from typing import Any

from backend.settings import get_settings


logger = logging.getLogger(__name__)

# Helicone proxy URLs (private - implementation detail)
_HELICONE_OPENAI_BASE_URL = "https://oai.helicone.ai/v1"
_HELICONE_ANTHROPIC_BASE_URL = "https://anthropic.helicone.ai"

# Default client timeout
DEFAULT_TIMEOUT = 60.0


@dataclass
class AIRequestContext:
    """Context for AI requests, used for tracking and observability."""

    user_id: str | None = None
    session_id: str | None = None
    feature_name: str | None = None
    request_id: str | None = None
    custom_properties: dict[str, str] = field(default_factory=dict)

    def to_tracking_headers(self) -> dict[str, str]:
        """Convert context to provider-specific tracking headers.

        Currently generates Helicone headers when Helicone is enabled.
        The public API is provider-agnostic to allow future observability
        provider changes without affecting callers.
        """
        headers: dict[str, str] = {}

        if self.user_id:
            headers["Helicone-User-Id"] = self.user_id

        if self.session_id:
            headers["Helicone-Session-Id"] = self.session_id

        if self.feature_name:
            headers["Helicone-Property-Feature"] = self.feature_name

        if self.request_id:
            headers["Helicone-Request-Id"] = self.request_id

        # Add environment for filtering in Helicone dashboard
        headers["Helicone-Property-Environment"] = get_settings().environment

        # Add custom properties
        for key, value in self.custom_properties.items():
            header_key = f"Helicone-Property-{key.replace('_', '-').title()}"
            headers[header_key] = str(value)

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
        client_kwargs: dict[str, Any] = {
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
        client_kwargs: dict[str, Any] = {
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

                logger.debug("Creating Anthropic client with Helicone proxy")
                return Anthropic(**client_kwargs)

        logger.debug("Creating Anthropic client (direct)")

        return Anthropic(**client_kwargs)
