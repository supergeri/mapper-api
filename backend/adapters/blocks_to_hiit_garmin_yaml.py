"""
Convert blocks JSON to Garmin Planner HIIT workout YAML format.

This converter handles HIIT workouts (for time, AMRAP, etc.) and outputs
Garmin Planner YAML format (Hyrox-style) with sport type "hiit".
"""
import yaml
import re
from datetime import datetime, timedelta
from backend.adapters.blocks_to_hyrox_yaml import (
    map_exercise_to_garmin,
    add_category_to_exercise_name
)


def is_hiit_workout(blocks_json: dict) -> bool:
    """Detect if a workout is a HIIT workout."""
    # Handle None or non-dict inputs gracefully
    if blocks_json is None or not isinstance(blocks_json, dict):
        return False
    
    for block in blocks_json.get("blocks", []):
        structure = block.get("structure") or ""
        structure = structure.lower() if structure else ""
        if "for time" in structure or "amrap" in structure or "emom" in structure:
            return True
        
        # Check if exercises have HIIT type
        for ex in block.get("exercises", []):
            if ex.get("type", "").upper() == "HIIT":
                return True
        
        for superset in block.get("supersets", []):
            for ex in superset.get("exercises", []):
                if ex.get("type", "").upper() == "HIIT":
                    return True
    
    return False


def to_hiit_garmin_yaml(blocks_json: dict) -> str:
    """
    Convert blocks JSON format to Garmin Planner HIIT workout YAML format.
    
    Output format (Garmin Planner YAML - Hyrox-style):
    settings:
      deleteSameNameWorkout: true
    workouts:
      "Workout Name":
        sport: hiit
        steps:
          - repeatUntilTime(35min):
            - run: lap | 1200m
            - "Exercise Name [category: CATEGORY]": "lap | notes"
    schedulePlan:
      start_from: '2025-11-05'
      workouts:
        - "Workout Name"
    """
    settings = {"deleteSameNameWorkout": True}
    workouts = {}
    
    workout_name = blocks_json.get("title", "HIIT Workout")
    workout_steps = []
    
    all_steps = []
    time_cap_sec = None
    
    # Process all blocks
    for block in blocks_json.get("blocks", []):
        # Check for time cap in structure (e.g., "for time (cap: 35 min)")
        structure = block.get("structure") or ""
        time_work_sec = block.get("time_work_sec")
        
        # Extract time cap if present
        if time_work_sec:
            time_cap_sec = time_work_sec
        elif structure and "cap:" in structure.lower():
            # Try to parse time cap from structure string
            cap_match = re.search(r'cap:\s*(\d+)\s*(min|minute|m)', structure, re.IGNORECASE)
            if cap_match:
                minutes = int(cap_match.group(1))
                time_cap_sec = minutes * 60
        
        # Process standalone exercises
        for ex in block.get("exercises", []):
            step = _exercise_to_garmin_planner_step(ex)
            if step:
                all_steps.append(step)
        
        # Process supersets (for HIIT, these are typically sequential exercises)
        for superset in block.get("supersets", []):
            for ex in superset.get("exercises", []):
                step = _exercise_to_garmin_planner_step(ex)
                if step:
                    all_steps.append(step)
    
    # If we have a time cap, wrap steps in repeatUntilTime
    if time_cap_sec and all_steps:
        # Convert seconds to minutes if < 1 hour, otherwise keep as seconds
        duration_min = time_cap_sec / 60
        if duration_min < 60:
            repeat_key = f"repeatUntilTime({int(duration_min)}min)"
        else:
            repeat_key = f"repeatUntilTime({time_cap_sec})"
        
        workout_steps.append({repeat_key: all_steps})
    else:
        workout_steps.extend(all_steps)
    
    workouts[workout_name] = {
        "sport": "hiit",
        "steps": workout_steps
    }
    
    # Create schedule plan (default to today + 7 days)
    start_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    schedule_plan = {
        "start_from": start_date,
        "workouts": [workout_name]
    }
    
    # Build final document
    doc = {
        "settings": settings,
        "workouts": workouts,
        "schedulePlan": schedule_plan
    }
    
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False, allow_unicode=True)


def _exercise_to_garmin_planner_step(ex: dict) -> dict:
    """
    Convert a single exercise to a Garmin Planner YAML step.
    
    Returns format like:
    - For running: {"run": "lap | 1200m"}
    - For exercises: {"Exercise Name [category: CATEGORY]": "lap | notes"}
    """
    ex_name = ex.get("name", "")
    reps = ex.get("reps")
    distance_m = ex.get("distance_m")
    duration_sec = ex.get("duration_sec")
    
    # Check if this is a running/cardio exercise
    normalized_name = ex_name.lower()
    is_running = "run" in normalized_name and distance_m is not None
    
    # Build notes/description from original exercise name and details
    original_clean = ex_name.strip()
    # Remove prefixes like "A1:", "B2:", etc.
    original_clean = re.sub(r'^[A-Z]\d+[:\s;]+', '', original_clean, flags=re.IGNORECASE).strip()
    
    # Check if reps/distance are already in the name to avoid duplication
    has_reps_in_name = bool(re.search(r'\b\d+\s+reps?\b', original_clean, re.IGNORECASE))
    has_distance_in_name = bool(re.search(r'\b\d+\s*m\b', original_clean, re.IGNORECASE))
    
    notes_parts = []
    
    # For running exercises, use distance in notes
    if is_running:
        notes = f"{distance_m}m"
        return {"run": f"lap | {notes}"}
    
    # For non-running exercises, add distance to notes if present and not already in name
    if distance_m is not None and not has_distance_in_name:
        notes_parts.append(f"{distance_m}m")
    
    # Add reps to notes if present and not already in name
    if reps is not None and not has_reps_in_name:
        # Check if the exact rep number appears at the start of the name (e.g., "80 Walking Lunges")
        # or as "X reps" format
        rep_at_start = bool(re.search(rf'^{reps}\s+', original_clean, re.IGNORECASE))
        rep_in_name = bool(re.search(rf'\b{reps}\s+reps?\b', original_clean, re.IGNORECASE))
        if not rep_at_start and not rep_in_name:
            notes_parts.append(f"{reps} reps")
    
    # Add time to notes if present
    if duration_sec is not None:
        notes_parts.append(f"{duration_sec}s")
    
    # Map exercise to Garmin name
    garmin_name, description, mapping_info = map_exercise_to_garmin(
        ex_name, 
        ex_reps=reps, 
        ex_distance_m=distance_m
    )
    
    # Add category to exercise name
    garmin_name_with_category = add_category_to_exercise_name(garmin_name)
    
    # Build notes string
    if notes_parts:
        notes = f"{original_clean} ({', '.join(notes_parts)})"
    elif original_clean:
        notes = original_clean
    else:
        notes = ""
    
    # Format as Garmin Planner YAML: "Exercise Name [category: CATEGORY]": "lap | notes"
    if notes:
        return {garmin_name_with_category: f"lap | {notes}"}
    else:
        return {garmin_name_with_category: "lap"}

