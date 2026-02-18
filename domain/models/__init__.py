"""
Domain models for the Mapper API.

This package contains pure domain models that are independent of
infrastructure concerns (database, API, external services).

These models represent the core business concepts:
- Workout: The aggregate root containing blocks of exercises
- Block: A group of exercises performed together (straight, superset, circuit)
- Exercise: A single exercise with sets, reps, load, etc.
- Load: Weight/resistance value object
- WorkoutMetadata: Provenance and tracking information

Part of AMA-389: Define canonical Workout domain model
Part of AMA-373: Mapper-API Architecture Refactoring (Phase 3)

Usage:
    >>> from domain.models import Workout, Block, Exercise, Load

    >>> workout = Workout(
    ...     title="Full Body Strength",
    ...     blocks=[
    ...         Block(
    ...             label="Main Lifts",
    ...             exercises=[
    ...                 Exercise(
    ...                     name="Squat",
    ...                     sets=5,
    ...                     reps=5,
    ...                     load=Load(value=225, unit="lb")
    ...                 )
    ...             ]
    ...         )
    ...     ]
    ... )

    >>> # Serialize to JSON
    >>> json_str = workout.model_dump_json(indent=2)

    >>> # Deserialize from JSON
    >>> workout = Workout.model_validate_json(json_str)
"""

from domain.models.block import Block, BlockType
from domain.models.exercise import Exercise
from domain.models.load import Load
from domain.models.metadata import WorkoutMetadata, WorkoutSource
from domain.models.workout import Workout, WorkoutSettings

__all__ = [
    # Main entities
    "Workout",
    "WorkoutSettings",
    "Block",
    "Exercise",
    "Load",
    "WorkoutMetadata",
    # Enums
    "BlockType",
    "WorkoutSource",
]
