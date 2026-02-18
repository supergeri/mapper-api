"""
FastAPI Dependency Providers for AmakaFlow Mapper API.

Part of AMA-386: Create api/deps.py dependency providers
Updated in AMA-394: Add use case dependency providers
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
from typing import Optional, List, Dict, Any

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
    ExercisesRepository,
    ProgressionRepository,
    SearchRepository,
    EmbeddingService,
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
    SupabaseExercisesRepository,
    SupabaseProgressionRepository,
    SupabaseSearchRepository,
)

# Exercise matching service (AMA-299)
from backend.core.exercise_matcher import ExerciseMatchingService

# Progression service (AMA-299 Phase 3)
from backend.core.progression_service import ProgressionService

# Export service (AMA-610)
from backend.services.export_service import ExportService

# Export queue (AMA-612)
from backend.services.export_queue import ExportQueue

# Settings from Phase 0
from backend.settings import Settings, get_settings as _get_settings

# Auth from existing module (wrap to maintain single source of truth)
from backend.auth import (
    get_current_user as _get_current_user,
    get_optional_user as _get_optional_user,
)

# Use cases (Phase 3)
from application.use_cases import (
    MapWorkoutUseCase,
    ExportWorkoutUseCase,
    SaveWorkoutUseCase,
    PatchWorkoutUseCase,
    GetWorkoutUseCase,
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


def get_exercises_repo(
    client: Client = Depends(get_supabase_client_required),
) -> ExercisesRepository:
    """
    Get ExercisesRepository implementation.

    Returns a SupabaseExercisesRepository instance with injected client.
    Used for querying the canonical exercises table.

    Part of AMA-299: Exercise Database for Progression Tracking

    Args:
        client: Supabase client (injected)

    Returns:
        ExercisesRepository: Repository for canonical exercises
    """
    return SupabaseExercisesRepository(client)


def get_exercise_matcher(
    exercises_repo: ExercisesRepository = Depends(get_exercises_repo),
) -> ExerciseMatchingService:
    """
    Get ExerciseMatchingService with injected dependencies.

    The matching service uses a multi-stage approach:
    1. Exact name match (case-insensitive)
    2. Alias match (check aliases array)
    3. Fuzzy match using rapidfuzz
    4. LLM fallback (optional, disabled by default)

    Part of AMA-299: Exercise Database for Progression Tracking

    Args:
        exercises_repo: Exercises repository (injected)

    Returns:
        ExerciseMatchingService: Service for matching planned names to canonical exercises
    """
    return ExerciseMatchingService(
        exercises_repository=exercises_repo,
        llm_client=None,  # LLM fallback disabled by default
        enable_llm_fallback=False,
    )


def get_progression_repo(
    client: Client = Depends(get_supabase_client_required),
) -> ProgressionRepository:
    """
    Get ProgressionRepository implementation.

    Returns a SupabaseProgressionRepository instance with injected client.
    Used for querying exercise progression data.

    Part of AMA-299 Phase 3: Progression Features

    Args:
        client: Supabase client (injected)

    Returns:
        ProgressionRepository: Repository for progression data access
    """
    return SupabaseProgressionRepository(client)


def get_progression_service(
    progression_repo: ProgressionRepository = Depends(get_progression_repo),
    exercises_repo: ExercisesRepository = Depends(get_exercises_repo),
) -> ProgressionService:
    """
    Get ProgressionService with injected dependencies.

    Provides business logic for exercise progression tracking:
    - 1RM calculations
    - Exercise history enrichment
    - Personal record detection
    - Volume analytics

    Part of AMA-299 Phase 3: Progression Features

    Args:
        progression_repo: Progression repository (injected)
        exercises_repo: Exercises repository (injected)

    Returns:
        ProgressionService: Service for progression tracking
    """
    return ProgressionService(
        progression_repo=progression_repo,
        exercises_repo=exercises_repo,
    )


@lru_cache
def get_export_service() -> ExportService:
    """
    Get ExportService for format conversion.

    Provides methods for converting workouts to various export formats:
    - Ingest to Garmin YAML
    - Blocks to Garmin, Hyrox, HIIT, WorkoutKit, ZWO, FIT formats

    Part of AMA-610: Wire ExportService into exports router

    Returns:
        ExportService: Service for format conversion
    """
    return ExportService()


@lru_cache
def get_export_queue() -> ExportQueue:
    """
    Get ExportQueue for managing background export jobs.

    Provides async job queue for export operations:
    - Enqueue export jobs
    - Track job status
    - Process queued jobs

    Part of AMA-612: Wire ExportQueue into workouts router push endpoints

    Returns:
        ExportQueue: Queue for managing export jobs
    """
    return ExportQueue()


# =============================================================================
# Search Providers (AMA-432)
# =============================================================================


def get_search_repo(
    client: Client = Depends(get_supabase_client_required),
) -> SearchRepository:
    """
    Get SearchRepository implementation.

    Returns a SupabaseSearchRepository instance with injected client.
    Used for semantic and keyword search over workouts.

    Part of AMA-432: Semantic Search Endpoint

    Args:
        client: Supabase client (injected)

    Returns:
        SearchRepository: Repository for workout search operations
    """
    return SupabaseSearchRepository(client)


@lru_cache
def get_embedding_service() -> Optional[EmbeddingService]:
    """
    Get EmbeddingService if OpenAI is configured, None otherwise (cached).

    Returns None when OPENAI_API_KEY is not set, allowing the search
    endpoint to fall back to keyword search. The instance is cached
    for the lifetime of the process to reuse the underlying HTTP client.

    Part of AMA-432: Semantic Search Endpoint

    Returns:
        Optional[EmbeddingService]: Service for generating embeddings, or None
    """
    from backend.services.embedding_service import EmbeddingService as EmbeddingServiceImpl

    settings = _get_settings()
    if not settings.openai_api_key:
        return None
    return EmbeddingServiceImpl(
        api_key=settings.openai_api_key,
        model=settings.embedding_model,
    )


# =============================================================================
# Use Case Providers
# =============================================================================


def get_save_workout_use_case(
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> SaveWorkoutUseCase:
    """
    Get SaveWorkoutUseCase with injected dependencies.

    Args:
        workout_repo: Workout repository (injected)

    Returns:
        SaveWorkoutUseCase: Use case for saving workouts
    """
    return SaveWorkoutUseCase(workout_repo=workout_repo)


def get_get_workout_use_case(
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> GetWorkoutUseCase:
    """
    Get GetWorkoutUseCase with injected dependencies.

    Part of AMA-370: Refactor routers to call use-cases

    Args:
        workout_repo: Workout repository (injected)

    Returns:
        GetWorkoutUseCase: Use case for getting workouts
    """
    return GetWorkoutUseCase(workout_repo=workout_repo)


def get_patch_workout_use_case(
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> PatchWorkoutUseCase:
    """
    Get PatchWorkoutUseCase with injected dependencies.

    Part of AMA-433: PATCH /workouts/{id} endpoint implementation.

    Args:
        workout_repo: Workout repository (injected)

    Returns:
        PatchWorkoutUseCase: Use case for patching workouts
    """
    return PatchWorkoutUseCase(workout_repo=workout_repo)


def get_export_workout_use_case(
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> ExportWorkoutUseCase:
    """
    Get ExportWorkoutUseCase with injected dependencies.

    Args:
        workout_repo: Workout repository (injected)

    Returns:
        ExportWorkoutUseCase: Use case for exporting workouts
    """
    return ExportWorkoutUseCase(workout_repo=workout_repo)


def get_map_workout_use_case(
    exercise_match_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
    user_mapping_repo: UserMappingRepository = Depends(get_user_mapping_repo),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> MapWorkoutUseCase:
    """
    Get MapWorkoutUseCase with injected dependencies.

    Args:
        exercise_match_repo: Exercise matching repository (injected)
        user_mapping_repo: User mapping repository (injected)
        workout_repo: Workout repository (injected)

    Returns:
        MapWorkoutUseCase: Use case for mapping workouts
    """
    return MapWorkoutUseCase(
        exercise_match_repo=exercise_match_repo,
        user_mapping_repo=user_mapping_repo,
        workout_repo=workout_repo,
    )


# =============================================================================
# Program Providers (AMA-365)
# =============================================================================


def get_programs(
    profile_id: str,
    include_inactive: bool = False,
):
    """
    Get all programs for a user.

    Part of AMA-365: Create FastAPI deps providers

    Args:
        profile_id: User profile ID (injected via Depends)
        include_inactive: Include inactive programs

    Returns:
        List of program records
    """
    from backend.database import get_programs as _get_programs
    return _get_programs(profile_id, include_inactive)


def get_program(program_id: str, profile_id: str):
    """
    Get a single program by ID.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_program as _get_program
    return _get_program(program_id, profile_id)


def create_program(profile_id: str, name: str, description: str = None, color: str = None, icon: str = None):
    """
    Create a new workout program.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import create_program as _create_program
    return _create_program(profile_id, name, description, color, icon)


def update_program(program_id: str, profile_id: str, name: str = None, description: str = None, 
                   color: str = None, icon: str = None, is_active: bool = None,
                   current_day_index: int = None):
    """
    Update a workout program.

    Part of AMA-365: Create FastAPI deps providers
    Updated: AMA-351 - Add current_day_index parameter
    """
    from backend.database import update_program as _update_program
    return _update_program(program_id, profile_id, name, description, color, icon, current_day_index, is_active)


def delete_program(program_id: str, profile_id: str):
    """
    Delete a workout program.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import delete_program as _delete_program
    return _delete_program(program_id, profile_id)


def add_workout_to_program(program_id: str, profile_id: str, workout_id: str = None, 
                           follow_along_id: str = None, day_order: int = None):
    """
    Add a workout to a program.

    Part of AMA-365: Create FastAPI deps providers
    Updated: AMA-351 - Add follow_along_id and day_order parameters
    """
    from backend.database import add_workout_to_program as _add
    return _add(program_id, profile_id, workout_id, follow_along_id, day_order)


def remove_workout_from_program(member_id: str, profile_id: str):
    """
, profile_id:    Remove a workout from a program.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import remove_workout_from_program as _remove
    return _remove(member_id, profile_id)


# =============================================================================
# Tag Providers (AMA-365)
# =============================================================================


def get_user_tags(profile_id: str) -> List[Dict[str, Any]]:
    """
    Get all tags for a user.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_user_tags as _get_user_tags
    return _get_user_tags(profile_id)


def create_user_tag(profile_id: str, name: str, color: str = None) -> Optional[Dict[str, Any]]:
    """
    Create a new user tag.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import create_user_tag as _create_user_tag
    return _create_user_tag(profile_id, name, color)


def delete_user_tag(tag_id: str, profile_id: str) -> bool:
    """
    Delete a user tag.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import delete_user_tag as _delete_user_tag
    return _delete_user_tag(tag_id, profile_id)


# =============================================================================
# Account Providers (AMA-365)
# =============================================================================


def get_account_deletion_preview(profile_id: str):
    """
    Get a preview of all user data that will be deleted.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_account_deletion_preview as _get
    return _get(profile_id)


def delete_user_account(profile_id: str):
    """
    Delete user account and all associated data.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import delete_user_account as _delete
    return _delete(profile_id)


# =============================================================================
# Sync Providers (AMA-365)
# =============================================================================


def get_workout(workout_id: str, profile_id: str):
    """
    Get a workout by ID.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_workout as _get
    return _get(workout_id, profile_id)


def update_workout_ios_companion_sync(workout_id: str, profile_id: str):
    """
    Mark a workout as synced to iOS companion.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import update_workout_ios_companion_sync as _update
    return _update(workout_id, profile_id)


def update_workout_android_companion_sync(workout_id: str, profile_id: str):
    """
    Mark a workout as synced to Android companion.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import update_workout_android_companion_sync as _update
    return _update(workout_id, profile_id)


def get_ios_companion_pending_workouts(profile_id: str):
    """
    Get pending workouts for iOS companion.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_ios_companion_pending_workouts as _get
    return _get(profile_id)


def get_android_companion_pending_workouts(profile_id: str):
    """
    Get pending workouts for Android companion.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_android_companion_pending_workouts as _get
    return _get(profile_id)


def queue_workout_sync(workout_id: str, profile_id: str, platform: str):
    """
    Queue a workout for sync.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import queue_workout_sync as _queue
    return _queue(workout_id, profile_id, platform)


def get_pending_syncs(profile_id: str, platform: str = None):
    """
    Get pending syncs for a user.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_pending_syncs as _get
    return _get(profile_id, platform)


def confirm_sync(sync_id: str, profile_id: str):
    """
    Confirm a sync was completed.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import confirm_sync as _confirm
    return _confirm(sync_id, profile_id)


def report_sync_failed(sync_id: str, profile_id: str, error: str = None):
    """
    Report a sync failure.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import report_sync_failed as _report
    return _report(sync_id, profile_id, error)


def get_workout_sync_status(workout_id: str, user_id: str):
    """
    Get sync status for a workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_workout_sync_status as _get
    return _get(workout_id, user_id)


# =============================================================================
# Follow-Along Providers (AMA-365)
# =============================================================================


def save_follow_along_workout(
    user_id: str,
    source: str,
    source_url: str,
    title: str,
    description: Optional[str] = None,
    video_duration_sec: Optional[int] = None,
    thumbnail_url: Optional[str] = None,
    video_proxy_url: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None
) -> Optional[Dict[str, Any]]:
    """
    Save a follow-along workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import save_follow_along_workout as _save
    return _save(
        user_id=user_id,
        source=source,
        source_url=source_url,
        title=title,
        description=description,
        video_duration_sec=video_duration_sec,
        thumbnail_url=thumbnail_url,
        video_proxy_url=video_proxy_url,
        steps=steps
    )


def get_follow_along_workouts(user_id: str) -> List[Dict[str, Any]]:
    """
    Get follow-along workouts for a user.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_follow_along_workouts as _get
    return _get(user_id)


def get_follow_along_workout(workout_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a follow-along workout by ID.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import get_follow_along_workout as _get
    return _get(workout_id, user_id)


def update_follow_along_garmin_sync(workout_id: str, user_id: str, garmin_workout_id: str) -> bool:
    """
    Update Garmin sync status for follow-along workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import update_follow_along_garmin_sync as _update
    return _update(workout_id, user_id, garmin_workout_id)


def update_follow_along_apple_watch_sync(workout_id: str, user_id: str) -> bool:
    """
    Update Apple Watch sync status for follow-along workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import update_follow_along_apple_watch_sync as _update
    return _update(workout_id, user_id)


def update_follow_along_ios_companion_sync(workout_id: str, user_id: str) -> bool:
    """
    Update iOS companion sync status for follow-along workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import update_follow_along_ios_companion_sync as _update
    return _update(workout_id, user_id)


def delete_follow_along_workout(workout_id: str, user_id: str) -> bool:
    """
    Delete a follow-along workout.

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import delete_follow_along_workout as _delete
    return _delete(workout_id, user_id)


# =============================================================================
# Health Providers (AMA-365)
# =============================================================================


def reset_user_data(profile_id: str):
    """
    Reset all user data (for testing).

    Part of AMA-365: Create FastAPI deps providers
    """
    from backend.database import reset_user_data as _reset
    return _reset(profile_id)


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
    "get_exercises_repo",
    "get_progression_repo",
    "get_search_repo",
    # Services (AMA-299)
    "get_exercise_matcher",
    "get_progression_service",
    # Export Service (AMA-610)
    "get_export_service",
    # Export Queue (AMA-612)
    "get_export_queue",
    # Search (AMA-432)
    "get_embedding_service",
    # Use Cases
    "get_save_workout_use_case",
    "get_get_workout_use_case",
    "get_export_workout_use_case",
    "get_map_workout_use_case",
    "get_patch_workout_use_case",
    # Program Providers (AMA-365)
    "get_programs",
    "get_program",
    "create_program",
    "update_program",
    "delete_program",
    "add_workout_to_program",
    "remove_workout_from_program",
    # Tag Providers (AMA-365)
    "get_user_tags",
    "create_user_tag",
    "delete_user_tag",
    # Account Providers (AMA-365)
    "get_account_deletion_preview",
    "delete_user_account",
    # Sync Providers (AMA-365)
    "get_workout",
    "update_workout_ios_companion_sync",
    "update_workout_android_companion_sync",
    "get_ios_companion_pending_workouts",
    "get_android_companion_pending_workouts",
    "queue_workout_sync",
    "get_pending_syncs",
    "confirm_sync",
    "report_sync_failed",
    "get_workout_sync_status",
    # Follow-Along Providers (AMA-365)
    "save_follow_along_workout",
    "get_follow_along_workouts",
    "get_follow_along_workout",
    "update_follow_along_garmin_sync",
    "update_follow_along_apple_watch_sync",
    "update_follow_along_ios_companion_sync",
    "delete_follow_along_workout",
    # Health Providers (AMA-365)
    "reset_user_data",
    # Authentication
    "get_current_user",
    "get_optional_user",
]
