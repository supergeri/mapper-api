"""
Supabase Completion Repository Implementation.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This module implements the CompletionRepository protocol using Supabase as the backend.
Extracted from backend/workout_completions.py.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from supabase import Client
import logging

from application.ports.completion_repository import (
    CompletionRepository,
    HealthMetricsDTO,
    CompletionSummary,
)

logger = logging.getLogger(__name__)

# Input validation limits
MAX_STRING_LENGTH = 1000
MAX_DEVICE_INFO_SIZE = 10000


# ============================================================================
# Helper Functions (stateless utilities)
# ============================================================================

def validate_string_field(value: Optional[str], field_name: str) -> Optional[str]:
    """Validate and truncate string field to max length."""
    if value is None:
        return None
    if not isinstance(value, str):
        logger.warning(f"{field_name} must be a string, got {type(value)}")
        return None
    if len(value) > MAX_STRING_LENGTH:
        logger.warning(f"{field_name} exceeds {MAX_STRING_LENGTH} chars, truncating")
        return value[:MAX_STRING_LENGTH]
    return value


def validate_dict_field(value: Optional[Dict[str, Any]], field_name: str) -> Optional[Dict[str, Any]]:
    """Validate dict field size."""
    if value is None:
        return None
    if not isinstance(value, dict):
        logger.warning(f"{field_name} must be a dict, got {type(value)}")
        return None
    import json
    size = len(json.dumps(value))
    if size > MAX_DEVICE_INFO_SIZE:
        logger.warning(f"{field_name} exceeds {MAX_DEVICE_INFO_SIZE} bytes, rejecting")
        return None
    return value


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
    """
    intervals = execution_log.get("intervals") or []
    if not intervals:
        return False

    for interval in intervals:
        if interval.get("actual_duration_seconds") is not None:
            return True
        if interval.get("started_at") is not None:
            return True

        sets = interval.get("sets") or []
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
    """Merge weight data from set_logs into an existing execution_log."""
    if not set_logs:
        return execution_log

    set_log_map = {}
    for log in set_logs:
        idx = log.get("exercise_index")
        if idx is not None:
            set_log_map[idx] = log

    intervals = execution_log.get("intervals") or []
    updated_intervals = []

    for interval in intervals:
        idx = interval.get("interval_index")
        matching_log = set_log_map.get(idx)

        if matching_log and matching_log.get("sets"):
            existing_sets = interval.get("sets") or []
            set_logs_data = matching_log["sets"]

            updated_sets = []
            for i, existing_set in enumerate(existing_sets):
                updated_set = {**existing_set}
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


def _fix_execution_log_names(
    execution_log: Dict[str, Any],
    workout_structure: Optional[List[Dict[str, Any]]]
) -> Dict[str, Any]:
    """Fix missing planned_name values in stored execution_log."""
    intervals = execution_log.get("intervals") or []
    if not intervals:
        return execution_log

    structure_names = {}
    if workout_structure:
        for i, interval in enumerate(workout_structure):
            name = interval.get("name") or interval.get("target")
            if name:
                structure_names[i] = name

    fixed_intervals = []
    for interval in intervals:
        idx = interval.get("interval_index", 0)
        planned_name = interval.get("planned_name")

        if not planned_name:
            planned_name = structure_names.get(idx) or f"Exercise {idx + 1}"

        fixed_interval = {**interval, "planned_name": planned_name}

        sets = fixed_interval.get("sets") or []
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
    """Convert legacy set_logs to execution_log format."""
    if not set_logs:
        return None

    set_log_map = {}
    for log in set_logs:
        idx = log.get("exercise_index")
        if idx is not None:
            set_log_map[idx] = log

    intervals = []
    completed_count = 0
    skipped_count = 0

    if workout_structure:
        for i, interval in enumerate(workout_structure):
            matching_log = set_log_map.get(i)

            planned_name = (
                interval.get("name") or
                interval.get("target") or
                (matching_log.get("exercise_name") if matching_log else None) or
                f"Exercise {i + 1}"
            )

            interval_log = {
                "interval_index": i,
                "planned_kind": interval.get("kind") or interval.get("type"),
                "planned_name": planned_name,
                "status": "completed",
            }

            if matching_log and matching_log.get("sets"):
                exec_sets = []
                set_number = 1
                for set_entry in matching_log["sets"]:
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
                completed_count += 1
            else:
                completed_count += 1

            intervals.append(interval_log)
    else:
        from collections import OrderedDict
        exercise_groups: OrderedDict[str, list] = OrderedDict()

        for log in set_logs:
            exercise_name = log.get("exercise_name", "Unknown Exercise")
            if exercise_name not in exercise_groups:
                exercise_groups[exercise_name] = []
            exercise_groups[exercise_name].append(log)

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
    total_sets = sum(len(i.get("sets") or []) for i in intervals)
    sets_completed = sum(
        sum(1 for s in (i.get("sets") or []) if s.get("status") == "completed")
        for i in intervals
    )
    sets_skipped = total_sets - sets_completed

    summary = {
        "total_intervals": total,
        "completed": completed_count,
        "skipped": skipped_count,
        "not_reached": 0,
        "completion_percentage": round((completed_count / total) * 100, 1) if total > 0 else 0,
        "total_sets": total_sets,
        "sets_completed": sets_completed,
        "sets_skipped": sets_skipped,
        "total_duration_seconds": 0,
        "active_duration_seconds": 0,
    }

    return {
        "version": 2,
        "intervals": intervals,
        "summary": summary
    }


def _get_or_build_execution_log(
    record: Dict[str, Any],
    workout_structure: Optional[List[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """Get execution_log from record or build it from set_logs."""
    set_logs = record.get("set_logs")
    stored_execution_log = record.get("execution_log")
    completion_id = record.get("id", "unknown")

    logger.info(f"_get_or_build_execution_log for {completion_id}: "
                f"set_logs={bool(set_logs)} ({len(set_logs) if set_logs else 0} items), "
                f"stored_execution_log={bool(stored_execution_log)}")

    if stored_execution_log and _execution_log_has_detailed_data(stored_execution_log):
        result = _fix_execution_log_names(stored_execution_log, workout_structure)
        if set_logs:
            result = _merge_weights_into_execution_log(result, set_logs)
            logger.info(f"Using detailed execution_log with merged weights: "
                        f"{len(result.get('intervals', []))} intervals")
        else:
            logger.info(f"Using detailed execution_log: "
                        f"{len(result.get('intervals', []))} intervals")
        return result

    if set_logs:
        result = merge_set_logs_to_execution_log(workout_structure, set_logs)
        logger.info(f"Built execution_log from set_logs: "
                    f"{len(result.get('intervals', []))} intervals")
        return result

    if stored_execution_log:
        result = _fix_execution_log_names(stored_execution_log, workout_structure)
        logger.info(f"Using stored execution_log: "
                    f"{len(result.get('intervals', []))} intervals")
        return result

    logger.info(f"No execution_log data available for {completion_id}")
    return None


# ============================================================================
# Repository Implementation
# ============================================================================

class SupabaseCompletionRepository:
    """
    Supabase implementation of CompletionRepository.

    Handles workout completion persistence with health metrics from Apple Watch,
    Garmin, or manual entry.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected)
        """
        self._client = client

    def save(
        self,
        user_id: str,
        *,
        started_at: str,
        ended_at: str,
        health_metrics: HealthMetricsDTO,
        source: str = "apple_watch",
        workout_event_id: Optional[str] = None,
        follow_along_workout_id: Optional[str] = None,
        workout_id: Optional[str] = None,
        source_workout_id: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
        heart_rate_samples: Optional[List[Dict[str, Any]]] = None,
        workout_structure: Optional[List[Dict[str, Any]]] = None,
        set_logs: Optional[List[Dict[str, Any]]] = None,
        execution_log: Optional[Dict[str, Any]] = None,
        is_simulated: bool = False,
        simulation_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save a workout completion record."""
        # Validate heart_rate_samples if provided
        if heart_rate_samples is not None:
            if not isinstance(heart_rate_samples, list):
                logger.warning(f"heart_rate_samples must be a list, got {type(heart_rate_samples)}")
                heart_rate_samples = None
            else:
                # Validate structure: each sample should have required fields
                validated_samples = []
                for i, sample in enumerate(heart_rate_samples[:1000]):  # Limit to 1000 samples
                    if not isinstance(sample, dict):
                        logger.warning(f"heart_rate_samples[{i}] must be a dict")
                        continue
                    # Check for required fields (timestamp and value)
                    if "timestamp" not in sample and "seconds" not in sample:
                        logger.warning(f"heart_rate_samples[{i}] missing timestamp field")
                        continue
                    if "value" not in sample and "bpm" not in sample:
                        logger.warning(f"heart_rate_samples[{i}] missing heart rate value field")
                        continue
                    validated_samples.append(sample)
                heart_rate_samples = validated_samples[:500]  # Limit to 500 samples max

        # Validate device_info
        device_info = validate_dict_field(device_info, "device_info")

        try:
            duration_seconds = calculate_duration_seconds(started_at, ended_at)

            record = {
                "user_id": user_id,
                "workout_event_id": workout_event_id,
                "follow_along_workout_id": follow_along_workout_id,
                "workout_id": workout_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_seconds": duration_seconds,
                "avg_heart_rate": health_metrics.avg_heart_rate,
                "max_heart_rate": health_metrics.max_heart_rate,
                "min_heart_rate": health_metrics.min_heart_rate,
                "active_calories": health_metrics.active_calories,
                "total_calories": health_metrics.total_calories,
                "distance_meters": health_metrics.distance_meters,
                "steps": health_metrics.steps,
                "source": source,
                "source_workout_id": source_workout_id,
                "device_info": device_info,
                "heart_rate_samples": heart_rate_samples,
                "workout_structure": workout_structure,
            }

            if set_logs:
                record["set_logs"] = set_logs

            if execution_log:
                record["execution_log"] = execution_log
            elif set_logs:
                merged_execution_log = merge_set_logs_to_execution_log(
                    workout_structure,
                    set_logs
                )
                if merged_execution_log:
                    record["execution_log"] = merged_execution_log

            if is_simulated:
                record["is_simulated"] = True
                if simulation_config:
                    record["simulation_config"] = simulation_config

            result = self._client.table("workout_completions").insert(record).execute()

            if result.data and len(result.data) > 0:
                saved = result.data[0]
                logger.info(f"Workout completion saved for user {user_id}: {saved['id']}")

                summary = CompletionSummary(
                    duration_formatted=format_duration(duration_seconds),
                    avg_heart_rate=health_metrics.avg_heart_rate,
                    calories=health_metrics.active_calories
                )

                response = {
                    "success": True,
                    "id": saved["id"],
                    "summary": {
                        "duration_formatted": summary.duration_formatted,
                        "avg_heart_rate": summary.avg_heart_rate,
                        "calories": summary.calories,
                    },
                }
                if is_simulated:
                    response["is_simulated"] = True
                return response
            else:
                logger.error("Failed to insert workout completion: empty result")
                return {
                    "success": False,
                    "error": "Database insert returned empty result",
                    "error_code": "INSERT_FAILED"
                }

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error saving workout completion: {error_msg}")

            if "violates foreign key constraint" in error_msg:
                if "profiles" in error_msg:
                    return {
                        "success": False,
                        "error": "User profile not found",
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
                return {
                    "success": False,
                    "error": "Permission denied",
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

    def get_by_id(
        self,
        user_id: str,
        completion_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single completion with full details including HR samples."""
        try:
            result = self._client.table("workout_completions") \
                .select("*") \
                .eq("id", completion_id) \
                .eq("user_id", user_id) \
                .single() \
                .execute()

            if not result.data:
                return None

            record = result.data

            workout_structure = record.get("workout_structure")
            workout_name = None

            if record.get("workout_id"):
                try:
                    w_result = self._client.table("workouts") \
                        .select("title, workout_data") \
                        .eq("id", record["workout_id"]) \
                        .single() \
                        .execute()
                    if w_result.data:
                        workout_name = w_result.data.get("title")
                        if not workout_structure:
                            workout_data = w_result.data.get("workout_data")
                            if workout_data and isinstance(workout_data, dict):
                                workout_structure = workout_data.get("intervals")
                except Exception:
                    pass
            elif record.get("follow_along_workout_id"):
                try:
                    fa_result = self._client.table("follow_along_workouts") \
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
                    we_result = self._client.table("workout_events") \
                        .select("title") \
                        .eq("id", record["workout_event_id"]) \
                        .single() \
                        .execute()
                    if we_result.data:
                        workout_name = we_result.data.get("title")
                except Exception:
                    pass

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
                "workout_structure": workout_structure,
                "intervals": workout_structure,
                "set_logs": record.get("set_logs"),
                "execution_log": _get_or_build_execution_log(record, workout_structure),
                "created_at": record["created_at"],
                "is_simulated": is_simulated,
                "simulation_config": simulation_config,
                "simulation_badge": simulation_badge,
            }

        except Exception as e:
            logger.error(f"Error fetching completion {completion_id}: {e}")
            return None

    def get_user_completions(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        include_simulated: bool = True,
    ) -> Dict[str, Any]:
        """Get completion history for a user."""
        try:
            query = self._client.table("workout_completions") \
                .select(
                    "id, started_at, ended_at, duration_seconds, "
                    "avg_heart_rate, max_heart_rate, min_heart_rate, active_calories, total_calories, "
                    "distance_meters, steps, "
                    "source, workout_event_id, follow_along_workout_id, workout_id, created_at"
                ) \
                .eq("user_id", user_id)

            if not include_simulated:
                try:
                    query = query.or_("is_simulated.eq.false,is_simulated.is.null")
                except Exception:
                    pass

            result = query \
                .order("started_at", desc=True) \
                .range(offset, offset + limit - 1) \
                .execute()

            completions = []
            for record in result.data or []:
                workout_name = None
                if record.get("workout_id"):
                    try:
                        w_result = self._client.table("workouts") \
                            .select("title") \
                            .eq("id", record["workout_id"]) \
                            .single() \
                            .execute()
                        if w_result.data:
                            workout_name = w_result.data.get("title")
                    except Exception:
                        pass
                elif record.get("follow_along_workout_id"):
                    try:
                        fa_result = self._client.table("follow_along_workouts") \
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
                        we_result = self._client.table("workout_events") \
                            .select("title") \
                            .eq("id", record["workout_event_id"]) \
                            .single() \
                            .execute()
                        if we_result.data:
                            workout_name = we_result.data.get("title")
                    except Exception:
                        pass

                completion_item = {
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
                }
                if record.get("is_simulated"):
                    completion_item["is_simulated"] = True
                completions.append(completion_item)

            count_query = self._client.table("workout_completions") \
                .select("id", count="exact") \
                .eq("user_id", user_id)

            if not include_simulated:
                try:
                    count_query = count_query.or_("is_simulated.eq.false,is_simulated.is.null")
                except Exception:
                    pass

            count_result = count_query.execute()
            total = count_result.count if count_result.count is not None else len(completions)

            return {
                "completions": completions,
                "total": total
            }

        except Exception as e:
            logger.error(f"Error fetching user completions: {e}")
            return {"completions": [], "total": 0}

    def save_voice_workout_with_completion(
        self,
        user_id: str,
        workout_data: Dict[str, Any],
        completion_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save a voice-created workout with its completion atomically."""
        try:
            from backend.database import save_workout as db_save_workout

            saved_workout = db_save_workout(
                profile_id=user_id,
                workout_data=workout_data,
                sources=[workout_data.get("source", "ai")],
                device="ios_companion",
                title=workout_data.get("name") or workout_data.get("title"),
                description=workout_data.get("description"),
            )

            if not saved_workout:
                return {
                    "success": False,
                    "error": "Failed to save workout",
                    "error_code": "WORKOUT_SAVE_FAILED"
                }

            workout_id = saved_workout["id"]
            logger.info(f"Voice workout saved with id: {workout_id}")

            completion_record = {
                "user_id": user_id,
                "workout_id": workout_id,
                "started_at": completion_data["started_at"],
                "ended_at": completion_data["ended_at"],
                "duration_seconds": completion_data.get("duration_seconds", 0),
                "source": completion_data.get("source", "manual"),
            }

            completion_result = self._client.table("workout_completions").insert(completion_record).execute()

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

            intervals = workout_data.get("intervals", [])
            duration_seconds = completion_data.get("duration_seconds", 0)

            return {
                "success": True,
                "workout_id": workout_id,
                "completion_id": completion_id,
                "summary": {
                    "workout_name": workout_data.get("name") or workout_data.get("title"),
                    "duration_formatted": format_duration(duration_seconds),
                    "intervals_count": len(intervals),
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

    def get_completed_workout_ids(
        self,
        user_id: str,
    ) -> set:
        """Get IDs of workouts that have been completed by the user."""
        try:
            result = self._client.table("workout_completions") \
                .select("workout_id") \
                .eq("user_id", user_id) \
                .not_.is_("workout_id", "null") \
                .execute()

            return {r["workout_id"] for r in (result.data or []) if r.get("workout_id")}

        except Exception as e:
            logger.error(f"Error fetching completed workout IDs: {e}")
            return set()
