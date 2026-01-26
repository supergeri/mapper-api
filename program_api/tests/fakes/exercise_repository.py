"""
Fake exercise repository for testing.

Part of AMA-462: Implement ProgramGenerator Service

This fake implementation stores data in memory and provides
helper methods for test setup and verification.
"""

from typing import Dict, List, Optional


class FakeExerciseRepository:
    """
    In-memory fake implementation of ExerciseRepository.

    Provides the same interface as SupabaseExerciseRepository
    but stores data in dictionaries for fast, isolated testing.
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._exercises: Dict[str, Dict] = {}

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    def seed(self, exercises: List[Dict]) -> None:
        """
        Seed the repository with test data.

        Args:
            exercises: List of exercise dictionaries to add
        """
        for exercise in exercises:
            exercise_id = exercise.get("id", exercise.get("name", "").lower().replace(" ", "-"))
            self._exercises[exercise_id] = {**exercise, "id": exercise_id}

    def seed_default_exercises(self) -> None:
        """Seed with common exercises for testing."""
        exercises = [
            # Push exercises
            {
                "id": "barbell-bench-press",
                "name": "Barbell Bench Press",
                "primary_muscles": ["chest"],
                "secondary_muscles": ["anterior_deltoid", "triceps"],
                "equipment": ["barbell", "bench"],
                "category": "compound",
                "movement_pattern": "push",
                "supports_1rm": True,
            },
            {
                "id": "incline-dumbbell-press",
                "name": "Incline Dumbbell Press",
                "primary_muscles": ["chest", "anterior_deltoid"],
                "secondary_muscles": ["triceps"],
                "equipment": ["dumbbells", "bench"],
                "category": "compound",
                "movement_pattern": "push",
                "supports_1rm": True,
            },
            {
                "id": "overhead-press",
                "name": "Overhead Press",
                "primary_muscles": ["anterior_deltoid"],
                "secondary_muscles": ["triceps", "chest"],
                "equipment": ["barbell"],
                "category": "compound",
                "movement_pattern": "push",
                "supports_1rm": True,
            },
            {
                "id": "tricep-pushdown",
                "name": "Tricep Pushdown",
                "primary_muscles": ["triceps"],
                "secondary_muscles": [],
                "equipment": ["cables"],
                "category": "isolation",
                "movement_pattern": "push",
                "supports_1rm": False,
            },
            # Pull exercises
            {
                "id": "barbell-row",
                "name": "Barbell Row",
                "primary_muscles": ["lats", "rhomboids"],
                "secondary_muscles": ["biceps", "rear_deltoid"],
                "equipment": ["barbell"],
                "category": "compound",
                "movement_pattern": "pull",
                "supports_1rm": True,
            },
            {
                "id": "lat-pulldown",
                "name": "Lat Pulldown",
                "primary_muscles": ["lats"],
                "secondary_muscles": ["biceps"],
                "equipment": ["cables"],
                "category": "compound",
                "movement_pattern": "pull",
                "supports_1rm": False,
            },
            {
                "id": "dumbbell-curl",
                "name": "Dumbbell Curl",
                "primary_muscles": ["biceps"],
                "secondary_muscles": ["forearms"],
                "equipment": ["dumbbells"],
                "category": "isolation",
                "movement_pattern": "pull",
                "supports_1rm": False,
            },
            # Leg exercises
            {
                "id": "barbell-squat",
                "name": "Barbell Squat",
                "primary_muscles": ["quadriceps", "glutes"],
                "secondary_muscles": ["hamstrings", "core"],
                "equipment": ["barbell", "squat_rack"],
                "category": "compound",
                "movement_pattern": "squat",
                "supports_1rm": True,
            },
            {
                "id": "romanian-deadlift",
                "name": "Romanian Deadlift",
                "primary_muscles": ["hamstrings", "glutes"],
                "secondary_muscles": ["lower_back"],
                "equipment": ["barbell"],
                "category": "compound",
                "movement_pattern": "hinge",
                "supports_1rm": True,
            },
            {
                "id": "leg-press",
                "name": "Leg Press",
                "primary_muscles": ["quadriceps"],
                "secondary_muscles": ["glutes"],
                "equipment": ["leg_press_machine"],
                "category": "compound",
                "movement_pattern": "squat",
                "supports_1rm": False,
            },
            {
                "id": "leg-curl",
                "name": "Leg Curl",
                "primary_muscles": ["hamstrings"],
                "secondary_muscles": [],
                "equipment": ["leg_curl_machine"],
                "category": "isolation",
                "movement_pattern": "hinge",
                "supports_1rm": False,
            },
            {
                "id": "calf-raise",
                "name": "Calf Raise",
                "primary_muscles": ["calves"],
                "secondary_muscles": [],
                "equipment": ["dumbbells"],
                "category": "isolation",
                "movement_pattern": "push",
                "supports_1rm": False,
            },
            # Bodyweight exercises
            {
                "id": "push-up",
                "name": "Push-Up",
                "primary_muscles": ["chest"],
                "secondary_muscles": ["anterior_deltoid", "triceps"],
                "equipment": [],
                "category": "compound",
                "movement_pattern": "push",
                "supports_1rm": False,
            },
            {
                "id": "pull-up",
                "name": "Pull-Up",
                "primary_muscles": ["lats"],
                "secondary_muscles": ["biceps"],
                "equipment": ["pull_up_bar"],
                "category": "compound",
                "movement_pattern": "pull",
                "supports_1rm": False,
            },
        ]
        self.seed(exercises)

    def reset(self) -> None:
        """Clear all stored data."""
        self._exercises.clear()

    def get_all_ids(self) -> List[str]:
        """Get all exercise IDs (for test verification)."""
        return list(self._exercises.keys())

    def count(self) -> int:
        """Get count of stored exercises."""
        return len(self._exercises)

    # -------------------------------------------------------------------------
    # Repository Interface Implementation
    # -------------------------------------------------------------------------

    def get_by_id(self, exercise_id: str) -> Optional[Dict]:
        """Get an exercise by its ID."""
        return self._exercises.get(exercise_id)

    def get_by_name(self, name: str) -> Optional[Dict]:
        """Get an exercise by its exact name."""
        for ex in self._exercises.values():
            if ex.get("name") == name:
                return ex
        return None

    def search_by_alias(self, alias: str) -> List[Dict]:
        """Search exercises by alias."""
        matches = []
        for ex in self._exercises.values():
            aliases = ex.get("aliases", [])
            if alias in aliases:
                matches.append(ex)
        return matches

    def get_by_muscle_groups(
        self,
        primary_muscles: List[str],
        include_secondary: bool = False,
    ) -> List[Dict]:
        """Get exercises targeting specific muscle groups."""
        matches = []
        muscles_set = set(primary_muscles)

        for ex in self._exercises.values():
            ex_muscles = set(ex.get("primary_muscles", []))
            if ex_muscles & muscles_set:
                matches.append(ex)
            elif include_secondary:
                sec_muscles = set(ex.get("secondary_muscles", []))
                if sec_muscles & muscles_set:
                    matches.append(ex)

        return matches

    def get_by_equipment(
        self,
        equipment: List[str],
        require_all: bool = False,
    ) -> List[Dict]:
        """Get exercises that use the specified equipment."""
        matches = []
        equipment_set = set(equipment)

        for ex in self._exercises.values():
            ex_equipment = set(ex.get("equipment", []))

            # Bodyweight exercises (no equipment) match any equipment list
            if not ex_equipment:
                matches.append(ex)
                continue

            if require_all:
                if ex_equipment <= equipment_set:
                    matches.append(ex)
            else:
                if ex_equipment & equipment_set:
                    matches.append(ex)

        return matches

    def get_by_movement_pattern(self, pattern: str) -> List[Dict]:
        """Get exercises by movement pattern."""
        return [
            ex for ex in self._exercises.values()
            if ex.get("movement_pattern") == pattern
        ]

    def get_by_category(self, category: str) -> List[Dict]:
        """Get exercises by category."""
        return [
            ex for ex in self._exercises.values()
            if ex.get("category") == category
        ]

    def search(
        self,
        muscle_groups: Optional[List[str]] = None,
        equipment: Optional[List[str]] = None,
        movement_pattern: Optional[str] = None,
        category: Optional[str] = None,
        supports_1rm: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Search exercises with multiple filter criteria."""
        results = list(self._exercises.values())

        if muscle_groups:
            muscle_set = set(muscle_groups)
            results = [
                ex for ex in results
                if set(ex.get("primary_muscles", [])) & muscle_set
            ]

        if equipment:
            equipment_set = set(equipment)
            results = [
                ex for ex in results
                if not ex.get("equipment") or set(ex.get("equipment", [])) & equipment_set
            ]

        if movement_pattern:
            results = [
                ex for ex in results
                if ex.get("movement_pattern") == movement_pattern
            ]

        if category:
            results = [
                ex for ex in results
                if ex.get("category") == category
            ]

        if supports_1rm is not None:
            results = [
                ex for ex in results
                if ex.get("supports_1rm") == supports_1rm
            ]

        return results[:limit]

    def get_all(self, limit: int = 500) -> List[Dict]:
        """Get all exercises."""
        return list(self._exercises.values())[:limit]

    def get_for_workout_type(
        self,
        workout_type: str,
        equipment: List[str],
        limit: int = 30,
    ) -> List[Dict]:
        """Get exercises suitable for a specific workout type."""
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
                "muscles": ["chest", "lats", "anterior_deltoid", "triceps", "biceps"],
                "patterns": ["push", "pull"],
            },
            "lower": {
                "muscles": ["quadriceps", "hamstrings", "glutes", "calves"],
                "patterns": ["squat", "hinge"],
            },
            "full_body": {
                "muscles": ["chest", "lats", "quadriceps", "hamstrings", "glutes"],
                "patterns": ["push", "pull", "squat", "hinge"],
            },
        }

        mapping = workout_mappings.get(workout_type.lower(), workout_mappings["full_body"])
        muscles_set = set(mapping["muscles"])
        equipment_set = set(equipment) if equipment else set()

        results = []
        for ex in self._exercises.values():
            ex_muscles = set(ex.get("primary_muscles", []))
            ex_equipment = set(ex.get("equipment", []))

            # Must target relevant muscles
            if not (ex_muscles & muscles_set):
                continue

            # Bodyweight exercises always match
            if not ex_equipment:
                results.append(ex)
                continue

            # Must have ALL required equipment available
            if equipment_set and not (ex_equipment <= equipment_set):
                continue

            results.append(ex)

        return results[:limit]

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
        source = self._exercises.get(exercise_id)
        if not source:
            return []

        movement_pattern = source.get("movement_pattern")
        primary_muscles = set(source.get("primary_muscles", []))
        category = source.get("category")
        source_equipment = set(source.get("equipment", []))

        if not movement_pattern or not primary_muscles:
            return []

        # Find candidates with same movement pattern
        candidates = []
        for ex_id, ex in self._exercises.items():
            if ex_id == exercise_id:
                continue
            if ex.get("movement_pattern") != movement_pattern:
                continue
            candidates.append(ex)

        # Score candidates by similarity
        def score_exercise(ex: Dict) -> float:
            score = 0.0
            ex_muscles = set(ex.get("primary_muscles", []))

            # Muscle overlap (0-1)
            if primary_muscles:
                overlap = len(ex_muscles & primary_muscles) / len(primary_muscles)
                score += overlap * 0.6  # 60% weight for muscle overlap

            # Same category bonus
            if ex.get("category") == category:
                score += 0.3  # 30% weight for same category

            # Equipment overlap bonus
            ex_equipment = set(ex.get("equipment", []))
            if ex_equipment and source_equipment:
                equipment_overlap = len(ex_equipment & source_equipment) / max(
                    len(source_equipment), 1
                )
                score += equipment_overlap * 0.1  # 10% weight for equipment similarity

            return score

        # Score and sort candidates
        scored = [(ex, score_exercise(ex)) for ex in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        return [ex for ex, score in scored[:limit]]

    def validate_exercise_name(self, name: str) -> Optional[Dict]:
        """
        Check if exercise exists by name or alias (case-insensitive).

        Args:
            name: The exercise name or alias to validate

        Returns:
            Exercise dictionary if found, None otherwise
        """
        if not name or not name.strip():
            return None

        name_lower = name.strip().lower()

        # Try case-insensitive name match first
        for ex in self._exercises.values():
            if ex.get("name", "").lower() == name_lower:
                return ex

        # Fall back to alias search (case-insensitive)
        for ex in self._exercises.values():
            aliases = ex.get("aliases", [])
            if any(alias.lower() == name_lower for alias in aliases):
                return ex

        return None
