"""
Application factory for FastAPI.

Part of AMA-461: Create program-api service scaffold

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

    # Initialize Sentry for error tracking
    _init_sentry(settings)

    # Create FastAPI app
    app = FastAPI(
        title="AmakaFlow Program API",
        description="Training program generation and management API",
        version="1.0.0",
    )

    # Configure CORS middleware
    _configure_cors(app)

    # Include API routers
    _include_routers(app)

    return app


def _init_sentry(settings: Settings) -> None:
    """Initialize Sentry SDK if DSN is configured."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            enable_tracing=True,
        )
        logger.info("Sentry initialized for program-api")


def _configure_cors(app: FastAPI) -> None:
    """Configure CORS middleware for the application."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _include_routers(app: FastAPI) -> None:
    """Include all API routers in the application."""
    from api.routers import (
        health_router,
        programs_router,
        generation_router,
        progression_router,
    )

    # Health router (no prefix - /health at root)
    app.include_router(health_router)

    # Domain routers
    app.include_router(programs_router)
    app.include_router(generation_router)
    app.include_router(progression_router)


# Default app instance for uvicorn
# This allows: uvicorn backend.main:app --reload
app = create_app()
