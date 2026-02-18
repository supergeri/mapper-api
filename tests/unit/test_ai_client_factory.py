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
    def test_context_with_custom_properties_sanitization(self, mock_get_settings):
        """Test that custom property values are sanitized to prevent header injection."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        # Test with newlines and control characters
        context = AIRequestContext(
            custom_properties={"key": "value\nwith\nnewlines\r\nand\rcarriage"}
        )
        headers = context.to_tracking_headers()

        # Newlines should be removed
        assert "\n" not in headers["Helicone-Property-Key"]
        assert "\r" not in headers["Helicone-Property-Key"]
        assert "valuewithnewlinesandcarriage" == headers["Helicone-Property-Key"]

    @patch("backend.ai.client_factory.get_settings")
    def test_context_header_name_sanitization(self, mock_get_settings):
        """Test that invalid header names are filtered out."""
        from backend.ai import AIRequestContext

        mock_settings = MagicMock()
        mock_settings.environment = "test"
        mock_get_settings.return_value = mock_settings

        # Test with invalid characters in key
        context = AIRequestContext(
            custom_properties={"invalid@key!": "value"}
        )
        headers = context.to_tracking_headers()

        # Invalid keys should be skipped
        assert "Helicone-Property-Invalid@Key!" not in headers

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


class TestAIClientFactory:
    """Tests for AIClientFactory client creation."""

    @patch("backend.ai.client_factory.get_settings")
    def test_create_openai_client_missing_api_key(self, mock_get_settings):
        """Test that missing API key raises ValueError."""
        # Import after patching to avoid import issues
        from unittest.mock import MagicMock
        from backend.ai import AIClientFactory

        mock_settings = MagicMock()
        mock_settings.OPENAI_API_KEY = None
        mock_settings.helicone_enabled = False
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            AIClientFactory.create_openai_client()

    @patch("backend.ai.client_factory.get_settings")
    def test_create_anthropic_client_missing_api_key(self, mock_get_settings):
        """Test that missing API key raises ValueError."""
        from backend.ai import AIClientFactory

        mock_settings = MagicMock()
        mock_settings.ANTHROPIC_API_KEY = None
        mock_settings.helicone_enabled = False
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="Anthropic API key not configured"):
            AIClientFactory.create_anthropic_client()


class TestHeaderSanitization:
    """Tests for header sanitization functions."""

    def test_sanitize_header_value_removes_newlines(self):
        """Test that newlines are removed from header values."""
        from backend.ai.client_factory import _sanitize_header_value

        result = _sanitize_header_value("test\nvalue\r\ntest")
        assert "\n" not in result
        assert "\r" not in result

    def test_sanitize_header_value_removes_control_chars(self):
        """Test that control characters are removed."""
        from backend.ai.client_factory import _sanitize_header_value

        # Control characters (0-31 except tab 9, newline 10, carriage return 13)
        result = _sanitize_header_value("test\x00value\x1ftest")
        assert "\x00" not in result
        assert "\x1f" not in result

    def test_sanitize_header_value_keeps_printable(self):
        """Test that printable ASCII is preserved."""
        from backend.ai.client_factory import _sanitize_header_value

        result = _sanitize_header_value("test-value_123.ABC")
        assert result == "test-value_123.ABC"

    def test_sanitize_header_name_valid(self):
        """Test that valid header names pass through."""
        from backend.ai.client_factory import _sanitize_header_name

        result = _sanitize_header_name("test_key")
        assert result == "Test-Key"

    def test_sanitize_header_name_invalid_chars(self):
        """Test that invalid characters result in empty string."""
        from backend.ai.client_factory import _sanitize_header_name

        result = _sanitize_header_name("invalid@key!")
        assert result == ""


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

    def test_validate_retry_params_valid(self):
        """Test that valid parameters pass validation."""
        from backend.ai.retry import _validate_retry_params

        # Should not raise
        _validate_retry_params(3, 1, 10)
        _validate_retry_params(1, 0.1, 1)

    def test_validate_retry_params_invalid_max_attempts(self):
        """Test that invalid max_attempts raises ValueError."""
        from backend.ai.retry import _validate_retry_params

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            _validate_retry_params(0, 1, 10)

        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            _validate_retry_params(-1, 1, 10)

    def test_validate_retry_params_invalid_wait_times(self):
        """Test that invalid wait times raise ValueError."""
        from backend.ai.retry import _validate_retry_params

        with pytest.raises(ValueError, match="min_wait_seconds must be positive"):
            _validate_retry_params(3, 0, 10)

        with pytest.raises(ValueError, match="max_wait_seconds must be positive"):
            _validate_retry_params(3, 1, 0)

        with pytest.raises(ValueError, match="min_wait_seconds.*cannot exceed"):
            _validate_retry_params(3, 10, 5)
