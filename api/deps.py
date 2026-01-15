"""
FastAPI Dependency Providers for AmakaFlow Mapper API.

Part of AMA-386: Create api/deps.py dependency providers
Phase 2 - Dependency Injection

This module provides FastAPI dependency injection functions that return
interface types (Protocols) rather than concrete implementations. This
enables clean separation of concerns and easy testing with mock implementations.

Architecture:
- Settings and Supabase client are cached per-process (lru_cache)
- Repository providers create new instances per-request
- Auth providers wrap existing Clerk/JWT logic

Usage in routers:
    from api.deps import get_workout_repo, get_current_user
    from application.ports import WorkoutRepository

    @router.get("/workouts")
    def list_workouts(
        user_id: str = Depends(get_current_user),
        workout_repo: WorkoutRepository = Depends(get_workout_repo),
    ):
        return workout_repo.get_list(user_id)

Testing:
    # Override dependencies in tests
    app.dependency_overrides[get_workout_repo] = lambda: MockWorkoutRepository()
"""

from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header
from supabase import Client, create_client

# Protocol types (interfaces)
from application.ports import (
    WorkoutRepository,
    CompletionRepository,
    DeviceRepository,
    UserProfileRepository,
    UserMappingRepository,
    GlobalMappingRepository,
    ExerciseMatchRepository,
)

# Concrete implementations
from infrastructure import (
    SupabaseWorkoutRepository,
    SupabaseCompletionRepository,
    SupabaseDeviceRepository,
    SupabaseUserProfileRepository,
    SupabaseUserMappingRepository,
    SupabaseGlobalMappingRepository,
    InMemoryExerciseMatchRepository,
)

# Settings from Phase 0
from backend.settings import Settings, get_settings as _get_settings

# Auth from existing module (wrap to maintain single source of truth)
from backend.auth import (
    get_current_user as _get_current_user,
    get_optional_user as _get_optional_user,
)


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
def get_supabase_client(
    settings: Settings = Depends(get_settings),
) -> Optional[Client]:
    """
    Get Supabase client instance (cached).

    Creates a Supabase client using credentials from settings.
    Returns None if credentials are not configured.

    Note: This function is cached for the lifetime of the process.
    The Depends() is evaluated at function definition time for caching,
    so we call get_settings() directly inside for the actual caching.

    Returns:
        Client: Supabase client instance, or None if not configured
    """
    # Get settings directly to ensure caching works properly
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
    from fastapi import HTTPException

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


def get_workout_repo(
    client: Client = Depends(get_supabase_client_required),
) -> WorkoutRepository:
    """
    Get WorkoutRepository implementation.

    Returns a SupabaseWorkoutRepository instance with injected client.
    The return type is the Protocol to enable easy mocking.

    Args:
        client: Supabase client (injected)

    Returns:
        WorkoutRepository: Repository for workout persistence
    """
    return SupabaseWorkoutRepository(client)


def get_completion_repo(
    client: Client = Depends(get_supabase_client_required),
) -> CompletionRepository:
    """
    Get CompletionRepository implementation.

    Returns a SupabaseCompletionRepository instance with injected client.

    Args:
        client: Supabase client (injected)

    Returns:
        CompletionRepository: Repository for workout completion tracking
    """
    return SupabaseCompletionRepository(client)


def get_device_repo(
    client: Client = Depends(get_supabase_client_required),
) -> DeviceRepository:
    """
    Get DeviceRepository implementation.

    Returns a SupabaseDeviceRepository instance with injected client.

    Args:
        client: Supabase client (injected)

    Returns:
        DeviceRepository: Repository for device pairing operations
    """
    return SupabaseDeviceRepository(client)


def get_user_profile_repo(
    client: Client = Depends(get_supabase_client_required),
) -> UserProfileRepository:
    """
    Get UserProfileRepository implementation.

    Returns a SupabaseUserProfileRepository instance with injected client.

    Args:
        client: Supabase client (injected)

    Returns:
        UserProfileRepository: Repository for user profile operations
    """
    return SupabaseUserProfileRepository(client)


def get_user_mapping_repo(
    client: Client = Depends(get_supabase_client_required),
    user_id: str = Depends(_get_current_user),
) -> UserMappingRepository:
    """
    Get UserMappingRepository implementation.

    Returns a SupabaseUserMappingRepository instance scoped to the current user.

    Args:
        client: Supabase client (injected)
        user_id: Current user ID (injected from auth)

    Returns:
        UserMappingRepository: Repository for user-specific exercise mappings
    """
    return SupabaseUserMappingRepository(client, user_id)


def get_global_mapping_repo(
    client: Client = Depends(get_supabase_client_required),
) -> GlobalMappingRepository:
    """
    Get GlobalMappingRepository implementation.

    Returns a SupabaseGlobalMappingRepository instance with injected client.

    Args:
        client: Supabase client (injected)

    Returns:
        GlobalMappingRepository: Repository for crowd-sourced mapping popularity
    """
    return SupabaseGlobalMappingRepository(client)


def get_exercise_match_repo() -> ExerciseMatchRepository:
    """
    Get ExerciseMatchRepository implementation.

    Returns an InMemoryExerciseMatchRepository instance.
    This repository uses local file data and doesn't require Supabase.

    Returns:
        ExerciseMatchRepository: Repository for fuzzy exercise matching
    """
    return InMemoryExerciseMatchRepository()


# =============================================================================
# Authentication Providers
# =============================================================================


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_test_auth: Optional[str] = Header(None, alias="X-Test-Auth"),
    x_test_user_id: Optional[str] = Header(None, alias="X-Test-User-Id"),
) -> str:
    """
    Get the current authenticated user ID.

    Wraps backend.auth.get_current_user for dependency injection.
    Supports multiple auth methods:
    - Clerk JWT (RS256 via JWKS)
    - Mobile pairing JWT (HS256)
    - API key authentication
    - E2E test bypass (dev/staging only)

    Args:
        authorization: Bearer token header
        x_api_key: API key header
        x_test_auth: Test auth secret (dev/staging only)
        x_test_user_id: Test user ID (dev/staging only)

    Returns:
        str: User ID from authentication

    Raises:
        HTTPException: 401 if authentication fails
    """
    return await _get_current_user(
        authorization=authorization,
        x_api_key=x_api_key,
        x_test_auth=x_test_auth,
        x_test_user_id=x_test_user_id,
    )


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_test_auth: Optional[str] = Header(None, alias="X-Test-Auth"),
    x_test_user_id: Optional[str] = Header(None, alias="X-Test-User-Id"),
) -> Optional[str]:
    """
    Get the current user ID if authenticated, None otherwise.

    Wraps backend.auth.get_optional_user for dependency injection.
    Use for endpoints that work differently when authenticated vs anonymous.

    Args:
        authorization: Bearer token header
        x_api_key: API key header
        x_test_auth: Test auth secret (dev/staging only)
        x_test_user_id: Test user ID (dev/staging only)

    Returns:
        Optional[str]: User ID if authenticated, None otherwise
    """
    return await _get_optional_user(
        authorization=authorization,
        x_api_key=x_api_key,
        x_test_auth=x_test_auth,
        x_test_user_id=x_test_user_id,
    )


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
    "get_workout_repo",
    "get_completion_repo",
    "get_device_repo",
    "get_user_profile_repo",
    "get_user_mapping_repo",
    "get_global_mapping_repo",
    "get_exercise_match_repo",
    # Authentication
    "get_current_user",
    "get_optional_user",
]
