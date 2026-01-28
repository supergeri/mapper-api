"""
Centralized settings configuration using Pydantic BaseSettings.

Part of AMA-376: Introduce settings.py with Pydantic BaseSettings

All environment variables are defined here with types, defaults, and validation.
Use get_settings() for dependency injection compatibility in FastAPI.

Usage:
    from backend.settings import get_settings, Settings

    # In FastAPI endpoints (dependency injection)
    @app.get("/")
    def read_root(settings: Settings = Depends(get_settings)):
        return {"environment": settings.environment}

    # Direct access (module-level)
    settings = get_settings()
    print(settings.supabase_url)
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Core Environment
    # -------------------------------------------------------------------------
    environment: str = Field(
        default="development",
        description="Runtime environment: development, staging, production",
    )

    # -------------------------------------------------------------------------
    # Supabase Database
    # -------------------------------------------------------------------------
    supabase_url: Optional[str] = Field(
        default=None,
        description="Supabase project URL",
    )
    supabase_service_role_key: Optional[str] = Field(
        default=None,
        description="Supabase service role key (full access)",
    )
    supabase_anon_key: Optional[str] = Field(
        default=None,
        description="Supabase anonymous key (limited access)",
    )

    @property
    def supabase_key(self) -> Optional[str]:
        """Get the best available Supabase key (service role preferred)."""
        return self.supabase_service_role_key or self.supabase_anon_key

    # -------------------------------------------------------------------------
    # Authentication - Clerk
    # -------------------------------------------------------------------------
    clerk_secret_key: Optional[str] = Field(
        default=None,
        description="Clerk secret key for backend API calls",
    )
    clerk_domain: str = Field(
        default="",
        description="Clerk domain for JWT validation",
    )

    # -------------------------------------------------------------------------
    # Authentication - Mobile/JWT
    # -------------------------------------------------------------------------
    jwt_secret: str = Field(
        default="amakaflow-mobile-jwt-secret-change-in-production",
        description="Secret key for mobile JWT token signing",
    )
    api_keys: str = Field(
        default="",
        description="Comma-separated list of valid API keys",
    )

    @property
    def api_keys_list(self) -> list[str]:
        """Parse API keys into a list."""
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------
    test_auth_secret: str = Field(
        default="",
        description="Secret for test authentication bypass",
    )
    test_reset_secret: str = Field(
        default="",
        description="Secret for test data reset endpoint",
    )

    # -------------------------------------------------------------------------
    # External Services - Garmin
    # -------------------------------------------------------------------------
    garmin_email: Optional[str] = Field(
        default=None,
        description="Garmin Connect account email",
    )
    garmin_password: Optional[str] = Field(
        default=None,
        description="Garmin Connect account password",
    )
    garmin_service_url: str = Field(
        default="http://garmin-sync-api:8002",
        description="URL for Garmin sync service",
    )
    garmin_unofficial_sync_enabled: bool = Field(
        default=False,
        description="Enable unofficial Garmin sync features",
    )
    garmin_export_debug: bool = Field(
        default=False,
        description="Enable debug logging for Garmin exports",
    )

    # -------------------------------------------------------------------------
    # External Services - Ingestor
    # -------------------------------------------------------------------------
    ingestor_url: str = Field(
        default="http://workout-ingestor-api:8004",
        description="URL for workout ingestor service",
    )
    ingestor_api_url: str = Field(
        default="http://workout-ingestor:8004",
        description="URL for ingestor API (image parsing)",
    )

    # -------------------------------------------------------------------------
    # External Services - Public URLs
    # -------------------------------------------------------------------------
    mapper_api_public_url: str = Field(
        default="https://api.amakaflow.com",
        description="Public URL for mapper API (used in pairing QR codes)",
    )

    # -------------------------------------------------------------------------
    # External Services - OpenAI (AMA-432: Semantic Search)
    # -------------------------------------------------------------------------
    openai_api_key: Optional[str] = Field(
        default=None,
        description="OpenAI API key for embedding generation",
    )
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model name",
    )

    # -------------------------------------------------------------------------
    # Observability - Sentry
    # -------------------------------------------------------------------------
    sentry_dsn: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking",
    )

    # -------------------------------------------------------------------------
    # Validators
    # -------------------------------------------------------------------------
    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Ensure environment is a valid value."""
        valid_environments = {"development", "staging", "production", "test"}
        if v.lower() not in valid_environments:
            raise ValueError(
                f"Invalid environment '{v}'. Must be one of: {valid_environments}"
            )
        return v.lower()

    # -------------------------------------------------------------------------
    # Helper Properties
    # -------------------------------------------------------------------------
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        """Check if running in test environment."""
        return self.environment == "test"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    For testing, you can clear the cache with get_settings.cache_clear().

    Returns:
        Settings: Application settings instance
    """
    return Settings()
