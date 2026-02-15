from typing import Optional, Dict, Any, List
from fastapi import Query, Response, Depends, Header, HTTPException
from backend.auth import get_current_user
from backend.main import app  # Import app from factory (AMA-377)
from backend.settings import get_settings
import logging
import httpx
import json
import os  # Still needed for env vars not yet in settings

from pydantic import BaseModel

logger = logging.getLogger(__name__)

from backend.adapters.ingest_to_cir import to_cir

from backend.core.canonicalize import canonicalize

from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml

from backend.adapters.blocks_to_hyrox_yaml import (
    to_hyrox_yaml,
    load_user_defaults,
    map_exercise_to_garmin,
)
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_zwo import to_zwo
from backend.adapters.blocks_to_fit import to_fit, to_fit_response, get_fit_metadata

from backend.core.exercise_suggestions import suggest_alternatives, find_similar_exercises, find_exercises_by_type, categorize_exercise
from backend.core.exercise_categories import add_category_to_exercise_name

from backend.core.workflow import validate_workout_mapping, process_workout_with_validation

from backend.core.user_mappings import (
    add_user_mapping,
    remove_user_mapping,
    get_user_mapping,
    get_all_user_mappings,
    clear_all_user_mappings
)
from backend.core.global_mappings import (
    record_mapping_choice,
    get_popular_mappings,
    get_popularity_stats
)

from backend.database import (
    save_workout,
    get_workouts,
    get_workout,
    update_workout_export_status,
    delete_workout,
    # AMA-122: Workout Library Enhancements
    toggle_workout_favorite,
    track_workout_usage,
    update_workout_tags,
    # AMA-594: Tag endpoints moved to api/routers/tags.py
    # get_user_tags, create_user_tag, delete_user_tag,
    # AMA-199: iOS Companion App Sync
    update_workout_ios_companion_sync,
    get_ios_companion_pending_workouts,
    get_incoming_workouts,
    # AMA-200: Account Deletion (moved to api/routers/account.py - AMA-596)
    # AMA-268: Mobile Profile
    get_profile,
    # AMA-307: Sync Queue
    queue_workout_sync,
    get_pending_syncs,
    confirm_sync,
    report_sync_failed,
    get_workout_sync_status,
)
from backend.follow_along_database import (
    save_follow_along_workout,
    get_follow_along_workouts,
    get_follow_along_workout,
    update_follow_along_garmin_sync,
    update_follow_along_apple_watch_sync,
    update_follow_along_ios_companion_sync
)
from backend.mobile_pairing import (
    GeneratePairingResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    PairingStatusResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    create_pairing_token,
    validate_and_use_token,
    get_pairing_status,
    revoke_user_tokens,
    get_paired_devices,
    revoke_device,
    refresh_jwt_for_device,
    fetch_clerk_profile,  # AMA-269: Fetch user profile from Clerk
)
from backend.workout_completions import (
    WorkoutCompletionRequest,
    save_workout_completion,
    get_user_completions,
    get_completion_by_id,
    # AMA-5: Voice workout with completion
    VoiceWorkoutCompletionRequest,
    save_voice_workout_with_completion,
)

# Feature flags accessed via settings (AMA-377)
_settings = get_settings()
GARMIN_UNOFFICIAL_SYNC_ENABLED = _settings.garmin_unofficial_sync_enabled
GARMIN_EXPORT_DEBUG = _settings.garmin_export_debug

# Note: FastAPI app is imported from backend.main (AMA-377)
# CORS middleware is configured in backend.main.create_app()



# Note: IngestPayload, ExerciseSuggestionRequest, BlocksPayload moved to api/routers/mapping.py (AMA-379)



# Note: /debug/garmin-test moved to api/routers/health.py (AMA-597)

# Note: /map/*, /workflow/*, /exercise/suggest moved to api/routers/mapping.py (AMA-379)


# Note: /exercise/*, /mappings/* moved to api/routers/mapping.py (AMA-379)


class UserDefaultsRequest(BaseModel):

    distance_handling: str = "lap"  # "lap" or "distance"
    default_exercise_value: str = "lap"  # "lap" or "button"
    ignore_distance: bool = True


@app.get("/settings/defaults")

def get_defaults():

    """Get current user default settings."""
    return load_user_defaults()


@app.put("/settings/defaults")

def update_defaults(p: UserDefaultsRequest):

    """Update user default settings."""
    import yaml
    import pathlib
    
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    USER_DEFAULTS_FILE = ROOT / "shared/settings/user_defaults.yaml"
    
    # Create directory if needed
    USER_DEFAULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Save settings
    data = {
        "defaults": {
            "distance_handling": p.distance_handling,
            "default_exercise_value": p.default_exercise_value,
            "ignore_distance": p.ignore_distance
        }
    }
    
    with open(USER_DEFAULTS_FILE, 'w') as f:
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False)
    
    return {
        "message": "Settings updated successfully",
        "settings": data["defaults"]
    }


# ============================================================================
# Workout Storage Endpoints
# ============================================================================

class SaveWorkoutRequest(BaseModel):
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
    profile_id: str | None = None  # Deprecated: use auth instead
    is_exported: bool = True
    exported_to_device: str | None = None


@app.post("/workouts/save")
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


@app.get("/workouts")
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


@app.get("/workouts/incoming")
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


# ============================================================================
# Workout Completion Endpoints - MOVED TO api/routers/workouts.py (AMA-381)
# ============================================================================


@app.get("/workouts/{workout_id}")
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


@app.put("/workouts/{workout_id}/export-status")
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


@app.delete("/workouts/{workout_id}")
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


class PushWorkoutToIOSCompanionRequest(BaseModel):
    userId: str | None = None  # Deprecated: use auth instead


@app.post("/workouts/{workout_id}/push/ios-companion")
def push_workout_to_ios_companion_endpoint(
    workout_id: str,
    request: PushWorkoutToIOSCompanionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Push a regular (blocks-based) workout to iOS Companion App.
    Transforms the workout structure into the iOS app's interval format.

    This endpoint is for workouts created through the standard workflow,
    not follow-along workouts ingested from Instagram.
    """
    from backend.database import get_workout

    # Get workout
    workout_record = get_workout(workout_id, user_id)
    if not workout_record:
        return {
            "success": False,
            "status": "error",
            "message": "Workout not found"
        }
    
    workout_data = workout_record.get("workout_data", {})
    title = workout_record.get("title") or workout_data.get("title", "Workout")
    
    # Detect sport type from workout structure
    # Check first block's structure or exercise types
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
        structure = block.get("structure", "regular")
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
    
    # Create payload for iOS Companion App
    payload = {
        "id": workout_id,
        "name": title,
        "sport": sport,
        "duration": total_duration,
        "source": "amakaflow",
        "sourceUrl": None,
        "intervals": intervals
    }

    # Queue workout for sync to iOS (AMA-307)
    # This creates a pending entry in the sync queue that iOS will confirm when downloaded
    queue_workout_sync(workout_id, user_id, device_type="ios")

    # Also update legacy column for backward compatibility
    update_workout_ios_companion_sync(workout_id, user_id)

    return {
        "success": True,
        "status": "success",
        "iosCompanionWorkoutId": workout_id,
        "payload": payload
    }


@app.get("/ios-companion/pending")
def get_ios_companion_pending_endpoint(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
    exclude_completed: bool = Query(True, description="Exclude workouts that have been completed")
):
    """
    Get workouts that have been pushed to iOS Companion App.

    This endpoint is called by the iOS Companion App to discover workouts
    that are ready to be synced to Apple Watch. Returns workouts where
    ios_companion_synced_at is set, ordered by most recently pushed.

    By default, excludes workouts that have been marked as completed in
    workout_completions table (AMA-236).

    The iOS app authenticates using a Mobile JWT obtained through pairing.

    The intervals field uses the same transformation as WorkoutKit export,
    properly handling:
    - Warmup from settings.workoutWarmup
    - Sets wrapped in RepeatInterval (e.g., 3 sets → repeat.reps=3)
    - Default rest times from settings
    """
    workouts = get_ios_companion_pending_workouts(user_id, limit=limit, exclude_completed=exclude_completed)

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
        except Exception as e:
            logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
            # Fallback to simple transformation
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
# Android Companion App Push (AMA-246)
# =============================================================================

class PushWorkoutToAndroidCompanionRequest(BaseModel):
    userId: str | None = None  # Deprecated: use auth instead


@app.post("/workouts/{workout_id}/push/android-companion")
def push_workout_to_android_companion_endpoint(
    workout_id: str,
    request: PushWorkoutToAndroidCompanionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Push a regular (blocks-based) workout to Android Companion App.
    Transforms the workout structure into the Android app's interval format.

    This endpoint is for workouts created through the standard workflow,
    not follow-along workouts.
    """
    from backend.database import get_workout, update_workout_android_companion_sync

    # Get workout
    workout_record = get_workout(workout_id, user_id)
    if not workout_record:
        return {
            "success": False,
            "status": "error",
            "message": "Workout not found"
        }

    workout_data = workout_record.get("workout_data", {})
    title = workout_record.get("title") or workout_data.get("title", "Workout")

    # Detect sport type from workout structure
    blocks = workout_data.get("blocks", [])
    sport = "strength"  # Default

    for block in blocks:
        structure = block.get("structure", "")
        if structure in ["tabata", "hiit", "circuit", "emom", "amrap"]:
            sport = "cardio"
            break

    # Build intervals from blocks (same transformation as iOS)
    intervals = []
    total_duration = 0

    for block in blocks:
        structure = block.get("structure", "regular")
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

    # Create payload for Android Companion App
    payload = {
        "id": workout_id,
        "name": title,
        "sport": sport,
        "duration": total_duration,
        "source": "amakaflow",
        "sourceUrl": None,
        "intervals": intervals
    }

    # Queue workout for sync to Android (AMA-307)
    # This creates a pending entry in the sync queue that Android will confirm when downloaded
    queue_workout_sync(workout_id, user_id, device_type="android")

    # Also update legacy column for backward compatibility
    update_workout_android_companion_sync(workout_id, user_id)

    return {
        "success": True,
        "status": "success",
        "androidCompanionWorkoutId": workout_id,
        "payload": payload
    }


@app.get("/android-companion/pending")
def get_android_companion_pending_endpoint(
    user_id: str = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
    exclude_completed: bool = Query(True, description="Exclude workouts that have been completed")
):
    """
    Get workouts that have been pushed to Android Companion App.

    This endpoint is called by the Android Companion App to discover workouts
    that are ready to be synced to Wear OS/Health Connect watches. Returns
    workouts where android_companion_synced_at is set, ordered by most recently pushed.

    By default, excludes workouts that have been marked as completed.

    The Android app authenticates using a Mobile JWT obtained through pairing.
    """
    from backend.database import get_android_companion_pending_workouts

    workouts = get_android_companion_pending_workouts(user_id, limit=limit, exclude_completed=exclude_completed)

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
        except Exception as e:
            logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
            # Fallback to simple transformation
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
            "pushedAt": workout_record.get("android_companion_synced_at"),
            "createdAt": workout_record.get("created_at"),
        })

    return {
        "success": True,
        "workouts": transformed,
        "count": len(transformed)
    }


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


# ============================================================================
# Follow-Along Workout Endpoints
# ============================================================================

class IngestFollowAlongRequest(BaseModel):
    instagramUrl: str
    userId: str | None = None  # Deprecated: use auth instead


class PushToGarminRequest(BaseModel):
    userId: str
    scheduleDate: Optional[str] = None  # YYYY-MM-DD format, or None for immediate import


class PushToAppleWatchRequest(BaseModel):
    userId: str


class PushToIOSCompanionRequest(BaseModel):
    userId: str


class CreateFollowAlongManualRequest(BaseModel):
    """Request to create a follow-along workout with manually entered data (no AI extraction)"""
    sourceUrl: str
    userId: str | None = None  # Deprecated: use auth instead
    title: str
    description: Optional[str] = None
    steps: List[Dict[str, Any]]
    source: Optional[str] = None  # 'instagram', 'youtube', 'tiktok', 'vimeo', 'other'
    thumbnailUrl: Optional[str] = None


@app.post("/follow-along/create")
def create_follow_along_manual_endpoint(
    request: CreateFollowAlongManualRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a follow-along workout with manually entered data.
    This is for Instagram and other platforms where we can't auto-extract exercises.
    """
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

    # Convert steps to the expected format
    formatted_steps = []
    for i, step in enumerate(request.steps):
        formatted_steps.append({
            "order": step.get("order", i),
            "label": step.get("label", f"Exercise {i + 1}"),
            "duration_sec": step.get("duration_sec"),
            "target_reps": step.get("target_reps"),
            "notes": step.get("notes"),
        })

    try:
        # Save to Supabase
        workout = save_follow_along_workout(
            user_id=user_id,
            source=source,
            source_url=request.sourceUrl,
            title=request.title,
            description=request.description,
            video_duration_sec=None,
            thumbnail_url=request.thumbnailUrl,
            video_proxy_url=None,
            steps=formatted_steps
        )

        if workout:
            return {
                "success": True,
                "followAlongWorkout": workout
            }
        else:
            return {
                "success": False,
                "message": "Failed to save workout to database"
            }
    except Exception as e:
        logger.error(f"Failed to create manual follow-along workout: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.post("/follow-along/ingest")
def ingest_follow_along_endpoint(
    request: IngestFollowAlongRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Ingest a follow-along workout from video URL (Instagram, YouTube, TikTok, Vimeo).
    Calls workout-ingestor-api to extract workout data, then stores in Supabase.
    """
    import httpx
    import os
    
    ingestor_url = os.getenv("INGESTOR_URL", "http://workout-ingestor-api:8004")
    video_url = request.instagramUrl  # Field name kept for backwards compatibility
    
    # Detect platform and choose endpoint
    if "youtube.com" in video_url or "youtu.be" in video_url:
        endpoint = "/ingest/youtube"
        source = "youtube"
        default_title = "YouTube Workout"
    elif "tiktok.com" in video_url:
        endpoint = "/ingest/url"  # Use generic URL ingest for TikTok
        source = "tiktok"
        default_title = "TikTok Workout"
    elif "vimeo.com" in video_url:
        endpoint = "/ingest/url"  # Use generic URL ingest for Vimeo
        source = "vimeo"
        default_title = "Vimeo Workout"
    elif "pinterest.com" in video_url or "pin.it" in video_url:
        endpoint = "/ingest/pinterest"
        source = "pinterest"
        default_title = "Pinterest Workout"
    else:
        # Default to Instagram
        endpoint = "/ingest/instagram_test"
        source = "instagram"
        default_title = "Instagram Workout"
    
    try:
        # Call workout-ingestor-api
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{ingestor_url}{endpoint}",
                json={
                    "url": video_url,
                    "use_vision": True,
                    "vision_provider": "openai",
                    "vision_model": "gpt-4o-mini",
                }
            )
            response.raise_for_status()
            ingestor_data = response.json()
        
        # Convert blocks/exercises format to steps format
        # YouTube returns: { blocks: [{ exercises: [...] }] }
        # Instagram returns: { steps: [...] }
        steps = ingestor_data.get("steps", [])
        
        if not steps and "blocks" in ingestor_data:
            # Convert blocks format to steps
            step_order = 1
            for block in ingestor_data.get("blocks", []):
                for exercise in block.get("exercises", []):
                    steps.append({
                        "order": step_order,
                        "label": exercise.get("name", f"Exercise {step_order}"),
                        "name": exercise.get("name"),
                        "targetReps": exercise.get("reps"),
                        "targetDurationSec": exercise.get("duration_sec"),
                        "notes": exercise.get("notes"),
                        "sets": exercise.get("sets"),
                    })
                    step_order += 1
        
        # Save to Supabase
        workout = save_follow_along_workout(
            user_id=user_id,
            source=source,
            source_url=video_url,
            title=ingestor_data.get("title", default_title),
            description=ingestor_data.get("description"),
            video_duration_sec=ingestor_data.get("videoDuration"),
            thumbnail_url=ingestor_data.get("thumbnail"),
            video_proxy_url=ingestor_data.get("videoUrl"),
            steps=steps
        )
        
        if workout:
            return {
                "success": True,
                "followAlongWorkout": workout
            }
        else:
            return {
                "success": False,
                "message": "Failed to save workout to database"
            }
    except Exception as e:
        logger.error(f"Failed to ingest follow-along workout: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.get("/follow-along")
def list_follow_along_endpoint(
    user_id: str = Depends(get_current_user)
):
    """List all follow-along workouts for the authenticated user."""
    workouts = get_follow_along_workouts(user_id=user_id)
    
    return {
        "success": True,
        "items": workouts
    }


class VoiceSettings(BaseModel):
    enabled: bool = True
    content: str = "name-reps"  # "name", "name-reps", or "name-notes"


class CreateFollowAlongFromWorkoutRequest(BaseModel):
    userId: str | None = None  # Deprecated: use auth instead
    workout: Dict[str, Any]
    sourceUrl: Optional[str] = None
    followAlongConfig: Optional[Dict[str, Any]] = None
    stepConfigs: Optional[List[Dict[str, Any]]] = None  # Phase 2: per-step video config
    voiceSettings: Optional[VoiceSettings] = None  # Phase 3: voice guidance settings


@app.post("/follow-along/from-workout")
def create_follow_along_from_workout(
    request: CreateFollowAlongFromWorkoutRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Create a follow-along workout from an existing structured workout.
    This converts a workout created through the normal flow into a follow-along format.
    """
    try:
        workout = request.workout
        config = request.followAlongConfig or {}
        step_configs_list = request.stepConfigs or []
        voice_settings = request.voiceSettings
        
        # Create lookup for step configs by exerciseId
        step_configs_map = {s.get("exerciseId"): s for s in step_configs_list}
        
        # Extract title
        title = workout.get("title", "Follow-Along Workout")
        
        # Detect source type from URL
        source = "manual"
        source_url = request.sourceUrl or ""
        if "youtube.com" in source_url or "youtu.be" in source_url:
            source = "youtube"
        elif "instagram.com" in source_url:
            source = "instagram"
        elif "tiktok.com" in source_url:
            source = "tiktok"
        
        # Build voice guidance text for each exercise
        def build_voice_text(exercise: Dict[str, Any], content_type: str) -> str:
            name = exercise.get("name", "Exercise")
            if content_type == "name":
                return name
            elif content_type == "name-reps":
                sets = exercise.get("sets", 3)
                reps = exercise.get("reps")
                duration = exercise.get("duration_sec")
                if reps:
                    return f"{name}. {sets} sets of {reps} reps"
                elif duration:
                    return f"{name}. {sets} sets of {duration} seconds"
                return name
            elif content_type == "name-notes":
                notes = exercise.get("notes", "")
                if notes:
                    return f"{name}. {notes}"
                return name
            return name
        
        # Convert workout blocks to follow-along steps
        steps = []
        step_order = 1
        
        voice_content = voice_settings.content if voice_settings else "name-reps"
        voice_enabled = voice_settings.enabled if voice_settings else True
        
        for block in workout.get("blocks", []):
            for exercise in block.get("exercises", []):
                exercise_id = exercise.get("id", f"step-{step_order}")
                
                # Get step config from Phase 2 stepConfigs or fallback to old config format
                step_config = step_configs_map.get(exercise_id, {})
                if not step_config:
                    # Fallback to old config format
                    old_config_steps = {s.get("exerciseId"): s for s in config.get("steps", [])}
                    step_config = old_config_steps.get(exercise_id, {})
                
                # Determine video URL based on config
                video_url = None
                video_source = step_config.get("videoSource", "none")
                
                if video_source == "original":
                    video_url = source_url  # Use the original source URL
                elif video_source == "custom":
                    video_url = step_config.get("customUrl")
                
                # Build voice text for this step
                voice_text = build_voice_text(exercise, voice_content) if voice_enabled else None
                
                steps.append({
                    "order": step_order,
                    "label": exercise.get("name", f"Exercise {step_order}"),
                    "name": exercise.get("name"),
                    "targetReps": exercise.get("reps"),
                    "targetDurationSec": exercise.get("duration_sec"),
                    "notes": exercise.get("notes"),
                    "sets": exercise.get("sets"),
                    "followAlongUrl": video_url,
                    "videoStartTimeSec": step_config.get("startTimeSec", 0),
                    "voiceText": voice_text,  # Phase 3: Text for TTS
                })
                step_order += 1
        
        # Save to database with voice settings
        saved_workout = save_follow_along_workout(
            user_id=user_id,
            source=source,
            source_url=source_url,
            title=title,
            description=workout.get("description"),
            video_duration_sec=None,
            thumbnail_url=None,
            video_proxy_url=source_url if source != "manual" else None,
            steps=steps,
            voice_enabled=voice_enabled,
            voice_content=voice_content
        )
        
        if saved_workout:
            return {
                "success": True,
                "followAlongWorkoutId": saved_workout.get("id"),
                "followAlongWorkout": saved_workout
            }
        else:
            return {
                "success": False,
                "message": "Failed to save follow-along workout"
            }
            
    except Exception as e:
        logger.error(f"Failed to create follow-along from workout: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.get("/follow-along/{workout_id}")
def get_follow_along_endpoint(
    workout_id: str,
    userId: str = Query(..., description="User ID")
):
    """Get a single follow-along workout by ID."""
    workout = get_follow_along_workout(workout_id, userId)
    
    if workout:
        return {
            "success": True,
            "followAlongWorkout": workout
        }
    else:
        return {
            "success": False,
            "message": "Workout not found"
        }


@app.delete("/follow-along/{workout_id}")
def delete_follow_along_endpoint(
    workout_id: str,
    userId: str = Query(..., description="User ID")
):
    """Delete a follow-along workout."""
    from backend.follow_along_database import delete_follow_along_workout
    
    success = delete_follow_along_workout(workout_id, userId)
    
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


# Idempotency registry (in-memory — fine for dev)
FOLLOW_ALONG_SYNC_CACHE = {}

def has_synced_before(workout_id: str, user_id: str, title: str):
    key = f"{user_id}:{workout_id}:{title}"
    return FOLLOW_ALONG_SYNC_CACHE.get(key) is True

def mark_synced(workout_id: str, user_id: str, title: str):
    key = f"{user_id}:{workout_id}:{title}"
    FOLLOW_ALONG_SYNC_CACHE[key] = True

@app.post("/follow-along/{workout_id}/push/garmin")
def push_to_garmin_endpoint(workout_id: str, request: PushToGarminRequest):
    """
    Push follow-along workout to Garmin via garmin-sync-api.

    - Respects GARMIN_UNOFFICIAL_SYNC_ENABLED.
    - Uses the same exercise mapping pipeline as YAML export
      (map_exercise_to_garmin + add_category_to_exercise_name).
    - Sends steps in the format expected by the unofficial Garmin Sync API:
      { "Garmin Exercise Name [category: XYZ]": "10 reps" } or "60s".
    - Prevents duplicate syncs using idempotency key.
    """
    import httpx
    import json

    # Backend guard for unofficial API
    if not GARMIN_UNOFFICIAL_SYNC_ENABLED:
        return {
            "success": False,
            "status": "error",
            "message": "Unofficial Garmin sync is disabled. Set GARMIN_UNOFFICIAL_SYNC_ENABLED=true to use this endpoint.",
        }

    # Get workout
    workout = get_follow_along_workout(workout_id, request.userId)
    if not workout:
        return {
            "success": False,
            "status": "error",
            "message": "Workout not found",
        }

    # Prevent duplicate syncs
    if has_synced_before(workout_id, request.userId, workout.get("title", "")):
        return {
            "success": True,
            "status": "already_synced",
            "message": "This workout was already synced to Garmin.",
            "garminWorkoutId": workout.get("title", ""),
        }

    # Get Garmin credentials from environment
    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")

    if not garmin_email or not garmin_password:
        return {
            "success": False,
            "status": "error",
            "message": "Garmin credentials not configured. Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables.",
        }

    steps: list[dict[str, str]] = []

    def build_step_from_follow_along_step(step: dict):
        """
        Build a single Garmin step from a follow-along step.

        Follow-along structure:
        - label: exercise label/name
        - target_reps: optional reps
        - duration_sec: optional duration in seconds

        We ALSO inject a human-friendly note into the step detail, using:
        - Any explicit `step["note"]` or `step["description"]` (future-proof)
        - Otherwise the description returned by map_exercise_to_garmin

        Final detail format (shown as Garmin Notes field):
            "10 reps | Some description text"
        """
        ex_name = step.get("label", "") or ""
        if not ex_name:
            return None

        reps = step.get("target_reps")
        duration = step.get("duration_sec")

        # In follow-along there is no pre-validated mapped_name, so we just use the label
        mapped_name = None
        candidate_names = [ex_name]

        garmin_name, description, mapping_info = map_exercise_to_garmin(
            ex_name,
            ex_reps=reps,
            ex_distance_m=None,
            mapped_name=mapped_name,
            candidate_names=candidate_names,
        )

        garmin_name_with_category = add_category_to_exercise_name(garmin_name)

        # Base target text
        if reps:
            base_detail = f"{reps} reps"
        elif duration:
            base_detail = f"{duration}s"
        else:
            base_detail = "10 reps"

        # Clean note text that we can also reuse for iPhone follow-along later
        note = (
            (step.get("note") or "").strip()
            or (step.get("description") or "").strip()
            or (description or "").strip()
        )

        if note:
            step_detail = f"{base_detail} | {note}"
        else:
            step_detail = base_detail

        step_obj = {garmin_name_with_category: step_detail}

        logger.info(
            "GARMIN_SYNC_FOLLOW_STEP original=%r garmin=%r detail=%r source=%s conf=%s note=%r",
            ex_name,
            garmin_name_with_category,
            step_detail,
            mapping_info.get("source"),
            mapping_info.get("confidence"),
            note,
        )

        return step_obj

    # Build steps list from follow-along workout steps
    for step in workout.get("steps", []):
        garmin_step = build_step_from_follow_along_step(step)
        if garmin_step:
            steps.append(garmin_step)

    if not steps:
        return {
            "success": False,
            "status": "error",
            "message": "No valid steps found to sync",
        }

    garmin_workouts = {
        workout["title"]: steps,
    }

    garmin_url = os.getenv("GARMIN_SERVICE_URL", "http://garmin-sync-api:8002")

    garmin_payload = {
        "email": garmin_email,
        "password": garmin_password,
        "workouts": garmin_workouts,
        "delete_same_name": False,
    }

    # Compare YAML export vs Follow-Along export
    try:
        # Convert follow-along workout to blocks format for YAML export
        blocks_json = {
            "title": workout["title"],
            "blocks": [{
                "label": "Main Block",
                "structure": "",
                "exercises": [
                    {
                        "name": step.get("label", ""),
                        "reps": step.get("target_reps"),
                        "duration_sec": step.get("duration_sec"),
                    }
                    for step in workout.get("steps", [])
                ]
            }]
        }
        yaml_export = to_hyrox_yaml(blocks_json)
        
        if GARMIN_EXPORT_DEBUG:
            print("=== GARMIN_EXPORT_VS_FOLLOW_ALONG_COMPARISON ===")
            print(json.dumps({
                "yaml_export": yaml_export,
                "follow_along_payload": garmin_payload
            }, indent=2))
    except Exception as e:
        if GARMIN_EXPORT_DEBUG:
            print("=== COMPARISON_ERROR ===", str(e))

    # Debug logging for sync payload
    if GARMIN_EXPORT_DEBUG:
        print("=== GARMIN_SYNC_PAYLOAD ===")
        print(json.dumps(garmin_payload, indent=2))

    try:
        with httpx.Client(timeout=30.0) as client:
            # Import workout
            logger.info("GARMIN_SYNC_FOLLOW_IMPORT payload=%s", json.dumps(garmin_payload, indent=2))
            response = client.post(f"{garmin_url}/workouts/import", json=garmin_payload)
            response.raise_for_status()

            # If scheduleDate is provided, schedule the workout
            if request.scheduleDate:
                schedule_date = request.scheduleDate
                schedule_payload = {
                    "email": garmin_email,
                    "password": garmin_password,
                    "start_from": schedule_date,
                    "workouts": [workout["title"]],
                }
                logger.info("GARMIN_SYNC_FOLLOW_SCHEDULE payload=%s", json.dumps(schedule_payload, indent=2))
                schedule_response = client.post(
                    f"{garmin_url}/workouts/schedule",
                    json=schedule_payload,
                )
                schedule_response.raise_for_status()

        garmin_workout_id = workout["title"]

        # Mark as synced to prevent duplicates
        mark_synced(workout_id, request.userId, workout["title"])

        # Update sync status
        update_follow_along_garmin_sync(
            workout_id=workout_id,
            user_id=request.userId,
            garmin_workout_id=garmin_workout_id,
        )

        return {
            "success": True,
            "status": "success",
            "garminWorkoutId": garmin_workout_id,
        }
    except Exception as e:
        logger.error(f"Failed to push follow-along workout to Garmin: {e}")
        return {
            "success": False,
            "status": "error",
            "message": str(e),
        }



@app.post("/workout/sync/garmin")
def sync_workout_to_garmin(request: dict):
    """
    Sync a regular workout to Garmin Connect via garmin-sync-api.

    - Respects GARMIN_UNOFFICIAL_SYNC_ENABLED.
    - Uses the same exercise mapping pipeline as the YAML export
      (map_exercise_to_garmin + add_category_to_exercise_name), so
      Garmin receives valid exercise names instead of generic steps.
    """
    import httpx
    import json

    logger = logging.getLogger(__name__)

    # Backend guard for unofficial API
    if not GARMIN_UNOFFICIAL_SYNC_ENABLED:
        return {
            "success": False,
            "status": "error",
            "message": "Unofficial Garmin sync is disabled. Set GARMIN_UNOFFICIAL_SYNC_ENABLED=true to use this endpoint.",
        }

    # Get workout data from request
    blocks_json = request.get("blocks_json")
    workout_title = request.get("workout_title", "Workout")
    schedule_date = request.get("schedule_date")

    if not blocks_json:
        return {
            "success": False,
            "status": "error",
            "message": "Workout data is required",
        }

    # Get Garmin credentials from environment
    garmin_email = os.getenv("GARMIN_EMAIL")
    garmin_password = os.getenv("GARMIN_PASSWORD")

    if not garmin_email or not garmin_password:
        return {
            "success": False,
            "status": "error",
            "message": "Garmin credentials not configured. Set GARMIN_EMAIL and GARMIN_PASSWORD environment variables.",
        }

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
        # Note: map_exercise_to_garmin signature: (ex_name, ex_reps=None, ex_distance_m=None, use_user_mappings=True)
        # Use mapped_name as the primary name if available
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
        return {
            "success": False,
            "status": "error",
            "message": "No valid exercises found to sync",
        }

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
        with httpx.Client(timeout=30.0) as client:
            # Import workout
            logger.info("GARMIN_SYNC_IMPORT payload=%s", json.dumps(garmin_payload, indent=2))
            response = client.post(f"{garmin_url}/workouts/import", json=garmin_payload)
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
                schedule_response = client.post(
                    f"{garmin_url}/workouts/schedule",
                    json=schedule_payload,
                )
                schedule_response.raise_for_status()

        return {
            "success": True,
            "status": "success",
            "message": "Workout synced to Garmin successfully",
            "garminWorkoutId": workout_title,
        }
    except Exception as e:
        logger.error(f"Failed to sync workout to Garmin: {e}")
        return {
            "success": False,
            "status": "error",
            "message": str(e),
        }

@app.post("/follow-along/{workout_id}/push/apple-watch")
def push_to_apple_watch_endpoint(workout_id: str, request: PushToAppleWatchRequest):
    """
    Push follow-along workout to Apple Watch.
    Returns payload that can be sent via WatchConnectivity.
    """
    # Get workout
    workout = get_follow_along_workout(workout_id, request.userId)
    if not workout:
        return {
            "success": False,
            "status": "error",
            "message": "Workout not found"
        }
    
    # Create payload for Apple Watch
    payload = {
        "id": workout["id"],
        "title": workout["title"],
        "steps": [
            {
                "order": step.get("order", 0),
                "label": step.get("label", ""),
                "durationSec": step.get("duration_sec", 0)
            }
            for step in workout.get("steps", [])
        ]
    }
    
    # Update sync status
    update_follow_along_apple_watch_sync(
        workout_id=workout_id,
        user_id=request.userId,
        apple_watch_workout_id=workout_id
    )
    
    return {
        "success": True,
        "status": "success",
        "appleWatchWorkoutId": workout_id,
        "payload": payload
    }


@app.post("/follow-along/{workout_id}/push/ios-companion")
def push_to_ios_companion_endpoint(workout_id: str, request: PushToIOSCompanionRequest):
    """
    Push follow-along workout to iOS Companion App.
    Returns payload formatted for the iOS app's WorkoutFlowView with full video URLs.
    
    This endpoint transforms the follow-along workout into the iOS companion app's
    expected format, including video URLs for the follow-along experience.
    """
    # Get workout
    workout = get_follow_along_workout(workout_id, request.userId)
    if not workout:
        return {
            "success": False,
            "status": "error",
            "message": "Workout not found"
        }
    
    # Detect video platform from source URL
    source_url = workout.get("source_url", "")
    source = workout.get("source", "other")
    
    # Map source to sport type
    sport_mapping = {
        "instagram": "strength",
        "youtube": "strength",
        "tiktok": "strength",
        "vimeo": "strength",
    }
    sport = sport_mapping.get(source, "other")
    
    # Get voice settings
    voice_enabled = workout.get("voice_enabled", True)
    voice_content = workout.get("voice_content", "name-reps")
    
    # Build intervals from steps
    intervals = []
    for step in workout.get("steps", []):
        duration_sec = step.get("duration_sec", 0)
        target_reps = step.get("target_reps")
        label = step.get("label", "")
        notes = step.get("notes")
        voice_text = step.get("voice_text")
        video_start_time = step.get("video_start_time_sec", 0)
        follow_along_url = step.get("follow_along_url")
        
        if target_reps:
            # Reps-based exercise
            interval = {
                "kind": "reps",
                "reps": target_reps,
                "name": label,
                "load": notes,  # Use notes as load hint if available
                "restSec": 60,  # Default rest
                "followAlongUrl": follow_along_url or source_url,
                "videoStartTimeSec": video_start_time,
                "voiceText": voice_text,  # Phase 3: TTS text
                "carouselPosition": None  # Can be set per-step if needed
            }
        else:
            # Time-based exercise
            interval = {
                "kind": "time",
                "seconds": duration_sec,
                "target": label,
                "followAlongUrl": follow_along_url or source_url,
                "videoStartTimeSec": video_start_time,
                "voiceText": voice_text,  # Phase 3: TTS text
            }
        
        intervals.append(interval)
    
    # Calculate total duration
    total_duration = workout.get("video_duration_sec") or sum(
        step.get("duration_sec", 0) for step in workout.get("steps", [])
    )
    
    # Create payload for iOS Companion App
    payload = {
        "id": workout["id"],
        "name": workout["title"],
        "sport": sport,
        "duration": total_duration,
        "source": source,
        "sourceUrl": source_url,
        "intervals": intervals,
        "voiceEnabled": voice_enabled,  # Phase 3: Voice guidance enabled
        "voiceContent": voice_content,  # Phase 3: Voice content type
    }
    
    # Update sync status
    update_follow_along_ios_companion_sync(
        workout_id=workout_id,
        user_id=request.userId
    )
    
    return {
        "success": True,
        "status": "success",
        "iosCompanionWorkoutId": workout_id,
        "payload": payload
    }


# =============================================================================
# Sync Queue Endpoints (AMA-307: Proper Sync State Tracking)
# =============================================================================

class QueueSyncRequest(BaseModel):
    device_type: str  # 'ios', 'android', 'garmin'
    device_id: str | None = None


class ConfirmSyncRequest(BaseModel):
    workout_id: str
    device_type: str
    device_id: str | None = None


class ReportSyncFailedRequest(BaseModel):
    workout_id: str
    device_type: str
    error: str
    device_id: str | None = None


@app.post("/workouts/{workout_id}/sync")
def queue_workout_sync_endpoint(
    workout_id: str,
    request: QueueSyncRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Queue a workout for sync to a device (AMA-307).

    Creates a 'pending' entry in the sync queue. The device will fetch
    pending workouts and confirm download to mark as 'synced'.

    This replaces the immediate 'synced' status from the old push endpoints.
    """
    if request.device_type not in ['ios', 'android', 'garmin']:
        raise HTTPException(status_code=400, detail="Invalid device_type. Must be ios, android, or garmin")

    # Verify workout exists and belongs to user
    workout = get_workout(workout_id, user_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    result = queue_workout_sync(
        workout_id=workout_id,
        user_id=user_id,
        device_type=request.device_type,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to queue workout for sync")

    return {
        "success": True,
        "status": result.get("status"),
        "queued_at": result.get("queued_at")
    }


@app.get("/sync/pending")
def get_pending_syncs_endpoint(
    device_type: str = Query(..., description="Device type: ios, android, or garmin"),
    device_id: str = Query(None, description="Optional device identifier"),
    user_id: str = Depends(get_current_user)
):
    """
    Get workouts pending sync for a device (AMA-307).

    Called by mobile apps to discover workouts queued for download.
    Returns full workout data including intervals, in the order they were queued.
    """
    if device_type not in ['ios', 'android', 'garmin']:
        raise HTTPException(status_code=400, detail="Invalid device_type")

    pending = get_pending_syncs(
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
        # This handles warmup, sets as RepeatInterval, and default rest
        try:
            workoutkit_dto = to_workoutkit(workout_data)
            intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
            sport = workoutkit_dto.sportType
        except Exception as e:
            logger.warning(f"Failed to transform workout {entry.get('workout_id')}: {e}")
            # Fallback to simple transformation
            intervals = []
            sport = "strengthTraining"
            for block in workout_data.get("blocks", []):
                for exercise in block.get("exercises", []):
                    intervals.append(convert_exercise_to_interval(exercise))

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

    return {
        "success": True,
        "workouts": workouts,
        "count": len(workouts)
    }


@app.post("/sync/confirm")
def confirm_sync_endpoint(
    request: ConfirmSyncRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Confirm that a workout was successfully downloaded (AMA-307).

    Called by mobile apps after successfully downloading a workout.
    Updates the sync status from 'pending' to 'synced'.
    """
    if request.device_type not in ['ios', 'android', 'garmin']:
        raise HTTPException(status_code=400, detail="Invalid device_type")

    result = confirm_sync(
        workout_id=request.workout_id,
        user_id=user_id,
        device_type=request.device_type,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=404, detail="No pending sync found for this workout")

    return {
        "success": True,
        "status": result.get("status"),
        "synced_at": result.get("synced_at")
    }


@app.post("/sync/failed")
def report_sync_failed_endpoint(
    request: ReportSyncFailedRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Report that a workout sync failed (AMA-307).

    Called by mobile apps when download fails.
    Updates the sync status from 'pending' to 'failed' with error message.
    """
    if request.device_type not in ['ios', 'android', 'garmin']:
        raise HTTPException(status_code=400, detail="Invalid device_type")

    result = report_sync_failed(
        workout_id=request.workout_id,
        user_id=user_id,
        device_type=request.device_type,
        error_message=request.error,
        device_id=request.device_id or ""
    )

    if not result:
        raise HTTPException(status_code=404, detail="No pending sync found for this workout")

    return {
        "success": True,
        "status": result.get("status"),
        "failed_at": result.get("failed_at")
    }


@app.get("/workouts/{workout_id}/sync-status")
def get_workout_sync_status_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Get sync status for a workout across all device types (AMA-307).

    Returns the current sync status (pending/synced/failed) for iOS, Android, and Garmin.
    """
    # Verify workout exists and belongs to user
    workout = get_workout(workout_id, user_id)
    if not workout:
        raise HTTPException(status_code=404, detail="Workout not found")

    sync_status = get_workout_sync_status(workout_id, user_id)

    return {
        "success": True,
        "workout_id": workout_id,
        "sync_status": sync_status
    }


# Health endpoint moved to api/routers/health.py (AMA-378)


# ============================================================================
# Mobile Pairing Endpoints - MOVED TO api/routers/pairing.py (AMA-382)
# ============================================================================


# Note: Account management endpoints moved to api/routers/account.py (AMA-596)

# Note: /map/to-fit, /map/fit-metadata, /map/preview-steps moved to api/routers/mapping.py (AMA-379)


# ============================================================================
# Bulk Import Endpoints (AMA-100: Bulk Import Controller)
# ============================================================================

from fastapi import UploadFile, File as FastAPIFile, Form

from backend.bulk_import import (
    bulk_import_service,
    BulkDetectRequest,
    BulkDetectResponse,
    BulkMapRequest,
    BulkMapResponse,
    BulkMatchRequest,
    BulkMatchResponse,
    BulkPreviewRequest,
    BulkPreviewResponse,
    BulkExecuteRequest,
    BulkExecuteResponse,
    BulkStatusResponse,
    ColumnMapping,
)


@app.post("/import/detect", response_model=BulkDetectResponse)
async def bulk_import_detect(request: BulkDetectRequest):
    """
    Detect and parse workout items from sources.

    Step 1 of the bulk import workflow.

    Accepts:
    - file: Base64-encoded file content (Excel, CSV, JSON, Text)
    - urls: List of URLs (YouTube, Instagram, TikTok)
    - images: Base64-encoded image data for OCR

    Returns detected items with confidence scores and any parsing errors.
    """
    return await bulk_import_service.detect_items(
        profile_id=request.profile_id,
        source_type=request.source_type,
        sources=request.sources,
    )


@app.post("/import/detect/file", response_model=BulkDetectResponse)
async def bulk_import_detect_file(
    file: UploadFile = FastAPIFile(...),
    profile_id: str = Form(..., description="User profile ID"),
):
    """
    Detect and parse workout items from an uploaded file.

    Step 1 of the bulk import workflow (file upload variant).

    Accepts file uploads via multipart/form-data:
    - Excel (.xlsx, .xls)
    - CSV (.csv)
    - JSON (.json)
    - Text (.txt)

    Returns detected items with confidence scores and any parsing errors.
    """
    import base64

    # Read file content
    content = await file.read()
    filename = file.filename or "upload.txt"

    # Encode as base64 with filename prefix for the parser
    base64_content = f"{filename}:{base64.b64encode(content).decode('utf-8')}"

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="file",
        sources=[base64_content],
    )


@app.post("/import/detect/urls", response_model=BulkDetectResponse)
async def bulk_import_detect_urls(
    profile_id: str = Form(..., description="User profile ID"),
    urls: str = Form(..., description="Newline or comma-separated URLs"),
):
    """
    Detect and parse workout items from URLs.

    Step 1 of the bulk import workflow (URL variant).

    Accepts URLs via form data (newline or comma-separated):
    - YouTube (youtube.com, youtu.be)
    - Instagram (instagram.com/p/, /reel/, /tv/)
    - TikTok (tiktok.com, vm.tiktok.com)

    Fetches metadata using oEmbed APIs for quick preview.
    Full workout extraction happens during the import step.

    Processing uses batch requests with max 5 concurrent connections.
    """
    # Parse URLs from form input (newline or comma-separated)
    url_list = []
    for line in urls.replace(",", "\n").split("\n"):
        url = line.strip()
        if url:
            url_list.append(url)

    if not url_list:
        return BulkDetectResponse(
            success=False,
            job_id="",
            items=[],
            metadata={"error": "No URLs provided"},
            total=0,
            success_count=0,
            error_count=0,
        )

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="urls",
        sources=url_list,
    )


@app.post("/import/detect/images", response_model=BulkDetectResponse)
async def bulk_import_detect_images(
    profile_id: str = Form(..., description="User profile ID"),
    files: list[UploadFile] = FastAPIFile(..., description="Image files to process"),
):
    """
    Detect and parse workout items from images.

    Step 1 of the bulk import workflow (Image variant).

    Accepts image uploads:
    - PNG, JPG, JPEG, WebP, HEIC, GIF
    - Max 20 images per request

    Uses Vision AI (GPT-4o-mini by default) to extract workout data.
    Returns structured workout data with confidence scores.

    Processing uses batch requests with max 3 concurrent connections
    (lower than URLs due to cost and rate limits).
    """
    import base64

    if not files:
        return BulkDetectResponse(
            success=False,
            job_id="",
            items=[],
            metadata={"error": "No images provided"},
            total=0,
            success_count=0,
            error_count=0,
        )

    # Limit to 20 images
    if len(files) > 20:
        return BulkDetectResponse(
            success=False,
            job_id="",
            items=[],
            metadata={"error": f"Too many images ({len(files)}). Maximum is 20."},
            total=0,
            success_count=0,
            error_count=0,
        )

    # Read files and convert to base64
    image_sources = []
    for file in files:
        content = await file.read()
        b64_data = base64.b64encode(content).decode("utf-8")
        image_sources.append({
            "data": b64_data,
            "filename": file.filename or "image.jpg",
        })

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="images",
        sources=image_sources,
    )


@app.post("/import/map", response_model=BulkMapResponse)
async def bulk_import_map(request: BulkMapRequest):
    """
    Apply column mappings to detected file data.

    Step 2 of the bulk import workflow (only for file imports).

    Transforms raw CSV/Excel data into structured workout data
    based on user-provided column mappings.
    """
    column_mappings = [ColumnMapping(**m) if isinstance(m, dict) else m for m in request.column_mappings]
    return await bulk_import_service.apply_column_mappings(
        job_id=request.job_id,
        profile_id=request.profile_id,
        column_mappings=column_mappings,
    )


@app.post("/import/match", response_model=BulkMatchResponse)
async def bulk_import_match(request: BulkMatchRequest):
    """
    Match exercises to Garmin exercise database.

    Step 3 of the bulk import workflow.

    Uses fuzzy matching to find Garmin equivalents for exercise names.
    Returns confidence scores and suggestions for ambiguous matches.
    """
    return await bulk_import_service.match_exercises(
        job_id=request.job_id,
        profile_id=request.profile_id,
        user_mappings=request.user_mappings,
    )


@app.post("/import/preview", response_model=BulkPreviewResponse)
async def bulk_import_preview(request: BulkPreviewRequest):
    """
    Generate preview of workouts to be imported.

    Step 4 of the bulk import workflow.

    Shows final workout structures, validation issues,
    and statistics before committing the import.
    """
    return await bulk_import_service.generate_preview(
        job_id=request.job_id,
        profile_id=request.profile_id,
        selected_ids=request.selected_ids,
    )


@app.post("/import/execute", response_model=BulkExecuteResponse)
async def bulk_import_execute(request: BulkExecuteRequest):
    """
    Execute the bulk import of workouts.

    Step 5 of the bulk import workflow.

    In async_mode (default), starts a background job and returns immediately.
    Use GET /import/status/{job_id} to track progress.
    """
    return await bulk_import_service.execute_import(
        job_id=request.job_id,
        profile_id=request.profile_id,
        workout_ids=request.workout_ids,
        device=request.device,
        async_mode=request.async_mode,
    )


@app.get("/import/status/{job_id}", response_model=BulkStatusResponse)
async def bulk_import_status(
    job_id: str,
    profile_id: str = Query(..., description="User profile ID")
):
    """
    Get status of a bulk import job.

    Returns progress percentage, current item being processed,
    and results for completed items.
    """
    return await bulk_import_service.get_import_status(
        job_id=job_id,
        profile_id=profile_id,
    )


@app.post("/import/cancel/{job_id}")
async def bulk_import_cancel(
    job_id: str,
    profile_id: str = Query(..., description="User profile ID")
):
    """
    Cancel a running bulk import job.

    Only works for jobs with status 'running'.
    Completed imports cannot be cancelled.
    """
    success = await bulk_import_service.cancel_import(
        job_id=job_id,
        profile_id=profile_id,
    )
    return {
        "success": success,
        "message": "Import cancelled" if success else "Failed to cancel import",
    }


# Note: ExerciseMatch models and /exercises/match moved to api/routers/mapping.py (AMA-379)


# ============================================================================
# Workout Library Enhancements (AMA-122)
# ============================================================================

class ToggleFavoriteRequest(BaseModel):
    profile_id: str
    is_favorite: bool


class TrackUsageRequest(BaseModel):
    profile_id: str


class UpdateTagsRequest(BaseModel):
    profile_id: str
    tags: List[str]


@app.patch("/workouts/{workout_id}/favorite")
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


@app.patch("/workouts/{workout_id}/used")
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


@app.patch("/workouts/{workout_id}/tags")
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


# Note: /tags endpoints moved to api/routers/tags.py (AMA-594)
# Note: /exercises/match/batch moved to api/routers/mapping.py (AMA-379)

# Note: /testing/reset-user-data moved to api/routers/health.py (AMA-597)
