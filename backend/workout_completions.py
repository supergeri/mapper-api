"""
Workout Completions module for storing health metrics from Apple Watch (AMA-189).
Handles saving and retrieving workout completion data with heart rate, calories, etc.
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class HealthMetrics(BaseModel):
    """Health metrics captured during workout."""
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    min_heart_rate: Optional[int] = None
    active_calories: Optional[int] = None
    total_calories: Optional[int] = None
    distance_meters: Optional[int] = None
    steps: Optional[int] = None


class SimulationConfig(BaseModel):
    """Simulation parameters when workout is run in simulation mode (AMA-273)."""
    speed: Optional[float] = None  # e.g., 10.0 for 10x speed
    behavior_profile: Optional[str] = None  # "efficient", "casual", "distracted"
    hr_profile: Optional[str] = None  # "athletic", "average"


class SetEntry(BaseModel):
    """Individual set within an exercise log (AMA-281)."""
    set_number: int
    weight: Optional[float] = None  # Weight used (null if skipped)
    unit: Optional[str] = None  # "lbs" or "kg" (null if weight not logged)
    completed: bool = True  # Whether the set was completed


class SetLog(BaseModel):
    """Log of sets for a single exercise (AMA-281)."""
    exercise_name: str
    exercise_index: int  # Position in the workout structure
    sets: List[SetEntry]


# AMA-290: Execution log models for capturing actual workout execution
class IntervalSetExecution(BaseModel):
    """Execution data for a single set within an interval (AMA-290)."""
    set_number: int
    status: str = "completed"  # "completed", "skipped"
    reps_completed: Optional[int] = None
    weight: Optional[float] = None
    unit: Optional[str] = None  # "lbs" or "kg"
    duration_sec: Optional[int] = None
    rpe: Optional[int] = None  # Rate of Perceived Exertion (1-10)


class IntervalExecution(BaseModel):
    """Execution data for a single interval (AMA-290)."""
    interval_index: int
    kind: Optional[str] = None  # "warmup", "cooldown", "work", "rest", "reps"
    name: Optional[str] = None
    status: str = "completed"  # "completed", "skipped", "modified"
    planned_duration_sec: Optional[int] = None
    actual_duration_sec: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    planned: Optional[Dict[str, Any]] = None  # For reps: {"sets": 4, "reps": 10}
    sets: Optional[List[IntervalSetExecution]] = None  # For reps-based intervals


class ExecutionSummary(BaseModel):
    """Summary statistics for execution log (AMA-290)."""
    total_intervals: int = 0
    completed: int = 0
    skipped: int = 0
    modified: int = 0
    completion_percentage: float = 0


class ExecutionLog(BaseModel):
    """Full execution log structure (AMA-290)."""
    intervals: List[IntervalExecution] = []
    summary: Optional[ExecutionSummary] = None


class WorkoutCompletionRequest(BaseModel):
    """Request from iOS app when workout completes."""
    workout_event_id: Optional[str] = None
    follow_along_workout_id: Optional[str] = None
    workout_id: Optional[str] = None  # For iOS Companion workouts from workouts table
    started_at: str  # ISO format
    ended_at: str    # ISO format
    health_metrics: HealthMetrics
    source: str = "apple_watch"  # 'apple_watch', 'garmin', 'manual'
    source_workout_id: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None
    heart_rate_samples: Optional[List[Dict[str, Any]]] = None  # [{t, bpm}, ...]
    workout_structure: Optional[List[Dict[str, Any]]] = None  # Original workout intervals (AMA-240)
    intervals: Optional[List[Dict[str, Any]]] = None  # Backwards compat alias for workout_structure
    # Weight tracking (AMA-281) - deprecated, use execution_log instead
    set_logs: Optional[List[SetLog]] = None  # Logged weights per exercise/set
    # Execution log (AMA-290) - captures actual execution vs planned
    execution_log: Optional[Dict[str, Any]] = None
    # Simulation fields (AMA-273)
    is_simulated: bool = False
    simulation_config: Optional[SimulationConfig] = None


class WorkoutCompletionSummary(BaseModel):
    """Summary returned after saving completion."""
    duration_formatted: str
    avg_heart_rate: Optional[int] = None
    calories: Optional[int] = None


class WorkoutCompletionResponse(BaseModel):
    """Response after saving workout completion."""
    success: bool
    id: Optional[str] = None
    summary: Optional[WorkoutCompletionSummary] = None
    message: Optional[str] = None


# ============================================================================
# Helper Functions
# ============================================================================

def format_duration(seconds: int) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS."""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def calculate_duration_seconds(started_at: str, ended_at: str) -> int:
    """Calculate duration in seconds between two ISO timestamps."""
    try:
        start = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        end = datetime.fromisoformat(ended_at.replace('Z', '+00:00'))
        return int((end - start).total_seconds())
    except Exception as e:
        logger.error(f"Error calculating duration: {e}")
        return 0


def _execution_log_has_detailed_data(execution_log: Dict[str, Any]) -> bool:
    """
    Check if execution_log has detailed data that would be lost if rebuilt from set_logs.

    AMA-314: Returns True if the execution_log has interval-level data like
    actual_duration_seconds or set-level data like reps_planned that isn't in set_logs.
    """
    intervals = execution_log.get("intervals", [])
    if not intervals:
        return False

    # Check if any interval has duration data or detailed set data
    for interval in intervals:
        # Check for duration data
        if interval.get("actual_duration_seconds") is not None:
            return True
        if interval.get("started_at") is not None:
            return True

        # Check sets for detailed data
        sets = interval.get("sets", [])
        for set_data in sets:
            if set_data.get("reps_planned") is not None:
                return True
            if set_data.get("duration_seconds") is not None:
                return True

    return False


def _merge_weights_into_execution_log(
    execution_log: Dict[str, Any],
    set_logs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Merge weight data from set_logs into an existing execution_log.

    AMA-314: This preserves the detailed interval data (duration, reps_planned, etc.)
    from execution_log while adding weight information from set_logs.
    """
    if not set_logs:
        return execution_log

    # Build lookup: exercise_index -> set_log
    set_log_map = {}
    for log in set_logs:
        idx = log.get("exercise_index")
        if idx is not None:
            set_log_map[idx] = log

    intervals = execution_log.get("intervals", [])
    updated_intervals = []

    for interval in intervals:
        idx = interval.get("interval_index")
        matching_log = set_log_map.get(idx)

        if matching_log and matching_log.get("sets"):
            # Merge weight data into existing sets
            existing_sets = interval.get("sets", [])
            set_logs_data = matching_log["sets"]

            updated_sets = []
            for i, existing_set in enumerate(existing_sets):
                updated_set = {**existing_set}
                # Find matching set_log entry by set_number
                set_num = existing_set.get("set_number", i + 1)
                if set_num <= len(set_logs_data):
                    set_entry = set_logs_data[set_num - 1]
                    weight_val = set_entry.get("weight")
                    unit = set_entry.get("unit", "lbs")
                    if weight_val is not None and updated_set.get("weight") is None:
                        updated_set["weight"] = {
                            "components": [{"source": "manual", "value": weight_val, "unit": unit}],
                            "display_label": f"{weight_val} {unit}"
                        }
                updated_sets.append(updated_set)

            updated_intervals.append({**interval, "sets": updated_sets})
        else:
            updated_intervals.append(interval)

    return {**execution_log, "intervals": updated_intervals}


def _get_or_build_execution_log(
    record: Dict[str, Any],
    workout_structure: Optional[List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """
    Get execution_log from record or build it from set_logs.

    AMA-314: Prioritize stored execution_log when it has detailed data
    (duration, reps_planned) that would be lost if rebuilt from set_logs.
    """
    set_logs = record.get("set_logs")
    stored_execution_log = record.get("execution_log")
    completion_id = record.get("id", "unknown")

    logger.info(f"[AMA-314] _get_or_build_execution_log for {completion_id}: "
                f"set_logs={bool(set_logs)} ({len(set_logs) if set_logs else 0} items), "
                f"stored_execution_log={bool(stored_execution_log)}")

    # AMA-314: If we have stored execution_log with detailed data, use it
    # and optionally merge weight data from set_logs
    if stored_execution_log and _execution_log_has_detailed_data(stored_execution_log):
        result = _fix_execution_log_names(stored_execution_log, workout_structure)
        if set_logs:
            # Merge weight data from set_logs into the detailed execution_log
            result = _merge_weights_into_execution_log(result, set_logs)
            logger.info(f"[AMA-314] Using detailed execution_log with merged weights: "
                        f"{len(result.get('intervals', []))} intervals")
        else:
            logger.info(f"[AMA-314] Using detailed execution_log: "
                        f"{len(result.get('intervals', []))} intervals")
        return result

    # If we have set_logs but no detailed execution_log, rebuild from set_logs
    if set_logs:
        result = merge_set_logs_to_execution_log(workout_structure, set_logs)
        logger.info(f"[AMA-314] Built execution_log from set_logs: "
                    f"{len(result.get('intervals', []))} intervals")
        return result

    # Fall back to stored execution_log (even without detailed data)
    if stored_execution_log:
        result = _fix_execution_log_names(stored_execution_log, workout_structure)
        logger.info(f"[AMA-314] Using stored execution_log: "
                    f"{len(result.get('intervals', []))} intervals")
        return result

    logger.info(f"[AMA-314] No execution_log data available for {completion_id}")
    return None


def _fix_execution_log_names(
    execution_log: Dict[str, Any],
    workout_structure: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """
    Fix missing planned_name values in stored execution_log.

    Adds fallback names from workout_structure or generates "Exercise N" names.
    Also ensures sequential set numbering within each interval.
    """
    intervals = execution_log.get("intervals", [])
    if not intervals:
        return execution_log

    # Build name lookup from workout_structure
    structure_names = {}
    if workout_structure:
        for i, interval in enumerate(workout_structure):
            name = interval.get("name") or interval.get("target")
            if name:
                structure_names[i] = name

    # Fix each interval
    fixed_intervals = []
    for interval in intervals:
        idx = interval.get("interval_index", 0)
        planned_name = interval.get("planned_name")

        # Fix missing name
        if not planned_name:
            planned_name = structure_names.get(idx) or f"Exercise {idx + 1}"

        fixed_interval = {**interval, "planned_name": planned_name}

        # Fix set numbering if sets exist
        sets = fixed_interval.get("sets", [])
        if sets:
            fixed_sets = []
            for i, s in enumerate(sets):
                fixed_set = {**s, "set_number": i + 1}
                fixed_sets.append(fixed_set)
            fixed_interval["sets"] = fixed_sets

        fixed_intervals.append(fixed_interval)

    return {**execution_log, "intervals": fixed_intervals}


def merge_set_logs_to_execution_log(
    workout_structure: Optional[List[Dict[str, Any]]],
    set_logs: Optional[List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """
    Convert legacy set_logs to execution_log format (AMA-290).

    When set_logs is provided but execution_log is not, build an execution_log
    from the set_logs data merged with workout_structure intervals.

    Args:
        workout_structure: List of planned intervals from the workout
        set_logs: Legacy set_logs data with weight entries

    Returns:
        ExecutionLog dict or None if no data to merge
    """
    if not set_logs:
        return None

    # Build a lookup map from exercise_index to set_log
    set_log_map = {}
    for log in set_logs:
        idx = log.get("exercise_index")
        if idx is not None:
            set_log_map[idx] = log

    intervals = []
    completed_count = 0
    skipped_count = 0

    # If we have workout_structure, iterate through all intervals
    if workout_structure:
        for i, interval in enumerate(workout_structure):
            # Check if this interval has matching set_log data
            matching_log = set_log_map.get(i)

            # Get planned_name from workout_structure, fallback to exercise_name from set_log
            planned_name = (
                interval.get("name") or
                interval.get("target") or
                (matching_log.get("exercise_name") if matching_log else None) or
                f"Exercise {i + 1}"  # Last resort fallback
            )

            interval_log = {
                "interval_index": i,
                "planned_kind": interval.get("kind") or interval.get("type"),
                "planned_name": planned_name,
                "status": "completed",  # Default for intervals with set_logs
            }

            if matching_log and matching_log.get("sets"):
                # Convert set_logs format to execution_log sets format
                exec_sets = []
                set_number = 1  # Sequential numbering within this interval
                for set_entry in matching_log["sets"]:
                    # Build weight object in the format iOS expects
                    weight_obj = None
                    weight_val = set_entry.get("weight")
                    unit = set_entry.get("unit", "lbs")
                    if weight_val is not None:
                        weight_obj = {
                            "components": [{"source": "manual", "value": weight_val, "unit": unit}],
                            "display_label": f"{weight_val} {unit}"
                        }
                    exec_set = {
                        "set_number": set_number,  # Sequential within interval
                        "status": "completed" if set_entry.get("completed", True) else "skipped",
                        "weight": weight_obj,
                        "reps_completed": set_entry.get("reps_completed"),
                    }
                    exec_sets.append(exec_set)
                    set_number += 1
                interval_log["sets"] = exec_sets
                completed_count += 1
            else:
                # Interval without set_log data - mark as completed (we only have data for reps exercises)
                completed_count += 1

            intervals.append(interval_log)
    else:
        # No workout_structure - group set_logs by exercise name
        # Group by exercise_name to combine sets for the same exercise
        from collections import OrderedDict
        exercise_groups: OrderedDict[str, list] = OrderedDict()

        for log in set_logs:
            exercise_name = log.get("exercise_name", "Unknown Exercise")
            if exercise_name not in exercise_groups:
                exercise_groups[exercise_name] = []
            exercise_groups[exercise_name].append(log)

        # Create one interval per exercise group
        for interval_idx, (exercise_name, logs) in enumerate(exercise_groups.items()):
            interval_log = {
                "interval_index": interval_idx,
                "planned_kind": "reps",
                "planned_name": exercise_name,
                "status": "completed",
            }

            exec_sets = []
            set_number = 1
            for log in logs:
                if log.get("sets"):
                    for set_entry in log["sets"]:
                        # Build weight object in the format iOS expects
                        weight_obj = None
                        weight_val = set_entry.get("weight")
                        unit = set_entry.get("unit", "lbs")
                        if weight_val is not None:
                            weight_obj = {
                                "components": [{"source": "manual", "value": weight_val, "unit": unit}],
                                "display_label": f"{weight_val} {unit}"
                            }
                        exec_set = {
                            "set_number": set_number,
                            "status": "completed" if set_entry.get("completed", True) else "skipped",
                            "weight": weight_obj,
                            "reps_completed": set_entry.get("reps_completed"),
                        }
                        exec_sets.append(exec_set)
                        set_number += 1

            interval_log["sets"] = exec_sets
            intervals.append(interval_log)
            completed_count += 1

    total = len(intervals)
    # Count total sets from intervals
    total_sets = sum(len(i.get("sets", [])) for i in intervals)
    sets_completed = sum(
        sum(1 for s in i.get("sets", []) if s.get("status") == "completed")
        for i in intervals
    )
    sets_skipped = total_sets - sets_completed

    summary = {
        "total_intervals": total,
        "completed": completed_count,
        "skipped": skipped_count,
        "not_reached": 0,  # iOS expects this field
        "completion_percentage": round((completed_count / total) * 100, 1) if total > 0 else 0,
        "total_sets": total_sets,
        "sets_completed": sets_completed,
        "sets_skipped": sets_skipped,
        "total_duration_seconds": 0,  # Not available from set_logs
        "active_duration_seconds": 0,  # Not available from set_logs
    }

    return {
        "version": 2,  # v2 execution_log format
        "intervals": intervals,
        "summary": summary
    }


# ============================================================================
# Database Operations
# ============================================================================

def get_supabase_client():
    """Get Supabase client - imported from database module."""
    from backend.database import get_supabase_client as _get_client
    return _get_client()


def save_workout_completion(
    user_id: str,
    request: WorkoutCompletionRequest
) -> Dict[str, Any]:
    """
    Save a workout completion record to the database.

    Args:
        user_id: The Clerk user ID
        request: Workout completion data from iOS app

    Returns:
        Dict with completion info on success, or error details on failure.
        Success: {"success": True, "id": str, "summary": dict}
        Failure: {"success": False, "error": str, "error_code": str}
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return {
            "success": False,
            "error": "Database connection unavailable",
            "error_code": "DB_UNAVAILABLE"
        }

    try:
        # Calculate duration
        duration_seconds = calculate_duration_seconds(request.started_at, request.ended_at)

        # Build record
        # Use workout_structure if provided, otherwise fall back to intervals for backwards compat (AMA-240)
        workout_structure = request.workout_structure or request.intervals

        record = {
            "user_id": user_id,
            "workout_event_id": request.workout_event_id,
            "follow_along_workout_id": request.follow_along_workout_id,
            "workout_id": request.workout_id,
            "started_at": request.started_at,
            "ended_at": request.ended_at,
            "duration_seconds": duration_seconds,
            "avg_heart_rate": request.health_metrics.avg_heart_rate,
            "max_heart_rate": request.health_metrics.max_heart_rate,
            "min_heart_rate": request.health_metrics.min_heart_rate,
            "active_calories": request.health_metrics.active_calories,
            "total_calories": request.health_metrics.total_calories,
            "distance_meters": request.health_metrics.distance_meters,
            "steps": request.health_metrics.steps,
            "source": request.source,
            "source_workout_id": request.source_workout_id,
            "device_info": request.device_info,
            "heart_rate_samples": request.heart_rate_samples,
            "workout_structure": workout_structure,  # AMA-240
        }

        # AMA-281: Add set_logs if provided (weight tracking)
        if request.set_logs:
            record["set_logs"] = [log.model_dump() for log in request.set_logs]

        # AMA-290: Handle execution_log
        # If execution_log provided directly, use it
        # Otherwise, if set_logs provided, merge into execution_log format
        if request.execution_log:
            record["execution_log"] = request.execution_log
        elif request.set_logs:
            # Convert set_logs to execution_log format for unified storage
            set_logs_dicts = [log.model_dump() for log in request.set_logs]
            merged_execution_log = merge_set_logs_to_execution_log(
                workout_structure,
                set_logs_dicts
            )
            if merged_execution_log:
                record["execution_log"] = merged_execution_log

        # AMA-273: Only add simulation fields if simulated (backwards compat for pre-migration)
        # This allows inserts to work even if the columns don't exist yet
        if request.is_simulated:
            record["is_simulated"] = True
            if request.simulation_config:
                record["simulation_config"] = request.simulation_config.model_dump()

        # Insert into database
        result = supabase.table("workout_completions").insert(record).execute()

        if result.data and len(result.data) > 0:
            saved = result.data[0]
            logger.info(f"Workout completion saved for user {user_id}: {saved['id']}")

            # Build summary
            summary = WorkoutCompletionSummary(
                duration_formatted=format_duration(duration_seconds),
                avg_heart_rate=request.health_metrics.avg_heart_rate,
                calories=request.health_metrics.active_calories
            )

            response = {
                "success": True,
                "id": saved["id"],
                "summary": summary.model_dump(),
            }
            # AMA-273: Only include is_simulated in response if true
            if request.is_simulated:
                response["is_simulated"] = True
            return response
        else:
            logger.error("Failed to insert workout completion: empty result from database")
            return {
                "success": False,
                "error": "Database insert returned empty result",
                "error_code": "INSERT_FAILED"
            }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error saving workout completion: {error_msg}")

        # Provide specific error messages for common issues
        if "violates foreign key constraint" in error_msg:
            if "profiles" in error_msg:
                return {
                    "success": False,
                    "error": "User profile not found. Please ensure your account is fully set up.",
                    "error_code": "PROFILE_NOT_FOUND"
                }
            elif "follow_along_workouts" in error_msg:
                return {
                    "success": False,
                    "error": "Follow-along workout not found",
                    "error_code": "WORKOUT_NOT_FOUND"
                }
            elif "workout_events" in error_msg:
                return {
                    "success": False,
                    "error": "Workout event not found",
                    "error_code": "EVENT_NOT_FOUND"
                }
            elif "workouts" in error_msg:
                return {
                    "success": False,
                    "error": "Workout not found",
                    "error_code": "WORKOUT_NOT_FOUND"
                }
        elif "row-level security" in error_msg.lower() or "permission denied" in error_msg.lower():
            logger.error("RLS/Permissions error: Check SUPABASE_SERVICE_ROLE_KEY configuration")
            return {
                "success": False,
                "error": "Permission denied. Please contact support.",
                "error_code": "RLS_ERROR"
            }
        elif "violates check constraint" in error_msg:
            return {
                "success": False,
                "error": "Either workout_event_id or follow_along_workout_id is required",
                "error_code": "MISSING_WORKOUT_LINK"
            }

        return {
            "success": False,
            "error": "Failed to save workout completion",
            "error_code": "UNKNOWN_ERROR"
        }


def get_user_completions(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    include_simulated: bool = True  # AMA-273: Filter simulated completions
) -> Dict[str, Any]:
    """
    Get workout completions for a user.

    Args:
        user_id: The Clerk user ID
        limit: Max number of records to return
        offset: Number of records to skip
        include_simulated: Whether to include simulated completions (default True)

    Returns:
        Dict with completions list and total count
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return {"completions": [], "total": 0}

    try:
        # Get completions with workout names via joins
        # Note: We select basic fields, excluding heart_rate_samples for list view
        # AMA-274: Don't explicitly select is_simulated (column may not exist yet)
        query = supabase.table("workout_completions") \
            .select(
                "id, started_at, ended_at, duration_seconds, "
                "avg_heart_rate, max_heart_rate, min_heart_rate, active_calories, total_calories, "
                "distance_meters, steps, "
                "source, workout_event_id, follow_along_workout_id, workout_id, created_at"
            ) \
            .eq("user_id", user_id)

        # AMA-273: Filter out simulated completions if requested
        # AMA-274: Wrap in try/catch for backwards compat (column may not exist)
        if not include_simulated:
            try:
                query = query.or_("is_simulated.eq.false,is_simulated.is.null")
            except Exception:
                pass  # Column doesn't exist yet, return all

        result = query \
            .order("started_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()

        completions = []
        for record in result.data or []:
            # Get workout name from the appropriate table based on which FK is set
            workout_name = None
            if record.get("workout_id"):
                # iOS Companion workouts from workouts table
                try:
                    w_result = supabase.table("workouts") \
                        .select("title") \
                        .eq("id", record["workout_id"]) \
                        .single() \
                        .execute()
                    if w_result.data:
                        workout_name = w_result.data.get("title")
                except Exception:
                    pass
            elif record.get("follow_along_workout_id"):
                # Try to get follow-along workout title
                try:
                    fa_result = supabase.table("follow_along_workouts") \
                        .select("title") \
                        .eq("id", record["follow_along_workout_id"]) \
                        .single() \
                        .execute()
                    if fa_result.data:
                        workout_name = fa_result.data.get("title")
                except Exception:
                    pass
            elif record.get("workout_event_id"):
                # Try to get workout event title
                try:
                    we_result = supabase.table("workout_events") \
                        .select("title") \
                        .eq("id", record["workout_event_id"]) \
                        .single() \
                        .execute()
                    if we_result.data:
                        workout_name = we_result.data.get("title")
                except Exception:
                    pass

            completions.append({
                "id": record["id"],
                "workout_name": workout_name or "Workout",
                "started_at": record["started_at"],
                "duration_seconds": record["duration_seconds"],
                "avg_heart_rate": record.get("avg_heart_rate"),
                "max_heart_rate": record.get("max_heart_rate"),
                "min_heart_rate": record.get("min_heart_rate"),
                "active_calories": record.get("active_calories"),
                "total_calories": record.get("total_calories"),
                "distance_meters": record.get("distance_meters"),
                "steps": record.get("steps"),
                "source": record["source"],
            })
            # AMA-274: Only add is_simulated if present in record
            if record.get("is_simulated"):
                completions[-1]["is_simulated"] = True

        # Get total count (respecting the same filter)
        count_query = supabase.table("workout_completions") \
            .select("id", count="exact") \
            .eq("user_id", user_id)

        # AMA-274: Wrap in try/catch for backwards compat (column may not exist)
        if not include_simulated:
            try:
                count_query = count_query.or_("is_simulated.eq.false,is_simulated.is.null")
            except Exception:
                pass  # Column doesn't exist yet

        count_result = count_query.execute()

        total = count_result.count if count_result.count is not None else len(completions)

        return {
            "completions": completions,
            "total": total
        }

    except Exception as e:
        logger.error(f"Error fetching user completions: {e}")
        return {"completions": [], "total": 0}


def get_completion_by_id(
    user_id: str,
    completion_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get a single workout completion with full details including HR samples.

    Args:
        user_id: The Clerk user ID
        completion_id: The completion ID

    Returns:
        Full completion record or None if not found
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return None

    try:
        result = supabase.table("workout_completions") \
            .select("*") \
            .eq("id", completion_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not result.data:
            return None

        record = result.data

        # Get workout_structure from stored record, or fall back to fetching from source (AMA-240)
        workout_structure = record.get("workout_structure")

        # Get workout name and intervals from the appropriate table based on which FK is set
        workout_name = None
        if record.get("workout_id"):
            # iOS Companion workouts from workouts table
            try:
                w_result = supabase.table("workouts") \
                    .select("title, workout_data") \
                    .eq("id", record["workout_id"]) \
                    .single() \
                    .execute()
                if w_result.data:
                    workout_name = w_result.data.get("title")
                    # Fall back to fetching intervals if not stored in completion (backwards compat)
                    if not workout_structure:
                        workout_data = w_result.data.get("workout_data")
                        if workout_data and isinstance(workout_data, dict):
                            workout_structure = workout_data.get("intervals")
            except Exception:
                pass
        elif record.get("follow_along_workout_id"):
            try:
                fa_result = supabase.table("follow_along_workouts") \
                    .select("title") \
                    .eq("id", record["follow_along_workout_id"]) \
                    .single() \
                    .execute()
                if fa_result.data:
                    workout_name = fa_result.data.get("title")
            except Exception:
                pass
        elif record.get("workout_event_id"):
            try:
                we_result = supabase.table("workout_events") \
                    .select("title") \
                    .eq("id", record["workout_event_id"]) \
                    .single() \
                    .execute()
                if we_result.data:
                    workout_name = we_result.data.get("title")
            except Exception:
                pass

        # AMA-273: Build simulation badge if completion is simulated
        is_simulated = record.get("is_simulated", False)
        simulation_config = record.get("simulation_config")
        simulation_badge = None
        if is_simulated:
            simulation_badge = {
                "label": "Simulated",
                "speed": simulation_config.get("speed") if simulation_config else None,
                "profile": simulation_config.get("behavior_profile") if simulation_config else None,
            }

        return {
            "id": record["id"],
            "workout_name": workout_name or "Workout",
            "started_at": record["started_at"],
            "ended_at": record["ended_at"],
            "duration_seconds": record["duration_seconds"],
            "duration_formatted": format_duration(record["duration_seconds"]),
            "avg_heart_rate": record.get("avg_heart_rate"),
            "max_heart_rate": record.get("max_heart_rate"),
            "min_heart_rate": record.get("min_heart_rate"),
            "active_calories": record.get("active_calories"),
            "total_calories": record.get("total_calories"),
            "distance_meters": record.get("distance_meters"),
            "steps": record.get("steps"),
            "source": record["source"],
            "source_workout_id": record.get("source_workout_id"),
            "device_info": record.get("device_info"),
            "heart_rate_samples": record.get("heart_rate_samples"),
            "workout_structure": workout_structure,  # AMA-240: stored or fetched from source
            "intervals": workout_structure,  # Backwards compat alias for iOS (AMA-240)
            "set_logs": record.get("set_logs"),  # AMA-281: Weight tracking per exercise/set
            # AMA-290: Regenerate execution_log from set_logs on every fetch for consistency
            "execution_log": _get_or_build_execution_log(record, workout_structure),
            "created_at": record["created_at"],
            # AMA-273: Simulation fields
            "is_simulated": is_simulated,
            "simulation_config": simulation_config,
            "simulation_badge": simulation_badge,
        }

    except Exception as e:
        logger.error(f"Error fetching completion {completion_id}: {e}")
        return None


# ============================================================================
# Voice Workout with Completion (AMA-5)
# ============================================================================

class VoiceWorkout(BaseModel):
    """Workout data from voice parsing (AMA-5)."""
    id: Optional[str] = None
    name: str
    sport: str
    duration: int  # seconds
    description: Optional[str] = None
    intervals: List[Dict[str, Any]]
    source: str = "ai"
    sourceUrl: Optional[str] = None


class VoiceCompletionData(BaseModel):
    """Completion data for voice-created workout."""
    started_at: str  # ISO format
    ended_at: str    # ISO format
    duration_seconds: int
    source: str = "manual"


class VoiceWorkoutCompletionRequest(BaseModel):
    """Request to save a voice-created workout with completion (AMA-5)."""
    workout: VoiceWorkout
    completion: VoiceCompletionData


def save_voice_workout_with_completion(
    user_id: str,
    request: VoiceWorkoutCompletionRequest
) -> Dict[str, Any]:
    """
    Save a voice-created workout and its completion in one transaction.

    Creates both a workout record and a linked completion record.
    Used by the iOS app when saving voice-created workouts.

    Args:
        user_id: The Clerk user ID
        request: Workout and completion data from iOS app

    Returns:
        Dict with workout_id and completion_id on success, or error details on failure.
    """
    from backend.database import save_workout as db_save_workout

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return {
            "success": False,
            "error": "Database connection unavailable",
            "error_code": "DB_UNAVAILABLE"
        }

    try:
        # 1. Save the workout to workouts table
        workout_data = {
            "title": request.workout.name,
            "sport": request.workout.sport,
            "duration": request.workout.duration,
            "description": request.workout.description,
            "intervals": request.workout.intervals,
            "source": request.workout.source,
            "sourceUrl": request.workout.sourceUrl,
        }

        saved_workout = db_save_workout(
            profile_id=user_id,
            workout_data=workout_data,
            sources=[request.workout.source],
            device="ios_companion",
            title=request.workout.name,
            description=request.workout.description,
        )

        if not saved_workout:
            return {
                "success": False,
                "error": "Failed to save workout",
                "error_code": "WORKOUT_SAVE_FAILED"
            }

        workout_id = saved_workout["id"]
        logger.info(f"Voice workout saved with id: {workout_id}")

        # 2. Save the completion linked to the workout
        completion_record = {
            "user_id": user_id,
            "workout_id": workout_id,
            "started_at": request.completion.started_at,
            "ended_at": request.completion.ended_at,
            "duration_seconds": request.completion.duration_seconds,
            "source": request.completion.source,
        }

        completion_result = supabase.table("workout_completions").insert(completion_record).execute()

        if not completion_result.data or len(completion_result.data) == 0:
            logger.error("Failed to save completion for voice workout")
            return {
                "success": False,
                "error": "Workout saved but completion failed",
                "error_code": "COMPLETION_SAVE_FAILED",
                "workout_id": workout_id
            }

        completion_id = completion_result.data[0]["id"]
        logger.info(f"Voice workout completion saved with id: {completion_id}")

        return {
            "success": True,
            "workout_id": workout_id,
            "completion_id": completion_id,
            "summary": {
                "workout_name": request.workout.name,
                "duration_formatted": format_duration(request.completion.duration_seconds),
                "intervals_count": len(request.workout.intervals),
            }
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error saving voice workout with completion: {error_msg}")

        if "violates foreign key constraint" in error_msg:
            if "profiles" in error_msg:
                return {
                    "success": False,
                    "error": "User profile not found",
                    "error_code": "PROFILE_NOT_FOUND"
                }

        return {
            "success": False,
            "error": "Failed to save workout and completion",
            "error_code": "UNKNOWN_ERROR"
        }
