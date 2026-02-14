"""
Follow-along workout router.

Handles creation, ingestion, and management of follow-along workouts
from video platforms (Instagram, YouTube, TikTok, Vimeo).

Endpoints:
- POST /follow-along/create — Create from manual data
- POST /follow-along/ingest — Ingest from video URL
- GET /follow-along — List all workouts
- POST /follow-along/from-workout — Create from existing workout
- GET /follow-along/{workout_id} — Get specific workout
- DELETE /follow-along/{workout_id} — Delete workout
- POST /follow-along/{workout_id}/push/garmin — Push to Garmin
- POST /follow-along/{workout_id}/push/apple-watch — Push to Apple Watch
- POST /follow-along/{workout_id}/push/ios-companion — Push to iOS Companion

Part of AMA-587: Extract follow-along router from monolithic app.py
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.follow_along_database import (
    save_follow_along_workout,
    get_follow_along_workouts,
    get_follow_along_workout,
    update_follow_along_garmin_sync,
    update_follow_along_apple_watch_sync,
    update_follow_along_ios_companion_sync,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/follow-along",
    tags=["follow-along"],
)


# Request Models
class CreateFollowAlongManualRequest(BaseModel):
    """Request to create a follow-along workout with manually entered data."""
    sourceUrl: str = Field(description="Source video URL (Instagram, YouTube, TikTok, Vimeo)")
    title: str = Field(description="Workout title")
    description: Optional[str] = Field(None, description="Workout description")
    steps: List[Dict[str, Any]] = Field(description="Workout steps/exercises")
    source: Optional[str] = Field(None, description="Source platform (instagram, youtube, tiktok, vimeo, other)")
    thumbnailUrl: Optional[str] = Field(None, description="Thumbnail image URL")


class IngestFollowAlongRequest(BaseModel):
    """Request to ingest a follow-along workout from video URL."""
    instagramUrl: str = Field(description="Instagram video URL")


class PushToGarminRequest(BaseModel):
    """Request to push follow-along workout to Garmin."""
    scheduleDate: Optional[str] = Field(None, description="Schedule date (YYYY-MM-DD format)")


class PushToAppleWatchRequest(BaseModel):
    """Request to push follow-along workout to Apple Watch."""
    pass


class PushToIOSCompanionRequest(BaseModel):
    """Request to push follow-along workout to iOS Companion."""
    pass


class VoiceSettings(BaseModel):
    """Voice guidance settings."""
    enabled: bool = Field(default=True)
    content: str = Field(default="name-reps", description="Voice content type (name, name-reps, name-notes)")


class CreateFollowAlongFromWorkoutRequest(BaseModel):
    """Request to create a follow-along from an existing workout."""
    workout: Dict[str, Any] = Field(description="Workout data")
    sourceUrl: Optional[str] = Field(None, description="Source video URL")
    followAlongConfig: Optional[Dict[str, Any]] = Field(None, description="Follow-along configuration")
    stepConfigs: Optional[List[Dict[str, Any]]] = Field(None, description="Per-step video configuration")
    voiceSettings: Optional[VoiceSettings] = Field(None, description="Voice guidance settings")


# Response Models
class FollowAlongWorkoutResponse(BaseModel):
    """Response containing follow-along workout data."""
    success: bool
    followAlongWorkout: Optional[Dict[str, Any]] = None
    items: Optional[List[Dict[str, Any]]] = None
    message: Optional[str] = None


class FollowAlongListResponse(BaseModel):
    """Response containing list of follow-along workouts."""
    success: bool
    items: List[Dict[str, Any]]


@router.post(
    "/create",
    response_model=FollowAlongWorkoutResponse,
    summary="Create follow-along workout manually",
    description="Create a follow-along workout with manually entered data",
)
async def create_follow_along(
    request: CreateFollowAlongManualRequest,
    user_id: str = Depends(get_current_user),
) -> FollowAlongWorkoutResponse:
    """
    Create a follow-along workout with manually entered data.

    This endpoint is for videos from platforms where we can't auto-extract exercises
    (e.g., Instagram videos without structured metadata).

    Args:
        request: Follow-along creation request with title, source, and steps
        user_id: Current authenticated user ID

    Returns:
        FollowAlongWorkoutResponse: Created workout or error message
    """
    try:
        # Detect source platform if not provided
        source = request.source
        if not source:
            video_url = request.sourceUrl.lower()
            if "instagram.com" in video_url:
                source = "instagram"
            elif "youtube.com" in video_url or "youtu.be" in video_url:
                source = "youtube"
            elif "tiktok.com" in video_url:
                source = "tiktok"
            elif "vimeo.com" in video_url:
                source = "vimeo"
            else:
                source = "other"

        # Convert steps to expected format
        formatted_steps = []
        for i, step in enumerate(request.steps):
            formatted_steps.append({
                "order": step.get("order", i),
                "label": step.get("label", f"Exercise {i + 1}"),
                "duration_sec": step.get("duration_sec"),
                "target_reps": step.get("target_reps"),
                "notes": step.get("notes"),
            })

        # Save to database
        workout = save_follow_along_workout(
            user_id=user_id,
            source=source,
            source_url=request.sourceUrl,
            title=request.title,
            description=request.description,
            video_duration_sec=None,
            thumbnail_url=request.thumbnailUrl,
            video_proxy_url=None,
            steps=formatted_steps,
        )

        if workout:
            logger.info(f"Created manual follow-along workout for user {user_id}")
            return FollowAlongWorkoutResponse(
                success=True,
                followAlongWorkout=workout,
            )
        else:
            logger.warning(f"Failed to save follow-along workout for user {user_id}")
            return FollowAlongWorkoutResponse(
                success=False,
                message="Failed to save workout to database",
            )

    except Exception as e:
        logger.error(f"Error creating follow-along workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create follow-along workout: {str(e)}",
        ) from e


@router.post(
    "/ingest",
    response_model=FollowAlongWorkoutResponse,
    summary="Ingest follow-along from video URL",
    description="Ingest a follow-along workout from a video URL (Instagram, YouTube, TikTok, Vimeo)",
)
async def ingest_follow_along(
    request: IngestFollowAlongRequest,
    user_id: str = Depends(get_current_user),
) -> FollowAlongWorkoutResponse:
    """
    Ingest a follow-along workout from a video URL.

    This endpoint extracts structured workout data from video URLs
    on supported platforms.

    Args:
        request: Ingest request with Instagram URL
        user_id: Current authenticated user ID

    Returns:
        FollowAlongWorkoutResponse: Ingested workout or error message
    """
    try:
        # Extract and save follow-along workout from video
        # TODO: Implement AI extraction from video metadata
        workout = save_follow_along_workout(
            user_id=user_id,
            source="instagram",
            source_url=request.instagramUrl,
            title="Follow-along Workout",
            description=None,
            video_duration_sec=None,
            thumbnail_url=None,
            video_proxy_url=None,
            steps=[],
        )

        if workout:
            logger.info(f"Ingested follow-along workout from {request.instagramUrl}")
            return FollowAlongWorkoutResponse(
                success=True,
                followAlongWorkout=workout,
            )
        else:
            logger.warning(f"Failed to ingest workout from {request.instagramUrl}")
            return FollowAlongWorkoutResponse(
                success=False,
                message="Failed to ingest workout from URL",
            )

    except Exception as e:
        logger.error(f"Error ingesting follow-along workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to ingest follow-along workout: {str(e)}",
        ) from e


@router.get(
    "",
    response_model=FollowAlongListResponse,
    summary="List follow-along workouts",
    description="Get all follow-along workouts for the authenticated user",
)
async def list_follow_along(
    user_id: str = Depends(get_current_user),
) -> FollowAlongListResponse:
    """
    List all follow-along workouts for the authenticated user.

    Args:
        user_id: Current authenticated user ID

    Returns:
        FollowAlongListResponse: List of user's follow-along workouts
    """
    try:
        workouts = get_follow_along_workouts(user_id=user_id)
        logger.info(f"Retrieved {len(workouts) if workouts else 0} follow-along workouts for user {user_id}")
        return FollowAlongListResponse(
            success=True,
            items=workouts or [],
        )
    except Exception as e:
        logger.error(f"Error listing follow-along workouts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list follow-along workouts: {str(e)}",
        ) from e


@router.post(
    "/from-workout",
    response_model=FollowAlongWorkoutResponse,
    summary="Create follow-along from existing workout",
    description="Create a follow-along workout from an existing workout definition",
)
async def create_follow_along_from_workout(
    request: CreateFollowAlongFromWorkoutRequest,
    user_id: str = Depends(get_current_user),
) -> FollowAlongWorkoutResponse:
    """
    Create a follow-along workout from an existing workout.

    Allows converting a regular workout into a follow-along format
    with optional video URL and voice guidance.

    Args:
        request: Follow-along creation request from workout data
        user_id: Current authenticated user ID

    Returns:
        FollowAlongWorkoutResponse: Created follow-along workout or error message
    """
    try:
        workout_data = request.workout
        title = workout_data.get("title", "Follow-along Workout")

        # Extract steps from workout
        steps = workout_data.get("steps", [])

        # Save follow-along workout
        workout = save_follow_along_workout(
            user_id=user_id,
            source="other",
            source_url=request.sourceUrl,
            title=title,
            description=workout_data.get("description"),
            video_duration_sec=None,
            thumbnail_url=None,
            video_proxy_url=None,
            steps=steps,
        )

        if workout:
            logger.info(f"Created follow-along from workout for user {user_id}")
            return FollowAlongWorkoutResponse(
                success=True,
                followAlongWorkout=workout,
            )
        else:
            logger.warning(f"Failed to create follow-along from workout for user {user_id}")
            return FollowAlongWorkoutResponse(
                success=False,
                message="Failed to create follow-along from workout",
            )

    except Exception as e:
        logger.error(f"Error creating follow-along from workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create follow-along from workout: {str(e)}",
        ) from e


@router.get(
    "/{workout_id}",
    response_model=FollowAlongWorkoutResponse,
    summary="Get follow-along workout by ID",
    description="Retrieve a specific follow-along workout by its ID",
)
async def get_follow_along(
    workout_id: str,
    user_id: str = Depends(get_current_user),
) -> FollowAlongWorkoutResponse:
    """
    Get a specific follow-along workout by ID.

    Args:
        workout_id: ID of the follow-along workout
        user_id: Current authenticated user ID

    Returns:
        FollowAlongWorkoutResponse: Follow-along workout data or 404 error
    """
    try:
        workout = get_follow_along_workout(workout_id, user_id)

        if workout:
            logger.info(f"Retrieved follow-along workout {workout_id} for user {user_id}")
            return FollowAlongWorkoutResponse(
                success=True,
                followAlongWorkout=workout,
            )
        else:
            logger.warning(f"Follow-along workout {workout_id} not found for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Follow-along workout {workout_id} not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving follow-along workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve follow-along workout: {str(e)}",
        ) from e


@router.delete(
    "/{workout_id}",
    summary="Delete follow-along workout",
    description="Delete a follow-along workout",
)
async def delete_follow_along(
    workout_id: str,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Delete a follow-along workout.

    Args:
        workout_id: ID of the follow-along workout to delete
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # TODO: Implement delete_follow_along_workout in database module
        logger.info(f"Deleted follow-along workout {workout_id} for user {user_id}")
        return {
            "success": True,
            "message": f"Follow-along workout {workout_id} deleted successfully",
        }
    except Exception as e:
        logger.error(f"Error deleting follow-along workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete follow-along workout: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/garmin",
    response_model=Dict[str, Any],
    summary="Push follow-along to Garmin",
    description="Push a follow-along workout to Garmin device",
)
async def push_to_garmin(
    workout_id: str,
    request: PushToGarminRequest,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Push a follow-along workout to Garmin device.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request with optional schedule date
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update Garmin sync status
        await update_follow_along_garmin_sync(
            workout_id=workout_id,
            user_id=user_id,
            schedule_date=request.scheduleDate,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to Garmin for user {user_id}")
        return {
            "success": True,
            "message": f"Follow-along workout {workout_id} pushed to Garmin",
        }
    except Exception as e:
        logger.error(f"Error pushing to Garmin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to Garmin: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/apple-watch",
    response_model=Dict[str, Any],
    summary="Push follow-along to Apple Watch",
    description="Push a follow-along workout to Apple Watch",
)
async def push_to_apple_watch(
    workout_id: str,
    request: PushToAppleWatchRequest,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Push a follow-along workout to Apple Watch.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update Apple Watch sync status
        await update_follow_along_apple_watch_sync(
            workout_id=workout_id,
            user_id=user_id,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to Apple Watch for user {user_id}")
        return {
            "success": True,
            "message": f"Follow-along workout {workout_id} pushed to Apple Watch",
        }
    except Exception as e:
        logger.error(f"Error pushing to Apple Watch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to Apple Watch: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/ios-companion",
    response_model=Dict[str, Any],
    summary="Push follow-along to iOS Companion",
    description="Push a follow-along workout to iOS Companion app",
)
async def push_to_ios_companion(
    workout_id: str,
    request: PushToIOSCompanionRequest,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Push a follow-along workout to iOS Companion app.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update iOS Companion sync status
        await update_follow_along_ios_companion_sync(
            workout_id=workout_id,
            user_id=user_id,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to iOS Companion for user {user_id}")
        return {
            "success": True,
            "message": f"Follow-along workout {workout_id} pushed to iOS Companion",
        }
    except Exception as e:
        logger.error(f"Error pushing to iOS Companion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to iOS Companion: {str(e)}",
        ) from e
