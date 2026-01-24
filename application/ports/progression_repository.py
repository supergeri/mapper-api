"""
Progression Repository Interface (Port).

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

This module defines the abstract interface for querying exercise progression data.
Used by the ProgressionService for history, 1RM tracking, and volume analytics.
"""
from typing import Protocol, Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import date


@dataclass
class SetPerformance:
    """A single set's performance data from a completed workout."""
    set_number: int
    weight: Optional[float] = None
    weight_unit: str = "lbs"
    reps_completed: Optional[int] = None
    reps_planned: Optional[int] = None
    status: str = "completed"  # completed, skipped


@dataclass
class ExerciseSession:
    """A single session where an exercise was performed."""
    completion_id: str
    workout_date: str  # ISO format
    workout_name: Optional[str] = None
    exercise_name: str = ""
    canonical_exercise_id: Optional[str] = None
    sets: List[SetPerformance] = None

    def __post_init__(self):
        if self.sets is None:
            self.sets = []


@dataclass
class PersonalRecord:
    """A personal record (PR) for an exercise."""
    exercise_id: str
    exercise_name: str
    record_type: str  # "1rm", "max_weight", "max_reps", "max_volume"
    value: float
    unit: str  # "lbs", "kg", "reps"
    achieved_at: str  # ISO format
    completion_id: str
    details: Optional[Dict[str, Any]] = None  # e.g., weight/reps used to calculate 1RM


@dataclass
class LastWeightResult:
    """The last weight used for an exercise."""
    exercise_id: str
    exercise_name: str
    weight: float
    weight_unit: str
    reps_completed: int
    workout_date: str
    completion_id: str


@dataclass
class VolumeDataPoint:
    """Volume data for a specific period."""
    period: str  # ISO date or period label
    muscle_group: str
    total_volume: float  # weight * reps
    total_sets: int
    total_reps: int


class ProgressionRepository(Protocol):
    """
    Abstract interface for exercise progression data access.

    This protocol defines the contract for querying workout completion data
    to extract progression metrics like exercise history, 1RM, and volume.
    """

    def get_exercise_history(
        self,
        user_id: str,
        exercise_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get the history of a specific exercise for a user.

        Returns sessions where the exercise was performed, ordered by date descending.
        Each session includes all sets with weight, reps, and status.

        Args:
            user_id: User ID (Clerk user ID)
            exercise_id: Canonical exercise ID (slug)
            limit: Maximum sessions to return
            offset: Sessions to skip for pagination

        Returns:
            Dict with:
                - "sessions": List of ExerciseSession data (as dicts)
                - "total": Total number of sessions
                - "exercise": Exercise metadata
        """
        ...

    def get_all_exercise_sessions(
        self,
        user_id: str,
        exercise_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all sessions for an exercise (for calculating records).

        Returns all sessions without pagination, for use in calculating
        personal records like 1RM across all history.

        Args:
            user_id: User ID
            exercise_id: Canonical exercise ID

        Returns:
            List of session dicts with sets data
        """
        ...

    def get_last_weight_used(
        self,
        user_id: str,
        exercise_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the last weight used for an exercise.

        Returns the most recent completed set with a weight value.
        Used for the "Use Last Weight" feature in companion apps.

        Args:
            user_id: User ID
            exercise_id: Canonical exercise ID

        Returns:
            Dict with weight, unit, reps, date, and completion_id,
            or None if no weight history exists
        """
        ...

    def get_volume_by_muscle_group(
        self,
        user_id: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "daily",  # "daily", "weekly", "monthly"
        muscle_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Get training volume aggregated by muscle group.

        Calculates total volume (weight * reps) for each muscle group
        over the specified time period.

        Args:
            user_id: User ID
            start_date: Start of date range (defaults to 30 days ago)
            end_date: End of date range (defaults to today)
            granularity: How to group data ("daily", "weekly", "monthly")
            muscle_groups: Filter to specific muscle groups, or None for all

        Returns:
            Dict with:
                - "data": List of VolumeDataPoint data (as dicts)
                - "summary": Aggregate totals by muscle group
                - "period": Date range info
        """
        ...

    def get_exercises_with_history(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get a list of exercises that the user has history for.

        Returns canonical exercise IDs and names where the user has
        at least one completed session with weight data.

        Args:
            user_id: User ID
            limit: Maximum exercises to return

        Returns:
            List of exercise dicts with id, name, and session count
        """
        ...
