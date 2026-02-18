"""Tests for AIClientFactory and AIRequestContext (AMA-422)."""
import pytest
from unittest.mock import patch, MagicMock


class TestAIRequestContext:
    """Tests for AIRequestContext dataclass."""

    @patch("backend.ai.client_factory.get_settings")
    def test_empty_context(self, mock_get_settings):
        """Test context with no fields set."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext()
        headers = context.to_tracking_headers()

        # Should have environment header
        assert "Helicone-Property-Environment" in headers

    @patch("backend.ai.client_factory.get_settings")
    def test_context_with_user_id(self, mock_get_settings):
        """Test context with user_id."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext(user_id="user123")
        headers = context.to_tracking_headers()

        assert headers["Helicone-User-Id"] == "user123"

    @patch("backend.ai.client_factory.get_settings")
    def test_context_with_session_id(self, mock_get_settings):
        """Test context with session_id."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext(session_id="session456")
        headers = context.to_tracking_headers()

        assert headers["Helicone-Session-Id"] == "session456"

    @patch("backend.ai.client_factory.get_settings")
    def test_context_with_feature_name(self, mock_get_settings):
        """Test context with feature_name."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext(feature_name="exercise_selection")
        headers = context.to_tracking_headers()

        assert headers["Helicone-Property-Feature"] == "exercise_selection"

    @patch("backend.ai.client_factory.get_settings")
    def test_context_with_custom_properties(self, mock_get_settings):
        """Test context with custom properties."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext(
            custom_properties={"model": "gpt-4o-mini", "embedding_type": "text"}
        )
        headers = context.to_tracking_headers()

        assert headers["Helicone-Property-Model"] == "gpt-4o-mini"
        assert headers["Helicone-Property-Embedding-Type"] == "text"

    @patch("backend.ai.client_factory.get_settings")
    def test_full_context(self, mock_get_settings):
        """Test context with all fields."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        context = AIRequestContext(
            user_id="user123",
            session_id="session456",
            feature_name="test_feature",
            request_id="req789",
            custom_properties={"key": "value"},
        )
        headers = context.to_tracking_headers()

        assert headers["Helicone-User-Id"] == "user123"
        assert headers["Helicone-Session-Id"] == "session456"
        assert headers["Helicone-Property-Feature"] == "test_feature"
        assert headers["Helicone-Request-Id"] == "req789"
        assert headers["Helicone-Property-Key"] == "value"


class TestRetryUtilities:
    """Tests for retry utilities."""

    def test_is_retryable_error_rate_limit(self):
        """Test that rate limit errors are retryable."""
        from backend.ai.retry import is_retryable_error

        assert is_retryable_error(Exception("rate limit exceeded"))
        assert is_retryable_error(Exception("429 Too Many Requests"))

    def test_is_retryable_error_server_error(self):
        """Test that server errors are retryable."""
        from backend.ai.retry import is_retryable_error

        assert is_retryable_error(Exception("500 Internal Server Error"))
        assert is_retryable_error(Exception("502 Bad Gateway"))
        assert is_retryable_error(Exception("503 Service Unavailable"))

    def test_is_retryable_error_timeout(self):
        """Test that timeout errors are retryable."""
        from backend.ai.retry import is_retryable_error

        assert is_retryable_error(Exception("Request timed out"))
        assert is_retryable_error(Exception("timeout"))

    def test_is_not_retryable_auth_error(self):
        """Test that auth errors are not retryable."""
        from backend.ai.retry import is_retryable_error

        assert not is_retryable_error(Exception("401 Unauthorized"))

    def test_is_not_retryable_bad_request(self):
        """Test that bad request errors are not retryable."""
        from backend.ai.retry import is_retryable_error

        assert not is_retryable_error(Exception("400 Bad Request"))
        assert not is_retryable_error(Exception("404 Not Found"))
