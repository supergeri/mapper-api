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
        }

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

            return {
                "success": True,
                "id": saved["id"],
                "summary": summary.model_dump(),
            }
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
    offset: int = 0
) -> Dict[str, Any]:
    """
    Get workout completions for a user.

    Args:
        user_id: The Clerk user ID
        limit: Max number of records to return
        offset: Number of records to skip

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
        result = supabase.table("workout_completions") \
            .select(
                "id, started_at, ended_at, duration_seconds, "
                "avg_heart_rate, max_heart_rate, active_calories, total_calories, "
                "source, workout_event_id, follow_along_workout_id, workout_id, created_at"
            ) \
            .eq("user_id", user_id) \
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
                "active_calories": record.get("active_calories"),
                "source": record["source"],
            })

        # Get total count
        count_result = supabase.table("workout_completions") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()

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
            "created_at": record["created_at"],
        }

    except Exception as e:
        logger.error(f"Error fetching completion {completion_id}: {e}")
        return None
