"""
Supabase Progression Repository Implementation.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

This module implements the ProgressionRepository protocol using Supabase.
Queries the workout_completions table's execution_log JSONB column
to extract exercise history, weights, and calculate progression metrics.
"""
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from collections import defaultdict
import logging

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseProgressionRepository:
    """
    Supabase implementation of ProgressionRepository.

    Extracts progression data from workout_completions.execution_log JSONB column.
    Uses JSONB operators and functions for efficient querying.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected)
        """
        self._client = client

    def get_exercise_history(
        self,
        user_id: str,
        exercise_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get the history of a specific exercise for a user.

        Queries workout_completions and extracts intervals from execution_log
        where the canonical_exercise_id matches.
        """
        try:
            # Query completions that have execution_log with this exercise
            # We need to filter post-query since Supabase can't filter JSONB arrays directly
            result = self._client.table("workout_completions") \
                .select(
                    "id, started_at, ended_at, execution_log, "
                    "workout_id, follow_along_workout_id, workout_event_id"
                ) \
                .eq("user_id", user_id) \
                .not_.is_("execution_log", "null") \
                .order("started_at", desc=True) \
                .execute()

            all_sessions = []

            for record in result.data or []:
                execution_log = record.get("execution_log", {})
                intervals = execution_log.get("intervals", [])

                # Find matching intervals for this exercise
                matching_sets = []
                for interval in intervals:
                    canonical_id = interval.get("canonical_exercise_id")
                    if canonical_id != exercise_id:
                        continue

                    # Extract sets from this interval
                    for set_data in interval.get("sets", []):
                        weight = None
                        weight_unit = "lbs"

                        # Parse weight from structured format
                        weight_obj = set_data.get("weight")
                        if weight_obj and isinstance(weight_obj, dict):
                            components = weight_obj.get("components", [])
                            if components:
                                weight = components[0].get("value")
                                weight_unit = components[0].get("unit", "lbs")
                        elif isinstance(weight_obj, (int, float)):
                            weight = weight_obj

                        matching_sets.append({
                            "set_number": set_data.get("set_number", 1),
                            "weight": weight,
                            "weight_unit": weight_unit,
                            "reps_completed": set_data.get("reps_completed"),
                            "reps_planned": set_data.get("reps_planned"),
                            "status": set_data.get("status", "completed"),
                        })

                if matching_sets:
                    # Get workout name
                    workout_name = self._get_workout_name(record)

                    all_sessions.append({
                        "completion_id": record["id"],
                        "workout_date": record["started_at"][:10] if record.get("started_at") else "",
                        "workout_name": workout_name,
                        "exercise_id": exercise_id,
                        "exercise_name": intervals[0].get("planned_name", exercise_id) if intervals else exercise_id,
                        "sets": matching_sets,
                    })

            total = len(all_sessions)
            paginated = all_sessions[offset:offset + limit]

            return {
                "sessions": paginated,
                "total": total,
                "exercise": {"id": exercise_id},
            }

        except Exception as e:
            logger.exception(f"Error fetching exercise history: {e}")
            return {"sessions": [], "total": 0, "exercise": {"id": exercise_id}}

    def get_all_exercise_sessions(
        self,
        user_id: str,
        exercise_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all sessions for an exercise (no pagination)."""
        result = self.get_exercise_history(
            user_id,
            exercise_id,
            limit=1000,  # High limit to get all
            offset=0,
        )
        return result.get("sessions", [])

    def get_last_weight_used(
        self,
        user_id: str,
        exercise_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the last weight used for an exercise."""
        try:
            # Get the most recent session
            sessions = self.get_exercise_history(
                user_id,
                exercise_id,
                limit=5,  # Check last few sessions
                offset=0,
            ).get("sessions", [])

            # Find the most recent set with a weight
            for session in sessions:
                for set_data in session.get("sets", []):
                    if set_data.get("weight") is not None and set_data.get("status") == "completed":
                        return {
                            "exercise_id": exercise_id,
                            "weight": set_data["weight"],
                            "weight_unit": set_data.get("weight_unit", "lbs"),
                            "reps_completed": set_data.get("reps_completed", 0),
                            "workout_date": session.get("workout_date", ""),
                            "completion_id": session.get("completion_id", ""),
                        }

            return None

        except Exception as e:
            logger.exception(f"Error fetching last weight: {e}")
            return None

    def get_volume_by_muscle_group(
        self,
        user_id: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "daily",
        muscle_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get training volume aggregated by muscle group."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            # Query completions in date range
            result = self._client.table("workout_completions") \
                .select("id, started_at, execution_log") \
                .eq("user_id", user_id) \
                .gte("started_at", start_date.isoformat()) \
                .lte("started_at", (end_date + timedelta(days=1)).isoformat()) \
                .not_.is_("execution_log", "null") \
                .execute()

            # Load exercises to get muscle group mapping
            exercises_result = self._client.table("exercises") \
                .select("id, primary_muscles") \
                .execute()

            exercise_muscles = {}
            for ex in exercises_result.data or []:
                exercise_muscles[ex["id"]] = ex.get("primary_muscles", [])

            # Aggregate volume by muscle group and period
            volume_data: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(
                lambda: defaultdict(lambda: {"volume": 0.0, "sets": 0, "reps": 0})
            )
            summary: Dict[str, Dict[str, float]] = defaultdict(
                lambda: {"total_volume": 0.0, "total_sets": 0, "total_reps": 0}
            )

            for record in result.data or []:
                execution_log = record.get("execution_log", {})
                started_at = record.get("started_at", "")[:10]

                if not started_at:
                    continue

                # Determine period key based on granularity
                period_key = started_at
                if granularity == "weekly":
                    d = date.fromisoformat(started_at)
                    week_start = d - timedelta(days=d.weekday())
                    period_key = week_start.isoformat()
                elif granularity == "monthly":
                    period_key = started_at[:7]

                for interval in execution_log.get("intervals", []):
                    canonical_id = interval.get("canonical_exercise_id")
                    if not canonical_id:
                        continue

                    muscles = exercise_muscles.get(canonical_id, ["other"])

                    # Filter by muscle groups if specified
                    if muscle_groups:
                        if not any(m in muscles for m in muscle_groups):
                            continue

                    for set_data in interval.get("sets", []):
                        if set_data.get("status") != "completed":
                            continue

                        weight = 0
                        weight_obj = set_data.get("weight")
                        if weight_obj and isinstance(weight_obj, dict):
                            components = weight_obj.get("components", [])
                            if components:
                                weight = components[0].get("value", 0) or 0
                        elif isinstance(weight_obj, (int, float)):
                            weight = weight_obj

                        reps = set_data.get("reps_completed", 0) or 0
                        volume = weight * reps

                        for muscle in muscles:
                            volume_data[muscle][period_key]["volume"] += volume
                            volume_data[muscle][period_key]["sets"] += 1
                            volume_data[muscle][period_key]["reps"] += reps
                            summary[muscle]["total_volume"] += volume
                            summary[muscle]["total_sets"] += 1
                            summary[muscle]["total_reps"] += reps

            # Convert to list format
            data_list = []
            for muscle, periods in volume_data.items():
                for period, totals in sorted(periods.items()):
                    data_list.append({
                        "period": period,
                        "muscle_group": muscle,
                        "total_volume": round(totals["volume"], 1),
                        "total_sets": totals["sets"],
                        "total_reps": totals["reps"],
                    })

            return {
                "data": data_list,
                "summary": {k: dict(v) for k, v in summary.items()},
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            }

        except Exception as e:
            logger.exception(f"Error fetching volume analytics: {e}")
            return {
                "data": [],
                "summary": {},
                "period": {
                    "start_date": start_date.isoformat() if start_date else "",
                    "end_date": end_date.isoformat() if end_date else "",
                },
            }

    def get_exercises_with_history(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get exercises that the user has history for."""
        try:
            # Query completions with execution_log
            result = self._client.table("workout_completions") \
                .select("execution_log") \
                .eq("user_id", user_id) \
                .not_.is_("execution_log", "null") \
                .execute()

            # Count sessions per exercise
            exercise_counts: Dict[str, int] = defaultdict(int)
            exercise_names: Dict[str, str] = {}

            for record in result.data or []:
                execution_log = record.get("execution_log", {})
                for interval in execution_log.get("intervals", []):
                    canonical_id = interval.get("canonical_exercise_id")
                    if canonical_id:
                        exercise_counts[canonical_id] += 1
                        if canonical_id not in exercise_names:
                            exercise_names[canonical_id] = interval.get("planned_name", canonical_id)

            # Build result
            exercises = [
                {
                    "exercise_id": ex_id,
                    "exercise_name": exercise_names.get(ex_id, ex_id),
                    "session_count": count,
                }
                for ex_id, count in exercise_counts.items()
            ]

            # Sort by session count descending
            exercises.sort(key=lambda x: x["session_count"], reverse=True)

            return exercises[:limit]

        except Exception as e:
            logger.exception(f"Error fetching exercises with history: {e}")
            return []

    def _get_workout_name(self, record: Dict[str, Any]) -> Optional[str]:
        """Get workout name from linked workout/event."""
        try:
            if record.get("workout_id"):
                w_result = self._client.table("workouts") \
                    .select("title") \
                    .eq("id", record["workout_id"]) \
                    .single() \
                    .execute()
                if w_result.data:
                    return w_result.data.get("title")

            elif record.get("follow_along_workout_id"):
                fa_result = self._client.table("follow_along_workouts") \
                    .select("title") \
                    .eq("id", record["follow_along_workout_id"]) \
                    .single() \
                    .execute()
                if fa_result.data:
                    return fa_result.data.get("title")

            elif record.get("workout_event_id"):
                we_result = self._client.table("workout_events") \
                    .select("title") \
                    .eq("id", record["workout_event_id"]) \
                    .single() \
                    .execute()
                if we_result.data:
                    return we_result.data.get("title")

        except Exception:
            pass

        return None
