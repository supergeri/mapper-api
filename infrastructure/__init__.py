"""
Infrastructure Layer for AmakaFlow Mapper API.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This package contains concrete implementations of repository interfaces:
- db/: Supabase database implementations
- (future) cache/: Redis or in-memory cache implementations
- (future) external/: External service integrations
"""

# Re-export database repositories for convenient access
from infrastructure.db import (
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

__all__ = [
    "SupabaseWorkoutRepository",
    "SupabaseCompletionRepository",
    "SupabaseDeviceRepository",
    "SupabaseUserProfileRepository",
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
