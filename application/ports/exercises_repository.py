"""
Exercises Repository Interface (Port).

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

This module defines the abstract interface for querying the canonical exercises table.
Implementations may use Supabase or other backends.
"""
from typing import Protocol, Optional, List, Dict, Any


class ExercisesRepository(Protocol):
    """
    Abstract interface for querying canonical exercises.

    This protocol defines the contract for reading from the exercises table.
    Used by the ExerciseMatchingService for name matching operations.
    """

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get all exercises from the database.

        Args:
            limit: Maximum number of exercises to return

        Returns:
            List of exercise dictionaries
        """
        ...

    def get_by_id(self, exercise_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an exercise by its canonical ID (slug).

        Args:
            exercise_id: The exercise slug (e.g., "barbell-bench-press")

        Returns:
            Exercise dictionary or None if not found
        """
        ...

    def find_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find an exercise by exact name match (case-insensitive).

        Args:
            name: The exercise name to search for

        Returns:
            Exercise dictionary or None if not found
        """
        ...

    def find_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Find an exercise where the given alias is in the aliases array.

        Args:
            alias: The alias to search for

        Returns:
            Exercise dictionary or None if not found
        """
        ...

    def search_by_name_pattern(
        self, pattern: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search for exercises where name matches a pattern (ILIKE).

        Args:
            pattern: SQL LIKE pattern (e.g., "%bench%")
            limit: Maximum results to return

        Returns:
            List of matching exercises
        """
        ...

    def find_by_muscle_group(
        self, muscle: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find exercises that target a specific primary muscle group.

        Args:
            muscle: Muscle group (e.g., "chest", "lats", "quadriceps")
            limit: Maximum results to return

        Returns:
            List of exercises targeting that muscle
        """
        ...

    def find_by_equipment(
        self, equipment: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Find exercises that use specific equipment.

        Args:
            equipment: Equipment type (e.g., "barbell", "dumbbell", "cable")
            limit: Maximum results to return

        Returns:
            List of exercises using that equipment
        """
        ...

    def find_compound_exercises(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find all compound exercises (multi-joint movements).

        Args:
            limit: Maximum results to return

        Returns:
            List of compound exercises
        """
        ...

    def find_exercises_supporting_1rm(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find exercises that support 1RM calculation.

        Args:
            limit: Maximum results to return

        Returns:
            List of exercises supporting 1RM tracking
        """
        ...
