"""
Get Workout Use Case.

Part of AMA-370: Refactor routers to call use-cases

This use case handles retrieving workouts from the database.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from application.ports import WorkoutRepository


@dataclass
class GetWorkoutResult:
    """Result of getting a single workout."""
    success: bool
    workout: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass
class ListWorkoutsResult:
    """Result of listing workouts."""
    success: bool
    workouts: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0
    error: Optional[str] = None


@dataclass
class GetIncomingWorkoutsResult:
    """Result of getting incoming workouts."""
    success: bool
    workouts: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0
    error: Optional[str] = None


class GetWorkoutUseCase:
    """
    Use case for retrieving workouts.
    
    Encapsulates all logic for getting individual workouts,
    listing workouts with filters, and getting incoming workouts.
    """
    
    def __init__(self, workout_repo: WorkoutRepository):
        """
        Initialize with required dependencies.
        
        Args:
            workout_repo: Repository for workout persistence
        """
        self._workout_repo = workout_repo
    
    def get_workout(
        self,
        workout_id: str,
        user_id: str,
    ) -> GetWorkoutResult:
        """
        Get a single workout by ID.
        
        Args:
            workout_id: ID of the workout to retrieve
            user_id: Current user ID (for authorization)
            
        Returns:
            GetWorkoutResult with workout data or error
        """
        workout = self._workout_repo.get(workout_id, user_id)
        
        if workout:
            # Include sync status in response
            sync_status = self._workout_repo.get_sync_status(workout_id, user_id)
            workout["sync_status"] = sync_status
            return GetWorkoutResult(
                success=True,
                workout=workout,
            )
        else:
            return GetWorkoutResult(
                success=False,
                error="Workout not found or not owned by user",
            )
    
    def list_workouts(
        self,
        user_id: str,
        device: Optional[str] = None,
        is_exported: Optional[bool] = None,
        limit: int = 50,
    ) -> ListWorkoutsResult:
        """
        List workouts for a user with optional filters.
        
        Args:
            user_id: Current user ID
            device: Optional device filter
            is_exported: Optional export status filter
            limit: Maximum number of workouts to return
            
        Returns:
            ListWorkoutsResult with workout list
        """
        workouts = self._workout_repo.get_list(
            profile_id=user_id,
            device=device,
            is_exported=is_exported,
            limit=limit,
        )
        
        # Batch fetch sync status for all workouts to avoid N+1 queries
        workout_ids = [w.get("id") for w in workouts if w.get("id")]
        if workout_ids:
            sync_status_map = self._workout_repo.batch_get_sync_status(workout_ids, user_id)
            for workout in workouts:
                workout_id = workout.get("id")
                if workout_id:
                    workout["sync_status"] = sync_status_map.get(
                        workout_id, 
                        {"ios": None, "android": None, "garmin": None}
                    )
        
        return ListWorkoutsResult(
            success=True,
            workouts=workouts,
            count=len(workouts),
        )
    
    def get_incoming_workouts(
        self,
        user_id: str,
        limit: int = 50,
    ) -> GetIncomingWorkoutsResult:
        """
        Get incoming workouts that haven't been completed yet.
        
        Args:
            user_id: Current user ID
            limit: Maximum number of workouts to return
            
        Returns:
            GetIncomingWorkoutsResult with pending workouts
        """
        workouts = self._workout_repo.get_incoming(user_id, limit=limit)
        
        return GetIncomingWorkoutsResult(
            success=True,
            workouts=workouts,
            count=len(workouts),
        )
    
    def delete_workout(
        self,
        workout_id: str,
        user_id: str,
    ) -> bool:
        """
        Delete a workout.
        
        Args:
            workout_id: ID of the workout to delete
            user_id: Current user ID (for authorization)
            
        Returns:
            True if deleted successfully
        """
        return self._workout_repo.delete(workout_id, user_id)
    
    def update_export_status(
        self,
        workout_id: str,
        user_id: str,
        is_exported: bool,
        exported_to_device: Optional[str] = None,
    ) -> bool:
        """
        Update workout export status.
        
        Args:
            workout_id: ID of the workout
            user_id: Current user ID
            is_exported: New export status
            exported_to_device: Device it was exported to
            
        Returns:
            True if updated successfully
        """
        return self._workout_repo.update_export_status(
            workout_id=workout_id,
            profile_id=user_id,
            is_exported=is_exported,
            exported_to_device=exported_to_device,
        )
    
    def toggle_favorite(
        self,
        workout_id: str,
        user_id: str,
        is_favorite: bool,
    ) -> Optional[Dict[str, Any]]:
        """
        Toggle favorite status for a workout.
        
        Args:
            workout_id: ID of the workout
            user_id: Current user ID
            is_favorite: New favorite status
            
        Returns:
            Updated workout record or None on failure
        """
        return self._workout_repo.toggle_favorite(
            workout_id=workout_id,
            profile_id=user_id,
            is_favorite=is_favorite,
        )
    
    def track_usage(
        self,
        workout_id: str,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Track that a workout was used.
        
        Args:
            workout_id: ID of the workout
            user_id: Current user ID
            
        Returns:
            Updated workout record or None on failure
        """
        return self._workout_repo.track_usage(
            workout_id=workout_id,
            profile_id=user_id,
        )
    
    def update_tags(
        self,
        workout_id: str,
        user_id: str,
        tags: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Update tags for a workout.
        
        Args:
            workout_id: ID of the workout
            user_id: Current user ID
            tags: New list of tags
            
        Returns:
            Updated workout record or None on failure
        """
        return self._workout_repo.update_tags(
            workout_id=workout_id,
            profile_id=user_id,
            tags=tags,
        )
