"""
Account management router.

Handles account-related operations including preview of deletion data
and account deletion with all associated data cleanup.

Endpoints:
- GET /account/deletion-preview — Preview what will be deleted
- DELETE /account — Delete account and all associated data

Part of AMA-596: Extract account router from monolithic app.py
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user
from api.deps import (
    get_account_deletion_preview,
    delete_user_account,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/account",
    tags=["account"],
)


@router.get("/deletion-preview")
async def get_deletion_preview(
    user_id: str = Depends(get_current_user)
):
    """
    Get a preview of all user data that will be deleted when account is deleted.

    Returns counts of:
    - workouts: Number of saved workouts
    - workout_completions: Number of completed workout records
    - programs: Number of workout programs
    - tags: Number of custom tags
    - follow_along_workouts: Number of follow-along workouts
    - paired_devices: Number of iOS devices paired
    - voice_settings: Whether voice settings exist
    - voice_corrections: Number of voice correction entries
    - strava_connection: Whether Strava is connected
    - garmin_connection: Whether Garmin is connected
    - total_items: Total count of deletable items
    - has_ios_devices: Boolean indicating if iOS app needs attention
    - has_external_connections: Boolean indicating if external services connected
    """
    try:
        preview = get_account_deletion_preview(user_id)
        if "error" in preview:
            raise HTTPException(status_code=500, detail=preview["error"])
        return preview
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get deletion preview for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("")
async def delete_account(
    user_id: str = Depends(get_current_user)
):
    """
    Delete user account and all associated data.

    This permanently deletes:
    - All workouts
    - All workout completions
    - All programs and tags
    - All follow-along workouts
    - All paired devices
    - Voice settings and corrections
    - External service connections (Strava, Garmin)
    - Calendar events
    - User profile

    Note: This does NOT delete the Clerk user - that must be done separately
    via Clerk's API or dashboard.
    """
    try:
        result = delete_user_account(user_id)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Failed to delete account"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete account for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
