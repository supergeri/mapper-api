"""
Fake Workout Repository for testing.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

This module provides an in-memory implementation of WorkoutRepository
for fast, isolated testing without database dependencies.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import copy


class FakeWorkoutRepository:
    """
    In-memory fake implementation of WorkoutRepository for testing.

    Stores workouts in a dict keyed by workout ID. Supports seeding with
    test data and resets between tests.

    Usage:
        repo = FakeWorkoutRepository()
        repo.seed([{"id": "w1", "title": "Test Workout", ...}])
        result = repo.save(profile_id="user1", workout_data={...}, ...)
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._workouts: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        """Clear all stored workouts."""
        self._workouts.clear()

    def seed(self, workouts: List[Dict[str, Any]]) -> None:
        """
        Seed the repository with test data.

        Args:
            workouts: List of workout dicts. Must include 'id' and 'profile_id'.
        """
        for workout in workouts:
            workout_id = workout.get("id") or str(uuid.uuid4())
            self._workouts[workout_id] = {**workout, "id": workout_id}

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all stored workouts (test helper)."""
        return list(self._workouts.values())

    # =========================================================================
    # WorkoutRepository Protocol Methods
    # =========================================================================

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
        """Save a workout to in-memory storage."""
        now = datetime.now(timezone.utc).isoformat()

        # Use provided ID or generate new one
        wid = workout_id or str(uuid.uuid4())

        # Check for existing (update case)
        existing = self._workouts.get(wid)

        workout = {
            "id": wid,
            "profile_id": profile_id,
            "workout_data": copy.deepcopy(workout_data),
            "sources": sources,
            "device": device,
            "exports": exports,
            "validation": validation,
            "title": title or workout_data.get("title", "Untitled"),
            "description": description,
            "is_exported": False,
            "is_favorite": existing.get("is_favorite", False) if existing else False,
            "times_completed": existing.get("times_completed", 0) if existing else 0,
            "last_used_at": existing.get("last_used_at") if existing else None,
            "tags": existing.get("tags", []) if existing else [],
            "synced_to_ios": existing.get("synced_to_ios", False) if existing else False,
            "synced_to_android": existing.get("synced_to_android", False) if existing else False,
            "created_at": existing.get("created_at", now) if existing else now,
            "updated_at": now,
        }

        self._workouts[wid] = workout
        return copy.deepcopy(workout)

    def get(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single workout by ID."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            return copy.deepcopy(workout)
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
        results = []
        for workout in self._workouts.values():
            if workout.get("profile_id") != profile_id:
                continue
            if device is not None and workout.get("device") != device:
                continue
            if is_exported is not None and workout.get("is_exported") != is_exported:
                continue
            results.append(copy.deepcopy(workout))

        # Sort by created_at descending
        results.sort(key=lambda w: w.get("created_at", ""), reverse=True)
        return results[:limit]

    def delete(
        self,
        workout_id: str,
        profile_id: str,
    ) -> bool:
        """Delete a workout."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            del self._workouts[workout_id]
            return True
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
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            workout["is_exported"] = is_exported
            if exported_to_device:
                workout["exported_to_device"] = exported_to_device
            workout["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False

    def toggle_favorite(
        self,
        workout_id: str,
        profile_id: str,
        is_favorite: bool,
    ) -> Optional[Dict[str, Any]]:
        """Toggle favorite status for a workout."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            workout["is_favorite"] = is_favorite
            workout["updated_at"] = datetime.now(timezone.utc).isoformat()
            return copy.deepcopy(workout)
        return None

    def track_usage(
        self,
        workout_id: str,
        profile_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Track that a workout was used."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            workout["times_completed"] = workout.get("times_completed", 0) + 1
            workout["last_used_at"] = datetime.now(timezone.utc).isoformat()
            workout["updated_at"] = datetime.now(timezone.utc).isoformat()
            return copy.deepcopy(workout)
        return None

    def update_tags(
        self,
        workout_id: str,
        profile_id: str,
        tags: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Update tags for a workout."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            workout["tags"] = tags
            workout["updated_at"] = datetime.now(timezone.utc).isoformat()
            return copy.deepcopy(workout)
        return None

    def get_incoming(
        self,
        profile_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get incoming workouts pending completion."""
        results = []
        for workout in self._workouts.values():
            if workout.get("profile_id") != profile_id:
                continue
            # Filter to companion-synced but not completed
            if workout.get("synced_to_ios") or workout.get("synced_to_android"):
                if workout.get("times_completed", 0) == 0:
                    results.append(copy.deepcopy(workout))

        results.sort(key=lambda w: w.get("created_at", ""), reverse=True)
        return results[:limit]

    def get_sync_status(
        self,
        workout_id: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get sync status for a workout."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == user_id:
            return {
                "ios": workout.get("synced_to_ios", False),
                "android": workout.get("synced_to_android", False),
                "garmin": workout.get("is_exported", False),
            }
        return {"ios": False, "android": False, "garmin": False}

    def update_companion_sync(
        self,
        workout_id: str,
        profile_id: str,
        platform: str,
    ) -> bool:
        """Mark a workout as synced to a companion app."""
        workout = self._workouts.get(workout_id)
        if workout and workout.get("profile_id") == profile_id:
            if platform == "ios":
                workout["synced_to_ios"] = True
            elif platform == "android":
                workout["synced_to_android"] = True
            workout["updated_at"] = datetime.now(timezone.utc).isoformat()
            return True
        return False
