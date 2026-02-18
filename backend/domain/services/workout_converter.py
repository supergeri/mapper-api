"""
Workout converter: canonical model <-> blocks_json format.

Part of AMA-368: [Phase 3.2] Add converters into canonical model

This module provides bidirectional conversion between the canonical Workout
domain model and the blocks_json format used by the web editor and stored
in the database.

Functions:
    blocks_json_to_workout: Convert blocks_json to canonical Workout
    workout_to_blocks_json: Convert canonical Workout to blocks_json

Both functions are pure (no side effects) and fully unit testable.
"""

from typing import Any, Dict, List

from domain.models import Block, BlockType, Exercise, Load, Workout, WorkoutMetadata, WorkoutSource


def blocks_json_to_workout(blocks_json: Dict[str, Any]) -> Workout:
    """
    Convert blocks_json format to canonical Workout domain model.

    This is the main entry point for converting from the blocks_json
    format (used by web editor, stored in database) to the canonical
    Workout model.

    The blocks_json format has:
    - title: Workout title
    - description: Optional description
    - notes: Optional notes
    - tags: List of tags
    - blocks[]: List of blocks, each with:
        - label: Block label
        - structure: Block type ("straight", "superset", "circuit", "timed_round")
        - rounds: Number of rounds
        - exercises[]: List of exercises
        - rest_between_sec: Rest between rounds
    - metadata: Optional metadata with sources, platform, source_url

    Each exercise has:
    - name: Exercise name
    - canonical_name: Optional mapped name
    - sets: Number of sets
    - reps: Reps (int or string like "3+1", "AMRAP")
    - duration_sec: Duration in seconds
    - rest_sec: Rest after exercise
    - weight, weight_unit: Load
    - tempo: Tempo notation
    - notes: Exercise notes
    - distance, distance_unit: Distance for cardio

    Args:
        blocks_json: Dictionary with blocks format data.

    Returns:
        Canonical Workout domain model.

    Raises:
        ValueError: If required fields are missing or invalid.

    Examples:
        >>> blocks_json = {
        ...     "title": "Full Body",
        ...     "blocks": [
        ...         {
        ...             "structure": "straight",
        ...             "exercises": [
        ...                 {"name": "Squat", "reps": 10, "sets": 3},
        ...             ]
        ...         }
        ...     ]
        ... }
        >>> workout = blocks_json_to_workout(blocks_json)
        >>> workout.title
        'Full Body'
    """
    _validate_blocks_json(blocks_json)

    title = blocks_json.get("title") or blocks_json.get("name") or "Workout"
    description = blocks_json.get("description")
    notes = blocks_json.get("notes")
    tags = blocks_json.get("tags", [])

    # Convert blocks
    all_blocks: List[Block] = []
    for block_data in blocks_json.get("blocks", []):
        all_blocks.extend(_convert_block(block_data))

    # Build metadata
    sources: List[WorkoutSource] = []
    metadata_dict = blocks_json.get("metadata", {})

    # Parse sources from metadata
    source_list = metadata_dict.get("sources", [])
    for src in source_list:
        try:
            sources.append(WorkoutSource(src))
        except ValueError:
            pass

    metadata = WorkoutMetadata(
        sources=sources,
        source_url=metadata_dict.get("source_url"),
        platform=metadata_dict.get("platform"),
    )

    return Workout(
        id=blocks_json.get("id"),
        title=title,
        description=description,
        notes=notes,
        tags=tags if isinstance(tags, list) else [],
        blocks=all_blocks,
        metadata=metadata,
        is_favorite=blocks_json.get("is_favorite", False),
        times_completed=blocks_json.get("times_completed", 0),
    )


def _validate_blocks_json(blocks_json: Dict[str, Any]) -> None:
    """
    Validate blocks_json has required fields.

    Raises:
        ValueError: If validation fails.
    """
    if not blocks_json:
        raise ValueError("blocks_json cannot be empty")

    blocks = blocks_json.get("blocks")
    if not blocks:
        raise ValueError("blocks_json must contain 'blocks' array")

    if not isinstance(blocks, list):
        raise ValueError("'blocks' must be an array")

    # Validate each block has exercises
    for i, block in enumerate(blocks):
        exercises = block.get("exercises") if isinstance(block, dict) else None
        if not exercises:
            raise ValueError(f"Block {i} must contain 'exercises' array")


def _convert_block(block_data: Dict[str, Any]) -> List[Block]:
    """Convert a single block from blocks_json to domain Block."""
    import re

    # Parse block type
    structure = block_data.get("structure", "")
    try:
        block_type = BlockType(structure) if structure else BlockType.STRAIGHT
    except ValueError:
        block_type = BlockType.STRAIGHT

    # Parse rounds
    rounds = block_data.get("rounds", 1)
    if isinstance(rounds, str):
        match = re.search(r"(\d+)", rounds)
        rounds = int(match.group(1)) if match else 1

    # Parse exercises
    exercises = []
    for ex_data in block_data.get("exercises", []):
        exercises.append(_convert_exercise(ex_data))

    if not exercises:
        raise ValueError("Block must contain at least one exercise")

    return [
        Block(
            label=block_data.get("label"),
            type=block_type,
            rounds=rounds,
            exercises=exercises,
            rest_between_seconds=block_data.get("rest_between_sec"),
        )
    ]


def _convert_exercise(ex_data: Dict[str, Any]) -> Exercise:
    """Convert a single exercise from blocks_json to domain Exercise."""
    import re

    name = ex_data.get("name", "Exercise")

    # Parse reps - handle int, string, or duration format
    reps_raw = ex_data.get("reps")
    int_reps = None
    str_reps = None
    duration_secs = None

    if reps_raw is not None:
        if isinstance(reps_raw, int):
            int_reps = reps_raw
        else:
            reps_str = str(reps_raw).strip().lower()
            # Check for duration (e.g., "60s", "30sec")
            for suffix in ["s", "sec", "secs"]:
                if reps_str.endswith(suffix):
                    try:
                        duration_secs = int(float(reps_str[: -len(suffix)]))
                        break
                    except ValueError:
                        pass
            else:
                # Not a duration, treat as string reps
                str_reps = str(reps_raw)

    # Handle explicit duration_sec field
    if duration_secs is None and ex_data.get("duration_sec"):
        duration_secs = int(ex_data["duration_sec"])

    # Parse load
    load = None
    weight = ex_data.get("weight")
    if weight is not None:
        try:
            value = float(weight)
            if value > 0:
                unit = ex_data.get("weight_unit", "lb")
                if unit.lower() in ("kg", "kgs"):
                    unit = "kg"
                else:
                    unit = "lb"
                load = Load(value=value, unit=unit)
        except (ValueError, TypeError):
            pass

    return Exercise(
        name=name,
        canonical_name=ex_data.get("canonical_name"),
        tempo=ex_data.get("tempo"),
        sets=ex_data.get("sets"),
        reps=int_reps if int_reps is not None else str_reps,
        duration_seconds=duration_secs,
        load=load,
        rest_seconds=ex_data.get("rest_sec"),
        notes=ex_data.get("notes"),
    )


def workout_to_blocks_json(workout: Workout) -> Dict[str, Any]:
    """
    Convert canonical Workout domain model to blocks_json format.

    This is the inverse of blocks_json_to_workout - converts the domain
    model back to the JSON structure expected by the web editor
    and stored in the database.

    Args:
        workout: Domain Workout to convert.

    Returns:
        Dictionary in blocks_json format.

    Examples:
        >>> from domain.models import Workout, Block, Exercise
        >>> workout = Workout(
        ...     title="My Workout",
        ...     blocks=[Block(exercises=[Exercise(name="Squat", sets=3, reps=10)])]
        ... )
        >>> blocks_json = workout_to_blocks_json(workout)
        >>> blocks_json["title"]
        'My Workout'
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

            # Serialize distance (if present - requires AMA-367)
            if hasattr(ex, 'distance') and ex.distance is not None:
                ex_data["distance"] = ex.distance
            if hasattr(ex, 'distance_unit') and ex.distance_unit is not None:
                ex_data["distance_unit"] = ex.distance_unit

            exercises_data.append(ex_data)

        block_data: Dict[str, Any] = {}

        if block.label:
            block_data["label"] = block.label

        # Serialize block type
        if block.type != BlockType.STRAIGHT:
            block_data["structure"] = block.type.value

        # Only write rounds > 1
        if block.rounds > 1:
            block_data["rounds"] = block.rounds

        if block.rest_between_seconds:
            block_data["rest_between_sec"] = block.rest_between_seconds

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

    # Include metadata
    if workout.metadata.sources or workout.metadata.platform or workout.metadata.source_url:
        result["metadata"] = {}
        if workout.metadata.sources:
            result["metadata"]["sources"] = [s.value for s in workout.metadata.sources]
        if workout.metadata.platform:
            result["metadata"]["platform"] = workout.metadata.platform
        if workout.metadata.source_url:
            result["metadata"]["source_url"] = workout.metadata.source_url

    return result
