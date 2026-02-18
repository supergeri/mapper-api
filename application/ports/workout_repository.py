"""
Workout Repository Interface (Port).

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

This module defines the abstract interface for workout persistence operations.
Implementations may use Supabase, in-memory storage, or other backends.
"""
from typing import Protocol, Optional, List, Dict, Any


class WorkoutRepository(Protocol):
    """
    Abstract interface for workout persistence operations.

    This protocol defines the contract for workout storage and retrieval.
    Implementations must provide all methods defined here.

    Domain types are used instead of database-specific types to maintain
    clean architecture boundaries.
    """

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
        Save a workout to persistent storage.

        Supports deduplication: if workout_id is provided, updates existing.
        Otherwise, may deduplicate by profile_id + title + device.

        Args:
            profile_id: User profile ID (Clerk user ID)
            workout_data: Full workout structure including blocks/intervals
            sources: List of source identifiers (e.g., ["youtube", "ai"])
            device: Target device type ("garmin", "apple", "ios_companion")
            exports: Optional export formats (FIT, ZWO, etc.)
            validation: Optional validation results
            title: Optional workout title (extracted from workout_data if not provided)
            description: Optional workout description
            workout_id: Optional existing workout ID for explicit updates

        Returns:
            Saved workout record with id, or None on failure
        """
        ...

    def get(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single workout by ID.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID (for authorization)

        Returns:
            Workout record or None if not found/unauthorized
        """
        ...

    def get_list(
        self,
        profile_id: str,
        *,
        device: Optional[str] = None,
        is_exported: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get workouts for a user with optional filters.

        Args:
            profile_id: User profile ID
            device: Filter by device type (optional)
            is_exported: Filter by export status (optional)
            limit: Maximum number of workouts to return

        Returns:
            List of workout records, ordered by created_at desc
        """
        ...

    def delete(
        self,
        workout_id: str,
        profile_id: str,
    ) -> bool:
        """
        Delete a workout.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID (for authorization)

        Returns:
            True if deleted, False if not found or unauthorized
        """
        ...

    def update_export_status(
        self,
        workout_id: str,
        profile_id: str,
        *,
        is_exported: bool = True,
        exported_to_device: Optional[str] = None,
    ) -> bool:
        """
        Update workout export status.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID (for authorization)
            is_exported: Whether workout has been exported
            exported_to_device: Device it was exported to

        Returns:
            True if updated successfully
        """
        ...

    def toggle_favorite(
        self,
        workout_id: str,
        profile_id: str,
        is_favorite: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Toggle favorite status for a workout.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID
            is_favorite: New favorite status

        Returns:
            Updated workout record or None on failure
        """
        ...

    def track_usage(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Track that a workout was used (increment times_completed, update last_used_at).

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID

        Returns:
            Updated workout record or None on failure
        """
        ...

    def update_tags(
        self,
        workout_id: str,
        profile_id: str,
        tags: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Update tags for a workout.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID
            tags: New list of tag strings

        Returns:
            Updated workout record or None on failure
        """
        ...

    def get_incoming(
        self,
        profile_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get incoming workouts pending completion.

        Returns workouts pushed to companion apps that haven't been completed yet.

        Args:
            profile_id: User profile ID
            limit: Maximum number of workouts to return

        Returns:
            List of pending workout records
        """
        ...

    def get_sync_status(
        self,
        workout_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get sync status for a workout across all device types.

        Args:
            workout_id: Workout UUID
            user_id: User ID

        Returns:
            Dict with sync status per device type (ios, android, garmin)
        """
        ...

    def batch_get_sync_status(
        self,
        workout_ids: List[str],
        user_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get sync status for multiple workouts in a single query.

        This method avoids N+1 query issues when fetching sync status
        for a list of workouts.

        Args:
            workout_ids: List of workout UUIDs
            user_id: User ID

        Returns:
            Dict mapping workout_id to sync status dict
        """
        ...

    def update_companion_sync(
        self,
        workout_id: str,
        profile_id: str,
        platform: str,
    ) -> bool:
        """
        Mark a workout as synced to a companion app.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID
            platform: Platform identifier ("ios" or "android")

        Returns:
            True if updated successfully
        """
        ...

    def get_workout_by_id(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a workout by ID with all fields for patching.

        Similar to get() but explicitly named for patch operations.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID (for authorization)

        Returns:
            Full workout record or None if not found/unauthorized
        """
        ...

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
        """
        Update workout data and optionally clear embedding hash.

        Used for patch operations where the full workout_data JSON
        has been modified.

        Args:
            workout_id: Workout UUID
            profile_id: User profile ID (for authorization)
            workout_data: Updated workout_data JSON
            title: Optional updated title
            description: Optional updated description
            tags: Optional updated tags list
            clear_embedding: Whether to clear embedding_content_hash

        Returns:
            Updated workout record or None on failure
        """
        ...

    def log_patch_audit(
        self,
        workout_id: str,
        user_id: str,
        operations: List[Dict[str, Any]],
        changes_applied: int,
    ) -> None:
        """
        Log patch operations to audit trail.

        This is a best-effort operation - failures should not
        cause the main patch operation to fail.

        Args:
            workout_id: Workout UUID that was patched
            user_id: User who performed the patch
            operations: List of patch operations applied
            changes_applied: Number of operations that resulted in changes
        """
        ...
