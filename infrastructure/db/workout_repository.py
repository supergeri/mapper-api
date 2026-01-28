"""
Supabase implementation of WorkoutRepository.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This module provides the concrete Supabase implementation for workout persistence.
Logic moved from backend/database.py with constructor-injected client.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseWorkoutRepository:
    """
    Supabase implementation of WorkoutRepository protocol.

    All Supabase query logic for workouts is encapsulated here.
    The client is injected via constructor for testability.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected, not global)
        """
        self._client = client

    def save(
        self,
        profile_id: str,
        workout_data: Dict[str, Any],
        sources: List[str],
        device: str,
        *,
        exports: Optional[Dict[str, Any]] = None,
        validation: Optional[Dict[str, Any]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        workout_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Save a workout to Supabase with deduplication.

        If a workout with the same profile_id, title, and device already exists,
        it will be updated instead of creating a duplicate.
        """
        try:
            # Extract title from workout_data if not provided
            effective_title = title or workout_data.get("title")

            # Check for existing workout with same profile_id, title, and device
            existing_workout = None

            if workout_id:
                # Explicit update - check if workout exists
                check_result = self._client.table("workouts").select("id").eq("id", workout_id).eq("profile_id", profile_id).execute()
                if check_result.data and len(check_result.data) > 0:
                    existing_workout = check_result.data[0]
            elif effective_title:
                # Check for duplicate by title + device + profile_id
                check_result = self._client.table("workouts").select("id, created_at").eq("profile_id", profile_id).eq("title", effective_title).eq("device", device).order("created_at", desc=True).limit(1).execute()
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
                data["updated_at"] = datetime.now(timezone.utc).isoformat()

                result = self._client.table("workouts").update(data).eq("id", existing_workout["id"]).eq("profile_id", profile_id).execute()

                if result.data and len(result.data) > 0:
                    logger.info(f"Workout updated (dedup) for profile {profile_id}, id: {existing_workout['id']}")
                    return result.data[0]
                return None
            else:
                # Insert new workout
                result = self._client.table("workouts").insert(data).execute()

                if result.data and len(result.data) > 0:
                    logger.info(f"Workout saved for profile {profile_id}")
                    return result.data[0]
                return None
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to save workout: {e}")
            if "PGRST" in error_msg or "permission" in error_msg.lower() or "row-level security" in error_msg.lower():
                logger.error("RLS/Permissions error: Consider using SUPABASE_SERVICE_ROLE_KEY instead of SUPABASE_ANON_KEY for backend API")
            return None

    def get(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single workout by ID."""
        try:
            result = self._client.table("workouts").select("*").eq("id", workout_id).eq("profile_id", profile_id).single().execute()
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Failed to get workout {workout_id}: {e}")
            return None

    def get_list(
        self,
        profile_id: str,
        *,
        device: Optional[str] = None,
        is_exported: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get workouts for a user with optional filters."""
        try:
            query = self._client.table("workouts").select("*").eq("profile_id", profile_id)

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

    def delete(
        self,
        workout_id: str,
        profile_id: str,
    ) -> bool:
        """Delete a workout."""
        try:
            logger.info(f"Attempting to delete workout {workout_id} for profile {profile_id}")
            result = self._client.table("workouts").delete().eq("id", workout_id).eq("profile_id", profile_id).execute()

            deleted_count = len(result.data) if result.data else 0

            if deleted_count > 0:
                logger.info(f"Workout {workout_id} deleted successfully ({deleted_count} row(s))")
                return True
            else:
                logger.warning(f"No workout found with id {workout_id} for profile {profile_id} (0 rows deleted)")
                # Check if workout exists with different profile_id (for debugging)
                check_result = self._client.table("workouts").select("id, profile_id").eq("id", workout_id).execute()
                if check_result.data and len(check_result.data) > 0:
                    logger.warning(f"Workout {workout_id} exists but belongs to different profile: {check_result.data[0].get('profile_id')}")
                return False
        except Exception as e:
            logger.error(f"Failed to delete workout {workout_id}: {e}")
            return False

    def update_export_status(
        self,
        workout_id: str,
        profile_id: str,
        *,
        is_exported: bool = True,
        exported_to_device: Optional[str] = None,
    ) -> bool:
        """Update workout export status."""
        try:
            update_data = {
                "is_exported": is_exported,
            }

            if is_exported:
                update_data["exported_at"] = datetime.now(timezone.utc).isoformat()
                if exported_to_device:
                    update_data["exported_to_device"] = exported_to_device
            else:
                update_data["exported_at"] = None
                update_data["exported_to_device"] = None

            result = self._client.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()
            return result.data is not None
        except Exception as e:
            logger.error(f"Failed to update workout export status: {e}")
            return False

    def toggle_favorite(
        self,
        workout_id: str,
        profile_id: str,
        is_favorite: bool,
    ) -> Optional[Dict[str, Any]]:
        """Toggle favorite status for a workout."""
        try:
            update_data = {"is_favorite": is_favorite}

            # If favoriting, get next favorite_order
            if is_favorite:
                max_order_result = self._client.table("workouts").select("favorite_order").eq("profile_id", profile_id).eq("is_favorite", True).order("favorite_order", desc=True).limit(1).execute()
                max_order = 0
                if max_order_result.data and len(max_order_result.data) > 0 and max_order_result.data[0].get("favorite_order"):
                    max_order = max_order_result.data[0]["favorite_order"]
                update_data["favorite_order"] = max_order + 1
            else:
                update_data["favorite_order"] = None

            result = self._client.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout {workout_id} favorite status updated to {is_favorite}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to toggle favorite for workout {workout_id}: {e}")
            return None

    def track_usage(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Track that a workout was used (increment times_completed, update last_used_at)."""
        try:
            # First get current times_completed
            current = self._client.table("workouts").select("times_completed").eq("id", workout_id).eq("profile_id", profile_id).single().execute()

            if not current.data:
                return None

            current_count = current.data.get("times_completed") or 0

            update_data = {
                "times_completed": current_count + 1,
                "last_used_at": datetime.now(timezone.utc).isoformat()
            }

            result = self._client.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout {workout_id} usage tracked (count: {current_count + 1})")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to track usage for workout {workout_id}: {e}")
            return None

    def update_tags(
        self,
        workout_id: str,
        profile_id: str,
        tags: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Update tags for a workout."""
        try:
            result = self._client.table("workouts").update({"tags": tags}).eq("id", workout_id).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout {workout_id} tags updated: {tags}")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to update tags for workout {workout_id}: {e}")
            return None

    def get_incoming(
        self,
        profile_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get incoming workouts pending completion."""
        try:
            result = self._client.table("workouts") \
                .select("id, title, description, workout_data, device, ios_companion_synced_at, created_at") \
                .eq("profile_id", profile_id) \
                .not_.is_("ios_companion_synced_at", "null") \
                .order("ios_companion_synced_at", desc=True) \
                .limit(limit) \
                .execute()

            workouts = result.data if result.data else []

            # Filter out completed workouts
            if workouts:
                completed_ids = self._get_completed_workout_ids(profile_id)
                workouts = [w for w in workouts if w["id"] not in completed_ids]

            return workouts
        except Exception as e:
            logger.error(f"Failed to get incoming workouts for {profile_id}: {e}")
            return []

    def _get_completed_workout_ids(self, profile_id: str) -> set:
        """Get IDs of workouts that the user has completed."""
        try:
            result = self._client.table("workout_completions") \
                .select("workout_id") \
                .eq("user_id", profile_id) \
                .not_.is_("workout_id", "null") \
                .execute()

            if result.data:
                return {r["workout_id"] for r in result.data if r.get("workout_id")}
            return set()
        except Exception as e:
            logger.error(f"Failed to get completed workout IDs for {profile_id}: {e}")
            return set()

    def get_sync_status(
        self,
        workout_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get sync status for a workout across all device types."""
        try:
            result = self._client.table("workout_sync_queue").select(
                "device_type, device_id, status, queued_at, synced_at, failed_at, error_message"
            ).eq("workout_id", workout_id).eq("user_id", user_id).execute()

            sync_status = {"ios": None, "android": None, "garmin": None}

            if result.data:
                for entry in result.data:
                    device_type = entry.get("device_type")
                    if device_type in sync_status:
                        sync_status[device_type] = {
                            "status": entry.get("status"),
                            "queued_at": entry.get("queued_at"),
                            "synced_at": entry.get("synced_at"),
                            "failed_at": entry.get("failed_at"),
                            "error_message": entry.get("error_message"),
                            "device_id": entry.get("device_id") or None,
                        }

            return sync_status

        except Exception as e:
            logger.error(f"Failed to get workout sync status: {e}")
            return {"ios": None, "android": None, "garmin": None}

    def update_companion_sync(
        self,
        workout_id: str,
        profile_id: str,
        platform: str,
    ) -> bool:
        """Mark a workout as synced to a companion app."""
        try:
            now = datetime.now(timezone.utc).isoformat()

            if platform == "ios":
                column = "ios_companion_synced_at"
            elif platform == "android":
                column = "android_companion_synced_at"
            else:
                logger.error(f"Unknown platform: {platform}")
                return False

            result = self._client.table("workouts").update({
                column: now,
                "updated_at": now,
            }).eq("id", workout_id).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout {workout_id} marked as synced to {platform.upper()} Companion")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update {platform} companion sync for workout {workout_id}: {e}")
            return False

    # =========================================================================
    # Sync Queue Operations (AMA-307)
    # =========================================================================

    def queue_sync(
        self,
        workout_id: str,
        user_id: str,
        device_type: str,
        device_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Queue a workout for sync to a device."""
        try:
            result = self._client.table("workout_sync_queue").upsert({
                "workout_id": workout_id,
                "user_id": user_id,
                "device_type": device_type,
                "device_id": device_id or "",
                "status": "pending",
                "queued_at": "now()",
                "synced_at": None,
                "failed_at": None,
                "error_message": None,
            }, on_conflict="workout_id,device_type,device_id").execute()

            if result.data and len(result.data) > 0:
                return {
                    "status": "pending",
                    "queued_at": result.data[0].get("queued_at")
                }

            logger.warning(f"No data returned from sync queue upsert for workout {workout_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to queue workout sync: {e}")
            return None

    def get_pending_syncs(
        self,
        user_id: str,
        device_type: str,
        device_id: str = ""
    ) -> List[Dict[str, Any]]:
        """Get pending workout syncs for a device."""
        try:
            query = self._client.table("workout_sync_queue").select(
                "id, workout_id, queued_at, workouts(id, title, workout_data, created_at)"
            ).eq("user_id", user_id).eq("device_type", device_type).eq("status", "pending")

            if device_id:
                query = query.in_("device_id", [device_id, ""])
            else:
                query = query.eq("device_id", "")

            result = query.order("queued_at", desc=False).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get pending syncs: {e}")
            return []

    def confirm_sync(
        self,
        workout_id: str,
        user_id: str,
        device_type: str,
        device_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Confirm that a workout was successfully downloaded by the device."""
        try:
            result = self._client.table("workout_sync_queue").update({
                "status": "synced",
                "synced_at": "now()",
            }).eq("workout_id", workout_id).eq(
                "user_id", user_id
            ).eq("device_type", device_type).eq(
                "device_id", device_id or ""
            ).execute()

            if result.data and len(result.data) > 0:
                return {
                    "status": "synced",
                    "synced_at": result.data[0].get("synced_at")
                }

            logger.warning(f"No sync queue entry found for workout {workout_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to confirm sync: {e}")
            return None

    def report_sync_failed(
        self,
        workout_id: str,
        user_id: str,
        device_type: str,
        error_message: str,
        device_id: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Report that a workout sync failed."""
        try:
            result = self._client.table("workout_sync_queue").update({
                "status": "failed",
                "failed_at": "now()",
                "error_message": error_message,
            }).eq("workout_id", workout_id).eq(
                "user_id", user_id
            ).eq("device_type", device_type).eq(
                "device_id", device_id or ""
            ).execute()

            if result.data and len(result.data) > 0:
                return {
                    "status": "failed",
                    "failed_at": result.data[0].get("failed_at"),
                    "error_message": error_message
                }

            logger.warning(f"No sync queue entry found for workout {workout_id}")
            return None

        except Exception as e:
            logger.error(f"Failed to report sync failure: {e}")
            return None

    # =========================================================================
    # Patch Operations (AMA-433)
    # =========================================================================

    def get_workout_by_id(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a workout by ID with all fields for patching."""
        # Delegate to existing get() method
        return self.get(workout_id, profile_id)

    def update_workout_data(
        self,
        workout_id: str,
        profile_id: str,
        workout_data: Dict[str, Any],
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        clear_embedding: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Update workout data and optionally clear embedding hash."""
        try:
            update_data: Dict[str, Any] = {
                "workout_data": workout_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

            if title is not None:
                update_data["title"] = title
            if description is not None:
                update_data["description"] = description
            if tags is not None:
                update_data["tags"] = tags
            if clear_embedding:
                update_data["embedding_content_hash"] = None

            result = self._client.table("workouts").update(update_data).eq("id", workout_id).eq("profile_id", profile_id).execute()

            if result.data and len(result.data) > 0:
                logger.info(f"Workout {workout_id} data updated (clear_embedding={clear_embedding})")
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Failed to update workout data for {workout_id}: {e}")
            return None

    def log_patch_audit(
        self,
        workout_id: str,
        user_id: str,
        operations: List[Dict[str, Any]],
        changes_applied: int,
    ) -> None:
        """
        Log patch operations to audit trail (best-effort).

        This method logs to workout_edit_history table. Failures are
        logged but do not raise exceptions to avoid affecting the
        main patch operation.
        """
        try:
            self._client.table("workout_edit_history").insert({
                "workout_id": workout_id,
                "user_id": user_id,
                "operations": operations,
                "changes_applied": changes_applied,
            }).execute()

            logger.debug(f"Logged patch audit for workout {workout_id}: {changes_applied} changes")
        except Exception as e:
            # Best-effort - log but don't raise
            logger.warning(f"Failed to log patch audit for {workout_id}: {e}")
