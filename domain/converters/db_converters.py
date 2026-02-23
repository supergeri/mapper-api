"""
Converters: Database row format <-> domain Workout.

Part of AMA-390: Add converters for ingest and block formats

Provides bidirectional conversion between Supabase database rows
and the canonical Workout domain model.

Database schema (workouts table):
- id: UUID
- profile_id: User ID
- workout_data: JSONB (blocks format)
- sources: Array of strings (e.g., ["ai", "youtube"])
- device: Target device string
- title: Workout title
- description: Workout description
- tags: Array of strings
- is_exported, exported_at, exported_to_device: Export tracking
- is_favorite, favorite_order: Favorite tracking
- times_completed, last_used_at: Usage tracking
- created_at, updated_at: Timestamps
- ios_companion_synced_at: iOS companion sync timestamp
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from domain.converters.blocks_to_workout import blocks_to_workout
from domain.models import BlockType, Workout, WorkoutMetadata, WorkoutSource


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        # Handle ISO format with or without timezone
        try:
            # Try ISO format with Z suffix
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_sources(sources: Any) -> List[WorkoutSource]:
    """Parse sources from database array to WorkoutSource enum list."""
    if not sources:
        return []

    result: List[WorkoutSource] = []
    for src in sources:
        try:
            result.append(WorkoutSource(src))
        except ValueError:
            # Unknown source type, skip
            pass
    return result


def db_row_to_workout(row: Dict[str, Any]) -> Workout:
    """
    Convert a database row to domain Workout.

    The database stores workout_data in blocks format, so we use
    blocks_to_workout for the core conversion and then overlay
    the database-specific fields.

    Args:
        row: Dictionary representing a database row from workouts table.

    Returns:
        Canonical Workout domain model.

    Raises:
        ValueError: If workout_data is missing or invalid.

    Examples:
        >>> row = {
        ...     "id": "123e4567-e89b-12d3-a456-426614174000",
        ...     "title": "Test Workout",
        ...     "workout_data": {
        ...         "title": "Test Workout",
        ...         "blocks": [{"exercises": [{"name": "Squat", "reps": 10}]}]
        ...     },
        ...     "sources": ["ai"],
        ...     "device": "garmin",
        ...     "is_favorite": True,
        ...     "times_completed": 5,
        ... }
        >>> workout = db_row_to_workout(row)
        >>> workout.id
        '123e4567-e89b-12d3-a456-426614174000'
    """
    workout_data = row.get("workout_data")
    if not workout_data:
        raise ValueError("Database row missing workout_data")

    # Use title from row if present, otherwise fall back to workout_data
    if row.get("title"):
        workout_data = {**workout_data, "title": row["title"]}
    if row.get("description"):
        workout_data = {**workout_data, "description": row["description"]}

    # Convert blocks format to Workout
    workout = blocks_to_workout(workout_data)

    # Build enhanced metadata from database fields
    sources = _parse_sources(row.get("sources", []))
    metadata = WorkoutMetadata(
        sources=sources,
        source_url=row.get("source_url"),
        platform=row.get("device"),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
        is_exported=row.get("is_exported", False),
        exported_at=_parse_datetime(row.get("exported_at")),
        exported_to_device=row.get("exported_to_device"),
        ios_companion_synced_at=_parse_datetime(row.get("ios_companion_synced_at")),
    )

    # Overlay database fields onto workout
    return Workout(
        id=row.get("id"),
        title=workout.title,
        description=workout.description or row.get("description"),
        notes=workout.notes,
        tags=row.get("tags", []) or workout.tags,
        blocks=workout.blocks,
        metadata=metadata,
        is_favorite=row.get("is_favorite", False),
        times_completed=row.get("times_completed", 0),
        last_used_at=_parse_datetime(row.get("last_used_at")),
    )


def workout_to_db_row(
    workout: Workout,
    profile_id: str,
    device: str = "garmin",
) -> Dict[str, Any]:
    """
    Convert domain Workout to database row format.

    This produces a dictionary suitable for inserting/updating the
    workouts table in Supabase. The workout_data field is serialized
    to blocks format.

    Args:
        workout: Domain Workout to convert.
        profile_id: User's profile ID (required for database row).
        device: Target device identifier (default: "garmin").

    Returns:
        Dictionary with database column values.

    Examples:
        >>> from domain.models import Workout, Block, Exercise
        >>> workout = Workout(
        ...     title="My Workout",
        ...     blocks=[Block(exercises=[Exercise(name="Squat", sets=3, reps=10)])]
        ... )
        >>> row = workout_to_db_row(workout, "user-123", "garmin")
        >>> row["title"]
        'My Workout'
        >>> row["profile_id"]
        'user-123'
    """
    # Build workout_data in blocks format
    workout_data = _workout_to_blocks_format(workout)

    # Extract sources as strings
    sources = [src.value for src in workout.metadata.sources]

    row: Dict[str, Any] = {
        "profile_id": profile_id,
        "title": workout.title,
        "workout_data": workout_data,
        "sources": sources,
        "device": device,
    }

    # Optional fields
    if workout.id:
        row["id"] = workout.id

    if workout.description:
        row["description"] = workout.description

    if workout.tags:
        row["tags"] = workout.tags

    # Export tracking
    row["is_exported"] = workout.metadata.is_exported
    if workout.metadata.exported_at:
        row["exported_at"] = workout.metadata.exported_at.isoformat()
    if workout.metadata.exported_to_device:
        row["exported_to_device"] = workout.metadata.exported_to_device

    # Favorite tracking
    row["is_favorite"] = workout.is_favorite

    # Usage tracking
    row["times_completed"] = workout.times_completed
    if workout.last_used_at:
        row["last_used_at"] = workout.last_used_at.isoformat()

    # iOS companion sync
    if workout.metadata.ios_companion_synced_at:
        row["ios_companion_synced_at"] = workout.metadata.ios_companion_synced_at.isoformat()

    return row


def _workout_to_blocks_format(workout: Workout) -> Dict[str, Any]:
    """
    Serialize domain Workout to blocks format JSON.

    This is the inverse of blocks_to_workout - converts the domain
    model back to the JSON structure expected by the web editor
    and stored in the database.
    """
    blocks_data: List[Dict[str, Any]] = []

    for block in workout.blocks:
        exercises_data: List[Dict[str, Any]] = []

        for ex in block.exercises:
            ex_data: Dict[str, Any] = {"name": ex.name}

            if ex.canonical_name:
                ex_data["canonical_name"] = ex.canonical_name
            if ex.sets is not None:
                ex_data["sets"] = ex.sets
            if ex.reps is not None:
                ex_data["reps"] = ex.reps
            if ex.duration_seconds is not None:
                ex_data["duration_sec"] = ex.duration_seconds
            if ex.rest_seconds is not None:
                ex_data["rest_sec"] = ex.rest_seconds
            if ex.tempo:
                ex_data["tempo"] = ex.tempo
            if ex.notes:
                ex_data["notes"] = ex.notes

            # Serialize load
            if ex.load:
                ex_data["weight"] = ex.load.value
                ex_data["weight_unit"] = ex.load.unit

            exercises_data.append(ex_data)

        block_data: Dict[str, Any] = {}

        if block.label:
            block_data["label"] = block.label

        # Serialize block type as structure field for downstream consumers.
        # Straight is the implicit default — only non-straight types are stored.
        if block.type != BlockType.STRAIGHT:
            block_data["structure"] = block.type.value

        # Only write rounds > 1; rounds=1 is the read-path default and omitting
        # it keeps the JSON compact. This means "explicitly 1 round" is
        # indistinguishable from "rounds not specified" — acceptable trade-off.
        if block.rounds > 1:
            block_data["rounds"] = block.rounds

        if block.rest_between_seconds:
            block_data["rest_between_sec"] = block.rest_between_seconds

        # All block types store exercises uniformly in exercises[].
        block_data["exercises"] = exercises_data

        blocks_data.append(block_data)

    result: Dict[str, Any] = {
        "title": workout.title,
        "blocks": blocks_data,
    }

    if workout.description:
        result["description"] = workout.description
    if workout.notes:
        result["notes"] = workout.notes
    if workout.tags:
        result["tags"] = workout.tags

    # Include workout_type at top level for backward compatibility
    if workout.metadata.workout_type:
        result["workout_type"] = workout.metadata.workout_type

    # Include metadata
    if workout.metadata.sources or workout.metadata.platform or workout.metadata.workout_type:
        result["metadata"] = {}
        if workout.metadata.sources:
            result["metadata"]["sources"] = [s.value for s in workout.metadata.sources]
        if workout.metadata.platform:
            result["metadata"]["platform"] = workout.metadata.platform
        if workout.metadata.source_url:
            result["metadata"]["source_url"] = workout.metadata.source_url
        if workout.metadata.workout_type:
            result["metadata"]["workout_type"] = workout.metadata.workout_type

    return result
