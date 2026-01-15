"""
Unit tests for backend/main.py

Part of AMA-377: Introduce main.py with create_app() factory
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from backend.main import create_app, _init_sentry, _configure_cors, _log_feature_flags
from backend.settings import Settings


@pytest.mark.unit
class TestCreateApp:
    """Test the create_app() factory function."""

    def test_create_app_returns_fastapi_instance(self):
        """create_app() should return a FastAPI application instance."""
        settings = Settings(environment="test", _env_file=None)
        app = create_app(settings=settings)
        assert isinstance(app, FastAPI)

    def test_create_app_uses_default_settings_when_none_provided(self):
        """create_app() should use get_settings() when no settings provided."""
        with patch("backend.main.get_settings") as mock_get_settings:
            mock_settings = Settings(environment="test", _env_file=None)
            mock_get_settings.return_value = mock_settings

            app = create_app(settings=None)

            mock_get_settings.assert_called_once()
            assert isinstance(app, FastAPI)

    def test_create_app_configures_app_metadata(self):
        """create_app() should configure app title and description."""
        settings = Settings(environment="test", _env_file=None)
        app = create_app(settings=settings)

        assert app.title == "AmakaFlow Mapper API"
        assert app.version == "1.0.0"

    def test_create_app_with_custom_settings(self):
        """create_app() should accept custom settings."""
        custom_settings = Settings(
            environment="production",
            garmin_export_debug=True,
            _env_file=None
        )
        app = create_app(settings=custom_settings)
        assert isinstance(app, FastAPI)


@pytest.mark.unit
class TestInitSentry:
    """Test Sentry initialization."""

    def test_init_sentry_skipped_when_no_dsn(self):
        """Sentry should not be initialized when DSN is not set."""
        settings = Settings(sentry_dsn=None, _env_file=None)

        with patch("backend.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)
            mock_init.assert_not_called()

    def test_init_sentry_called_when_dsn_provided(self):
        """Sentry should be initialized when DSN is provided."""
        settings = Settings(
            sentry_dsn="https://test@sentry.io/123",
            environment="test",
            _env_file=None
        )

        with patch("backend.main.sentry_sdk.init") as mock_init:
            _init_sentry(settings)
            mock_init.assert_called_once_with(
                dsn="https://test@sentry.io/123",
                environment="test",
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                enable_tracing=True,
            )


@pytest.mark.unit
class TestConfigureCors:
    """Test CORS configuration."""

    def test_configure_cors_adds_middleware(self):
        """_configure_cors should add CORS middleware to the app."""
        app = FastAPI()

        # Before CORS, app has no user-added middleware
        initial_middleware_count = len(app.user_middleware)

        _configure_cors(app)

        # After CORS, app should have one additional middleware
        assert len(app.user_middleware) == initial_middleware_count + 1


@pytest.mark.unit
class TestLogFeatureFlags:
    """Test feature flag logging."""

    def test_log_feature_flags_logs_debug_active(self, caplog):
        """Should log warning when garmin_export_debug is True."""
        settings = Settings(garmin_export_debug=True, _env_file=None)

        with caplog.at_level("WARNING"):
            _log_feature_flags(settings)

        assert "GARMIN_EXPORT_DEBUG ACTIVE" in caplog.text

    def test_log_feature_flags_logs_debug_disabled(self, caplog):
        """Should log info when garmin_export_debug is False."""
        settings = Settings(garmin_export_debug=False, _env_file=None)

        with caplog.at_level("INFO"):
            _log_feature_flags(settings)

        assert "GARMIN_EXPORT_DEBUG is disabled" in caplog.text


@pytest.mark.integration
class TestAppIntegration:
    """Integration tests for the created app."""

    def test_app_can_handle_requests(self):
        """Created app should be able to handle HTTP requests."""
        settings = Settings(environment="test", _env_file=None)
        app = create_app(settings=settings)

        # Add a simple test endpoint
        @app.get("/test-health")
        def health():
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test-health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_cors_allows_requests(self):
        """CORS should allow cross-origin requests."""
        settings = Settings(environment="test", _env_file=None)
        app = create_app(settings=settings)

        @app.get("/test-cors")
        def cors_test():
            return {"cors": "enabled"}

        client = TestClient(app)
        response = client.get(
            "/test-cors",
            headers={"Origin": "http://localhost:3000"}
        )

        assert response.status_code == 200
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


@pytest.mark.unit
class TestMultipleAppInstances:
    """Test that multiple app instances can be created."""

    def test_create_multiple_independent_apps(self):
        """Should be able to create multiple independent app instances."""
        settings1 = Settings(environment="test", _env_file=None)
        settings2 = Settings(environment="production", _env_file=None)

        app1 = create_app(settings=settings1)
        app2 = create_app(settings=settings2)

        # Apps should be different instances
        assert app1 is not app2

        # Both should be valid FastAPI instances
        assert isinstance(app1, FastAPI)
        assert isinstance(app2, FastAPI)
