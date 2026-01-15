"""
Domain converters for transforming external formats to canonical Workout model.

Part of AMA-390: Add converters for ingest and block formats

This module provides pure converter functions for transforming various
workout data formats into the canonical Workout domain model:

- ingest_to_workout: ParsedWorkout (from AI parsing) -> Workout
- blocks_to_workout: Blocks JSON (from web editor) -> Workout
- db_row_to_workout: Database row (from Supabase) -> Workout
- workout_to_db_row: Workout -> Database row (for persistence)

All converters are pure functions with no side effects.

Examples:
    >>> from domain.converters import ingest_to_workout, blocks_to_workout
    >>> from backend.parsers.models import ParsedWorkout

    >>> # Convert from AI parsing output
    >>> parsed = ParsedWorkout(name="Test", exercises=[...])
    >>> workout = ingest_to_workout(parsed)

    >>> # Convert from web editor format
    >>> blocks_json = {"title": "Test", "blocks": [...]}
    >>> workout = blocks_to_workout(blocks_json)

    >>> # Convert to/from database
    >>> row = workout_to_db_row(workout, profile_id="user-123")
    >>> workout = db_row_to_workout(row)
"""

from domain.converters.blocks_to_workout import blocks_to_workout
from domain.converters.db_converters import db_row_to_workout, workout_to_db_row
from domain.converters.ingest_to_workout import ingest_to_workout

__all__ = [
    "ingest_to_workout",
    "blocks_to_workout",
    "db_row_to_workout",
    "workout_to_db_row",
]
