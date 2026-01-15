"""
Unit tests for backend/settings.py

Part of AMA-376: Introduce settings.py with Pydantic BaseSettings
"""

import pytest
from pydantic import ValidationError

from backend.settings import Settings, get_settings


class TestSettingsDefaults:
    """Test that Settings applies correct defaults."""

    def test_environment_default(self):
        """Default environment should be development."""
        settings = Settings()
        assert settings.environment == "development"

    def test_supabase_fields_default_to_none(self):
        """Supabase fields should default to None."""
        settings = Settings()
        assert settings.supabase_url is None
        assert settings.supabase_service_role_key is None
        assert settings.supabase_anon_key is None

    def test_clerk_fields_defaults(self):
        """Clerk fields should have correct defaults."""
        settings = Settings()
        assert settings.clerk_secret_key is None
        assert settings.clerk_domain == ""

    def test_jwt_secret_has_default(self):
        """JWT secret should have a default value."""
        settings = Settings()
        assert settings.jwt_secret == "amakaflow-mobile-jwt-secret-change-in-production"

    def test_garmin_service_url_default(self):
        """Garmin service URL should have default."""
        settings = Settings()
        assert settings.garmin_service_url == "http://garmin-sync-api:8002"

    def test_ingestor_url_default(self):
        """Ingestor URL should have default."""
        settings = Settings()
        assert settings.ingestor_url == "http://workout-ingestor-api:8004"

    def test_mapper_api_public_url_default(self):
        """Mapper API public URL should have default."""
        settings = Settings()
        assert settings.mapper_api_public_url == "https://api.amakaflow.com"

    def test_garmin_flags_default_to_false(self):
        """Garmin feature flags should default to False."""
        settings = Settings()
        assert settings.garmin_unofficial_sync_enabled is False
        assert settings.garmin_export_debug is False

    def test_sentry_dsn_default_to_none(self):
        """Sentry DSN should default to None."""
        settings = Settings()
        assert settings.sentry_dsn is None


class TestSettingsValidation:
    """Test Settings validation behavior."""

    def test_valid_environments_accepted(self):
        """Valid environment values should be accepted."""
        for env in ["development", "staging", "production", "test"]:
            settings = Settings(environment=env)
            assert settings.environment == env

    def test_environment_case_insensitive(self):
        """Environment validation should be case-insensitive."""
        settings = Settings(environment="PRODUCTION")
        assert settings.environment == "production"

    def test_invalid_environment_raises_error(self):
        """Invalid environment should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(environment="invalid")
        assert "Invalid environment" in str(exc_info.value)


class TestSettingsProperties:
    """Test Settings computed properties."""

    def test_supabase_key_prefers_service_role(self):
        """supabase_key should prefer service role key over anon key."""
        settings = Settings(
            supabase_service_role_key="service-key",
            supabase_anon_key="anon-key",
        )
        assert settings.supabase_key == "service-key"

    def test_supabase_key_falls_back_to_anon(self):
        """supabase_key should fall back to anon key if no service role."""
        settings = Settings(supabase_anon_key="anon-key")
        assert settings.supabase_key == "anon-key"

    def test_supabase_key_returns_none_if_neither(self):
        """supabase_key should return None if no keys set."""
        settings = Settings()
        assert settings.supabase_key is None

    def test_api_keys_list_parses_comma_separated(self):
        """api_keys_list should parse comma-separated keys."""
        settings = Settings(api_keys="key1, key2, key3")
        assert settings.api_keys_list == ["key1", "key2", "key3"]

    def test_api_keys_list_handles_empty(self):
        """api_keys_list should handle empty string."""
        settings = Settings(api_keys="")
        assert settings.api_keys_list == []

    def test_api_keys_list_strips_whitespace(self):
        """api_keys_list should strip whitespace from keys."""
        settings = Settings(api_keys="  key1  ,  key2  ")
        assert settings.api_keys_list == ["key1", "key2"]

    def test_is_production_property(self):
        """is_production should return True only in production."""
        prod_settings = Settings(environment="production")
        dev_settings = Settings(environment="development")
        assert prod_settings.is_production is True
        assert dev_settings.is_production is False

    def test_is_development_property(self):
        """is_development should return True only in development."""
        dev_settings = Settings(environment="development")
        prod_settings = Settings(environment="production")
        assert dev_settings.is_development is True
        assert prod_settings.is_development is False

    def test_is_test_property(self):
        """is_test should return True only in test environment."""
        test_settings = Settings(environment="test")
        dev_settings = Settings(environment="development")
        assert test_settings.is_test is True
        assert dev_settings.is_test is False


class TestGetSettings:
    """Test get_settings() function."""

    def test_get_settings_returns_settings_instance(self):
        """get_settings() should return a Settings instance."""
        # Clear cache to ensure fresh instance
        get_settings.cache_clear()
        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_get_settings_is_cached(self):
        """get_settings() should return the same cached instance."""
        get_settings.cache_clear()
        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2

    def test_get_settings_cache_can_be_cleared(self):
        """get_settings() cache can be cleared for testing."""
        get_settings.cache_clear()
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()
        # After clearing cache, we get a new instance
        # (though values will be the same since env vars haven't changed)
        assert isinstance(settings2, Settings)


class TestSettingsFromEnv:
    """Test Settings loading from environment variables."""

    def test_settings_loads_from_env(self, monkeypatch):
        """Settings should load values from environment variables."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
        monkeypatch.setenv("JWT_SECRET", "my-secret")

        # Clear cache and create new instance
        get_settings.cache_clear()
        settings = Settings()

        assert settings.environment == "staging"
        assert settings.supabase_url == "https://test.supabase.co"
        assert settings.jwt_secret == "my-secret"

    def test_boolean_env_vars(self, monkeypatch):
        """Boolean fields should parse string env vars correctly."""
        monkeypatch.setenv("GARMIN_UNOFFICIAL_SYNC_ENABLED", "true")
        monkeypatch.setenv("GARMIN_EXPORT_DEBUG", "false")

        settings = Settings()

        assert settings.garmin_unofficial_sync_enabled is True
        assert settings.garmin_export_debug is False

    def test_boolean_env_vars_case_insensitive(self, monkeypatch):
        """Boolean parsing should be case-insensitive."""
        monkeypatch.setenv("GARMIN_UNOFFICIAL_SYNC_ENABLED", "TRUE")

        settings = Settings()

        assert settings.garmin_unofficial_sync_enabled is True
