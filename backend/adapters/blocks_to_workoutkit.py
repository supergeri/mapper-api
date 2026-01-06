"""Converter from blocks JSON format to Apple WorkoutKit DTO format."""
import re
from typing import List, Optional
from backend.adapters.workoutkit_schemas import (
    WKPlanDTO,
    WKIntervalDTO,
    WKStepDTO,
    TimeStep,
    DistanceStep,
    RepsStep,
    RestStep,
    WarmupInterval,
    CooldownInterval,
    RepeatInterval,
    Schedule,
)
from backend.adapters.blocks_to_hyrox_yaml import (
    map_exercise_to_garmin,
    extract_rounds,
)


def parse_exercise_name(ex_name: str) -> str:
    """Extract clean exercise name from formatted name like 'A1: EXERCISE X10'."""
    if not ex_name:
        return ""
    # Remove prefix like "A1:", "B2:", etc.
    clean = re.sub(r'^[A-Z]\d+[:\s;]+', '', ex_name, flags=re.IGNORECASE).strip()
    # Remove trailing patterns like "X10", "X5", "wb", etc.
    clean = re.sub(r'\s+X\s*\d+.*$', '', clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\s+wb$', '', clean, flags=re.IGNORECASE).strip()
    return clean


def exercise_to_step(exercise: dict, default_rest_sec: Optional[int] = None) -> Optional[WKStepDTO]:
    """Convert a single exercise to a WKStepDTO."""
    ex_name = exercise.get("name", "")
    reps = exercise.get("reps")
    duration_sec = exercise.get("duration_sec")
    rest_sec = exercise.get("rest_sec") or default_rest_sec
    distance_m = exercise.get("distance_m")
    distance_range = exercise.get("distance_range")
    
    # Get mapped exercise name (use Garmin mapping for reps steps)
    garmin_name, _, _ = map_exercise_to_garmin(
        ex_name,
        ex_reps=reps,
        ex_distance_m=distance_m
    )

    # Use the clean exercise name for display (AMA-243: preserve original name)
    clean_name = parse_exercise_name(ex_name)
    # For reps steps, use Garmin name if available; for time/distance steps, use clean name
    garmin_exercise_name = garmin_name if garmin_name else clean_name
    display_name = clean_name  # Use original name for iOS display (AMA-243)
    
    # Check for "EACH SIDE" pattern and extract reps if present
    each_side_match = re.search(r'X\s*(\d+)\s+EACH\s+SIDE', ex_name, re.IGNORECASE)
    if each_side_match and reps is None:
        # If exercise has "X § EACH SIDE" or similar, use a default rep count
        # For single-arm exercises, typically we do both sides
        reps_from_name = each_side_match.group(1)
        if reps_from_name.isdigit():
            reps = int(reps_from_name) * 2  # Both sides
        else:
            reps = 10  # Default for "EACH SIDE" without number
    
    # Priority: time > distance > reps
    if duration_sec is not None:
        return TimeStep(
            kind="time",
            seconds=duration_sec,
            target=display_name or None  # Exercise name for iOS display (AMA-243)
        )

    if distance_m is not None:
        return DistanceStep(
            kind="distance",
            meters=distance_m,
            target=display_name or None  # Exercise name for iOS display (AMA-243)
        )

    if distance_range:
        # Parse distance range like "25-30m" - take average or max
        match = re.search(r'(\d+)-(\d+)', distance_range)
        if match:
            min_dist = int(match.group(1))
            max_dist = int(match.group(2))
            avg_dist = (min_dist + max_dist) // 2
            return DistanceStep(
                kind="distance",
                meters=avg_dist,
                target=display_name or None  # Exercise name for iOS display (AMA-243)
            )
    
    # Default to reps if available, otherwise use time-based
    if reps is not None:
        return RepsStep(
            kind="reps",
            reps=reps,
            name=garmin_exercise_name,  # Use Garmin name for reps (structured data)
            load=None,  # Can be extended later if load info is available
            restSec=rest_sec
        )

    # If no reps, check for reps_range
    reps_range = exercise.get("reps_range")
    if reps_range:
        # Parse range like "6-10" - take average
        match = re.search(r'(\d+)-(\d+)', reps_range)
        if match:
            min_reps = int(match.group(1))
            max_reps = int(match.group(2))
            avg_reps = (min_reps + max_reps) // 2
            return RepsStep(
                kind="reps",
                reps=avg_reps,
                name=garmin_exercise_name,  # Use Garmin name for reps (structured data)
                load=None,
                restSec=rest_sec
            )

    # Check for "EACH SIDE" without number - default to 10 reps (5 each side)
    if re.search(r'EACH\s+SIDE', ex_name, re.IGNORECASE) and reps is None:
        return RepsStep(
            kind="reps",
            reps=10,  # Default: 5 each side
            name=garmin_exercise_name,  # Use Garmin name for reps (structured data)
            load=None,
            restSec=rest_sec
        )

    # Final fallback: time-based with 60 seconds if no other info
    return TimeStep(
        kind="time",
        seconds=duration_sec if duration_sec else 60,
        target=display_name or None  # Exercise name for iOS display (AMA-243)
    )


def block_to_intervals(block: dict, default_rest_sec: Optional[int] = None) -> List[WKIntervalDTO]:
    """Convert a block to WorkoutKit intervals.

    For strength training with sets:
    - Each exercise with sets > 1 is wrapped in a RepeatInterval
    - Rest between sets is included in the repeat

    Args:
        block: The block data from workout JSON
        default_rest_sec: Default rest time from workout settings (used if exercise has no rest_sec)
    """
    structure = block.get("structure", "")
    rounds = extract_rounds(structure) if structure else 1
    rest_between_sec = block.get("rest_between_sec")
    time_work_sec = block.get("time_work_sec")

    intervals: List[WKIntervalDTO] = []

    # If this is an interval block (time_work_sec is set), handle it specially
    if time_work_sec:
        # Check if exercises have duration_sec and rest_sec (like "SKIER 60S ON 90S OFF X3")
        exercises = block.get("exercises", [])
        if exercises:
            ex = exercises[0]
            duration_sec = ex.get("duration_sec") or time_work_sec
            rest_sec = ex.get("rest_sec") or rest_between_sec or default_rest_sec
            # Get exercise name for display (AMA-243)
            ex_name = parse_exercise_name(ex.get("name", ""))

            # Create work interval with exercise name
            work_step = TimeStep(kind="time", seconds=duration_sec, target=ex_name or None)
            interval_steps: List[WKStepDTO] = [work_step]

            # Add rest interval
            if rest_sec:
                rest_step = RestStep(kind="rest", seconds=rest_sec)
                interval_steps.append(rest_step)

            # Get number of sets/reps from exercise or block structure
            sets = ex.get("sets") or rounds

            # Wrap in repeat
            if sets > 1:
                return [RepeatInterval(kind="repeat", reps=sets, intervals=interval_steps)]
            else:
                return interval_steps
        else:
            # Fallback: use time_work_sec and rest_between_sec (no exercise name available)
            work_step = TimeStep(kind="time", seconds=time_work_sec, target=None)
            interval_steps: List[WKStepDTO] = [work_step]

            if rest_between_sec or default_rest_sec:
                rest_step = RestStep(kind="rest", seconds=rest_between_sec or default_rest_sec)
                interval_steps.append(rest_step)

            if rounds > 1:
                return [RepeatInterval(kind="repeat", reps=rounds, intervals=interval_steps)]
            else:
                return interval_steps

    # Process standalone exercises - handle sets for strength training
    for ex in block.get("exercises", []):
        step = exercise_to_step(ex, default_rest_sec)
        if step:
            sets = ex.get("sets")
            rest_sec = ex.get("rest_sec") or default_rest_sec

            # If exercise has multiple sets, wrap in RepeatInterval
            if sets and sets > 1:
                # Create interval with exercise step and rest between sets
                set_intervals: List[WKStepDTO] = [step]
                if rest_sec:
                    set_intervals.append(RestStep(kind="rest", seconds=rest_sec))
                intervals.append(RepeatInterval(kind="repeat", reps=sets, intervals=set_intervals))
            else:
                intervals.append(step)

    # Process supersets
    for superset_idx, superset in enumerate(block.get("supersets", [])):
        superset_steps: List[WKStepDTO] = []

        for ex_idx, ex in enumerate(superset.get("exercises", [])):
            step = exercise_to_step(ex, default_rest_sec)
            if step:
                superset_steps.append(step)
                # Add rest between exercises in superset if specified
                superset_rest = superset.get("rest_between_sec")
                if superset_rest and ex_idx < len(superset.get("exercises", [])) - 1:
                    # Add rest step between exercises (not after last one)
                    rest_step = RestStep(kind="rest", seconds=superset_rest)
                    superset_steps.append(rest_step)

        # Add rest between supersets if specified and not the last superset
        if rest_between_sec and superset_idx < len(block.get("supersets", [])) - 1:
            rest_step = RestStep(kind="rest", seconds=rest_between_sec)
            superset_steps.append(rest_step)

        # Handle superset sets - wrap in repeat if needed
        superset_sets = superset.get("sets") or 1
        if superset_sets > 1:
            intervals.append(RepeatInterval(kind="repeat", reps=superset_sets, intervals=superset_steps))
        else:
            intervals.extend(superset_steps)

    # If we have multiple intervals and rounds > 1 (circuit structure), wrap all in repeat
    if len(intervals) > 0 and rounds > 1:
        return [RepeatInterval(kind="repeat", reps=rounds, intervals=intervals)]

    return intervals


def to_workoutkit(blocks_json: dict) -> WKPlanDTO:
    """Convert blocks JSON to WorkoutKit DTO format.

    Handles:
    - Workout-level warmup from settings.workoutWarmup
    - Default rest times from settings.defaultRestSec
    - Sets for strength exercises (wrapped in RepeatInterval)
    - Blocks labeled as warmup/cooldown
    """
    title = blocks_json.get("title", "Imported Workout")
    intervals: List[WKIntervalDTO] = []

    # Extract workout settings
    settings = blocks_json.get("settings", {})
    default_rest_sec = settings.get("defaultRestSec")
    default_rest_type = settings.get("defaultRestType", "button")

    # Only use timed rest if type is 'timed', otherwise don't add automatic rest
    if default_rest_type != "timed":
        default_rest_sec = None

    # Check for workout-level warmup from settings
    workout_warmup = settings.get("workoutWarmup", {})
    if workout_warmup.get("enabled"):
        warmup_duration = workout_warmup.get("durationSec", 300)
        intervals.append(WarmupInterval(
            kind="warmup",
            seconds=warmup_duration,
            target=None
        ))

    # Process each block
    for block in blocks_json.get("blocks", []):
        block_label = block.get("label", "").lower()
        has_exercises = len(block.get("exercises", [])) > 0 or len(block.get("supersets", [])) > 0

        # Check if this is a warmup or cooldown block
        if "warmup" in block_label or "primer" in block_label:
            # If block has exercises, convert them to intervals (don't add separate warmup)
            if has_exercises:
                block_intervals = block_to_intervals(block, default_rest_sec)
                intervals.extend(block_intervals)
            else:
                # No exercises, just add a warmup interval (if not already added from settings)
                if not workout_warmup.get("enabled"):
                    warmup_duration = block.get("time_work_sec") or 300  # 5 minutes default
                    intervals.append(WarmupInterval(
                        kind="warmup",
                        seconds=warmup_duration,
                        target=None
                    ))
        elif "cooldown" in block_label:
            # If block has exercises, convert them to intervals (don't add separate cooldown)
            if has_exercises:
                block_intervals = block_to_intervals(block, default_rest_sec)
                intervals.extend(block_intervals)
            else:
                # No exercises, just add a cooldown interval
                cooldown_duration = block.get("time_work_sec") or 300  # 5 minutes default
                intervals.append(CooldownInterval(
                    kind="cooldown",
                    seconds=cooldown_duration,
                    target=None
                ))
        else:
            # Regular block - convert to intervals
            block_intervals = block_to_intervals(block, default_rest_sec)
            intervals.extend(block_intervals)

    # Determine sport type - default to strengthTraining for workout plans
    sport_type = "strengthTraining"

    # Create schedule if source has date info (can be extended)
    schedule = None

    return WKPlanDTO(
        title=title,
        sportType=sport_type,
        intervals=intervals,
        schedule=schedule
    )

