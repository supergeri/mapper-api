"""
Exercise repository port (interface).

Part of AMA-462: Implement ProgramGenerator Service

This Protocol defines the contract for exercise data access.
Infrastructure implementations (e.g., Supabase) must satisfy this interface.
"""

from typing import Dict, List, Optional, Protocol


class ExerciseRepository(Protocol):
    """
    Repository interface for exercise data access.

    Exercises are read-only reference data used during program generation
    to select appropriate exercises based on equipment, muscle groups, etc.
    """

    def get_by_id(self, exercise_id: str) -> Optional[Dict]:
        """
        Get an exercise by its ID (slug).

        Args:
            exercise_id: The exercise slug identifier

        Returns:
            Exercise dictionary if found, None otherwise
        """
        ...

    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        Get an exercise by its exact name.

        Args:
            name: The exercise name

        Returns:
            Exercise dictionary if found, None otherwise
        """
        ...

    def search_by_alias(self, alias: str) -> List[Dict]:
        """
        Search exercises by alias.

        Args:
            alias: Alias to search for

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_by_muscle_groups(
        self,
        primary_muscles: List[str],
        include_secondary: bool = False,
    ) -> List[Dict]:
        """
        Get exercises targeting specific muscle groups.

        Args:
            primary_muscles: List of primary muscle groups to target
            include_secondary: If True, also match secondary muscles

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_by_equipment(
        self,
        equipment: List[str],
        require_all: bool = False,
    ) -> List[Dict]:
        """
        Get exercises that use the specified equipment.

        Args:
            equipment: List of available equipment
            require_all: If True, exercise must use all equipment

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_by_movement_pattern(self, pattern: str) -> List[Dict]:
        """
        Get exercises by movement pattern.

        Args:
            pattern: Movement pattern (push, pull, squat, hinge, etc.)

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_by_category(self, category: str) -> List[Dict]:
        """
        Get exercises by category.

        Args:
            category: Exercise category (compound, isolation, cardio)

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def search(
        self,
        muscle_groups: Optional[List[str]] = None,
        equipment: Optional[List[str]] = None,
        movement_pattern: Optional[str] = None,
        category: Optional[str] = None,
        supports_1rm: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Search exercises with multiple filter criteria.

        Args:
            muscle_groups: Filter by primary muscle groups
            equipment: Filter by available equipment
            movement_pattern: Filter by movement pattern
            category: Filter by category
            supports_1rm: Filter by 1RM support
            limit: Maximum number of results

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_all(self, limit: int = 500) -> List[Dict]:
        """
        Get all exercises.

        Args:
            limit: Maximum number of results

        Returns:
            List of all exercise dictionaries
        """
        ...

    def get_for_workout_type(
        self,
        workout_type: str,
        equipment: List[str],
        limit: int = 30,
    ) -> List[Dict]:
        """
        Get exercises suitable for a specific workout type.

        This is a convenience method that maps workout types to muscle groups
        and movement patterns.

        Args:
            workout_type: Type of workout (push, pull, legs, upper, lower, full_body)
            equipment: Available equipment to filter by
            limit: Maximum number of results

        Returns:
            List of matching exercise dictionaries
        """
        ...

    def get_similar_exercises(
        self,
        exercise_id: str,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Find similar/alternative exercises based on movement pattern and muscles.

        Args:
            exercise_id: The ID of the exercise to find alternatives for
            limit: Maximum number of similar exercises to return

        Returns:
            List of similar exercise dictionaries, scored by similarity
        """
        ...

    def validate_exercise_name(self, name: str) -> Optional[Dict]:
        """
        Check if exercise exists by name or alias (case-insensitive).

        Args:
            name: The exercise name or alias to validate

        Returns:
            Exercise dictionary if found, None otherwise
        """
        ...
