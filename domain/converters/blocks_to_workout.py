"""
Converter: Blocks format (web editor JSON) to domain Workout.

Part of AMA-390: Add converters for ingest and block formats

Converts the blocks-based JSON format used by the web editor to the
canonical Workout domain model.
"""

import re
from typing import Any, Dict, List, Optional

from domain.models import Block, BlockType, Exercise, Load, Workout, WorkoutMetadata, WorkoutSource


def _parse_structure(structure_str: Optional[str]) -> int:
    """
    Parse structure string to get number of rounds.

    Args:
        structure_str: String like "3 rounds", "3", or None

    Returns:
        Number of rounds (default 1)
    """
    if not structure_str:
        return 1

    match = re.search(r"(\d+)", str(structure_str))
    return int(match.group(1)) if match else 1


def _parse_reps(reps_raw: Any) -> tuple[Optional[int], Optional[str], Optional[int]]:
    """
    Parse reps value into (int_reps, string_reps, duration_seconds).

    Args:
        reps_raw: Reps value (int, str, or None)

    Returns:
        Tuple of (int_reps, string_reps, duration_seconds).
    """
    if reps_raw is None:
        return None, None, None

    if isinstance(reps_raw, int):
        return reps_raw, None, None

    reps_str = str(reps_raw).strip()

    # Check for duration format (e.g., "60s", "30sec")
    lower = reps_str.lower()
    for suffix in ["s", "sec", "secs", "second", "seconds"]:
        if lower.endswith(suffix):
            num_part = reps_str[: -len(suffix)].strip()
            try:
                return None, None, int(float(num_part))
            except ValueError:
                break

    # Check for distance format (e.g., "500m", "1km") - treated as string reps
    if re.match(r"^[\d.]+\s*(m|km|mi)$", lower):
        return None, reps_str, None

    # Try to parse as integer
    try:
        return int(reps_str), None, None
    except ValueError:
        pass

    # Complex rep scheme (e.g., "3+1", "AMRAP", "8-10")
    return None, reps_str, None


def _parse_load(
    weight: Any, weight_unit: Optional[str] = None
) -> Optional[Load]:
    """
    Parse weight value into Load object.

    Args:
        weight: Weight value (number or string)
        weight_unit: Unit string (kg, lbs, lb)

    Returns:
        Load object or None
    """
    if weight is None:
        return None

    try:
        value = float(weight)
        if value <= 0:
            return None

        # Normalize unit
        unit = "lb"  # default
        if weight_unit:
            unit_lower = weight_unit.lower().strip()
            if unit_lower in ("kg", "kgs"):
                unit = "kg"

        return Load(value=value, unit=unit)
    except (ValueError, TypeError):
        return None


def _convert_exercise(ex_data: Dict[str, Any]) -> Exercise:
    """
    Convert exercise dict from blocks format to domain Exercise.
    """
    name = ex_data.get("name", "Exercise")
    int_reps, str_reps, duration_secs = _parse_reps(ex_data.get("reps"))

    # Handle explicit duration_sec field
    if duration_secs is None and ex_data.get("duration_sec"):
        duration_secs = int(ex_data["duration_sec"])

    # Parse load from weight/weight_unit
    load = _parse_load(ex_data.get("weight"), ex_data.get("weight_unit"))

    # Map rest_sec to rest_seconds
    rest_seconds = ex_data.get("rest_sec") or ex_data.get("rest_seconds")

    return Exercise(
        name=name,
        canonical_name=ex_data.get("canonical_name"),
        tempo=ex_data.get("tempo"),
        sets=ex_data.get("sets"),
        reps=int_reps if int_reps is not None else str_reps,
        duration_seconds=duration_secs,
        load=load,
        rest_seconds=rest_seconds,
        notes=ex_data.get("notes"),
    )


def _convert_block(block_data: Dict[str, Any]) -> List[Block]:
    """
    Convert block dict from blocks format to domain Block(s).

    A single block in the input format can produce multiple domain blocks
    if it contains both supersets and standalone exercises.
    """
    blocks: List[Block] = []

    # Get block-level settings
    label = block_data.get("label") or block_data.get("name")
    rounds = _parse_structure(block_data.get("structure"))
    rest_between = block_data.get("rest_between_rounds_sec") or block_data.get("rest_between_sec")

    # Process supersets
    supersets = block_data.get("supersets", [])
    for i, superset in enumerate(supersets):
        superset_exercises = superset.get("exercises", [])
        if superset_exercises:
            exercises = [_convert_exercise(ex) for ex in superset_exercises]

            # Determine block type based on exercise count
            if len(exercises) > 1:
                block_type = BlockType.SUPERSET
                superset_label = label or f"Superset {i + 1}"
            else:
                block_type = BlockType.STRAIGHT
                superset_label = label

            blocks.append(
                Block(
                    label=superset_label,
                    type=block_type,
                    rounds=rounds,
                    exercises=exercises,
                    rest_between_seconds=superset.get("rest_between_sec") or rest_between,
                )
            )

    # Process standalone exercises
    standalone = block_data.get("exercises", [])
    if standalone:
        exercises = [_convert_exercise(ex) for ex in standalone]
        blocks.append(
            Block(
                label=label,
                type=BlockType.STRAIGHT,
                rounds=rounds,
                exercises=exercises,
                rest_between_seconds=rest_between,
            )
        )

    return blocks


def blocks_to_workout(blocks_json: Dict[str, Any]) -> Workout:
    """
    Convert blocks format JSON to domain Workout.

    The blocks format is used by the web editor and has:
    - title: Workout name
    - blocks[]: Array of block objects
      - structure: "3 rounds" or "3"
      - supersets[]: Array of superset groups
        - exercises[]: Array of exercises in superset
      - exercises[]: Standalone exercises (not in superset)
      - rest_between_sec, rest_between_rounds_sec

    Each exercise has:
    - name: Exercise name
    - reps: Reps (int or string like "60s", "500m", "3+1")
    - sets: Number of sets
    - duration_sec: Duration in seconds
    - rest_sec: Rest after exercise
    - weight, weight_unit: Load

    Args:
        blocks_json: Dictionary with blocks format data.

    Returns:
        Canonical Workout domain model.

    Examples:
        >>> blocks_json = {
        ...     "title": "Full Body",
        ...     "blocks": [
        ...         {
        ...             "structure": "3 rounds",
        ...             "exercises": [
        ...                 {"name": "Squat", "reps": 10, "sets": 3},
        ...             ]
        ...         }
        ...     ]
        ... }
        >>> workout = blocks_to_workout(blocks_json)
        >>> workout.title
        'Full Body'
    """
    title = blocks_json.get("title") or blocks_json.get("name") or "Workout"
    description = blocks_json.get("description")
    notes = blocks_json.get("notes")
    tags = blocks_json.get("tags", [])

    # Convert blocks
    all_blocks: List[Block] = []
    for block_data in blocks_json.get("blocks", []):
        all_blocks.extend(_convert_block(block_data))

    # Ensure at least one block
    if not all_blocks:
        # Create a placeholder block if no exercises found
        raise ValueError("Workout must contain at least one block with exercises")

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
