"""
Mapping Repository Interface (Port).

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

This module defines the abstract interface for exercise mapping persistence.
Handles user-defined mappings and global/crowd-sourced popularity data.
"""
from typing import Protocol, Optional, List, Dict, Any, Tuple


class UserMappingRepository(Protocol):
    """
    Abstract interface for user-defined exercise mapping persistence.

    User mappings store personal exercise_name -> garmin_name mappings
    that override the default fuzzy matching.
    """

    def add(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> Dict[str, Any]:
        """
        Add or update a user-defined mapping.

        Args:
            exercise_name: Original exercise name from workout source
            garmin_name: Target Garmin exercise name

        Returns:
            Dict with the saved mapping details
        """
        ...

    def remove(
        self,
        exercise_name: str,
    ) -> bool:
        """
        Remove a user-defined mapping.

        Args:
            exercise_name: Exercise name to remove mapping for

        Returns:
            True if mapping was removed, False if not found
        """
        ...

    def get(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """
        Get the mapped Garmin name for an exercise.

        Args:
            exercise_name: Exercise name to look up

        Returns:
            Garmin name if mapping exists, None otherwise
        """
        ...

    def get_all(self) -> Dict[str, str]:
        """
        Get all user-defined mappings.

        Returns:
            Dict of exercise_name -> garmin_name mappings
        """
        ...

    def clear_all(self) -> None:
        """
        Clear all user-defined mappings.
        """
        ...


class GlobalMappingRepository(Protocol):
    """
    Abstract interface for global/crowd-sourced mapping popularity.

    Tracks which Garmin exercises users choose for ambiguous exercise names,
    enabling crowd-sourced suggestion improvements.
    """

    def record_choice(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> None:
        """
        Record a user's mapping choice for global popularity tracking.

        Increments the popularity count for this exercise_name -> garmin_name pair.

        Args:
            exercise_name: Original exercise name
            garmin_name: Chosen Garmin exercise name
        """
        ...

    def get_popular(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Tuple[str, int]]:
        """
        Get popular Garmin mappings for an exercise name.

        Args:
            exercise_name: Exercise name to look up
            limit: Maximum number of results

        Returns:
            List of (garmin_name, count) tuples sorted by popularity
        """
        ...

    def get_stats(self) -> Dict[str, Any]:
        """
        Get global popularity statistics.

        Returns:
            Dict with total_exercises, total_mappings, most_mapped, etc.
        """
        ...


class ExerciseMatchRepository(Protocol):
    """
    Abstract interface for exercise matching operations.

    Provides fuzzy matching against the Garmin exercise database.
    Note: This is primarily a read-only service, but defined as a repository
    for consistency with the ports pattern.
    """

    def find_match(
        self,
        exercise_name: str,
        *,
        threshold: float = 0.3,
    ) -> Tuple[Optional[str], float]:
        """
        Find the best matching Garmin exercise for a name.

        Args:
            exercise_name: Exercise name to match
            threshold: Minimum confidence threshold (0-1)

        Returns:
            Tuple of (matched_name, confidence) or (None, 0) if no match
        """
        ...

    def get_suggestions(
        self,
        exercise_name: str,
        *,
        limit: int = 5,
        score_cutoff: float = 0.3,
    ) -> List[Tuple[str, float]]:
        """
        Get suggested Garmin exercises for a name.

        Args:
            exercise_name: Exercise name to get suggestions for
            limit: Maximum number of suggestions
            score_cutoff: Minimum confidence score

        Returns:
            List of (garmin_name, confidence) tuples sorted by confidence
        """
        ...

    def find_similar(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find similar exercises to the given name.

        Args:
            exercise_name: Exercise name to find similar exercises for
            limit: Maximum number of results

        Returns:
            List of similar exercise dicts
        """
        ...

    def find_by_type(
        self,
        exercise_name: str,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Find exercises of the same type (e.g., all squats).

        Args:
            exercise_name: Exercise to categorize and find similar types
            limit: Maximum number of results

        Returns:
            List of exercise dicts of the same type
        """
        ...

    def categorize(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """
        Get the category/type of an exercise.

        Args:
            exercise_name: Exercise name to categorize

        Returns:
            Category string or None if unknown
        """
        ...
