"""
Infrastructure Database Layer.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This package provides Supabase-backed implementations of the repository interfaces
defined in application.ports. These implementations can be injected into services
and routers for clean separation of concerns and testability.

Usage:
    from supabase import create_client
    from infrastructure.db import (
        SupabaseWorkoutRepository,
        SupabaseCompletionRepository,
        SupabaseDeviceRepository,
        SupabaseUserProfileRepository,
        SupabaseUserMappingRepository,
        SupabaseGlobalMappingRepository,
        InMemoryExerciseMatchRepository,
    )

    # Create Supabase client
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Instantiate repositories with injected client
    workout_repo = SupabaseWorkoutRepository(client)
    completion_repo = SupabaseCompletionRepository(client)
    device_repo = SupabaseDeviceRepository(client)
    profile_repo = SupabaseUserProfileRepository(client)
    user_mapping_repo = SupabaseUserMappingRepository(client, user_id="user_123")
    global_mapping_repo = SupabaseGlobalMappingRepository(client)
    exercise_match_repo = InMemoryExerciseMatchRepository()
"""

from infrastructure.db.workout_repository import SupabaseWorkoutRepository
from infrastructure.db.completion_repository import SupabaseCompletionRepository
from infrastructure.db.device_repository import (
    SupabaseDeviceRepository,
    SupabaseUserProfileRepository,
)
from infrastructure.db.mapping_repository import (
    SupabaseUserMappingRepository,
    SupabaseGlobalMappingRepository,
    InMemoryExerciseMatchRepository,
)
from infrastructure.db.exercises_repository import SupabaseExercisesRepository
from infrastructure.db.progression_repository import SupabaseProgressionRepository
from infrastructure.db.search_repository import SupabaseSearchRepository

__all__ = [
    # Workout persistence
    "SupabaseWorkoutRepository",

    # Completion tracking
    "SupabaseCompletionRepository",

    # Device pairing and user profiles
    "SupabaseDeviceRepository",
    "SupabaseUserProfileRepository",

    # Exercise mapping
    "SupabaseUserMappingRepository",
    "SupabaseGlobalMappingRepository",
    "InMemoryExerciseMatchRepository",

    # Canonical exercises (AMA-299)
    "SupabaseExercisesRepository",

    # Progression tracking (AMA-299 Phase 3)
    "SupabaseProgressionRepository",

    # Search (AMA-432)
    "SupabaseSearchRepository",
]
