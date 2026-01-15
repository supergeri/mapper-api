"""
Completion Repository Interface (Port).

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

This module defines the abstract interface for workout completion persistence.
Completions track health metrics from Apple Watch, Garmin, or manual entry.
"""
from typing import Protocol, Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class HealthMetricsDTO:
    """Health metrics captured during a workout."""
    avg_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    min_heart_rate: Optional[int] = None
    active_calories: Optional[int] = None
    total_calories: Optional[int] = None
    distance_meters: Optional[int] = None
    steps: Optional[int] = None


@dataclass
class CompletionSummary:
    """Summary returned after saving a completion."""
    duration_formatted: str
    avg_heart_rate: Optional[int] = None
    calories: Optional[int] = None


class CompletionRepository(Protocol):
    """
    Abstract interface for workout completion persistence.

    This protocol defines the contract for storing and retrieving workout
    completion records with health metrics from various sources.
    """

    def save(
        self,
        user_id: str,
        *,
        started_at: str,
        ended_at: str,
        health_metrics: HealthMetricsDTO,
        source: str = "apple_watch",
        workout_event_id: Optional[str] = None,
        follow_along_workout_id: Optional[str] = None,
        workout_id: Optional[str] = None,
        source_workout_id: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
        heart_rate_samples: Optional[List[Dict[str, Any]]] = None,
        workout_structure: Optional[List[Dict[str, Any]]] = None,
        set_logs: Optional[List[Dict[str, Any]]] = None,
        execution_log: Optional[Dict[str, Any]] = None,
        is_simulated: bool = False,
        simulation_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Save a workout completion record.

        At least one of workout_event_id, follow_along_workout_id, or workout_id
        must be provided to link the completion to a workout.

        Args:
            user_id: User ID (Clerk user ID)
            started_at: ISO format start timestamp
            ended_at: ISO format end timestamp
            health_metrics: Health data captured during workout
            source: Data source ("apple_watch", "garmin", "manual")
            workout_event_id: Link to calendar event (optional)
            follow_along_workout_id: Link to follow-along workout (optional)
            workout_id: Link to iOS Companion workout (optional)
            source_workout_id: External workout ID from source device
            device_info: Device metadata
            heart_rate_samples: Time series heart rate data
            workout_structure: Original workout intervals
            set_logs: Weight tracking per exercise/set (legacy)
            execution_log: Detailed execution vs planned data
            is_simulated: Whether workout was run in simulation mode
            simulation_config: Simulation parameters if simulated

        Returns:
            Dict with success status, completion ID, and summary on success,
            or error details on failure.
        """
        ...

    def get_by_id(
        self,
        user_id: str,
        completion_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get a single completion with full details including HR samples.

        Args:
            user_id: User ID for authorization
            completion_id: Completion UUID

        Returns:
            Full completion record or None if not found
        """
        ...

    def get_user_completions(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        include_simulated: bool = True,
    ) -> Dict[str, Any]:
        """
        Get completion history for a user.

        Args:
            user_id: User ID
            limit: Maximum records to return
            offset: Records to skip for pagination
            include_simulated: Whether to include simulated completions

        Returns:
            Dict with "completions" list and "total" count
        """
        ...

    def save_voice_workout_with_completion(
        self,
        user_id: str,
        workout_data: Dict[str, Any],
        completion_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Save a voice-created workout with its completion atomically.

        Creates both a workout record and a linked completion record.
        Used when users create workouts via voice and want to log them immediately.

        Args:
            user_id: User ID
            workout_data: Voice workout structure (name, sport, intervals, etc.)
            completion_data: Timing and source info for completion

        Returns:
            Dict with workout_id, completion_id, and summary on success,
            or error details on failure.
        """
        ...

    def get_completed_workout_ids(
        self,
        user_id: str,
    ) -> set:
        """
        Get IDs of workouts that have been completed by the user.

        Used to filter out completed workouts from incoming/pending lists.

        Args:
            user_id: User ID

        Returns:
            Set of workout IDs that have completions
        """
        ...
