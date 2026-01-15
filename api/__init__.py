"""
API package for AmakaFlow Mapper API.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-386: Add dependency providers

This package contains:
- deps.py: FastAPI dependency providers for DI
- routers/: API route handlers
"""

# Re-export dependency providers for convenient access
from api.deps import (
    get_settings,
    get_supabase_client,
    get_supabase_client_required,
    get_workout_repo,
    get_completion_repo,
    get_device_repo,
    get_user_profile_repo,
    get_user_mapping_repo,
    get_global_mapping_repo,
    get_exercise_match_repo,
    get_current_user,
    get_optional_user,
)

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
