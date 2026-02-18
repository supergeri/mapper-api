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
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, HttpUrl, field_validator

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

# AMA-599: Idempotency guard for Garmin syncs - prevents duplicate syncs
# Uses in-memory cache with TTL for production readiness
# For multi-instance deployments, consider database-based deduplication
FOLLOW_ALONG_GARMIN_SYNC_CACHE: Dict[str, tuple[str, datetime]] = {}
CACHE_MAX_SIZE = 1000
CACHE_TTL_HOURS = 24


def _cleanup_cache() -> None:
    """Remove expired entries from the cache to prevent unbounded memory growth."""
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=CACHE_TTL_HOURS)
    expired_keys = [
        key for key, (_, timestamp) in FOLLOW_ALONG_GARMIN_SYNC_CACHE.items()
        if timestamp < cutoff
    ]
    for key in expired_keys:
        del FOLLOW_ALONG_GARMIN_SYNC_CACHE[key]


def _has_garmin_synced_before(workout_id: str, user_id: str) -> bool:
    """Check if this workout+user combination has been synced to Garmin recently."""
    _cleanup_cache()  # Clean expired entries before checking
    cache_key = f"{user_id}:{workout_id}"
    return cache_key in FOLLOW_ALONG_GARMIN_SYNC_CACHE


def _mark_garmin_synced(workout_id: str, user_id: str, garmin_workout_id: str) -> None:
    """Mark a workout as synced to Garmin for this user."""
    # Enforce size limit to prevent unbounded memory growth
    if len(FOLLOW_ALONG_GARMIN_SYNC_CACHE) >= CACHE_MAX_SIZE:
        _cleanup_cache()
        # If still at capacity, remove oldest entries
        if len(FOLLOW_ALONG_GARMIN_SYNC_CACHE) >= CACHE_MAX_SIZE:
            sorted_keys = sorted(
                FOLLOW_ALONG_GARMIN_SYNC_CACHE.items(),
                key=lambda x: x[1][1]
            )
            for key, _ in sorted_keys[:CACHE_MAX_SIZE // 4]:
                del FOLLOW_ALONG_GARMIN_SYNC_CACHE[key]
    
    cache_key = f"{user_id}:{workout_id}"
    FOLLOW_ALONG_GARMIN_SYNC_CACHE[cache_key] = (garmin_workout_id, datetime.utcnow())


# Platform type for source detection
VideoPlatform = Literal["instagram", "youtube", "tiktok", "vimeo", "other"]


def _detect_source_platform(url: str) -> VideoPlatform:
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
    
    @field_validator('garminWorkoutId')
    @classmethod
    def validate_garmin_workout_id(cls, v: str) -> str:
        """Validate Garmin workout ID format."""
        if not v or not v.strip():
            raise ValueError("Garmin workout ID cannot be empty")
        # Garmin workout IDs are typically alphanumeric with dashes
        if len(v) > 100:
            raise ValueError("Garmin workout ID exceeds maximum length")
        return v.strip()


class PushToAppleWatchRequest(BaseModel):
    """Request to push follow-along workout to Apple Watch."""
    appleWatchWorkoutId: str = Field(description="Apple Watch workout ID")
    
    @field_validator('appleWatchWorkoutId')
    @classmethod
    def validate_apple_watch_workout_id(cls, v: str) -> str:
        """Validate Apple Watch workout ID format."""
        if not v or not v.strip():
            raise ValueError("Apple Watch workout ID cannot be empty")
        if len(v) > 100:
            raise ValueError("Apple Watch workout ID exceeds maximum length")
        return v.strip()


class PushToIOSCompanionRequest(BaseModel):
    """Request to push follow-along workout to iOS Companion."""
    iosCompanionWorkoutId: str = Field(description="iOS Companion workout ID")


class CreateFollowAlongFromWorkoutRequest(BaseModel):
    """Request to create a follow-along from an existing workout."""
    workout: "WorkoutData" = Field(description="Workout data")
    sourceUrl: Optional[HttpUrl] = Field(None, description="Source video URL")
    
    model_config = {"extra": "allow"}  # Allow extra fields from source


# Forward reference resolution for type hints
class WorkoutStepData(BaseModel):
    """Validated workout step data."""
    order: Optional[int] = None
    label: Optional[str] = None
    duration_sec: Optional[int] = None
    target_reps: Optional[int] = None
    notes: Optional[str] = None


class WorkoutData(BaseModel):
    """Validated workout data structure."""
    title: str
    description: Optional[str] = None
    steps: List[Dict[str, Any]] = []
    
    model_config = {"extra": "allow"}  # Allow extra fields from source


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
        logger.error(f"Error creating follow-along workout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create follow-along workout",
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
        # Note: AI extraction from video metadata is not yet implemented.
        # Currently creates a placeholder workout. Full extraction requires
        # integrating video metadata APIs (YouTube Data API, etc.) or ML models.
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
        logger.error(f"Error ingesting follow-along workout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to ingest follow-along workout",
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
        logger.error(f"Error listing follow-along workouts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list follow-along workouts",
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
        title = workout_data.title if hasattr(workout_data, 'title') else workout_data.get("title", "Follow-along Workout")

        # Extract steps from workout
        steps = workout_data.steps if hasattr(workout_data, 'steps') else workout_data.get("steps", [])

        # Save follow-along workout
        workout = save_follow_along_workout(
            user_id=user_id,
            source="other",
            source_url=str(request.sourceUrl) if request.sourceUrl else None,
            title=title,
            description=workout_data.description if hasattr(workout_data, 'description') else workout_data.get("description"),
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
        logger.error(f"Error creating follow-along from workout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create follow-along from workout",
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
        logger.error(f"Error retrieving follow-along workout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve follow-along workout",
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
        logger.error(f"Error deleting follow-along workout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete follow-along workout",
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
    # AMA-599: Idempotency guard - prevent duplicate Garmin syncs
    if _has_garmin_synced_before(workout_id, user_id):
        logger.warning(f"Duplicate Garmin sync attempt for workout {workout_id} user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} already synced to Garmin",
        )
    
    try:
        # Update Garmin sync status
        update_follow_along_garmin_sync(
            workout_id=workout_id,
            user_id=user_id,
            garmin_workout_id=request.garminWorkoutId,
        )
        
        # Mark as synced to prevent future duplicates
        _mark_garmin_synced(workout_id, user_id, request.garminWorkoutId)

        logger.info(f"Pushed follow-along workout {workout_id} to Garmin for user {user_id}")
        return PushResponse(
            success=True,
            message=f"Follow-along workout {workout_id} pushed to Garmin",
        )
    except Exception as e:
        logger.error(f"Error pushing to Garmin: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to push to Garmin",
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
        logger.error(f"Error pushing to Apple Watch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to push to Apple Watch",
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
        logger.error(f"Error pushing to iOS Companion: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to push to iOS Companion",
        ) from e
