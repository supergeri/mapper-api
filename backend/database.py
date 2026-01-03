"""
Database module for Supabase integration.
Handles workout storage and retrieval.
"""
import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)

# Initialize Supabase client
def get_supabase_client() -> Optional[Client]:
    """Get Supabase client instance."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials not configured. Workout storage will be disabled.")
        return None
    
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def save_workout(
    profile_id: str,
    workout_data: Dict[str, Any],
    sources: List[str],
    device: str,
    exports: Optional[Dict[str, Any]] = None,
    validation: Optional[Dict[str, Any]] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    workout_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Save a workout to Supabase with deduplication.

    If a workout with the same profile_id, title, and device already exists,
    it will be updated instead of creating a duplicate.

    Args:
        profile_id: User profile ID
        workout_data: Full workout structure
        sources: List of source strings
        device: Device ID (garmin, apple, zwift, etc.)
        exports: Export formats if available
        validation: Validation response if available
        title: Optional workout title
        description: Optional workout description
        workout_id: Optional existing workout ID (for explicit updates)

    Returns:
        Saved workout data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # Extract title from workout_data if not provided
        effective_title = title or workout_data.get("title")

        # Check for existing workout with same profile_id, title, and device
        # This prevents duplicates from multiple save calls in the workflow
        existing_workout = None

        if workout_id:
            # Explicit update - check if workout exists
            check_result = supabase.table("workouts").select("id").eq("id", workout_id).eq("profile_id", profile_id).execute()
            if check_result.data and len(check_result.data) > 0:
                existing_workout = check_result.data[0]
        elif effective_title:
            # Check for duplicate by title + device + profile_id
            check_result = supabase.table("workouts").select("id, created_at").eq("profile_id", profile_id).eq("title", effective_title).eq("device", device).order("created_at", desc=True).limit(1).execute()
            if check_result.data and len(check_result.data) > 0:
                existing_workout = check_result.data[0]
                logger.info(f"Found existing workout with same title/device: {existing_workout['id']}")

        data = {
            "profile_id": profile_id,
            "workout_data": workout_data,
            "sources": sources,
            "device": device,
            "is_exported": False,
        }

        if exports:
            data["exports"] = exports
        if validation:
            data["validation"] = validation
        if effective_title:
            data["title"] = effective_title
        if description:
            data["description"] = description

        if existing_workout:
            # Update existing workout instead of creating duplicate
            from datetime import datetime, timezone
            data["updated_at"] = datetime.now(timezone.utc).isoformat()

            result = supabase.table("workouts").update(data).eq("id", existing_workout["id"]).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout updated (dedup) for profile {profile_id}, id: {existing_workout['id']}")
                return result.data[0]
            return None
        else:
            # Insert new workout
            result = supabase.table("workouts").insert(data).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout saved for profile {profile_id}")
                return result.data[0]
            return None
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to save workout: {e}")
        # Check if it's an RLS/permissions error
        if "PGRST" in error_msg or "permission" in error_msg.lower() or "row-level security" in error_msg.lower():
            logger.error("RLS/Permissions error: Consider using SUPABASE_SERVICE_ROLE_KEY instead of SUPABASE_ANON_KEY for backend API")
        return None


def get_workouts(
    profile_id: str,
    device: Optional[str] = None,
    is_exported: Optional[bool] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get workouts for a user.
    
    Args:
        profile_id: User profile ID
        device: Filter by device (optional)
        is_exported: Filter by export status (optional)
        limit: Maximum number of workouts to return
        
    Returns:
        List of workout records
    """
    supabase = get_supabase_client()
    if not supabase:
        return []
    
    try:
        query = supabase.table("workouts").select("*").eq("profile_id", profile_id)
        
        if device:
            query = query.eq("device", device)
        if is_exported is not None:
            query = query.eq("is_exported", is_exported)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get workouts: {e}")
        return []


def get_workout(workout_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single workout by ID.
    
    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)
        
    Returns:
        Workout data or None if not found
    """
    supabase = get_supabase_client()
    if not supabase:
        return None
    
    try:
        result = supabase.table("workouts").select("*").eq("id", workout_id).eq("profile_id", profile_id).single().execute()
        return result.data if result.data else None
    except Exception as e:
        logger.error(f"Failed to get workout {workout_id}: {e}")
        return None


def update_workout_export_status(
    workout_id: str,
    profile_id: str,
    is_exported: bool = True,
    exported_to_device: Optional[str] = None
) -> bool:
    """
    Update workout export status.
    
    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)
        is_exported: Whether workout has been exported
        exported_to_device: Device ID it was exported to
        
    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        return False
    
    try:
        from datetime import datetime, timezone
        
        update_data = {
            "is_exported": is_exported,
        }
        
        if is_exported:
            update_data["exported_at"] = datetime.now(timezone.utc).isoformat()
            if exported_to_device:
                update_data["exported_to_device"] = exported_to_device
        else:
            # Clear export info if marking as not exported
            update_data["exported_at"] = None
            update_data["exported_to_device"] = None
        
        result = supabase.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()
        return result.data is not None
    except Exception as e:
        logger.error(f"Failed to update workout export status: {e}")
        return False


def delete_workout(workout_id: str, profile_id: str) -> bool:
    """
    Delete a workout.

    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return False

    try:
        logger.info(f"Attempting to delete workout {workout_id} for profile {profile_id}")
        result = supabase.table("workouts").delete().eq("id", workout_id).eq("profile_id", profile_id).execute()

        # Check if any rows were actually deleted
        # Supabase delete() returns result.data with the deleted rows
        deleted_count = len(result.data) if result.data else 0

        if deleted_count > 0:
            logger.info(f"Workout {workout_id} deleted successfully ({deleted_count} row(s))")
            return True
        else:
            logger.warning(f"No workout found with id {workout_id} for profile {profile_id} (0 rows deleted)")
            # Check if workout exists with different profile_id (for debugging)
            check_result = supabase.table("workouts").select("id, profile_id").eq("id", workout_id).execute()
            if check_result.data and len(check_result.data) > 0:
                logger.warning(f"Workout {workout_id} exists but belongs to different profile: {check_result.data[0].get('profile_id')}")
            return False
    except Exception as e:
        logger.error(f"Failed to delete workout {workout_id}: {e}")
        return False


# ============================================================================
# AMA-122: Favorites, Usage Tracking, Programs, and Tags
# ============================================================================

def toggle_workout_favorite(workout_id: str, profile_id: str, is_favorite: bool) -> Optional[Dict[str, Any]]:
    """
    Toggle the favorite status of a workout.

    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)
        is_favorite: Whether to mark as favorite

    Returns:
        Updated workout data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        update_data = {"is_favorite": is_favorite}

        # If favoriting, get next favorite_order
        if is_favorite:
            max_order_result = supabase.table("workouts").select("favorite_order").eq("profile_id", profile_id).eq("is_favorite", True).order("favorite_order", desc=True).limit(1).execute()
            max_order = 0
            if max_order_result.data and len(max_order_result.data) > 0 and max_order_result.data[0].get("favorite_order"):
                max_order = max_order_result.data[0]["favorite_order"]
            update_data["favorite_order"] = max_order + 1
        else:
            update_data["favorite_order"] = None

        result = supabase.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Workout {workout_id} favorite status updated to {is_favorite}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to toggle favorite for workout {workout_id}: {e}")
        return None


def track_workout_usage(workout_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
    """
    Track that a workout was used/loaded (increments times_completed and updates last_used_at).

    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)

    Returns:
        Updated workout data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        from datetime import datetime, timezone

        # First get current times_completed
        current = supabase.table("workouts").select("times_completed").eq("id", workout_id).eq("profile_id", profile_id).single().execute()

        if not current.data:
            return None

        current_count = current.data.get("times_completed") or 0

        update_data = {
            "times_completed": current_count + 1,
            "last_used_at": datetime.now(timezone.utc).isoformat()
        }

        result = supabase.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Workout {workout_id} usage tracked (count: {current_count + 1})")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to track usage for workout {workout_id}: {e}")
        return None


def update_workout_tags(workout_id: str, profile_id: str, tags: List[str]) -> Optional[Dict[str, Any]]:
    """
    Update the tags for a workout.

    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)
        tags: List of tag strings

    Returns:
        Updated workout data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        result = supabase.table("workouts").update({"tags": tags}).eq("id", workout_id).eq("profile_id", profile_id).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Workout {workout_id} tags updated: {tags}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to update tags for workout {workout_id}: {e}")
        return None


# ============================================================================
# Program Management
# ============================================================================

def create_program(
    profile_id: str,
    name: str,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Create a new workout program.

    Args:
        profile_id: User profile ID
        name: Program name
        description: Optional description
        color: Optional color for UI
        icon: Optional icon identifier

    Returns:
        Created program data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        data = {
            "profile_id": profile_id,
            "name": name
        }
        if description:
            data["description"] = description
        if color:
            data["color"] = color
        if icon:
            data["icon"] = icon

        result = supabase.table("workout_programs").insert(data).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Program '{name}' created for profile {profile_id}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to create program: {e}")
        return None


def get_programs(profile_id: str, include_inactive: bool = False) -> List[Dict[str, Any]]:
    """
    Get all programs for a user.

    Args:
        profile_id: User profile ID
        include_inactive: Whether to include inactive programs

    Returns:
        List of program records
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        query = supabase.table("workout_programs").select("*").eq("profile_id", profile_id)

        if not include_inactive:
            query = query.eq("is_active", True)

        query = query.order("created_at", desc=True)

        result = query.execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get programs: {e}")
        return []


def get_program(program_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single program by ID with its members.

    Args:
        program_id: Program UUID
        profile_id: User profile ID (for security)

    Returns:
        Program data with members or None if not found
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # Get program
        program_result = supabase.table("workout_programs").select("*").eq("id", program_id).eq("profile_id", profile_id).single().execute()

        if not program_result.data:
            return None

        program = program_result.data

        # Get program members
        members_result = supabase.table("program_members").select("*").eq("program_id", program_id).order("day_order").execute()

        program["members"] = members_result.data if members_result.data else []

        return program
    except Exception as e:
        logger.error(f"Failed to get program {program_id}: {e}")
        return None


def update_program(
    program_id: str,
    profile_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
    icon: Optional[str] = None,
    current_day_index: Optional[int] = None,
    is_active: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """
    Update a program.

    Args:
        program_id: Program UUID
        profile_id: User profile ID (for security)
        name: New name (optional)
        description: New description (optional)
        color: New color (optional)
        icon: New icon (optional)
        current_day_index: New current day (optional)
        is_active: New active status (optional)

    Returns:
        Updated program data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        update_data = {}
        if name is not None:
            update_data["name"] = name
        if description is not None:
            update_data["description"] = description
        if color is not None:
            update_data["color"] = color
        if icon is not None:
            update_data["icon"] = icon
        if current_day_index is not None:
            update_data["current_day_index"] = current_day_index
        if is_active is not None:
            update_data["is_active"] = is_active

        if not update_data:
            return get_program(program_id, profile_id)

        result = supabase.table("workout_programs").update(update_data).eq("id", program_id).eq("profile_id", profile_id).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Program {program_id} updated")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to update program {program_id}: {e}")
        return None


def delete_program(program_id: str, profile_id: str) -> bool:
    """
    Delete a program.

    Args:
        program_id: Program UUID
        profile_id: User profile ID (for security)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        result = supabase.table("workout_programs").delete().eq("id", program_id).eq("profile_id", profile_id).execute()

        deleted_count = len(result.data) if result.data else 0
        if deleted_count > 0:
            logger.info(f"Program {program_id} deleted")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete program {program_id}: {e}")
        return False


def add_workout_to_program(
    program_id: str,
    profile_id: str,
    workout_id: Optional[str] = None,
    follow_along_id: Optional[str] = None,
    day_order: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Add a workout to a program.

    Args:
        program_id: Program UUID
        profile_id: User profile ID (for security)
        workout_id: Workout UUID (one of workout_id or follow_along_id required)
        follow_along_id: Follow-along workout ID
        day_order: Position in program (auto-assigned if not provided)

    Returns:
        Created member data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    if not workout_id and not follow_along_id:
        logger.error("Either workout_id or follow_along_id must be provided")
        return None

    try:
        # Verify program belongs to user
        program_check = supabase.table("workout_programs").select("id").eq("id", program_id).eq("profile_id", profile_id).execute()
        if not program_check.data:
            logger.error(f"Program {program_id} not found for profile {profile_id}")
            return None

        # Get next day_order if not provided
        if day_order is None:
            max_order_result = supabase.table("program_members").select("day_order").eq("program_id", program_id).order("day_order", desc=True).limit(1).execute()
            if max_order_result.data and len(max_order_result.data) > 0:
                day_order = max_order_result.data[0]["day_order"] + 1
            else:
                day_order = 0

        data = {
            "program_id": program_id,
            "day_order": day_order
        }
        if workout_id:
            data["workout_id"] = workout_id
        if follow_along_id:
            data["follow_along_id"] = follow_along_id

        result = supabase.table("program_members").insert(data).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Workout added to program {program_id} at position {day_order}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to add workout to program: {e}")
        return None


def remove_workout_from_program(member_id: str, profile_id: str) -> bool:
    """
    Remove a workout from a program.

    Args:
        member_id: Program member UUID
        profile_id: User profile ID (for security)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        # Get the member to find the program_id
        member = supabase.table("program_members").select("program_id").eq("id", member_id).single().execute()
        if not member.data:
            return False

        # Verify program belongs to user
        program_check = supabase.table("workout_programs").select("id").eq("id", member.data["program_id"]).eq("profile_id", profile_id).execute()
        if not program_check.data:
            logger.error(f"Program not found for profile {profile_id}")
            return False

        result = supabase.table("program_members").delete().eq("id", member_id).execute()

        deleted_count = len(result.data) if result.data else 0
        if deleted_count > 0:
            logger.info(f"Member {member_id} removed from program")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to remove workout from program: {e}")
        return False


# ============================================================================
# User Tags Management
# ============================================================================

def get_user_tags(profile_id: str) -> List[Dict[str, Any]]:
    """
    Get all tags for a user.

    Args:
        profile_id: User profile ID

    Returns:
        List of tag records
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        result = supabase.table("user_tags").select("*").eq("profile_id", profile_id).order("name").execute()
        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get user tags: {e}")
        return []


def create_user_tag(profile_id: str, name: str, color: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Create a new user tag.

    Args:
        profile_id: User profile ID
        name: Tag name
        color: Optional color for UI

    Returns:
        Created tag data or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        data = {
            "profile_id": profile_id,
            "name": name
        }
        if color:
            data["color"] = color

        result = supabase.table("user_tags").insert(data).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Tag '{name}' created for profile {profile_id}")
            return result.data[0]
        return None
    except Exception as e:
        logger.error(f"Failed to create tag: {e}")
        return None


def delete_user_tag(tag_id: str, profile_id: str) -> bool:
    """
    Delete a user tag.

    Args:
        tag_id: Tag UUID
        profile_id: User profile ID (for security)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        result = supabase.table("user_tags").delete().eq("id", tag_id).eq("profile_id", profile_id).execute()

        deleted_count = len(result.data) if result.data else 0
        if deleted_count > 0:
            logger.info(f"Tag {tag_id} deleted")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete tag {tag_id}: {e}")
        return False


# =============================================================================
# iOS Companion App Sync (AMA-199)
# =============================================================================

def update_workout_ios_companion_sync(workout_id: str, profile_id: str) -> bool:
    """
    Mark a workout as synced to iOS Companion App.

    Sets ios_companion_synced_at to current timestamp.

    Args:
        workout_id: Workout UUID
        profile_id: User profile ID (for security)

    Returns:
        True if successful, False otherwise
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        result = supabase.table("workouts").update({
            "ios_companion_synced_at": now,
            "updated_at": now,
        }).eq("id", workout_id).eq("profile_id", profile_id).execute()

        if result.data and len(result.data) > 0:
            logger.info(f"Workout {workout_id} marked as synced to iOS Companion")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to update iOS companion sync for workout {workout_id}: {e}")
        return False


def get_ios_companion_pending_workouts(profile_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Get workouts that have been pushed to iOS Companion App.

    Returns workouts where ios_companion_synced_at is not null,
    ordered by most recently synced.

    Args:
        profile_id: User profile ID
        limit: Maximum number of workouts to return

    Returns:
        List of workout records with iOS companion sync data
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        result = supabase.table("workouts") \
            .select("id, title, description, workout_data, device, ios_companion_synced_at, created_at") \
            .eq("profile_id", profile_id) \
            .not_.is_("ios_companion_synced_at", "null") \
            .order("ios_companion_synced_at", desc=True) \
            .limit(limit) \
            .execute()

        return result.data if result.data else []
    except Exception as e:
        logger.error(f"Failed to get iOS companion pending workouts for {profile_id}: {e}")
        return []


# =============================================================================
# Account Deletion Preview (AMA-200)
# =============================================================================

def get_account_deletion_preview(profile_id: str) -> Dict[str, Any]:
    """
    Get a preview of all user data that will be deleted when account is deleted.

    This helps users understand what they're losing before confirming deletion.
    Counts items across all user-related tables.

    Args:
        profile_id: User profile ID (Clerk user ID)

    Returns:
        Dict with counts and details of data to be deleted
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"error": "Database not available"}

    preview = {
        "workouts": 0,
        "workout_completions": 0,
        "programs": 0,
        "tags": 0,
        "follow_along_workouts": 0,
        "paired_devices": 0,
        "voice_settings": False,
        "voice_corrections": 0,
        "strava_connection": False,
        "garmin_connection": False,
    }

    try:
        # Count workouts
        workouts_result = supabase.table("workouts") \
            .select("id", count="exact") \
            .eq("profile_id", profile_id) \
            .execute()
        preview["workouts"] = workouts_result.count or 0

        # Count workout completions
        try:
            completions_result = supabase.table("workout_completions") \
                .select("id", count="exact") \
                .eq("user_id", profile_id) \
                .execute()
            preview["workout_completions"] = completions_result.count or 0
        except Exception:
            pass  # Table might not exist yet

        # Count programs
        try:
            programs_result = supabase.table("workout_programs") \
                .select("id", count="exact") \
                .eq("profile_id", profile_id) \
                .execute()
            preview["programs"] = programs_result.count or 0
        except Exception:
            pass  # Table might not exist yet

        # Count tags
        try:
            tags_result = supabase.table("user_tags") \
                .select("id", count="exact") \
                .eq("profile_id", profile_id) \
                .execute()
            preview["tags"] = tags_result.count or 0
        except Exception:
            pass  # Table might not exist yet

        # Count follow-along workouts
        try:
            follow_along_result = supabase.table("follow_along_workouts") \
                .select("id", count="exact") \
                .eq("user_id", profile_id) \
                .execute()
            preview["follow_along_workouts"] = follow_along_result.count or 0
        except Exception:
            pass  # Table might not exist yet

        # Count paired devices (used pairing tokens)
        try:
            devices_result = supabase.table("mobile_pairing_tokens") \
                .select("id", count="exact") \
                .eq("clerk_user_id", profile_id) \
                .not_.is_("used_at", "null") \
                .execute()
            preview["paired_devices"] = devices_result.count or 0
        except Exception:
            pass  # Table might not exist yet

        # Check voice settings
        try:
            voice_settings_result = supabase.table("user_voice_settings") \
                .select("id") \
                .eq("user_id", profile_id) \
                .execute()
            preview["voice_settings"] = bool(voice_settings_result.data)
        except Exception:
            pass  # Table might not exist

        # Count voice corrections
        try:
            voice_corrections_result = supabase.table("user_voice_corrections") \
                .select("id", count="exact") \
                .eq("user_id", profile_id) \
                .execute()
            preview["voice_corrections"] = voice_corrections_result.count or 0
        except Exception:
            pass  # Table might not exist

        # Check Strava connection
        try:
            strava_result = supabase.table("strava_tokens") \
                .select("id") \
                .eq("user_id", profile_id) \
                .execute()
            preview["strava_connection"] = bool(strava_result.data)
        except Exception:
            pass  # Table might not exist

        # Check Garmin connection
        try:
            garmin_result = supabase.table("garmin_tokens") \
                .select("id") \
                .eq("user_id", profile_id) \
                .execute()
            preview["garmin_connection"] = bool(garmin_result.data)
        except Exception:
            pass  # Table might not exist

        # Calculate totals
        preview["total_items"] = (
            preview["workouts"] +
            preview["workout_completions"] +
            preview["programs"] +
            preview["tags"] +
            preview["follow_along_workouts"] +
            preview["voice_corrections"]
        )

        preview["has_ios_devices"] = preview["paired_devices"] > 0
        preview["has_external_connections"] = (
            preview["strava_connection"] or preview["garmin_connection"]
        )

        return preview

    except Exception as e:
        logger.error(f"Failed to get account deletion preview: {e}")
        return {"error": str(e)}


def delete_user_account(profile_id: str) -> Dict[str, Any]:
    """
    Delete all user data from the database.

    This permanently removes all user data across all tables.
    Should only be called after user confirmation.

    Args:
        profile_id: User profile ID (Clerk user ID)

    Returns:
        Dict with deletion results
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"success": False, "error": "Database not available"}

    deleted_counts = {}

    try:
        # Delete workouts
        try:
            result = supabase.table("workouts").delete().eq("profile_id", profile_id).execute()
            deleted_counts["workouts"] = len(result.data) if result.data else 0
        except Exception as e:
            logger.warning(f"Error deleting workouts: {e}")
            deleted_counts["workouts"] = 0

        # Delete workout completions
        try:
            result = supabase.table("workout_completions").delete().eq("user_id", profile_id).execute()
            deleted_counts["workout_completions"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["workout_completions"] = 0

        # Delete workout programs
        try:
            result = supabase.table("workout_programs").delete().eq("profile_id", profile_id).execute()
            deleted_counts["programs"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["programs"] = 0

        # Delete user tags
        try:
            result = supabase.table("user_tags").delete().eq("profile_id", profile_id).execute()
            deleted_counts["tags"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["tags"] = 0

        # Delete follow-along workouts
        try:
            result = supabase.table("follow_along_workouts").delete().eq("user_id", profile_id).execute()
            deleted_counts["follow_along_workouts"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["follow_along_workouts"] = 0

        # Delete mobile pairing tokens
        try:
            result = supabase.table("mobile_pairing_tokens").delete().eq("clerk_user_id", profile_id).execute()
            deleted_counts["paired_devices"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["paired_devices"] = 0

        # Delete voice settings
        try:
            result = supabase.table("user_voice_settings").delete().eq("user_id", profile_id).execute()
            deleted_counts["voice_settings"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["voice_settings"] = 0

        # Delete voice corrections
        try:
            result = supabase.table("user_voice_corrections").delete().eq("user_id", profile_id).execute()
            deleted_counts["voice_corrections"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["voice_corrections"] = 0

        # Delete Strava tokens
        try:
            result = supabase.table("strava_tokens").delete().eq("user_id", profile_id).execute()
            deleted_counts["strava_tokens"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["strava_tokens"] = 0

        # Delete Garmin tokens
        try:
            result = supabase.table("garmin_tokens").delete().eq("user_id", profile_id).execute()
            deleted_counts["garmin_tokens"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["garmin_tokens"] = 0

        # Delete workout events (calendar)
        try:
            result = supabase.table("workout_events").delete().eq("user_id", profile_id).execute()
            deleted_counts["workout_events"] = len(result.data) if result.data else 0
        except Exception:
            deleted_counts["workout_events"] = 0

        # Finally delete the profile itself
        try:
            result = supabase.table("profiles").delete().eq("id", profile_id).execute()
            deleted_counts["profile"] = 1 if result.data else 0
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")
            deleted_counts["profile"] = 0

        # Delete the Clerk user account
        clerk_deleted = False
        clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
        if clerk_secret_key:
            try:
                import httpx
                response = httpx.delete(
                    f"https://api.clerk.com/v1/users/{profile_id}",
                    headers={
                        "Authorization": f"Bearer {clerk_secret_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=10.0,
                )
                if response.status_code in (200, 204):
                    clerk_deleted = True
                    logger.info(f"Deleted Clerk user {profile_id}")
                elif response.status_code == 404:
                    # User doesn't exist in Clerk, that's fine
                    clerk_deleted = True
                    logger.info(f"Clerk user {profile_id} not found (already deleted)")
                else:
                    logger.error(f"Failed to delete Clerk user {profile_id}: {response.status_code} {response.text}")
            except Exception as e:
                logger.error(f"Error deleting Clerk user {profile_id}: {e}")
        else:
            logger.warning("CLERK_SECRET_KEY not configured, skipping Clerk user deletion")

        deleted_counts["clerk_user"] = 1 if clerk_deleted else 0

        logger.info(f"Deleted user account {profile_id}: {deleted_counts}")
        return {"success": True, "deleted": deleted_counts}

    except Exception as e:
        logger.error(f"Failed to delete user account {profile_id}: {e}")
        return {"success": False, "error": str(e)}

