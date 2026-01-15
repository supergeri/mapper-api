"""
Completions router for workout completion tracking.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-383: Move completion endpoints from workouts.py
Updated in AMA-388: Refactor to use dependency injection for repositories

This router contains endpoints for:
- /workouts/complete - Record workout completion
- /workouts/completions - List/create workout completions
- /workouts/completions/{completion_id} - Get completion details

IMPORTANT: These endpoints use /workouts/ prefix for backwards compatibility.
They must be registered BEFORE the workouts router to ensure proper routing,
since /workouts/{workout_id} would otherwise capture "complete" and "completions".
"""

import logging

from fastapi import APIRouter, Query, Depends

from api.deps import get_current_user, get_completion_repo
from application.ports import CompletionRepository, HealthMetricsDTO
from backend.workout_completions import (
    WorkoutCompletionRequest,
    VoiceWorkoutCompletionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Completions"],
)


# =============================================================================
# Workout Completion Endpoints (AMA-189)
# IMPORTANT: These must be registered BEFORE /workouts/{workout_id} to avoid
# "completions" being parsed as a workout_id parameter.
# =============================================================================


@router.post("/workouts/complete")
def record_workout_completion_endpoint(
    request: WorkoutCompletionRequest,
    user_id: str = Depends(get_current_user),
    completion_repo: CompletionRepository = Depends(get_completion_repo),
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

    # Convert Pydantic model to DTO
    health_metrics = HealthMetricsDTO(
        avg_heart_rate=request.health_metrics.avg_heart_rate,
        max_heart_rate=request.health_metrics.max_heart_rate,
        min_heart_rate=request.health_metrics.min_heart_rate,
        active_calories=request.health_metrics.active_calories,
        total_calories=request.health_metrics.total_calories,
        distance_meters=request.health_metrics.distance_meters,
        steps=request.health_metrics.steps,
    )

    result = completion_repo.save(
        user_id,
        started_at=request.started_at,
        ended_at=request.ended_at,
        health_metrics=health_metrics,
        source=request.source,
        workout_event_id=request.workout_event_id,
        follow_along_workout_id=request.follow_along_workout_id,
        workout_id=request.workout_id,
        source_workout_id=request.source_workout_id,
        device_info=request.device_info,
        heart_rate_samples=request.heart_rate_samples,
        workout_structure=request.workout_structure or request.intervals,
        set_logs=[s.model_dump() for s in request.set_logs] if request.set_logs else None,
        execution_log=request.execution_log,
        is_simulated=request.is_simulated,
        simulation_config=request.simulation_config.model_dump() if request.simulation_config else None,
    )

    if result.get("success"):
        return {
            "success": True,
            "id": result.get("completion_id") or result.get("id"),
            "summary": result.get("summary")
        }
    else:
        # Return specific error from repository
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
    user_id: str = Depends(get_current_user),
    completion_repo: CompletionRepository = Depends(get_completion_repo),
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
    result = completion_repo.get_user_completions(
        user_id,
        limit=limit,
        offset=offset,
        include_simulated=include_simulated,
    )
    return {
        "success": True,
        "completions": result["completions"],
        "total": result["total"]
    }


@router.get("/workouts/completions/{completion_id}")
def get_workout_completion_endpoint(
    completion_id: str,
    user_id: str = Depends(get_current_user),
    completion_repo: CompletionRepository = Depends(get_completion_repo),
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
    result = completion_repo.get_by_id(user_id, completion_id)

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
    user_id: str = Depends(get_current_user),
    completion_repo: CompletionRepository = Depends(get_completion_repo),
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
    result = completion_repo.save_voice_workout_with_completion(
        user_id,
        workout_data=request.workout.model_dump(),
        completion_data=request.completion.model_dump(),
    )

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
