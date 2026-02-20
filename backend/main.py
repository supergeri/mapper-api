"""
Application factory for FastAPI.

Part of AMA-377: Introduce main.py with create_app() factory
Updated in AMA-378: Add router wiring

This module provides a factory function for creating FastAPI application instances.
The factory pattern allows for:
- Easy testing with custom settings
- Multiple app instances with different configurations
- Clear separation of app creation from route definitions

Usage:
    from backend.main import create_app
    from backend.settings import Settings

    # Default app (uses get_settings())
    app = create_app()

    # Test app with custom settings
    test_settings = Settings(environment="test", _env_file=None)
    test_app = create_app(settings=test_settings)
"""

import logging
import os
from typing import Optional

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """
    Create and configure a FastAPI application instance.

    Args:
        settings: Optional Settings instance. If not provided, uses get_settings()
                  which loads from environment variables.

    Returns:
        Configured FastAPI application instance.
    """
    if settings is None:
        settings = get_settings()

    # Initialize Sentry for error tracking (AMA-225)
    _init_sentry(settings)

    # Create FastAPI app
    app = FastAPI(
        title="AmakaFlow Mapper API",
        description="Workout mapping and transformation API",
        version="1.0.0",
    )

    # Configure CORS middleware
    _configure_cors(app)

    # Replay capture middleware (AMA-543) — opt-in via env var
    if os.environ.get("REPLAY_CAPTURE_ENABLED", "").lower() in ("1", "true", "yes"):
        from backend.capture import CaptureMiddleware
        capture_dir = os.environ.get("REPLAY_CAPTURE_DIR", "./captures")
        app.add_middleware(CaptureMiddleware, capture_dir=capture_dir)
        logger.info("Replay capture middleware enabled → %s", capture_dir)

    # Include API routers (AMA-378)
    _include_routers(app)

    # Log feature flags status
    _log_feature_flags(settings)

    return app


def _init_sentry(settings: Settings) -> None:
    """Initialize Sentry SDK if DSN is configured."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            profiles_sample_rate=0.1,
            enable_tracing=True,
        )
        logger.info("Sentry initialized for mapper-api")


def _configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the application."""
    # Restrict to specific trusted domains for production security
    # Add environment-specific origins as needed
    trusted_origins = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
    # Add production domains from environment if configured
    production_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
    trusted_origins.extend([origin.strip() for origin in production_origins if origin.strip()])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=trusted_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _include_routers(app: FastAPI) -> None:
    """Include all API routers in the application.

    Part of AMA-378: Router wiring for modular API structure.
    Updated in AMA-591: Add bulk import router.
    Updated in AMA-593: Add programs router
    Updated in AMA-594: Add tags router
    Updated in AMA-596: Add account router
    Updated in AMA-597: Move debug/testing endpoints to health router
    Updated in AMA-362: Add follow-along router
    Updated in AMA-439: Add chat router for SSE streaming
    """
    from api.routers import (
        account_router,
        health_router,
        mapping_router,
        exports_router,
        workouts_router,
        pairing_router,
        completions_router,
        exercises_router,
        progression_router,
        programs_router,
        tags_router,
        settings_router,
        follow_along_router,
        sync_router,
        bulk_import_router,
        chat_router,
    )

    # Health router (no prefix - /health at root)
    app.include_router(health_router)

    # Domain routers (with prefixes defined in each router)
    app.include_router(mapping_router)
    app.include_router(exports_router)
    # IMPORTANT: completions_router MUST come before workouts_router
    # so /workouts/completions routes match before /workouts/{workout_id}
    app.include_router(completions_router)
    app.include_router(workouts_router)
    app.include_router(pairing_router)
    # Canonical exercises (AMA-299)
    app.include_router(exercises_router)
    # Progression tracking (AMA-299 Phase 3)
    app.include_router(progression_router)
    # Workout programs (AMA-593)
    app.include_router(programs_router)
    # User tags (AMA-594)
    app.include_router(tags_router)
    # Follow-along workouts (AMA-587)
    app.include_router(follow_along_router)
    # User settings (AMA-585)
    app.include_router(settings_router)
    # Follow-along workouts (AMA-356)
    app.include_router(follow_along_router)
    # Account management (AMA-596)
    app.include_router(account_router)
    # Device sync (iOS, Android, Garmin) (AMA-589)
    app.include_router(sync_router)
    # Bulk import workflow (AMA-591)
    app.include_router(bulk_import_router)
    # Chat SSE streaming endpoint (AMA-439)
    app.include_router(chat_router)


def _log_feature_flags(settings: Settings) -> None:
    """Log the status of feature flags at startup."""
    if settings.garmin_export_debug:
        logger.warning("=== GARMIN_EXPORT_DEBUG ACTIVE (mapper-api) ===")
    else:
        logger.info("GARMIN_EXPORT_DEBUG is disabled (mapper-api)")

    if settings.garmin_unofficial_sync_enabled:
        logger.info("GARMIN_UNOFFICIAL_SYNC_ENABLED is active")


# Default app instance for uvicorn
# This allows: uvicorn backend.main:app --reload
app = create_app()
