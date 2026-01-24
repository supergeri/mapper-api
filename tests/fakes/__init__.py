"""
Fake Repository Implementations for Testing.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

This package provides in-memory fake implementations of repository interfaces
for fast, isolated testing. No database or external dependencies required.

Features:
- All fakes implement the same Protocol interfaces as real implementations
- Supports seeding with test data
- Supports reset() for test isolation
- Factory functions for common test scenarios

Usage:
    from tests.fakes import FakeWorkoutRepository, create_workout_repo

    # Direct instantiation
    repo = FakeWorkoutRepository()
    repo.seed([{"id": "w1", "profile_id": "user1", "title": "Test"}])

    # Factory function with pre-populated data
    repo = create_workout_repo(user_id="user1", num_workouts=5)
"""
from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime, timezone

# Import all fake implementations
from tests.fakes.workout_repository import FakeWorkoutRepository
from tests.fakes.completion_repository import FakeCompletionRepository
from tests.fakes.device_repository import FakeDeviceRepository, FakeUserProfileRepository
from tests.fakes.mapping_repository import (
    FakeUserMappingRepository,
    FakeGlobalMappingRepository,
    FakeExerciseMatchRepository,
)
from tests.fakes.exercises_repository import FakeExercisesRepository
from tests.fakes.progression_repository import (
    FakeProgressionRepository,
    create_test_sessions,
)


# =============================================================================
# Factory Functions
# =============================================================================


def create_workout_repo(
    *,
    user_id: str = "test_user",
    num_workouts: int = 0,
) -> FakeWorkoutRepository:
    """
    Create a FakeWorkoutRepository with optional pre-populated workouts.

    Args:
        user_id: User ID for generated workouts
        num_workouts: Number of sample workouts to create

    Returns:
        Pre-populated FakeWorkoutRepository
    """
    repo = FakeWorkoutRepository()

    if num_workouts > 0:
        workouts = []
        for i in range(num_workouts):
            workouts.append({
                "id": str(uuid.uuid4()),
                "profile_id": user_id,
                "title": f"Test Workout {i + 1}",
                "device": "garmin",
                "sources": ["test"],
                "workout_data": {
                    "title": f"Test Workout {i + 1}",
                    "sport": "strength_training",
                    "intervals": [{"kind": "work", "duration_sec": 30}],
                },
                "is_exported": i % 2 == 0,  # Half exported
                "is_favorite": i % 3 == 0,  # Some favorites
                "times_completed": i,
                "tags": [],
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        repo.seed(workouts)

    return repo


def create_completion_repo(
    *,
    user_id: str = "test_user",
    num_completions: int = 0,
) -> FakeCompletionRepository:
    """
    Create a FakeCompletionRepository with optional pre-populated completions.

    Args:
        user_id: User ID for generated completions
        num_completions: Number of sample completions to create

    Returns:
        Pre-populated FakeCompletionRepository
    """
    from application.ports import HealthMetricsDTO

    repo = FakeCompletionRepository()

    if num_completions > 0:
        completions = []
        for i in range(num_completions):
            completions.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": "2024-01-01T10:30:00Z",
                "duration_seconds": 1800,
                "source": "apple_watch",
                "avg_heart_rate": 120 + i,
                "max_heart_rate": 150 + i,
                "active_calories": 200 + i * 10,
                "is_simulated": i % 5 == 0,  # Some simulated
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        repo.seed(completions)

    return repo


def create_device_repo(
    *,
    user_id: str = "test_user",
    num_paired_devices: int = 0,
) -> FakeDeviceRepository:
    """
    Create a FakeDeviceRepository with optional pre-paired devices.

    Args:
        user_id: User ID for generated devices
        num_paired_devices: Number of paired devices to create

    Returns:
        Pre-populated FakeDeviceRepository
    """
    repo = FakeDeviceRepository()

    if num_paired_devices > 0:
        devices = []
        for i in range(num_paired_devices):
            devices.append({
                "device_id": str(uuid.uuid4()),
                "user_id": user_id,
                "device_info": {
                    "model": f"iPhone {12 + i}",
                    "os_version": f"iOS 17.{i}",
                },
                "paired_at": datetime.now(timezone.utc).isoformat(),
                "revoked": False,
            })
        repo.seed_devices(devices)

    return repo


def create_user_profile_repo(
    *,
    user_id: str = "test_user",
    email: str = "test@example.com",
    name: str = "Test User",
    data_counts: Optional[Dict[str, int]] = None,
) -> FakeUserProfileRepository:
    """
    Create a FakeUserProfileRepository with a pre-created profile.

    Args:
        user_id: User ID
        email: User email
        name: User display name
        data_counts: Optional counts for deletion preview

    Returns:
        Pre-populated FakeUserProfileRepository
    """
    repo = FakeUserProfileRepository()

    repo.seed([{
        "id": user_id,
        "email": email,
        "name": name,
        "avatar_url": None,
    }])

    if data_counts:
        repo.set_data_counts(user_id, data_counts)

    return repo


def create_user_mapping_repo(
    user_id: str = "test_user",
    *,
    mappings: Optional[Dict[str, str]] = None,
) -> FakeUserMappingRepository:
    """
    Create a FakeUserMappingRepository with optional pre-defined mappings.

    Args:
        user_id: User ID
        mappings: Optional exercise_name -> garmin_name mappings

    Returns:
        Pre-populated FakeUserMappingRepository
    """
    repo = FakeUserMappingRepository(user_id)

    if mappings:
        repo.seed(mappings)

    return repo


def create_global_mapping_repo(
    *,
    popularity: Optional[Dict[str, Dict[str, int]]] = None,
) -> FakeGlobalMappingRepository:
    """
    Create a FakeGlobalMappingRepository with optional popularity data.

    Args:
        popularity: Optional {exercise_name: {garmin_name: count}} data

    Returns:
        Pre-populated FakeGlobalMappingRepository
    """
    repo = FakeGlobalMappingRepository()

    if popularity:
        repo.seed(popularity)

    return repo


def create_exercise_match_repo(
    *,
    matches: Optional[Dict[str, tuple]] = None,
    garmin_exercises: Optional[List[Dict[str, Any]]] = None,
) -> FakeExerciseMatchRepository:
    """
    Create a FakeExerciseMatchRepository with optional matches.

    Args:
        matches: Optional {exercise_name: (garmin_name, confidence)} matches
        garmin_exercises: Optional list of Garmin exercises for find_similar

    Returns:
        Pre-populated FakeExerciseMatchRepository
    """
    repo = FakeExerciseMatchRepository()

    if matches:
        repo.seed_matches(matches)

    if garmin_exercises:
        repo.seed_garmin_exercises(garmin_exercises)

    return repo


def create_exercises_repo(
    *,
    exercises: Optional[List[Dict[str, Any]]] = None,
) -> FakeExercisesRepository:
    """
    Create a FakeExercisesRepository with optional custom exercises.

    Part of AMA-299: Exercise Database for Progression Tracking

    Args:
        exercises: Optional list of exercises, or None for default test data

    Returns:
        Pre-populated FakeExercisesRepository
    """
    return FakeExercisesRepository(exercises=exercises)


def create_progression_repo(
    *,
    user_id: str = "test_user",
    num_sessions: int = 0,
    exercise_id: str = "barbell-bench-press",
) -> FakeProgressionRepository:
    """
    Create a FakeProgressionRepository with optional pre-populated sessions.

    Part of AMA-299 Phase 3: Progression Features

    Args:
        user_id: User ID for generated sessions
        num_sessions: Number of sample sessions to create
        exercise_id: Exercise ID to create sessions for

    Returns:
        Pre-populated FakeProgressionRepository
    """
    repo = FakeProgressionRepository()

    if num_sessions > 0:
        sessions = create_test_sessions(
            user_id=user_id,
            exercise_id=exercise_id,
            num_sessions=num_sessions,
        )
        repo.seed_sessions(user_id, sessions)

        # Seed exercise metadata
        repo.seed_exercise_metadata(exercise_id, {
            "id": exercise_id,
            "name": "Barbell Bench Press",
            "primary_muscles": ["chest"],
            "supports_1rm": True,
            "one_rm_formula": "brzycki",
        })

    return repo


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Fake implementations
    "FakeWorkoutRepository",
    "FakeCompletionRepository",
    "FakeDeviceRepository",
    "FakeUserProfileRepository",
    "FakeUserMappingRepository",
    "FakeGlobalMappingRepository",
    "FakeExerciseMatchRepository",
    "FakeExercisesRepository",
    "FakeProgressionRepository",
    # Factory functions
    "create_workout_repo",
    "create_completion_repo",
    "create_device_repo",
    "create_user_profile_repo",
    "create_user_mapping_repo",
    "create_global_mapping_repo",
    "create_exercise_match_repo",
    "create_exercises_repo",
    "create_progression_repo",
    "create_test_sessions",
]
