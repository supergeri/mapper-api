"""
Workouts router for workout CRUD and library management.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-381: Move workout CRUD endpoints from app.py

This router contains endpoints for:
- /workouts/save - Save workout to database
- /workouts - List user workouts
- /workouts/incoming - Get incoming (pending) workouts
- /workouts/complete - Record workout completion
- /workouts/completions - List/create workout completions
- /workouts/completions/{completion_id} - Get completion details
- /workouts/{workout_id} - Get, delete workout
- /workouts/{workout_id}/export-status - Update export status
- /workouts/{workout_id}/favorite - Toggle favorite
- /workouts/{workout_id}/used - Track usage
- /workouts/{workout_id}/tags - Update tags

IMPORTANT: Completion endpoints must be defined BEFORE parameterized routes
to avoid "completions" being parsed as a workout_id.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.database import (
    save_workout,
    get_workouts,
    get_workout,
    update_workout_export_status,
    delete_workout,
    toggle_workout_favorite,
    track_workout_usage,
    update_workout_tags,
    get_incoming_workouts,
    get_workout_sync_status,
)
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.workout_completions import (
    WorkoutCompletionRequest,
    save_workout_completion,
    get_user_completions,
    get_completion_by_id,
    VoiceWorkoutCompletionRequest,
    save_voice_workout_with_completion,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Workouts"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class SaveWorkoutRequest(BaseModel):
    """Request for saving a workout."""
    profile_id: str | None = None  # Deprecated: use auth instead
    workout_data: dict
    sources: list[str] = []
    device: str
    exports: dict | None = None
    validation: dict | None = None
    title: str | None = None
    description: str | None = None
    workout_id: str | None = None  # Optional: for explicit updates to existing workouts


class UpdateWorkoutExportRequest(BaseModel):
    """Request for updating workout export status."""
    profile_id: str | None = None  # Deprecated: use auth instead
    is_exported: bool = True
    exported_to_device: str | None = None


class ToggleFavoriteRequest(BaseModel):
    """Request for toggling workout favorite status."""
    profile_id: str
    is_favorite: bool


class TrackUsageRequest(BaseModel):
    """Request for tracking workout usage."""
    profile_id: str


class UpdateTagsRequest(BaseModel):
    """Request for updating workout tags."""
    profile_id: str
    tags: List[str]


# =============================================================================
# Helper Functions
# =============================================================================


def calculate_intervals_duration(intervals: list) -> int:
    """Calculate total duration in seconds from intervals list."""
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
    Convert a workout exercise to iOS companion interval format.
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
    load = ", ".join(load_parts) if load_parts else None

    if reps:
        # Rep-based exercise
        return {
            "kind": "reps",
            "reps": reps * (sets or 1),  # Total reps if multiple sets
            "name": name,
            "load": load,
            "restSec": rest_sec,
            "followAlongUrl": follow_along_url,
            "carouselPosition": None
        }
    elif duration_sec:
        # Time-based exercise
        return {
            "kind": "time",
            "seconds": duration_sec,
            "target": name
        }
    else:
        # Default to time-based with 60 seconds
        return {
            "kind": "time",
            "seconds": 60,
            "target": name
        }


# =============================================================================
# Workout CRUD Endpoints
# =============================================================================


@router.post("/workouts/save")
def save_workout_endpoint(
    request: SaveWorkoutRequest,
    user_id: str = Depends(get_current_user)
):
    """Save a workout to Supabase before syncing to device.

    With deduplication: if a workout with the same profile_id, title, and device
    already exists, it will be updated instead of creating a duplicate.
    """
    result = save_workout(
        profile_id=user_id,
        workout_data=request.workout_data,
        sources=request.sources,
        device=request.device,
        exports=request.exports,
        validation=request.validation,
        title=request.title,
        description=request.description,
        workout_id=request.workout_id
    )

    if result:
        return {
            "success": True,
            "workout_id": result.get("id"),
            "message": "Workout saved successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to save workout. Check server logs."
        }


@router.get("/workouts")
def get_workouts_endpoint(
    user_id: str = Depends(get_current_user),
    device: str = Query(None, description="Filter by device"),
    is_exported: bool = Query(None, description="Filter by export status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts")
):
    """Get workouts for the authenticated user, optionally filtered by device and export status."""
    workouts = get_workouts(
        profile_id=user_id,
        device=device,
        is_exported=is_exported,
        limit=limit
    )

    # Include sync status for each workout (AMA-307)
    for workout in workouts:
        workout_id = workout.get("id")
        if workout_id:
            workout["sync_status"] = get_workout_sync_status(workout_id, user_id)

    return {
        "success": True,
        "workouts": workouts,
        "count": len(workouts)
    }


@router.get("/workouts/incoming")
def get_incoming_workouts_endpoint(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts")
):
    """
    Get incoming workouts that haven't been completed yet (AMA-236).

    This endpoint returns workouts that have been pushed to iOS Companion App
    but have not yet been recorded as completed in workout_completions.

    Use this instead of /workouts to get a filtered list of workouts
    that still need to be done.

    Args:
        user_id: Authenticated user ID (from Clerk JWT)
        limit: Maximum number of workouts to return

    Returns:
        List of pending workouts in iOS Companion format
    """
    workouts = get_incoming_workouts(user_id, limit=limit)

    # Transform each workout to iOS companion format (same as /ios-companion/pending)
    transformed = []
    for workout_record in workouts:
        workout_data = workout_record.get("workout_data", {})
        title = workout_record.get("title") or workout_data.get("title", "Workout")

        # Use to_workoutkit to properly transform intervals
        try:
            workoutkit_dto = to_workoutkit(workout_data)
            intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
            sport = workoutkit_dto.sportType
        except Exception as e:
            logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
            intervals = []
            sport = "strengthTraining"
            for block in workout_data.get("blocks", []):
                for exercise in block.get("exercises", []):
                    intervals.append(convert_exercise_to_interval(exercise))

        # Calculate total duration from intervals
        total_duration = calculate_intervals_duration(intervals)

        transformed.append({
            "id": workout_record.get("id"),
            "name": title,
            "sport": sport,
            "duration": total_duration,
            "source": "amakaflow",
            "sourceUrl": None,
            "intervals": intervals,
            "pushedAt": workout_record.get("ios_companion_synced_at"),
            "createdAt": workout_record.get("created_at"),
        })

    return {
        "success": True,
        "workouts": transformed,
        "count": len(transformed)
    }


# =============================================================================
# Workout Completion Endpoints (AMA-189)
# IMPORTANT: These must be defined BEFORE /workouts/{workout_id} to avoid
# "completions" being parsed as a workout_id parameter.
# =============================================================================


@router.post("/workouts/complete")
def record_workout_completion_endpoint(
    request: WorkoutCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Record a workout completion with health metrics from Apple Watch.

    Called by iOS app when user finishes a workout. Stores heart rate,
    calories, duration, and other health data captured during the workout.

    Args:
        request: Workout completion data including health metrics
        user_id: Authenticated user ID (from Clerk JWT)

    Returns:
        Success status, completion ID, and summary
    """
    # Validate at least one workout link
    if not request.workout_event_id and not request.follow_along_workout_id and not request.workout_id:
        return {
            "success": False,
            "message": "One of workout_event_id, follow_along_workout_id, or workout_id is required"
        }

    result = save_workout_completion(user_id, request)

    if result.get("success"):
        return {
            "success": True,
            "id": result["id"],
            "summary": result["summary"]
        }
    else:
        # Return specific error from save_workout_completion
        return {
            "success": False,
            "message": result.get("error", "Failed to save workout completion"),
            "error_code": result.get("error_code", "UNKNOWN_ERROR")
        }


@router.get("/workouts/completions")
def list_workout_completions_endpoint(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    include_simulated: bool = Query(default=True),  # AMA-273
    user_id: str = Depends(get_current_user)
):
    """
    Get workout completion history for the authenticated user.

    Returns a paginated list of completed workouts with basic health metrics.
    Does not include full heart rate sample data (use single completion endpoint).

    Args:
        limit: Max number of records to return (default 50, max 100)
        offset: Number of records to skip for pagination
        include_simulated: Whether to include simulated completions (default True)
        user_id: Authenticated user ID (from Clerk JWT)

    Returns:
        List of completions and total count
    """
    result = get_user_completions(user_id, limit, offset, include_simulated)
    return {
        "success": True,
        "completions": result["completions"],
        "total": result["total"]
    }


@router.get("/workouts/completions/{completion_id}")
def get_workout_completion_endpoint(
    completion_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get detailed workout completion including heart rate samples.

    Returns the full completion record with all health metrics and
    heart rate time series data for displaying charts.

    Args:
        completion_id: The completion ID
        user_id: Authenticated user ID (from Clerk JWT)

    Returns:
        Full completion record or error if not found
    """
    result = get_completion_by_id(user_id, completion_id)

    if result:
        return {
            "success": True,
            "completion": result
        }
    else:
        return {
            "success": False,
            "message": "Completion not found"
        }


@router.post("/workouts/completions")
def save_voice_workout_completion_endpoint(
    request: VoiceWorkoutCompletionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Save a voice-created workout with its completion (AMA-5).

    Creates both a workout record and a linked completion record.
    Used by the iOS app when saving voice-created workouts.

    Args:
        request: Contains workout data and completion timing
        user_id: Authenticated user ID (from Clerk JWT)

    Request format:
        {
            "workout": {
                "name": "Upper Body Strength",
                "sport": "strength",
                "duration": 2700,
                "intervals": [
                    {"reps": {"sets": 4, "reps": 8, "name": "Bench Press", "load": "135 lbs"}}
                ],
                "source": "ai"
            },
            "completion": {
                "started_at": "2026-01-02T10:00:00.000Z",
                "ended_at": "2026-01-02T10:45:00.000Z",
                "duration_seconds": 2700,
                "source": "manual"
            }
        }

    Returns:
        Success status, workout_id, completion_id, and summary
    """
    result = save_voice_workout_with_completion(user_id, request)

    if result.get("success"):
        return {
            "success": True,
            "workout_id": result["workout_id"],
            "completion_id": result["completion_id"],
            "summary": result.get("summary")
        }
    else:
        return {
            "success": False,
            "message": result.get("error", "Failed to save workout and completion"),
            "error_code": result.get("error_code", "UNKNOWN_ERROR"),
            "workout_id": result.get("workout_id")  # Included if workout saved but completion failed
        }


# =============================================================================
# Workout CRUD Endpoints (Parameterized routes - must come AFTER specific paths)
# =============================================================================


@router.get("/workouts/{workout_id}")
def get_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get a single workout by ID."""
    workout = get_workout(workout_id, user_id)

    if workout:
        # Include sync status in response (AMA-307)
        sync_status = get_workout_sync_status(workout_id, user_id)
        workout["sync_status"] = sync_status
        return {
            "success": True,
            "workout": workout
        }
    else:
        return {
            "success": False,
            "message": "Workout not found"
        }


@router.put("/workouts/{workout_id}/export-status")
def update_workout_export_endpoint(
    workout_id: str,
    request: UpdateWorkoutExportRequest,
    user_id: str = Depends(get_current_user)
):
    """Update workout export status after syncing to device."""
    success = update_workout_export_status(
        workout_id=workout_id,
        profile_id=user_id,
        is_exported=request.is_exported,
        exported_to_device=request.exported_to_device
    )

    if success:
        return {
            "success": True,
            "message": "Export status updated successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update export status"
        }


@router.delete("/workouts/{workout_id}")
def delete_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a workout."""
    success = delete_workout(workout_id, user_id)

    if success:
        return {
            "success": True,
            "message": "Workout deleted successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to delete workout"
        }


@router.patch("/workouts/{workout_id}/favorite")
def toggle_workout_favorite_endpoint(workout_id: str, request: ToggleFavoriteRequest):
    """Toggle favorite status for a workout."""
    result = toggle_workout_favorite(
        workout_id=workout_id,
        profile_id=request.profile_id,
        is_favorite=request.is_favorite
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Favorite status updated"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update favorite status"
        }


@router.patch("/workouts/{workout_id}/used")
def track_workout_usage_endpoint(workout_id: str, request: TrackUsageRequest):
    """Track that a workout was used (update last_used_at and increment times_completed)."""
    result = track_workout_usage(
        workout_id=workout_id,
        profile_id=request.profile_id
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Usage tracked"
        }
    else:
        return {
            "success": False,
            "message": "Failed to track usage"
        }


@router.patch("/workouts/{workout_id}/tags")
def update_workout_tags_endpoint(workout_id: str, request: UpdateTagsRequest):
    """Update tags for a workout."""
    result = update_workout_tags(
        workout_id=workout_id,
        profile_id=request.profile_id,
        tags=request.tags
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Tags updated"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update tags"
        }
