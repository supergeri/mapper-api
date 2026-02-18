"""
Domain layer for the Mapper API.

This package contains pure domain models that are independent of
infrastructure concerns (database, API, external services).

Part of AMA-389: Define canonical Workout domain model
Part of AMA-373: Mapper-API Architecture Refactoring (Phase 3)
"""

from domain.models import (
    Block,
    BlockType,
    Exercise,
    Load,
    Workout,
    WorkoutSettings,
    WorkoutMetadata,
    WorkoutSource,
)

__all__ = [
    "Block",
    "BlockType",
    "Exercise",
    "Load",
    "Workout",
    "WorkoutSettings",
    "WorkoutMetadata",
    "WorkoutSource",
]
