"""
Sync router for device sync endpoints (iOS, Android, Garmin).

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-589: Extract sync endpoints from app.py

This router contains endpoints for:
- /workouts/{workout_id}/push/ios-companion - Push workout to iOS Companion App
- /ios-companion/pending - Get pending iOS sync workouts
- /workouts/{workout_id}/push/android-companion - Push workout to Android Companion App
- /android-companion/pending - Get pending Android sync workouts
- /workout/sync/garmin - Sync workout to Garmin Connect
- /workouts/{workout_id}/sync - Queue workout for device sync (AMA-307)
- /sync/pending - Get pending syncs for device
- /sync/confirm - Confirm device received workout
- /sync/failed - Mark sync as failed
- /workouts/{workout_id}/sync-status - Get sync status for workout

Note: Endpoints support iOS, Android, and Garmin devices with proper authentication.
Implements AMA-307 sync queue pattern for proper state tracking.
"""

import logging
import json
import os
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

import httpx
from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

from api.deps import get_current_user
from backend.database import (
    get_workout,
    update_workout_ios_companion_sync,
    update_workout_android_companion_sync,
    get_ios_companion_pending_workouts,
    get_android_companion_pending_workouts,
    queue_workout_sync,
    get_pending_syncs,
    confirm_sync,
    report_sync_failed,
    get_workout_sync_status,
)
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_hyrox_yaml import map_exercise_to_garmin
from backend.core.exercise_categories import add_category_to_exercise_name
from backend.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Device Sync"],
)

# Feature flags
_settings = get_settings()
GARMIN_UNOFFICIAL_SYNC_ENABLED = _settings.garmin_unofficial_sync_enabled
GARMIN_EXPORT_DEBUG = _settings.garmin_export_debug

# =============================================================================
# Security: Shared Garmin Account Configuration (AMA-589)
# =============================================================================
# CRITICAL: All users share the same Garmin Connect account via service account credentials
# This is a temporary solution for MVP. Production should implement per-user OAuth or
# encrypted per-user credential storage.
GARMIN_SHARED_ACCOUNT_ENABLED = os.getenv("GARMIN_UNOFFICIAL_SYNC_ENABLED", "false").lower() == "true"
GARMIN_CREDENTIAL_STRATEGY = "SHARED_SERVICE_ACCOUNT"  # TODO: Migrate to per-user credentials in AMA-XXX


# =============================================================================
# Enums
# =============================================================================


class DeviceType(str, Enum):
    """Supported device types for workout sync."""
    IOS = "ios"
    ANDROID = "android"
    GARMIN = "garmin"


# =============================================================================
# Request/Response Models
# =============================================================================


class PushWorkoutToIOSCompanionRequest(BaseModel):
    """Request to push workout to iOS Companion App."""
    userId: str | None = None  # Deprecated: use auth instead


class PushWorkoutToAndroidCompanionRequest(BaseModel):
    """Request to push workout to Android Companion App."""
    userId: str | None = None  # Deprecated: use auth instead


class SyncToGarminRequest(BaseModel):
    """Request to sync workout to Garmin Connect."""
    blocks_json: dict = Field(description="Workout blocks structure with exercises and supersets")
    workout_title: str = Field(min_length=1, max_length=256, description="Workout title")
    schedule_date: Optional[str] = Field(None, description="Schedule date in YYYY-MM-DD format")
    
    @field_validator('schedule_date')
    @classmethod
    def validate_schedule_date(cls, v):
        """Validate schedule_date is in YYYY-MM-DD format."""
        if v is None:
            return v
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError('schedule_date must be in YYYY-MM-DD format (e.g., 2026-02-13)')
        return v
    
    @field_validator('blocks_json')
    @classmethod
    def validate_blocks_json(cls, v):
        """Validate blocks_json has required structure."""
        if not isinstance(v, dict):
            raise ValueError('blocks_json must be a dictionary')
        if 'blocks' not in v:
            raise ValueError('blocks_json must contain "blocks" key with list of workout blocks')
        return v


class QueueSyncRequest(BaseModel):
    """Request to queue a workout for sync."""
    device_type: DeviceType
    device_id: str | None = None


class ConfirmSyncRequest(BaseModel):
    """Request to confirm workout sync receipt."""
    workout_id: str
    device_type: DeviceType
    device_id: str | None = None


class ReportSyncFailedRequest(BaseModel):
    """Request to report sync failure."""
    workout_id: str
    device_type: DeviceType
    error: str
    device_id: str | None = None


# =============================================================================
# Helper Functions
# =============================================================================


def calculate_intervals_duration(intervals: list) -> int:
    """
    Calculate total duration in seconds from intervals list.
    
    Recursively processes nested intervals (repeat blocks) and handles
    different interval types (time, reps, warmup, cooldown, distance).
    
    Args:
        intervals: List of interval dictionaries
        
    Returns:
        Total duration in seconds
    """
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
    Convert a workout exercise to iOS/Android companion interval format.
    
    Handles both rep-based and time-based exercises, including sets and rest times.
    
    Args:
        exercise: Exercise data dictionary
        
    Returns:
        Interval dictionary in companion app format
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


async def _transform_workout_to_companion(
    workout_data: dict,
    workout_title: str
) -> dict:
    """
    Transform workout data to companion app interval format (iOS/Android).
    
    Extracts common transformation logic shared by iOS and Android endpoints.
    Handles: intervals, warmup/cooldown, reps, durations, load calculation, step building.
    
    ISSUE 1 FIX (AMA-589): DRY Violation - Extract Duplicate iOS/Android Code
    This helper eliminates ~180 lines of identical transformation logic.
    
    Args:
        workout_data: Workout structure with blocks and exercises
        workout_title: Name/title for the workout
        
    Returns:
        Dictionary with keys: id, name, sport, duration, source, sourceUrl, intervals
        
    Raises:
        ValueError: If workout data structure is invalid
        TypeError: If required fields are missing or wrong type
    """
    try:
        # Detect sport type from workout structure
        blocks = workout_data.get("blocks", [])
        sport = "strength"  # Default
        
        for block in blocks:
            structure = block.get("structure", "")
            if structure in ["tabata", "hiit", "circuit", "emom", "amrap"]:
                sport = "cardio"
                break
        
        # Build intervals from blocks
        intervals = []
        total_duration = 0
        
        for block in blocks:
            exercises = block.get("exercises", [])
            rounds = block.get("rounds", 1) or 1
            rest_between_rounds = block.get("rest_between_rounds_sec") or block.get("rest_between_sec", 60)
            
            # Warmup block
            if block.get("label", "").lower() in ["warmup", "warm up", "warm-up"]:
                warmup_duration = sum(
                    e.get("duration_sec", 60) for e in exercises
                ) or 300
                intervals.append({
                    "kind": "warmup",
                    "seconds": warmup_duration,
                    "target": block.get("label", "Warmup")
                })
                total_duration += warmup_duration
                continue
            
            # Cooldown block
            if block.get("label", "").lower() in ["cooldown", "cool down", "cool-down"]:
                cooldown_duration = sum(
                    e.get("duration_sec", 60) for e in exercises
                ) or 300
                intervals.append({
                    "kind": "cooldown",
                    "seconds": cooldown_duration,
                    "target": block.get("label", "Cooldown")
                })
                total_duration += cooldown_duration
                continue
            
            # Create repeat block if rounds > 1
            if rounds > 1:
                inner_intervals = []
                for exercise in exercises:
                    inner_interval = convert_exercise_to_interval(exercise)
                    inner_intervals.append(inner_interval)
                
                intervals.append({
                    "kind": "repeat",
                    "reps": rounds,
                    "intervals": inner_intervals
                })
                
                # Calculate duration for repeat
                inner_duration = sum(
                    (e.get("duration_sec", 0) or 0) + (e.get("rest_sec", 0) or 0)
                    for e in exercises
                )
                total_duration += (inner_duration * rounds) + (rest_between_rounds * (rounds - 1))
            else:
                # Single round - add exercises directly
                for exercise in exercises:
                    interval = convert_exercise_to_interval(exercise)
                    intervals.append(interval)
                    total_duration += (exercise.get("duration_sec", 0) or 0) + (exercise.get("rest_sec", 0) or 0)
        
        # Create payload for companion app (iOS or Android will add their wrapper)
        return {
            "id": None,  # Will be set by caller
            "name": workout_title,
            "sport": sport,
            "duration": total_duration,
            "source": "amakaflow",
            "sourceUrl": None,
            "intervals": intervals
        }
    
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to transform workout to companion format: {e}", exc_info=True)
        raise ValueError(f"Invalid workout data structure: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during workout transformation: {e}", exc_info=True)
        raise


# =============================================================================
# iOS Companion App Endpoints (AMA-199)
# =============================================================================


@router.post("/workouts/{workout_id}/push/ios-companion")
async def push_workout_to_ios_companion_endpoint(
    workout_id: str,
    request: PushWorkoutToIOSCompanionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Push a regular (blocks-based) workout to iOS Companion App.
    
    Transforms the workout structure into the iOS app's interval format
    and queues it for sync. This endpoint is for workouts created through
    the standard workflow, not follow-along workouts ingested from Instagram.
    
    Args:
        workout_id: Workout identifier
        request: Push request (legacy userId field deprecated)
        user_id: Authenticated user ID from JWT
        
    Returns:
        Success response with payload for iOS Companion App format
        
    ISSUE 1 FIX (AMA-589): Uses shared helper function _transform_workout_to_companion
    """
    try:
        # Get workout
        workout_record = await run_in_threadpool(get_workout, workout_id, user_id)
        if not workout_record:
            raise HTTPException(status_code=404, detail="Workout not found")
        
        workout_data = workout_record.get("workout_data", {})
        title = workout_record.get("title") or workout_data.get("title", "Workout")
        
        # Use shared helper function to transform to companion format
        payload = await _transform_workout_to_companion(workout_data, title)
        payload["id"] = workout_id

        # Queue workout for sync to iOS (AMA-307)
        await run_in_threadpool(queue_workout_sync, workout_id, user_id, "ios")

        # Also update legacy column for backward compatibility
        await run_in_threadpool(update_workout_ios_companion_sync, workout_id, user_id)

        logger.info(f"Pushed iOS Companion workout {workout_id} for user {user_id}")

        return {
            "success": True,
            "status": "success",
            "iosCompanionWorkoutId": workout_id,
            "payload": payload
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to transform iOS Companion workout {workout_id}: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail="Invalid workout data structure")
    except Exception as e:
        logger.error(f"Unexpected error during iOS Companion push {workout_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.get("/ios-companion/pending")
async def get_ios_companion_pending_endpoint(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
    exclude_completed: bool = Query(True, description="Exclude workouts that have been completed")
):
    """
    Get workouts pending sync to iOS Companion App.
    
    Called by the iOS Companion App to discover workouts ready for sync to Apple Watch.
    Returns workouts where ios_companion_synced_at is set, ordered by most recently pushed.
    By default excludes completed workouts.
    
    Args:
        user_id: Authenticated user ID from JWT
        limit: Maximum number of workouts to return (1-100)
        exclude_completed: Whether to exclude completed workouts
        
    Returns:
        List of pending iOS Companion workouts with interval data
    """
    try:
        workouts = await run_in_threadpool(get_ios_companion_pending_workouts, user_id, limit=limit, exclude_completed=exclude_completed)

        # Transform each workout to iOS companion format
        transformed = []
        for workout_record in workouts:
            workout_data = workout_record.get("workout_data", {})
            title = workout_record.get("title") or workout_data.get("title", "Workout")

            # Use to_workoutkit to properly transform intervals
            # This handles warmup, sets as RepeatInterval, and default rest
            try:
                workoutkit_dto = to_workoutkit(workout_data)
                intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
                sport = workoutkit_dto.sportType
            except (ValueError, KeyError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
                # Fallback to simple transformation
                intervals = []
                sport = "strengthTraining"
                try:
                    for block in workout_data.get("blocks", []):
                        for exercise in block.get("exercises", []):
                            intervals.append(convert_exercise_to_interval(exercise))
                except (KeyError, AttributeError, TypeError) as fallback_err:
                    logger.warning(f"Fallback transformation also failed for {workout_record.get('id')}: {fallback_err}")

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

        logger.info(f"Retrieved {len(transformed)} pending iOS Companion workouts for user {user_id}")

        return {
            "success": True,
            "workouts": transformed,
            "count": len(transformed)
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to process iOS Companion pending workouts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process workout data")
    except Exception as e:
        logger.error(f"Unexpected error retrieving iOS Companion pending workouts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Operation failed")


# =============================================================================
# Android Companion App Endpoints (AMA-246)
# =============================================================================


@router.post("/workouts/{workout_id}/push/android-companion")
async def push_workout_to_android_companion_endpoint(
    workout_id: str,
    request: PushWorkoutToAndroidCompanionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Push a regular (blocks-based) workout to Android Companion App.
    
    Transforms the workout structure into the Android app's interval format
    and queues it for sync. This endpoint is for workouts created through
    the standard workflow, not follow-along workouts.
    
    Args:
        workout_id: Workout identifier
        request: Push request (legacy userId field deprecated)
        user_id: Authenticated user ID from JWT
        
    Returns:
        Success response with payload for Android Companion App format
        
    ISSUE 1 FIX (AMA-589): Uses shared helper function _transform_workout_to_companion
    """
    try:
        # Get workout
        workout_record = await run_in_threadpool(get_workout, workout_id, user_id)
        if not workout_record:
            raise HTTPException(status_code=404, detail="Workout not found")

        workout_data = workout_record.get("workout_data", {})
        title = workout_record.get("title") or workout_data.get("title", "Workout")

        # Use shared helper function to transform to companion format
        payload = await _transform_workout_to_companion(workout_data, title)
        payload["id"] = workout_id

        # Queue workout for sync to Android (AMA-307)
        await run_in_threadpool(queue_workout_sync, workout_id, user_id, "android")

        # Also update legacy column for backward compatibility
        await run_in_threadpool(update_workout_android_companion_sync, workout_id, user_id)

        logger.info(f"Pushed Android Companion workout {workout_id} for user {user_id}")

        return {
            "success": True,
            "status": "success",
            "androidCompanionWorkoutId": workout_id,
            "payload": payload
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to transform Android Companion workout {workout_id}: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail="Invalid workout data structure")
    except Exception as e:
        logger.error(f"Unexpected error during Android Companion push {workout_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.get("/android-companion/pending")
async def get_android_companion_pending_endpoint(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
    exclude_completed: bool = Query(True, description="Exclude workouts that have been completed")
):
    """
    Get workouts pending sync to Android Companion App.
    
    Called by the Android Companion App to discover workouts ready for sync
    to Wear OS/Health Connect watches. Returns workouts where
    android_companion_synced_at is set, ordered by most recently pushed.
    By default excludes completed workouts.
    
    Args:
        user_id: Authenticated user ID from JWT
        limit: Maximum number of workouts to return (1-100)
        exclude_completed: Whether to exclude completed workouts
        
    Returns:
        List of pending Android Companion workouts with interval data
    """
    try:
        workouts = await run_in_threadpool(get_android_companion_pending_workouts, user_id, limit=limit, exclude_completed=exclude_completed)

        # Transform each workout to companion format
        transformed = []
        for workout_record in workouts:
            workout_data = workout_record.get("workout_data", {})
            title = workout_record.get("title") or workout_data.get("title", "Workout")

            # Use to_workoutkit to properly transform intervals
            try:
                workoutkit_dto = to_workoutkit(workout_data)
                intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
                sport = workoutkit_dto.sportType
            except (ValueError, KeyError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
                # Fallback to simple transformation
                intervals = []
                sport = "strengthTraining"
                try:
                    for block in workout_data.get("blocks", []):
                        for exercise in block.get("exercises", []):
                            intervals.append(convert_exercise_to_interval(exercise))
                except (KeyError, AttributeError, TypeError) as fallback_err:
                    logger.warning(f"Fallback transformation also failed for {workout_record.get('id')}: {fallback_err}")

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
                "pushedAt": workout_record.get("android_companion_synced_at"),
                "createdAt": workout_record.get("created_at"),
            })

        logger.info(f"Retrieved {len(transformed)} pending Android Companion workouts for user {user_id}")

        return {
            "success": True,
            "workouts": transformed,
            "count": len(transformed)
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to process Android Companion pending workouts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process workout data")
    except Exception as e:
        logger.error(f"Unexpected error retrieving Android Companion pending workouts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Operation failed")


# =============================================================================
# Garmin Sync Endpoint (AMA-280: Unofficial Garmin Sync via garmin-sync-api)
# =============================================================================


@router.post("/workout/sync/garmin")
async def sync_workout_to_garmin(
    request: SyncToGarminRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Sync a regular workout to Garmin Connect via garmin-sync-api.
    
    Uses the same exercise mapping pipeline as the YAML export
    (map_exercise_to_garmin + add_category_to_exercise_name), so
    Garmin receives valid exercise names instead of generic steps.
    
    Respects GARMIN_UNOFFICIAL_SYNC_ENABLED environment flag.
    Requires GARMIN_EMAIL and GARMIN_PASSWORD environment variables.
    
    SECURITY NOTE (ISSUE 2 - AMA-589):
    ⚠️  Uses shared service account Garmin credentials (GARMIN_EMAIL/PASSWORD env vars).
    All users share the same Garmin account for sync operations.
    This is a temporary MVP solution. For production, implement per-user OAuth
    or encrypted credential storage with per-user API keys.
    
    Args:
        request: SyncToGarminRequest with:
            - blocks_json: Workout structure with blocks and exercises (validated)
            - workout_title: Name for the Garmin workout (1-256 chars)
            - schedule_date: Optional date to schedule workout (YYYY-MM-DD format)
        user_id: Authenticated user ID from JWT
            
    Returns:
        Success/error response with Garmin workout ID if successful
        
    Raises:
        HTTPException 400: Invalid request data (missing/malformed blocks_json)
        HTTPException 422: Invalid workout data structure (transformation failed)
        HTTPException 500: Garmin sync failed or credentials not configured
        HTTPException 503: Unofficial Garmin sync is disabled
    """
    # Backend guard for unofficial API
    if not GARMIN_UNOFFICIAL_SYNC_ENABLED:
        raise HTTPException(status_code=503, detail="Unofficial Garmin sync is disabled")

    # Get workout data from request
    blocks_json = request.blocks_json
    workout_title = request.workout_title
    schedule_date = request.schedule_date

    if not blocks_json:
        raise HTTPException(status_code=400, detail="Workout data is required")

    # Get Garmin credentials from environment
    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")

    if not garmin_email or not garmin_password:
        raise HTTPException(status_code=500, detail="Garmin credentials not configured")

    steps: list[dict[str, str]] = []

    def build_step_from_exercise(exercise: dict):
        """
        Build a single Garmin step (garmin_name_with_category -> '10 reps | note').

        We keep the existing target encoding but ALSO append a clean note
        derived from:
          - exercise["note"] (if present)
          - exercise["description"] (if present)
          - the description returned by map_exercise_to_garmin

        This note is what Garmin shows in the Notes field and can later be
        reused for an iPhone follow-along view.
        """
        ex_name = exercise.get("name", "") or ""
        if not ex_name:
            return None

        reps = exercise.get("reps")
        reps_range = exercise.get("reps_range")
        duration = exercise.get("duration_sec")
        distance_m = exercise.get("distance_m")

        # Use validated mapped_name if available
        mapped_name = exercise.get("mapped_name") or exercise.get("mapped_to")
        candidate_names: list[str] = []
        if mapped_name:
            candidate_names.append(mapped_name)
        candidate_names.append(ex_name)

        # Reuse the same mapping pipeline as blocks_to_hyrox_yaml
        exercise_name_to_map = mapped_name if mapped_name else ex_name
        garmin_name, description, mapping_info = map_exercise_to_garmin(
            exercise_name_to_map,
            ex_reps=reps,
            ex_distance_m=distance_m,
        )

        garmin_name_with_category = add_category_to_exercise_name(garmin_name)

        # Base target text
        if reps:
            base_detail = f"{reps} reps"
        elif reps_range:
            base_detail = f"{reps_range} reps"
        elif duration:
            base_detail = f"{duration}s"
        elif distance_m:
            base_detail = f"{distance_m}m"
        else:
            base_detail = "10 reps"

        # Clean note text
        note = (
            (exercise.get("note") or "").strip()
            or (exercise.get("description") or "").strip()
            or (description or "").strip()
        )

        if note:
            step_detail = f"{base_detail} | {note}"
        else:
            step_detail = base_detail

        step = {garmin_name_with_category: step_detail}

        logger.info(
            "GARMIN_SYNC_STEP original=%r mapped_name=%r garmin=%r detail=%r source=%s conf=%s note=%r",
            ex_name,
            mapped_name,
            garmin_name_with_category,
            step_detail,
            mapping_info.get("source"),
            mapping_info.get("confidence"),
            note,
        )

        return step

    # Walk through blocks / exercises / supersets and build steps list
    for block in blocks_json.get("blocks", []):
        # Standalone exercises
        for exercise in block.get("exercises", []):
            step = build_step_from_exercise(exercise)
            if step:
                steps.append(step)

        # Supersets
        for superset in block.get("supersets", []):
            for exercise in superset.get("exercises", []):
                step = build_step_from_exercise(exercise)
                if step:
                    steps.append(step)

    if not steps:
        raise HTTPException(status_code=400, detail="No valid exercises found to sync")

    # Final workouts payload for garmin-sync-api
    garmin_workouts = {workout_title: steps}

    garmin_url = os.getenv("GARMIN_SERVICE_URL", "http://garmin-sync-api:8002")

    garmin_payload = {
        "email": garmin_email,
        "password": garmin_password,
        "workouts": garmin_workouts,
        "delete_same_name": False,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Import workout
            logger.info("GARMIN_SYNC_IMPORT payload=%s", json.dumps(garmin_payload, indent=2))
            response = await client.post(f"{garmin_url}/workouts/import", json=garmin_payload)
            response.raise_for_status()

            # Optionally schedule the workout
            if schedule_date:
                schedule_payload = {
                    "email": garmin_email,
                    "password": garmin_password,
                    "start_from": schedule_date,
                    "workouts": [workout_title],
                }
                logger.info("GARMIN_SYNC_SCHEDULE payload=%s", json.dumps(schedule_payload, indent=2))
                schedule_response = await client.post(
                    f"{garmin_url}/workouts/schedule",
                    json=schedule_payload,
                )
                schedule_response.raise_for_status()

        logger.info(f"Synced workout to Garmin: {workout_title}")
        
        return {
            "success": True,
            "status": "success",
            "message": "Workout synced to Garmin successfully",
            "garminWorkoutId": workout_title,
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to build Garmin workout steps: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail="Invalid workout data structure")
    except Exception as e:
        logger.error(f"Unexpected error syncing workout to Garmin: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Garmin sync failed. Please try again.")


# =============================================================================
# Sync Queue Endpoints (AMA-307: Proper Sync State Tracking)
# =============================================================================


@router.post("/workouts/{workout_id}/sync")
async def queue_workout_sync_endpoint(
    workout_id: str,
    request: QueueSyncRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Queue a workout for sync to a device (AMA-307).

    Creates a 'pending' entry in the sync queue. The device will fetch
    pending workouts and confirm download to mark as 'synced'.

    This replaces the immediate 'synced' status from the old push endpoints.
    
    Args:
        workout_id: Workout identifier
        request: Queue sync request with device type and optional device ID
        user_id: Authenticated user ID from JWT
        
    Returns:
        Success response with queue status and timestamp
    """
    # Device type is validated by Pydantic (DeviceType enum)

    # Verify workout exists and belongs to user
    workout = await run_in_threadpool(get_workout, workout_id, user_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    result = await run_in_threadpool(
        queue_workout_sync,
        workout_id=workout_id,
        user_id=user_id,
        device_type=request.device_type.value,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=500, detail="Operation failed")

    logger.info(f"Queued workout {workout_id} for {request.device_type.value} sync by user {user_id}")

    return {
        "success": True,
        "status": result.get("status"),
        "queued_at": result.get("queued_at")
    }


@router.get("/sync/pending")
async def get_pending_syncs_endpoint(
    device_type: str = Query(..., description="Device type: ios, android, or garmin"),
    device_id: str = Query(None, description="Optional device identifier"),
    user_id: str = Depends(get_current_user)
):
    """
    Get workouts pending sync for a device (AMA-307).

    Called by mobile apps to discover workouts queued for download.
    Returns full workout data including intervals, in the order they were queued.
    
    Args:
        device_type: Type of device (ios, android, or garmin)
        device_id: Optional device identifier for multi-device support
        user_id: Authenticated user ID from JWT
        
    Returns:
        List of pending workouts with full interval data
    """
    try:
        # Validate device_type
        valid_types = {e.value for e in DeviceType}
        if device_type not in valid_types:
            raise HTTPException(status_code=400, detail="Invalid device_type")

        pending = await run_in_threadpool(
            get_pending_syncs,
            user_id=user_id,
            device_type=device_type,
            device_id=device_id or ""
        )

        # Transform to full workout format (same as /ios-companion/pending)
        workouts = []
        for entry in pending:
            workout_record = entry.get("workouts", {})
            if not workout_record:
                continue

            workout_data = workout_record.get("workout_data", {})
            title = workout_record.get("title") or workout_data.get("title", "Workout")

            # Use to_workoutkit to properly transform intervals
            try:
                workoutkit_dto = to_workoutkit(workout_data)
                intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
                sport = workoutkit_dto.sportType
            except (ValueError, KeyError, AttributeError, TypeError) as e:
                logger.warning(f"Failed to transform workout {entry.get('workout_id')}: {e}")
                # Fallback to simple transformation
                intervals = []
                sport = "strengthTraining"
                try:
                    for block in workout_data.get("blocks", []):
                        for exercise in block.get("exercises", []):
                            intervals.append(convert_exercise_to_interval(exercise))
                except (KeyError, AttributeError, TypeError) as fallback_err:
                    logger.warning(f"Fallback transformation failed for {entry.get('workout_id')}: {fallback_err}")

            # Calculate total duration from intervals
            total_duration = calculate_intervals_duration(intervals)

            workouts.append({
                "id": entry.get("workout_id"),
                "name": title,
                "sport": sport,
                "duration": total_duration,
                "source": "amakaflow",
                "sourceUrl": None,
                "intervals": intervals,
                "queued_at": entry.get("queued_at"),
                "created_at": workout_record.get("created_at"),
            })

        logger.info(f"Retrieved {len(workouts)} pending syncs for {device_type} device by user {user_id}")

        return {
            "success": True,
            "workouts": workouts,
            "count": len(workouts)
        }
    except HTTPException:
        raise
    except (ValueError, KeyError, AttributeError, TypeError) as e:
        logger.error(f"Failed to process pending syncs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process pending workouts")
    except Exception as e:
        logger.error(f"Unexpected error retrieving pending syncs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Operation failed")


@router.post("/sync/confirm")
async def confirm_sync_endpoint(
    request: ConfirmSyncRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Confirm that a workout was successfully downloaded (AMA-307).

    Called by mobile apps after successfully downloading a workout.
    Updates the sync status from 'pending' to 'synced'.
    
    Args:
        request: Confirm sync request with workout and device info
        user_id: Authenticated user ID from JWT
        
    Returns:
        Success response with sync status and timestamp
    """
    # Device type is validated by Pydantic (DeviceType enum)
    result = await run_in_threadpool(
        confirm_sync,
        workout_id=request.workout_id,
        user_id=user_id,
        device_type=request.device_type.value,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=404, detail="No pending sync found for this workout")

    logger.info(f"Confirmed sync for workout {request.workout_id} on {request.device_type} device by user {user_id}")

    return {
        "success": True,
        "status": result.get("status"),
        "synced_at": result.get("synced_at")
    }


@router.post("/sync/failed")
async def report_sync_failed_endpoint(
    request: ReportSyncFailedRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Report that a workout sync failed (AMA-307).

    Called by mobile apps when download fails.
    Updates the sync status from 'pending' to 'failed' with error message.
    
    Args:
        request: Failed sync report with workout, device, and error info
        user_id: Authenticated user ID from JWT
        
    Returns:
        Success response with failed sync status and timestamp
    """
    # Device type is validated by Pydantic (DeviceType enum)
    result = await run_in_threadpool(
        report_sync_failed,
        workout_id=request.workout_id,
        user_id=user_id,
        device_type=request.device_type.value,
        error_message=request.error,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=404, detail="No pending sync found for this workout")

    logger.error(f"Sync failed for workout {request.workout_id} on {request.device_type}: {request.error}")

    return {
        "success": True,
        "status": result.get("status"),
        "failed_at": result.get("failed_at")
    }


@router.get("/workouts/{workout_id}/sync-status")
async def get_workout_sync_status_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get sync status for a workout across all device types (AMA-307).

    Returns the current sync status (pending/synced/failed) for iOS, Android, and Garmin.
    
    Args:
        workout_id: Workout identifier
        user_id: Authenticated user ID from JWT
        
    Returns:
        Sync status across all device types
    """
    # Verify workout exists and belongs to user
    workout = await run_in_threadpool(get_workout, workout_id, user_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    sync_status = await run_in_threadpool(get_workout_sync_status, workout_id, user_id)

    logger.info(f"Retrieved sync status for workout {workout_id} by user {user_id}")

    return {
        "success": True,
        "workout_id": workout_id,
        "sync_status": sync_status
    }
