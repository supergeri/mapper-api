# AMA-599: Shared interval utilities
# Extracted from api/routers/workouts.py and api/routers/sync.py to avoid duplication
from __future__ import annotations

from typing import Any


def calculate_intervals_duration(intervals: list) -> int:
    """
    Calculate total duration in seconds from intervals list.

    Recursively processes nested intervals (repeat blocks) and handles
    different interval types (time, reps, warmup, cooldown, distance).

    Args:
        intervals: List of interval dictionaries

    Returns:
        Total duration in seconds
    """
    total = 0
    for interval in intervals:
        kind = interval.get("kind")
        if kind == "time" or kind == "warmup" or kind == "cooldown":
            total += interval.get("seconds", 0)
        elif kind == "reps":
            # Estimate ~3 seconds per rep for rep-based exercises
            total += interval.get("reps", 0) * 3
            total += interval.get("restSec", 0) or 0
        elif kind == "repeat":
            # Recursive calculation for repeat intervals
            reps = interval.get("reps", 1)
            inner_duration = calculate_intervals_duration(interval.get("intervals", []))
            total += inner_duration * reps
        elif kind == "distance":
            # Estimate ~6 min/km for distance-based
            meters = interval.get("meters", 0)
            total += int(meters * 0.36)  # 6 min/km = 360s/1000m
    return total


def convert_exercise_to_interval(exercise: dict) -> dict:
    """
    Convert a workout exercise to iOS/Android companion interval format.

    Handles both rep-based and time-based exercises, including sets and rest times.

    Args:
        exercise: Exercise data dictionary

    Returns:
        Interval dictionary in companion app format
    """
    name = exercise.get("name", "Exercise")
    reps = exercise.get("reps")
    sets = exercise.get("sets", 1) or 1
    duration_sec = exercise.get("duration_sec")
    rest_sec = exercise.get("rest_sec", 60)
    follow_along_url = exercise.get("followAlongUrl")

    # Determine load string
    load_parts = []
    if exercise.get("load"):
        load_parts.append(exercise.get("load"))
    if sets and sets > 1:
        load_parts.append(f"{sets} sets")
    load_str = " + ".join(load_parts) if load_parts else None

    # Build the interval
    interval: dict[str, Any] = {
        "name": name,
        "kind": "reps" if reps else "time",
    }

    if reps:
        interval["reps"] = reps
        if rest_sec:
            interval["restSec"] = rest_sec

    if duration_sec:
        interval["seconds"] = duration_sec

    if load_str:
        interval["load"] = load_str

    if follow_along_url:
        interval["followAlongUrl"] = follow_along_url

    return interval
