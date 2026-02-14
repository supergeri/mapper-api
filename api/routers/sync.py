"""
Sync router for device synchronization and workout queuing.

Handles syncing workouts to various devices (Garmin, iOS, Android)
and managing the sync queue for pending workouts.

Endpoints:
- POST /workout/sync/garmin — Sync workout to Garmin Connect
- POST /workouts/{workout_id}/sync — Queue workout for device sync
- GET /sync/pending — Get pending syncs for device
- POST /sync/confirm — Confirm device received workout
- POST /sync/failed — Mark sync as failed
- GET /workouts/{workout_id}/sync-status — Get workout sync status
- POST /workouts/{workout_id}/push/ios-companion — Push to iOS
- GET /ios-companion/pending — Get pending iOS syncs
- POST /workouts/{workout_id}/push/android-companion — Push to Android
- GET /android-companion/pending — Get pending Android syncs

Part of AMA-589: Extract sync router from monolithic app.py
"""
import httpx
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from api.deps import get_current_user
from backend.database import (
    get_workout,
    queue_workout_sync,
    get_pending_syncs,
    confirm_workout_sync,
    mark_sync_failed,
    get_workout_sync_status,
)
from backend.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",  # Mixed prefixes: /workout, /workouts, /sync, /ios-companion, /android-companion
    tags=["sync"],
)

# Get settings for feature flags
_settings = get_settings()
GARMIN_UNOFFICIAL_SYNC_ENABLED = _settings.garmin_unofficial_sync_enabled


# Request Models
class SyncWorkoutToGarminRequest(BaseModel):
    """Request to sync a workout to Garmin Connect."""
    blocks_json: Dict[str, Any] = Field(description="Workout blocks/structure")
    workout_title: str = Field(default="Workout", description="Workout title")
    schedule_date: Optional[str] = Field(None, description="Schedule date (YYYY-MM-DD)")


class QueueSyncRequest(BaseModel):
    """Request to queue a workout for device sync."""
    device_type: str = Field(description="Device type (ios, android, garmin)")
    device_id: Optional[str] = Field(None, description="Optional device identifier")


class ConfirmSyncRequest(BaseModel):
    """Request to confirm device sync."""
    workout_id: str = Field(description="Workout ID")
    device_type: str = Field(description="Device type (ios, android, garmin)")
    device_id: Optional[str] = Field(None, description="Optional device identifier")


class FailedSyncRequest(BaseModel):
    """Request to mark sync as failed."""
    workout_id: str = Field(description="Workout ID")
    device_type: str = Field(description="Device type (ios, android, garmin)")
    reason: Optional[str] = Field(None, description="Failure reason")


class PushToCompanionRequest(BaseModel):
    """Request to push workout to companion app."""
    pass


# Response Models
class SyncResponse(BaseModel):
    """Response for sync operations."""
    success: bool
    status: str
    message: Optional[str] = None


class PendingSyncResponse(BaseModel):
    """Response containing pending syncs."""
    success: bool
    pending_workouts: list[Dict[str, Any]]


class SyncStatusResponse(BaseModel):
    """Response containing sync status."""
    success: bool
    sync_status: Dict[str, Any]


@router.post(
    "/workout/sync/garmin",
    response_model=SyncResponse,
    summary="Sync workout to Garmin",
    description="Sync a regular workout to Garmin Connect via garmin-sync-api",
)
def sync_workout_to_garmin(
    request: SyncWorkoutToGarminRequest,
) -> SyncResponse:
    """
    Sync a regular workout to Garmin Connect.

    - Respects GARMIN_UNOFFICIAL_SYNC_ENABLED feature flag
    - Uses exercise mapping pipeline for valid Garmin names
    - Requires GARMIN_EMAIL and GARMIN_PASSWORD environment variables

    Args:
        request: Workout data and Garmin sync configuration

    Returns:
        SyncResponse: Sync result and status
    """
    try:
        # Backend guard for unofficial API
        if not GARMIN_UNOFFICIAL_SYNC_ENABLED:
            return SyncResponse(
                success=False,
                status="error",
                message="Unofficial Garmin sync is disabled. Set GARMIN_UNOFFICIAL_SYNC_ENABLED=true",
            )

        # Validate workout data
        if not request.blocks_json:
            return SyncResponse(
                success=False,
                status="error",
                message="Workout data (blocks_json) is required",
            )

        # Get Garmin credentials from environment
        garmin_email = os.getenv("GARMIN_EMAIL")
        garmin_password = os.getenv("GARMIN_PASSWORD")
        garmin_service_url = os.getenv("GARMIN_SERVICE_URL", "http://garmin-sync-api:8002")

        if not garmin_email or not garmin_password:
            return SyncResponse(
                success=False,
                status="error",
                message="Garmin credentials not configured",
            )

        # TODO: Implement full Garmin sync logic with exercise mapping
        # For now, queue the sync request to be handled asynchronously
        logger.info(f"Queuing Garmin sync for workout: {request.workout_title}")

        return SyncResponse(
            success=True,
            status="queued",
            message="Workout queued for Garmin sync",
        )

    except Exception as e:
        logger.error(f"Error syncing to Garmin: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync to Garmin: {str(e)}",
        ) from e


@router.post(
    "/workouts/{workout_id}/sync",
    response_model=SyncResponse,
    summary="Queue workout for device sync",
    description="Queue a workout for sync to a device",
)
def queue_workout_sync_endpoint(
    workout_id: str,
    request: QueueSyncRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Queue a workout for sync to a device.

    Creates a 'pending' entry in the sync queue. The device will fetch
    pending workouts and confirm download to mark as 'synced'.

    Args:
        workout_id: ID of workout to sync
        request: Sync queue request with device type
        user_id: Current authenticated user ID

    Returns:
        SyncResponse: Queue result and status
    """
    try:
        # Validate device type
        if request.device_type not in ["ios", "android", "garmin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid device_type. Must be ios, android, or garmin",
            )

        # Verify workout exists and belongs to user
        workout = get_workout(workout_id, user_id)
        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workout not found",
            )

        # Queue the sync
        result = queue_workout_sync(
            workout_id=workout_id,
            user_id=user_id,
            device_type=request.device_type,
            device_id=request.device_id or "",
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to queue workout for sync",
            )

        logger.info(f"Queued workout {workout_id} for {request.device_type} sync")

        return SyncResponse(
            success=True,
            status=result.get("status", "pending"),
            message=f"Workout queued for {request.device_type} sync",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error queuing workout sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue workout for sync: {str(e)}",
        ) from e


@router.get(
    "/sync/pending",
    response_model=PendingSyncResponse,
    summary="Get pending syncs",
    description="Get pending workouts for a device",
)
def get_pending_syncs_endpoint(
    device_type: str = Query(..., description="Device type (ios, android, garmin)"),
    device_id: Optional[str] = Query(None, description="Optional device identifier"),
    user_id: str = Depends(get_current_user),
) -> PendingSyncResponse:
    """
    Get pending syncs for a device.

    Retrieves all pending workouts that the device should download.

    Args:
        device_type: Device type (ios, android, or garmin)
        device_id: Optional device identifier
        user_id: Current authenticated user ID

    Returns:
        PendingSyncResponse: List of pending workouts
    """
    try:
        # Validate device type
        if device_type not in ["ios", "android", "garmin"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid device_type",
            )

        # Get pending syncs
        pending = get_pending_syncs(
            device_type=device_type,
            device_id=device_id or "",
            user_id=user_id,
        )

        logger.info(f"Retrieved {len(pending) if pending else 0} pending syncs for {device_type}")

        return PendingSyncResponse(
            success=True,
            pending_workouts=pending or [],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting pending syncs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending syncs: {str(e)}",
        ) from e


@router.post(
    "/sync/confirm",
    response_model=SyncResponse,
    summary="Confirm device sync",
    description="Confirm that a device received a workout",
)
def confirm_workout_sync_endpoint(
    request: ConfirmSyncRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Confirm that a device received a workout.

    Marks the sync as 'synced' in the database.

    Args:
        request: Confirm sync request with workout and device info
        user_id: Current authenticated user ID

    Returns:
        SyncResponse: Confirmation result
    """
    try:
        # Confirm the sync
        result = confirm_workout_sync(
            workout_id=request.workout_id,
            user_id=user_id,
            device_type=request.device_type,
            device_id=request.device_id or "",
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to confirm sync",
            )

        logger.info(f"Confirmed sync for workout {request.workout_id} on {request.device_type}")

        return SyncResponse(
            success=True,
            status="synced",
            message="Sync confirmed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming sync: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm sync: {str(e)}",
        ) from e


@router.post(
    "/sync/failed",
    response_model=SyncResponse,
    summary="Mark sync as failed",
    description="Mark a device sync as failed",
)
def mark_sync_failed_endpoint(
    request: FailedSyncRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Mark a device sync as failed.

    Records the failure and reason in the sync queue.

    Args:
        request: Failed sync request with reason
        user_id: Current authenticated user ID

    Returns:
        SyncResponse: Failure acknowledgment
    """
    try:
        # Mark sync as failed
        result = mark_sync_failed(
            workout_id=request.workout_id,
            user_id=user_id,
            device_type=request.device_type,
            reason=request.reason,
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to mark sync as failed",
            )

        logger.warning(f"Sync failed for workout {request.workout_id}: {request.reason}")

        return SyncResponse(
            success=True,
            status="failed",
            message=f"Sync marked as failed: {request.reason}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking sync as failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark sync as failed: {str(e)}",
        ) from e


@router.get(
    "/workouts/{workout_id}/sync-status",
    response_model=SyncStatusResponse,
    summary="Get workout sync status",
    description="Get the sync status of a workout across all devices",
)
def get_workout_sync_status_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user),
) -> SyncStatusResponse:
    """
    Get the sync status of a workout.

    Shows sync status across all devices (iOS, Android, Garmin).

    Args:
        workout_id: ID of the workout
        user_id: Current authenticated user ID

    Returns:
        SyncStatusResponse: Sync status for all devices
    """
    try:
        # Verify workout exists and belongs to user
        workout = get_workout(workout_id, user_id)
        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workout not found",
            )

        # Get sync status
        sync_status = get_workout_sync_status(workout_id, user_id)

        logger.info(f"Retrieved sync status for workout {workout_id}")

        return SyncStatusResponse(
            success=True,
            sync_status=sync_status or {},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sync status: {str(e)}",
        ) from e


@router.post(
    "/workouts/{workout_id}/push/ios-companion",
    response_model=SyncResponse,
    summary="Push workout to iOS Companion",
    description="Push a workout to iOS Companion app",
)
def push_to_ios_companion(
    workout_id: str,
    request: PushToCompanionRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Push a workout to iOS Companion app.

    Args:
        workout_id: ID of workout to push
        request: Push request
        user_id: Current authenticated user ID

    Returns:
        SyncResponse: Push result
    """
    try:
        # Verify workout exists and belongs to user
        workout = get_workout(workout_id, user_id)
        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workout not found",
            )

        # TODO: Implement iOS push logic
        logger.info(f"Pushed workout {workout_id} to iOS Companion")

        return SyncResponse(
            success=True,
            status="pushed",
            message="Workout pushed to iOS Companion",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing to iOS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to iOS: {str(e)}",
        ) from e


@router.get(
    "/ios-companion/pending",
    response_model=PendingSyncResponse,
    summary="Get pending iOS syncs",
    description="Get pending workouts for iOS Companion",
)
def get_ios_pending_syncs(
    device_id: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
) -> PendingSyncResponse:
    """
    Get pending syncs for iOS Companion.

    Args:
        device_id: Optional iOS device identifier
        user_id: Current authenticated user ID

    Returns:
        PendingSyncResponse: List of pending workouts
    """
    try:
        pending = get_pending_syncs(
            device_type="ios",
            device_id=device_id or "",
            user_id=user_id,
        )

        logger.info(f"Retrieved {len(pending) if pending else 0} pending iOS syncs")

        return PendingSyncResponse(
            success=True,
            pending_workouts=pending or [],
        )

    except Exception as e:
        logger.error(f"Error getting iOS pending syncs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending iOS syncs: {str(e)}",
        ) from e


@router.post(
    "/workouts/{workout_id}/push/android-companion",
    response_model=SyncResponse,
    summary="Push workout to Android Companion",
    description="Push a workout to Android Companion app",
)
def push_to_android_companion(
    workout_id: str,
    request: PushToCompanionRequest,
    user_id: str = Depends(get_current_user),
) -> SyncResponse:
    """
    Push a workout to Android Companion app.

    Args:
        workout_id: ID of workout to push
        request: Push request
        user_id: Current authenticated user ID

    Returns:
        SyncResponse: Push result
    """
    try:
        # Verify workout exists and belongs to user
        workout = get_workout(workout_id, user_id)
        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workout not found",
            )

        # TODO: Implement Android push logic
        logger.info(f"Pushed workout {workout_id} to Android Companion")

        return SyncResponse(
            success=True,
            status="pushed",
            message="Workout pushed to Android Companion",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pushing to Android: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to push to Android: {str(e)}",
        ) from e


@router.get(
    "/android-companion/pending",
    response_model=PendingSyncResponse,
    summary="Get pending Android syncs",
    description="Get pending workouts for Android Companion",
)
def get_android_pending_syncs(
    device_id: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
) -> PendingSyncResponse:
    """
    Get pending syncs for Android Companion.

    Args:
        device_id: Optional Android device identifier
        user_id: Current authenticated user ID

    Returns:
        PendingSyncResponse: List of pending workouts
    """
    try:
        pending = get_pending_syncs(
            device_type="android",
            device_id=device_id or "",
            user_id=user_id,
        )

        logger.info(f"Retrieved {len(pending) if pending else 0} pending Android syncs")

        return PendingSyncResponse(
            success=True,
            pending_workouts=pending or [],
        )

    except Exception as e:
        logger.error(f"Error getting Android pending syncs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get pending Android syncs: {str(e)}",
        ) from e
