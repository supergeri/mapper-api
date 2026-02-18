"""
Backend domain services for AMA-368.

This package contains service functions for the domain layer,
including converters for transforming between external formats
and the canonical Workout model.
"""

from backend.domain.services.workout_converter import (
    blocks_json_to_workout,
    workout_to_blocks_json,
)

__all__ = [
    "blocks_json_to_workout",
    "workout_to_blocks_json",
]
