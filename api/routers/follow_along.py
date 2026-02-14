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
from pydantic import BaseModel, Field, HttpUrl

from api.deps import get_current_user
from backend.database import (
    save_follow_along_workout,
    get_follow_along_workouts,
    get_follow_along_workout,
    update_follow_along_garmin_sync,
    update_follow_along_apple_watch_sync,
    update_follow_along_ios_companion_sync,
    delete_follow_along_workout,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/follow-along",
    tags=["follow-along"],
)


def _detect_source_platform(url: str) -> str:
    """Detect video source platform from URL."""
    video_url = url.lower()
    if "instagram.com" in video_url:
        return "instagram"
    elif "youtube.com" in video_url or "youtu.be" in video_url:
        return "youtube"
    elif "tiktok.com" in video_url:
        return "tiktok"
    elif "vimeo.com" in video_url:
        return "vimeo"
    return "other"


# Request Models
class CreateFollowAlongManualRequest(BaseModel):
    """Request to create a follow-along workout with manually entered data."""
    sourceUrl: HttpUrl = Field(description="Source video URL (Instagram, YouTube, TikTok, Vimeo)")
    title: str = Field(description="Workout title")
    description: Optional[str] = Field(None, description="Workout description")
    steps: List[Dict[str, Any]] = Field(description="Workout steps/exercises")
    source: Optional[str] = Field(None, description="Source platform (instagram, youtube, tiktok, vimeo, other)")
    thumbnailUrl: Optional[HttpUrl] = Field(None, description="Thumbnail image URL")


class IngestFollowAlongRequest(BaseModel):
    """Request to ingest a follow-along workout from video URL."""
    sourceUrl: HttpUrl = Field(description="Video URL (Instagram, YouTube, TikTok, Vimeo)")
    source: Optional[str] = Field(None, description="Source platform (instagram, youtube, tiktok, vimeo, other)")


class PushResponse(BaseModel):
    """Response for push operations."""
    success: bool
    message: str


class PushToGarminRequest(BaseModel):
    """Request to push follow-along workout to Garmin."""
    garminWorkoutId: str = Field(description="Garmin workout ID")


class PushToAppleWatchRequest(BaseModel):
    """Request to push follow-along workout to Apple Watch."""
    appleWatchWorkoutId: str = Field(description="Apple Watch workout ID")


class PushToIOSCompanionRequest(BaseModel):
    """Request to push follow-along workout to iOS Companion."""
    iosCompanionWorkoutId: str = Field(description="iOS Companion workout ID")


class CreateFollowAlongFromWorkoutRequest(BaseModel):
    """Request to create a follow-along from an existing workout."""
    workout: Dict[str, Any] = Field(description="Workout data")
    sourceUrl: Optional[HttpUrl] = Field(None, description="Source video URL")


# Response Models
class FollowAlongWorkoutResponse(BaseModel):
    """Response containing follow-along workout data."""
    success: bool
    followAlongWorkout: Optional[Dict[str, Any]] = None
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
def create_follow_along(
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
        source = request.source or _detect_source_platform(str(request.sourceUrl))

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
            source_url=str(request.sourceUrl),
            title=request.title,
            description=request.description,
            video_duration_sec=None,
            thumbnail_url=str(request.thumbnailUrl) if request.thumbnailUrl else None,
            video_proxy_url=None,
            steps=formatted_steps,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save workout to database",
            )

        logger.info(f"Created manual follow-along workout for user {user_id}")
        return FollowAlongWorkoutResponse(
            success=True,
            followAlongWorkout=workout,
        )

    except HTTPException:
        raise
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
def ingest_follow_along(
    request: IngestFollowAlongRequest,
    user_id: str = Depends(get_current_user),
) -> FollowAlongWorkoutResponse:
    """
    Ingest a follow-along workout from a video URL.

    This endpoint extracts structured workout data from video URLs
    on supported platforms.

    Args:
        request: Ingest request with video URL and optional source platform
        user_id: Current authenticated user ID

    Returns:
        FollowAlongWorkoutResponse: Ingested workout or error message
    """
    try:
        source = request.source or _detect_source_platform(str(request.sourceUrl))

        # Extract and save follow-along workout from video
        # TODO: Implement AI extraction from video metadata
        workout = save_follow_along_workout(
            user_id=user_id,
            source=source,
            source_url=str(request.sourceUrl),
            title="Follow-along Workout",
            description=None,
            video_duration_sec=None,
            thumbnail_url=None,
            video_proxy_url=None,
            steps=[],
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to ingest workout from URL",
            )

        logger.info(f"Ingested follow-along workout from {request.sourceUrl}")
        return FollowAlongWorkoutResponse(
            success=True,
            followAlongWorkout=workout,
        )

    except HTTPException:
        raise
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
def list_follow_along(
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
def create_follow_along_from_workout(
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
            source_url=str(request.sourceUrl) if request.sourceUrl else None,
            title=title,
            description=workout_data.get("description"),
            video_duration_sec=None,
            thumbnail_url=None,
            video_proxy_url=None,
            steps=steps,
        )

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create follow-along from workout",
            )

        logger.info(f"Created follow-along from workout for user {user_id}")
        return FollowAlongWorkoutResponse(
            success=True,
            followAlongWorkout=workout,
        )

    except HTTPException:
        raise
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
def get_follow_along(
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
    response_model=PushResponse,
    summary="Delete follow-along workout",
    description="Delete a follow-along workout",
)
def delete_follow_along(
    workout_id: str,
    user_id: str = Depends(get_current_user),
) -> PushResponse:
    """
    Delete a follow-along workout.

    Args:
        workout_id: ID of the follow-along workout to delete
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        delete_follow_along_workout(workout_id, user_id)
        logger.info(f"Deleted follow-along workout {workout_id} for user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} deleted successfully",
        )
    except Exception as e:
        logger.error(f"Error deleting follow-along workout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete follow-along workout: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/garmin",
    response_model=PushResponse,
    summary="Push follow-along to Garmin",
    description="Push a follow-along workout to Garmin device",
)
def push_to_garmin(
    workout_id: str,
    request: PushToGarminRequest,
    user_id: str = Depends(get_current_user),
) -> PushResponse:
    """
    Push a follow-along workout to Garmin device.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request with Garmin workout ID
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update Garmin sync status
        update_follow_along_garmin_sync(
            workout_id=workout_id,
            user_id=user_id,
            garmin_workout_id=request.garminWorkoutId,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to Garmin for user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} pushed to Garmin",
        )
    except Exception as e:
        logger.error(f"Error pushing to Garmin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to Garmin: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/apple-watch",
    response_model=PushResponse,
    summary="Push follow-along to Apple Watch",
    description="Push a follow-along workout to Apple Watch",
)
def push_to_apple_watch(
    workout_id: str,
    request: PushToAppleWatchRequest,
    user_id: str = Depends(get_current_user),
) -> PushResponse:
    """
    Push a follow-along workout to Apple Watch.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request with Apple Watch workout ID
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update Apple Watch sync status
        update_follow_along_apple_watch_sync(
            workout_id=workout_id,
            user_id=user_id,
            apple_watch_workout_id=request.appleWatchWorkoutId,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to Apple Watch for user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} pushed to Apple Watch",
        )
    except Exception as e:
        logger.error(f"Error pushing to Apple Watch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to Apple Watch: {str(e)}",
        ) from e


@router.post(
    "/{workout_id}/push/ios-companion",
    response_model=PushResponse,
    summary="Push follow-along to iOS Companion",
    description="Push a follow-along workout to iOS Companion app",
)
def push_to_ios_companion(
    workout_id: str,
    request: PushToIOSCompanionRequest,
    user_id: str = Depends(get_current_user),
) -> PushResponse:
    """
    Push a follow-along workout to iOS Companion app.

    Args:
        workout_id: ID of the follow-along workout
        request: Push request with iOS Companion workout ID
        user_id: Current authenticated user ID

    Returns:
        Success message
    """
    try:
        # Update iOS Companion sync status
        update_follow_along_ios_companion_sync(
            workout_id=workout_id,
            user_id=user_id,
        )

        logger.info(f"Pushed follow-along workout {workout_id} to iOS Companion for user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} pushed to iOS Companion",
        )
    except Exception as e:
        logger.error(f"Error pushing to iOS Companion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to iOS Companion: {str(e)}",
        ) from e
