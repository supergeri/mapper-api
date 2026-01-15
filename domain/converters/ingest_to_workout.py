"""
Converter: Ingest format (ParsedWorkout) to domain Workout.

Part of AMA-390: Add converters for ingest and block formats

Converts ParsedWorkout/ParsedExercise from AI parsing output to the
canonical Workout domain model.
"""

from collections import defaultdict
from typing import List, Optional

from backend.parsers.models import ParsedExercise, ParsedWorkout

from domain.models import Block, BlockType, Exercise, Load, Workout, WorkoutMetadata, WorkoutSource


def _parse_reps(reps_str: str) -> tuple[Optional[int], Optional[str], Optional[int]]:
    """
    Parse reps string into (int_reps, string_reps, duration_seconds).

    Returns:
        Tuple of (int_reps, string_reps, duration_seconds).
        - int_reps: Integer value if reps is a simple number
        - string_reps: String value if reps is complex (e.g., "3+1", "AMRAP")
        - duration_seconds: Seconds if reps represents duration (e.g., "60s")
    """
    if not reps_str:
        return None, None, None

    reps_str = reps_str.strip()

    # Check for duration format (e.g., "60s", "30 sec", "45 seconds")
    lower = reps_str.lower()
    for suffix in ["s", "sec", "secs", "second", "seconds"]:
        if lower.endswith(suffix):
            num_part = reps_str[: -len(suffix)].strip()
            try:
                return None, None, int(float(num_part))
            except ValueError:
                break

    # Try to parse as integer
    try:
        return int(reps_str), None, None
    except ValueError:
        pass

    # Complex rep scheme (e.g., "3+1", "AMRAP", "8-10")
    return None, reps_str, None


def _parse_weight(
    weight_str: Optional[str], unit: Optional[str]
) -> Optional[Load]:
    """
    Parse weight string and unit into Load object.

    Args:
        weight_str: Weight value as string (e.g., "135", "60")
        unit: Unit string (e.g., "kg", "lbs", "lb")

    Returns:
        Load object or None if weight is not specified.
    """
    if not weight_str:
        return None

    try:
        value = float(weight_str)
        if value <= 0:
            return None

        # Normalize unit
        normalized_unit = "lb"  # default
        if unit:
            unit_lower = unit.lower().strip()
            if unit_lower in ("kg", "kgs", "kilogram", "kilograms"):
                normalized_unit = "kg"

        return Load(value=value, unit=normalized_unit)
    except (ValueError, TypeError):
        return None


def _group_exercises_by_superset(
    exercises: List[ParsedExercise],
) -> List[tuple[Optional[str], List[ParsedExercise]]]:
    """
    Group exercises by superset_group.

    Returns list of (group_id, exercises) tuples, preserving order.
    Exercises without a superset_group form their own groups.
    """
    groups: List[tuple[Optional[str], List[ParsedExercise]]] = []
    current_group_id: Optional[str] = None
    current_group: List[ParsedExercise] = []

    for ex in exercises:
        group_id = ex.superset_group

        if group_id == current_group_id:
            # Same group, add to current
            current_group.append(ex)
        else:
            # Different group, flush current and start new
            if current_group:
                groups.append((current_group_id, current_group))
            current_group_id = group_id
            current_group = [ex]

    # Flush final group
    if current_group:
        groups.append((current_group_id, current_group))

    return groups


def _convert_exercise(parsed: ParsedExercise) -> Exercise:
    """
    Convert ParsedExercise to domain Exercise.
    """
    int_reps, str_reps, duration_secs = _parse_reps(parsed.reps)
    load = _parse_weight(parsed.weight, parsed.weight_unit)

    return Exercise(
        name=parsed.raw_name,
        tempo=parsed.tempo,
        sets=parsed.sets,
        reps=int_reps if int_reps is not None else str_reps,
        duration_seconds=duration_secs,
        load=load,
        rest_seconds=parsed.rest_seconds,
        notes=parsed.notes,
    )


def ingest_to_workout(parsed: ParsedWorkout) -> Workout:
    """
    Convert ParsedWorkout (ingest format) to domain Workout.

    The ingest format is a flat list of exercises. This converter:
    1. Groups exercises by superset_group into blocks
    2. Determines block type (straight vs superset) based on grouping
    3. Preserves metadata from parsing

    Args:
        parsed: ParsedWorkout from AI parsing output.

    Returns:
        Canonical Workout domain model.

    Examples:
        >>> from backend.parsers.models import ParsedWorkout, ParsedExercise
        >>> parsed = ParsedWorkout(
        ...     name="Test Workout",
        ...     exercises=[
        ...         ParsedExercise(raw_name="Squat", sets=3, reps="10"),
        ...         ParsedExercise(raw_name="Bench Press", sets=3, reps="10"),
        ...     ]
        ... )
        >>> workout = ingest_to_workout(parsed)
        >>> workout.title
        'Test Workout'
        >>> workout.total_exercises
        2
    """
    # Group exercises by superset
    groups = _group_exercises_by_superset(parsed.exercises)

    # Convert groups to blocks
    blocks: List[Block] = []
    for group_id, group_exercises in groups:
        exercises = [_convert_exercise(ex) for ex in group_exercises]

        # Determine block type
        if group_id is not None and len(exercises) > 1:
            # Multiple exercises with same superset_group = superset
            block_type = BlockType.SUPERSET
            label = f"Superset {group_id}"
        else:
            block_type = BlockType.STRAIGHT
            label = None

        blocks.append(
            Block(
                label=label,
                type=block_type,
                exercises=exercises,
            )
        )

    # Create metadata
    sources = [WorkoutSource.AI]  # Ingest format comes from AI parsing
    metadata = WorkoutMetadata(sources=sources)

    return Workout(
        title=parsed.name,
        description=parsed.description,
        blocks=blocks,
        metadata=metadata,
    )
