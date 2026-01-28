"""
Repository Interfaces (Ports) for AmakaFlow Mapper API.

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

This package defines abstract interfaces that decouple domain logic from
infrastructure (database, external services). Implementations are provided
in the infrastructure layer.

Architecture follows the Ports & Adapters (Hexagonal) pattern:
- Ports: Abstract interfaces defined here (what the domain needs)
- Adapters: Concrete implementations in infrastructure/ (how it's provided)

Usage:
    from application.ports import WorkoutRepository, CompletionRepository

    class WorkoutService:
        def __init__(self, workout_repo: WorkoutRepository):
            self.workout_repo = workout_repo

        def save_workout(self, ...):
            return self.workout_repo.save(...)
"""

# Workout persistence
from application.ports.workout_repository import WorkoutRepository

# Completion persistence
from application.ports.completion_repository import (
    CompletionRepository,
    HealthMetricsDTO,
    CompletionSummary,
)

# Device/pairing persistence
from application.ports.device_repository import (
    DeviceRepository,
    UserProfileRepository,
)

# Exercise mapping persistence
from application.ports.mapping_repository import (
    UserMappingRepository,
    GlobalMappingRepository,
    ExerciseMatchRepository,
)

# Canonical exercises (AMA-299)
from application.ports.exercises_repository import ExercisesRepository

# Progression tracking (AMA-299 Phase 3)
from application.ports.progression_repository import (
    ProgressionRepository,
    SetPerformance,
    ExerciseSession,
    PersonalRecord,
    LastWeightResult,
    VolumeDataPoint,
)

# Search (AMA-432: Semantic Search)
from application.ports.search_repository import SearchRepository
from application.ports.embedding_service import EmbeddingService

__all__ = [
    # Workout
    "WorkoutRepository",
    # Completion
    "CompletionRepository",
    "HealthMetricsDTO",
    "CompletionSummary",
    # Device/Profile
    "DeviceRepository",
    "UserProfileRepository",
    # Mapping
    "UserMappingRepository",
    "GlobalMappingRepository",
    "ExerciseMatchRepository",
    # Canonical exercises (AMA-299)
    "ExercisesRepository",
    # Progression tracking (AMA-299 Phase 3)
    "ProgressionRepository",
    "SetPerformance",
    "ExerciseSession",
    "PersonalRecord",
    "LastWeightResult",
    "VolumeDataPoint",
    # Search (AMA-432)
    "SearchRepository",
    "EmbeddingService",
]
