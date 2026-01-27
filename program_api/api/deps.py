"""
FastAPI Dependency Providers for AmakaFlow Program API.

Part of AMA-461: Create program-api service scaffold

This module provides FastAPI dependency injection functions that return
interface types (Protocols) rather than concrete implementations.

Architecture:
- Settings and Supabase client are cached per-process (lru_cache)
- Repository providers create new instances per-request
- Auth providers extract user from headers

Usage in routers:
    from api.deps import get_program_repo, get_current_user
    from application.ports import ProgramRepository

    @router.get("/programs")
    def list_programs(
        user_id: str = Depends(get_current_user),
        program_repo: ProgramRepository = Depends(get_program_repo),
    ):
        return program_repo.get_by_user(user_id)

Testing:
    # Override dependencies in tests
    app.dependency_overrides[get_program_repo] = lambda: MockProgramRepository()
"""

import os
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException
from supabase import Client, create_client

from application.ports import ExerciseRepository, ProgramRepository, TemplateRepository
from infrastructure.db import (
    SupabaseExerciseRepository,
    SupabaseProgramRepository,
    SupabaseTemplateRepository,
)
from infrastructure.calendar_client import CalendarClient
from backend.settings import Settings, get_settings as _get_settings


# =============================================================================
# Settings Provider
# =============================================================================


def get_settings() -> Settings:
    """
    Get application settings.

    Returns cached Settings instance from backend.settings.
    Use this as a FastAPI dependency for settings access.

    Returns:
        Settings: Application settings instance
    """
    return _get_settings()


# =============================================================================
# Supabase Client Provider
# =============================================================================


@lru_cache
def get_supabase_client() -> Optional[Client]:
    """
    Get Supabase client instance (cached).

    Creates a Supabase client using credentials from settings.
    Returns None if credentials are not configured.

    Returns:
        Client: Supabase client instance, or None if not configured
    """
    settings = _get_settings()

    if not settings.supabase_url or not settings.supabase_key:
        return None

    return create_client(settings.supabase_url, settings.supabase_key)


def get_supabase_client_required() -> Client:
    """
    Get Supabase client instance, raising if not configured.

    Use this dependency when the endpoint requires database access.
    Raises HTTPException 503 if database is not available.

    Returns:
        Client: Supabase client instance

    Raises:
        HTTPException: 503 if Supabase is not configured
    """
    client = get_supabase_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Database not available. Supabase credentials not configured.",
        )
    return client


# =============================================================================
# Repository Providers
# =============================================================================


def get_program_repo(
    client: Client = Depends(get_supabase_client_required),
) -> ProgramRepository:
    """
    Get ProgramRepository implementation.

    Returns a SupabaseProgramRepository instance with injected client.
    The return type is the Protocol to enable easy mocking.

    Args:
        client: Supabase client (injected)

    Returns:
        ProgramRepository: Repository for program persistence
    """
    return SupabaseProgramRepository(client)


def get_template_repo(
    client: Client = Depends(get_supabase_client_required),
) -> TemplateRepository:
    """
    Get TemplateRepository implementation.

    Returns a SupabaseTemplateRepository instance with injected client.
    The return type is the Protocol to enable easy mocking.

    Args:
        client: Supabase client (injected)

    Returns:
        TemplateRepository: Repository for template access
    """
    return SupabaseTemplateRepository(client)


def get_exercise_repo(
    client: Client = Depends(get_supabase_client_required),
) -> ExerciseRepository:
    """
    Get ExerciseRepository implementation.

    Returns a SupabaseExerciseRepository instance with injected client.
    The return type is the Protocol to enable easy mocking.

    Args:
        client: Supabase client (injected)

    Returns:
        ExerciseRepository: Repository for exercise data access
    """
    return SupabaseExerciseRepository(client)


# =============================================================================
# Calendar Client Provider (AMA-469)
# =============================================================================


def get_calendar_client(
    settings: Settings = Depends(get_settings),
) -> CalendarClient:
    """
    Get CalendarClient instance for Calendar-API communication.

    Returns a CalendarClient configured with the Calendar-API URL from settings.

    Args:
        settings: Application settings (injected)

    Returns:
        CalendarClient: Client for calendar event operations
    """
    return CalendarClient(base_url=settings.calendar_api_url)


# =============================================================================
# Authentication Providers
# =============================================================================


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> str:
    """
    Get the current authenticated user ID.

    Extracts user ID from the Authorization header.
    Supports Bearer token authentication via Clerk.

    Args:
        authorization: Bearer token header

    Returns:
        str: User ID from authentication

    Raises:
        HTTPException: 401 if authentication fails
        RuntimeError: If auth stub is used in production
    """
    # CRITICAL: Block production deployment with auth stub
    # This ensures we don't accidentally deploy without proper auth
    environment = os.environ.get("ENVIRONMENT", "development").lower()
    if environment == "production":
        raise RuntimeError(
            "Authentication stub cannot be used in production. "
            "Implement proper Clerk JWT validation before deploying. "
            "See AMA-463 for auth implementation tracking."
        )

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header",
        )

    # Extract bearer token
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format",
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # TODO: Implement proper Clerk JWT validation (AMA-463)
    # For now, this is a stub that will be replaced with real auth
    # The token should be validated against Clerk's JWKS
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )

    # Stub: Return token as user_id for now
    # Real implementation will decode JWT and extract user_id
    return token


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Get the current user ID if authenticated, None otherwise.

    Use for endpoints that work differently when authenticated vs anonymous.

    Args:
        authorization: Bearer token header

    Returns:
        Optional[str]: User ID if authenticated, None otherwise
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization)
    except HTTPException:
        return None


# =============================================================================
# Service-to-Service Authentication (AMA-469)
# =============================================================================


async def verify_service_token(
    x_service_token: Optional[str] = Header(None),
    settings: Settings = Depends(get_settings),
) -> bool:
    """
    Verify service-to-service authentication token.

    Used for internal API calls between services (e.g., Calendar-API calling
    Program-API webhook). Checks the X-Service-Token header against the
    configured internal_service_token.

    Args:
        x_service_token: Service token from header
        settings: Application settings (injected)

    Returns:
        bool: True if token is valid

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    # In test/development without token configured, allow all requests
    if not settings.internal_service_token:
        if settings.is_production:
            raise HTTPException(
                status_code=500,
                detail="Internal service token not configured in production",
            )
        return True

    if not x_service_token:
        raise HTTPException(
            status_code=401,
            detail="Missing X-Service-Token header for service authentication",
        )

    if x_service_token != settings.internal_service_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid service token",
        )

    return True


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Settings
    "get_settings",
    # Database
    "get_supabase_client",
    "get_supabase_client_required",
    # Repositories
    "get_exercise_repo",
    "get_program_repo",
    "get_template_repo",
    # Calendar
    "get_calendar_client",
    # Authentication
    "get_current_user",
    "get_optional_user",
    "verify_service_token",
]
