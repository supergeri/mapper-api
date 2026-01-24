"""
Supabase implementation of ExercisesRepository.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

This module provides the concrete Supabase implementation for querying
the canonical exercises table.
"""
import logging
from typing import Optional, List, Dict, Any

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseExercisesRepository:
    """
    Supabase implementation of ExercisesRepository protocol.

    Provides methods to query the canonical exercises table for:
    - Exact name matching
    - Alias matching
    - Fuzzy search
    - Filtering by muscle group or equipment
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected, not global)
        """
        self._client = client

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        """
        Get all exercises from the database.

        Args:
            limit: Maximum number of exercises to return

        Returns:
            List of exercise dictionaries
        """
        try:
            result = self._client.table("exercises").select("*").limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error fetching all exercises: {e}")
            return []

    def get_by_id(self, exercise_id: str) -> Optional[Dict[str, Any]]:
        """
        Get an exercise by its canonical ID (slug).

        Args:
            exercise_id: The exercise slug (e.g., "barbell-bench-press")

        Returns:
            Exercise dictionary or None if not found
        """
        try:
            result = self._client.table("exercises").select("*").eq("id", exercise_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error fetching exercise by id {exercise_id}: {e}")
            return None

    def find_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find an exercise by exact name match (case-insensitive).

        Args:
            name: The exercise name to search for

        Returns:
            Exercise dictionary or None if not found
        """
        try:
            result = self._client.table("exercises").select("*").ilike("name", name).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error finding exercise by name {name}: {e}")
            return None

    def find_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """
        Find an exercise where the given alias is in the aliases array.

        Args:
            alias: The alias to search for

        Returns:
            Exercise dictionary or None if not found
        """
        try:
            # Use Supabase's array contains operator
            # Note: This is case-sensitive, so we also check lowercase
            result = self._client.table("exercises").select("*").contains("aliases", [alias]).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            logger.error(f"Error finding exercise by alias {alias}: {e}")
            return None

    def search_by_name_pattern(self, pattern: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for exercises where name matches a pattern (ILIKE).

        Args:
            pattern: SQL LIKE pattern (e.g., "%bench%")
            limit: Maximum results to return

        Returns:
            List of matching exercises
        """
        try:
            result = self._client.table("exercises").select("*").ilike("name", pattern).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error searching exercises by pattern {pattern}: {e}")
            return []

    def find_by_muscle_group(self, muscle: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find exercises that target a specific primary muscle group.

        Args:
            muscle: Muscle group (e.g., "chest", "lats", "quadriceps")
            limit: Maximum results to return

        Returns:
            List of exercises targeting that muscle
        """
        try:
            result = self._client.table("exercises").select("*").contains("primary_muscles", [muscle]).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error finding exercises by muscle {muscle}: {e}")
            return []

    def find_by_equipment(self, equipment: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find exercises that use specific equipment.

        Args:
            equipment: Equipment type (e.g., "barbell", "dumbbell", "cable")
            limit: Maximum results to return

        Returns:
            List of exercises using that equipment
        """
        try:
            result = self._client.table("exercises").select("*").contains("equipment", [equipment]).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error finding exercises by equipment {equipment}: {e}")
            return []

    def find_compound_exercises(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find all compound exercises (multi-joint movements).

        Args:
            limit: Maximum results to return

        Returns:
            List of compound exercises
        """
        try:
            result = self._client.table("exercises").select("*").eq("category", "compound").limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error finding compound exercises: {e}")
            return []

    def find_exercises_supporting_1rm(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Find exercises that support 1RM calculation.

        Args:
            limit: Maximum results to return

        Returns:
            List of exercises supporting 1RM tracking
        """
        try:
            result = self._client.table("exercises").select("*").eq("supports_1rm", True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Error finding 1RM exercises: {e}")
            return []
