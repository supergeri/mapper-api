"""
Supabase implementation of ExerciseRepository.

Part of AMA-462: Implement ProgramGenerator Service

This implementation uses the Supabase Python client to interact with
the exercises table defined in AMA-299.
"""

from typing import Dict, List, Optional

from supabase import Client


class SupabaseExerciseRepository:
    """
    Supabase-backed exercise repository implementation.

    Queries against the exercises table which stores canonical exercise
    definitions with muscle groups, equipment, and metadata.
    """

    def __init__(self, client: Client):
        """
        Initialize repository with Supabase client.

        Args:
            client: Authenticated Supabase client
        """
        self._client = client

    def get_by_id(self, exercise_id: str) -> Optional[Dict]:
        """
        Get an exercise by its ID (slug).

        Args:
            exercise_id: The exercise slug identifier

        Returns:
            Exercise dictionary if found, None otherwise
        """
        response = (
            self._client.table("exercises")
            .select("*")
            .eq("id", exercise_id)
            .single()
            .execute()
        )
        return response.data if response.data else None

    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        Get an exercise by its exact name.

        Args:
            name: The exercise name

        Returns:
            Exercise dictionary if found, None otherwise
        """
        response = (
            self._client.table("exercises")
            .select("*")
            .eq("name", name)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    def search_by_alias(self, alias: str) -> List[Dict]:
        """
        Search exercises by alias.

        Args:
            alias: Alias to search for

        Returns:
            List of matching exercise dictionaries
        """
        # Use Supabase's contains operator for array search
        response = (
            self._client.table("exercises")
            .select("*")
            .contains("aliases", [alias])
            .execute()
        )
        return response.data

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
        # Use overlaps for array intersection (exercises that target ANY of the muscles)
        response = (
            self._client.table("exercises")
            .select("*")
            .overlaps("primary_muscles", primary_muscles)
            .execute()
        )

        if include_secondary:
            # Also get exercises where secondary muscles overlap
            secondary_response = (
                self._client.table("exercises")
                .select("*")
                .overlaps("secondary_muscles", primary_muscles)
                .execute()
            )
            # Merge and deduplicate
            seen_ids = {ex["id"] for ex in response.data}
            for ex in secondary_response.data:
                if ex["id"] not in seen_ids:
                    response.data.append(ex)

        return response.data

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
        if require_all:
            # Use contains for strict match
            response = (
                self._client.table("exercises")
                .select("*")
                .contains("equipment", equipment)
                .execute()
            )
        else:
            # Use overlaps for any match
            response = (
                self._client.table("exercises")
                .select("*")
                .overlaps("equipment", equipment)
                .execute()
            )
        return response.data

    def get_by_movement_pattern(self, pattern: str) -> List[Dict]:
        """
        Get exercises by movement pattern.

        Args:
            pattern: Movement pattern (push, pull, squat, hinge, etc.)

        Returns:
            List of matching exercise dictionaries
        """
        response = (
            self._client.table("exercises")
            .select("*")
            .eq("movement_pattern", pattern)
            .execute()
        )
        return response.data

    def get_by_category(self, category: str) -> List[Dict]:
        """
        Get exercises by category.

        Args:
            category: Exercise category (compound, isolation, cardio)

        Returns:
            List of matching exercise dictionaries
        """
        response = (
            self._client.table("exercises")
            .select("*")
            .eq("category", category)
            .execute()
        )
        return response.data

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
        query = self._client.table("exercises").select("*")

        if muscle_groups:
            query = query.overlaps("primary_muscles", muscle_groups)

        if equipment:
            query = query.overlaps("equipment", equipment)

        if movement_pattern:
            query = query.eq("movement_pattern", movement_pattern)

        if category:
            query = query.eq("category", category)

        if supports_1rm is not None:
            query = query.eq("supports_1rm", supports_1rm)

        query = query.limit(limit)

        response = query.execute()
        return response.data

    def get_all(self, limit: int = 500) -> List[Dict]:
        """
        Get all exercises.

        Args:
            limit: Maximum number of results

        Returns:
            List of all exercise dictionaries
        """
        response = (
            self._client.table("exercises")
            .select("*")
            .limit(limit)
            .execute()
        )
        return response.data

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
            workout_type: Type of workout (push, pull, legs, upper, lower, full)
            equipment: Available equipment
            limit: Maximum number of results

        Returns:
            List of matching exercise dictionaries
        """
        # Map workout types to muscle groups and patterns
        workout_mappings = {
            "push": {
                "muscles": ["chest", "anterior_deltoid", "triceps"],
                "patterns": ["push"],
            },
            "pull": {
                "muscles": ["lats", "rhomboids", "biceps", "rear_deltoid"],
                "patterns": ["pull"],
            },
            "legs": {
                "muscles": ["quadriceps", "hamstrings", "glutes", "calves"],
                "patterns": ["squat", "hinge"],
            },
            "upper": {
                "muscles": [
                    "chest",
                    "lats",
                    "anterior_deltoid",
                    "rear_deltoid",
                    "triceps",
                    "biceps",
                ],
                "patterns": ["push", "pull"],
            },
            "lower": {
                "muscles": ["quadriceps", "hamstrings", "glutes", "calves", "hip_flexors"],
                "patterns": ["squat", "hinge"],
            },
            "full_body": {
                "muscles": [
                    "chest",
                    "lats",
                    "quadriceps",
                    "hamstrings",
                    "glutes",
                    "anterior_deltoid",
                ],
                "patterns": ["push", "pull", "squat", "hinge"],
            },
        }

        mapping = workout_mappings.get(workout_type.lower(), workout_mappings["full_body"])

        # Build query with equipment filter and muscle group filter
        query = (
            self._client.table("exercises")
            .select("*")
            .overlaps("primary_muscles", mapping["muscles"])
        )

        if equipment:
            query = query.overlaps("equipment", equipment)

        query = query.limit(limit)

        response = query.execute()
        return response.data
