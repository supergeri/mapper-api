"""
Fake ExercisesRepository for testing.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

This module provides an in-memory fake implementation of ExercisesRepository
for unit testing without database access.
"""
from typing import Optional, List, Dict, Any


class FakeExercisesRepository:
    """
    In-memory fake implementation of ExercisesRepository for testing.

    Pre-populated with common exercises for testing matching behavior.
    """

    def __init__(self, exercises: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize with optional custom exercise list.

        Args:
            exercises: Custom exercise list, or None for default test data
        """
        if exercises is not None:
            self._exercises = exercises
        else:
            self._exercises = self._default_exercises()

    def _default_exercises(self) -> List[Dict[str, Any]]:
        """Return default test exercises."""
        return [
            {
                "id": "barbell-bench-press",
                "name": "Barbell Bench Press",
                "aliases": ["Bench Press", "Flat Bench Press", "BB Bench"],
                "primary_muscles": ["chest"],
                "secondary_muscles": ["anterior_deltoid", "triceps"],
                "equipment": ["barbell", "bench"],
                "default_weight_source": "barbell",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "push",
            },
            {
                "id": "dumbbell-bench-press",
                "name": "Dumbbell Bench Press",
                "aliases": ["DB Bench Press", "Flat DB Press"],
                "primary_muscles": ["chest"],
                "secondary_muscles": ["anterior_deltoid", "triceps"],
                "equipment": ["dumbbell", "bench"],
                "default_weight_source": "dumbbell",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "push",
            },
            {
                "id": "barbell-back-squat",
                "name": "Barbell Back Squat",
                "aliases": ["Back Squat", "Squat", "BB Squat"],
                "primary_muscles": ["quadriceps", "glutes"],
                "secondary_muscles": ["hamstrings", "core", "lower_back"],
                "equipment": ["barbell"],
                "default_weight_source": "barbell",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "squat",
            },
            {
                "id": "conventional-deadlift",
                "name": "Conventional Deadlift",
                "aliases": ["Deadlift", "Barbell Deadlift"],
                "primary_muscles": ["lower_back", "glutes", "hamstrings"],
                "secondary_muscles": ["traps", "forearms", "quadriceps"],
                "equipment": ["barbell"],
                "default_weight_source": "barbell",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "hinge",
            },
            {
                "id": "romanian-deadlift",
                "name": "Romanian Deadlift",
                "aliases": ["RDL", "Stiff Leg Deadlift"],
                "primary_muscles": ["hamstrings", "glutes"],
                "secondary_muscles": ["lower_back"],
                "equipment": ["barbell"],
                "default_weight_source": "barbell",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "hinge",
            },
            {
                "id": "pull-up",
                "name": "Pull-Up",
                "aliases": ["Pullup", "Pull Up", "Chin Up"],
                "primary_muscles": ["lats"],
                "secondary_muscles": ["biceps", "rhomboids", "posterior_deltoid"],
                "equipment": ["pull_up_bar", "bodyweight"],
                "default_weight_source": "bodyweight",
                "supports_1rm": False,
                "one_rm_formula": None,
                "category": "compound",
                "movement_pattern": "pull",
            },
            {
                "id": "push-up",
                "name": "Push-Up",
                "aliases": ["Pushup", "Push Up", "Press Up"],
                "primary_muscles": ["chest"],
                "secondary_muscles": ["anterior_deltoid", "triceps", "core"],
                "equipment": ["bodyweight"],
                "default_weight_source": "bodyweight",
                "supports_1rm": False,
                "one_rm_formula": None,
                "category": "compound",
                "movement_pattern": "push",
            },
            {
                "id": "dumbbell-curl",
                "name": "Dumbbell Curl",
                "aliases": ["DB Curl", "Bicep Curl"],
                "primary_muscles": ["biceps"],
                "secondary_muscles": ["forearms"],
                "equipment": ["dumbbell"],
                "default_weight_source": "dumbbell",
                "supports_1rm": False,
                "one_rm_formula": None,
                "category": "isolation",
                "movement_pattern": "pull",
            },
            {
                "id": "lat-pulldown",
                "name": "Lat Pulldown",
                "aliases": ["Cable Pulldown", "Wide Grip Pulldown"],
                "primary_muscles": ["lats"],
                "secondary_muscles": ["biceps", "rhomboids"],
                "equipment": ["cable"],
                "default_weight_source": "cable",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "pull",
            },
            {
                "id": "leg-press",
                "name": "Leg Press",
                "aliases": ["Machine Leg Press", "45 Degree Leg Press"],
                "primary_muscles": ["quadriceps", "glutes"],
                "secondary_muscles": ["hamstrings"],
                "equipment": ["machine"],
                "default_weight_source": "machine",
                "supports_1rm": True,
                "one_rm_formula": "brzycki",
                "category": "compound",
                "movement_pattern": "squat",
            },
        ]

    def get_all(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get all exercises."""
        return self._exercises[:limit]

    def get_by_id(self, exercise_id: str) -> Optional[Dict[str, Any]]:
        """Get exercise by ID."""
        for ex in self._exercises:
            if ex["id"] == exercise_id:
                return ex
        return None

    def find_by_exact_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find by exact name (case-insensitive)."""
        name_lower = name.lower()
        for ex in self._exercises:
            if ex["name"].lower() == name_lower:
                return ex
        return None

    def find_by_alias(self, alias: str) -> Optional[Dict[str, Any]]:
        """Find by alias (case-sensitive, as Supabase contains is)."""
        for ex in self._exercises:
            if alias in ex.get("aliases", []):
                return ex
        return None

    def search_by_name_pattern(
        self, pattern: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search by name pattern (simple substring match)."""
        # Remove SQL wildcards for substring match
        search_term = pattern.replace("%", "").lower()
        results = []
        for ex in self._exercises:
            if search_term in ex["name"].lower():
                results.append(ex)
                if len(results) >= limit:
                    break
        return results

    def find_by_muscle_group(
        self, muscle: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find by primary muscle group."""
        results = []
        for ex in self._exercises:
            if muscle in ex.get("primary_muscles", []):
                results.append(ex)
                if len(results) >= limit:
                    break
        return results

    def find_by_equipment(
        self, equipment: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find by equipment type."""
        results = []
        for ex in self._exercises:
            if equipment in ex.get("equipment", []):
                results.append(ex)
                if len(results) >= limit:
                    break
        return results

    def find_compound_exercises(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Find compound exercises."""
        results = []
        for ex in self._exercises:
            if ex.get("category") == "compound":
                results.append(ex)
                if len(results) >= limit:
                    break
        return results

    def find_exercises_supporting_1rm(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Find exercises supporting 1RM."""
        results = []
        for ex in self._exercises:
            if ex.get("supports_1rm"):
                results.append(ex)
                if len(results) >= limit:
                    break
        return results
