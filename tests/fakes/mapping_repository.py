"""
Fake Mapping Repositories for testing.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

This module provides in-memory implementations of UserMappingRepository,
GlobalMappingRepository, and ExerciseMatchRepository for fast, isolated testing.
"""
from typing import Optional, List, Dict, Any, Tuple
import copy


class FakeUserMappingRepository:
    """
    In-memory fake implementation of UserMappingRepository for testing.

    Stores user-defined exercise mappings in a dict.

    Usage:
        repo = FakeUserMappingRepository(user_id="user1")
        repo.seed({"bench press": "Barbell Bench Press"})
        repo.add("squat", "Barbell Back Squat")
    """

    def __init__(self, user_id: str):
        """Initialize with user ID and empty storage."""
        self._user_id = user_id
        self._mappings: Dict[str, str] = {}

    def reset(self) -> None:
        """Clear all stored mappings."""
        self._mappings.clear()

    def seed(self, mappings: Dict[str, str]) -> None:
        """
        Seed the repository with test data.

        Args:
            mappings: Dict of exercise_name -> garmin_name mappings
        """
        self._mappings.update(mappings)

    # =========================================================================
    # UserMappingRepository Protocol Methods
    # =========================================================================

    def add(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> Dict[str, Any]:
        """Add or update a user-defined mapping."""
        normalized = exercise_name.lower().strip()
        self._mappings[normalized] = garmin_name
        return {
            "exercise_name": normalized,
            "garmin_name": garmin_name,
            "user_id": self._user_id,
        }

    def remove(
        self,
        exercise_name: str,
    ) -> bool:
        """Remove a user-defined mapping."""
        normalized = exercise_name.lower().strip()
        if normalized in self._mappings:
            del self._mappings[normalized]
            return True
        return False

    def get(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """Get the mapped Garmin name for an exercise."""
        normalized = exercise_name.lower().strip()
        return self._mappings.get(normalized)

    def get_all(self) -> Dict[str, str]:
        """Get all user-defined mappings."""
        return copy.deepcopy(self._mappings)

    def clear_all(self) -> None:
        """Clear all user-defined mappings."""
        self._mappings.clear()


class FakeGlobalMappingRepository:
    """
    In-memory fake implementation of GlobalMappingRepository for testing.

    Stores global/crowd-sourced mapping popularity in a nested dict.

    Usage:
        repo = FakeGlobalMappingRepository()
        repo.seed({"bench press": {"Barbell Bench Press": 100, "Dumbbell Bench Press": 25}})
        repo.record_choice("squat", "Barbell Back Squat")
    """

    def __init__(self):
        """Initialize with empty storage."""
        # {normalized_exercise: {garmin_name: count}}
        self._popularity: Dict[str, Dict[str, int]] = {}

    def reset(self) -> None:
        """Clear all stored popularity data."""
        self._popularity.clear()

    def seed(self, popularity: Dict[str, Dict[str, int]]) -> None:
        """
        Seed the repository with test data.

        Args:
            popularity: Dict of {exercise_name: {garmin_name: count}}
        """
        for exercise, choices in popularity.items():
            normalized = exercise.lower().strip()
            self._popularity[normalized] = copy.deepcopy(choices)

    # =========================================================================
    # GlobalMappingRepository Protocol Methods
    # =========================================================================

    def record_choice(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> None:
        """Record a user's mapping choice for global popularity tracking."""
        normalized = exercise_name.lower().strip()
        if normalized not in self._popularity:
            self._popularity[normalized] = {}
        if garmin_name not in self._popularity[normalized]:
            self._popularity[normalized][garmin_name] = 0
        self._popularity[normalized][garmin_name] += 1

    def get_popular(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Tuple[str, int]]:
        """Get popular Garmin mappings for an exercise name."""
        normalized = exercise_name.lower().strip()
        if normalized not in self._popularity:
            return []

        # Sort by count (descending), then by name (ascending)
        popular = list(self._popularity[normalized].items())
        popular.sort(key=lambda x: (-x[1], x[0]))
        return popular[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get global popularity statistics."""
        total_choices = sum(
            sum(counts.values())
            for counts in self._popularity.values()
        )
        unique_exercises = len(self._popularity)
        unique_mappings = sum(len(counts) for counts in self._popularity.values())

        # Find most popular
        all_flat = []
        for exercise, choices in self._popularity.items():
            for garmin_name, count in choices.items():
                all_flat.append((exercise, garmin_name, count))

        most_popular = sorted(all_flat, key=lambda x: -x[2])[:10]

        return {
            "total_choices": total_choices,
            "unique_exercises": unique_exercises,
            "unique_mappings": unique_mappings,
            "most_popular": [
                {"exercise": ex, "garmin_name": garmin, "count": count}
                for ex, garmin, count in most_popular
            ],
        }


class FakeExerciseMatchRepository:
    """
    In-memory fake implementation of ExerciseMatchRepository for testing.

    Provides configurable fuzzy matching for testing exercise mapping scenarios.

    Usage:
        repo = FakeExerciseMatchRepository()
        repo.seed_matches({"bench press": ("Barbell Bench Press", 0.95)})
        result = repo.find_match("bench press")
    """

    # Exercise categories for find_by_type and categorize
    _CATEGORIES = {
        "squat": ["squat", "goblet", "lunge"],
        "press": ["press", "bench", "shoulder"],
        "pull": ["pull", "row", "lat"],
        "push_up": ["push up", "push-up", "pushup"],
        "deadlift": ["deadlift", "dead lift"],
        "curl": ["curl", "bicep"],
    }

    def __init__(self):
        """Initialize with empty matches."""
        # {normalized_exercise: (garmin_name, confidence)}
        self._matches: Dict[str, Tuple[str, float]] = {}
        # {normalized_exercise: [(garmin_name, confidence), ...]}
        self._suggestions: Dict[str, List[Tuple[str, float]]] = {}
        # Garmin exercise database for find_similar/find_by_type
        self._garmin_exercises: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Clear all configured matches."""
        self._matches.clear()
        self._suggestions.clear()
        self._garmin_exercises.clear()

    def seed_matches(self, matches: Dict[str, Tuple[str, float]]) -> None:
        """
        Seed direct matches for testing.

        Args:
            matches: Dict of {exercise_name: (garmin_name, confidence)}
        """
        for exercise, (garmin_name, confidence) in matches.items():
            normalized = exercise.lower().strip()
            self._matches[normalized] = (garmin_name, confidence)

    def seed_suggestions(self, suggestions: Dict[str, List[Tuple[str, float]]]) -> None:
        """
        Seed suggestions for testing.

        Args:
            suggestions: Dict of {exercise_name: [(garmin_name, confidence), ...]}
        """
        for exercise, suggestion_list in suggestions.items():
            normalized = exercise.lower().strip()
            self._suggestions[normalized] = list(suggestion_list)

    def seed_garmin_exercises(self, exercises: List[Dict[str, Any]]) -> None:
        """
        Seed Garmin exercise database for find_similar/find_by_type.

        Args:
            exercises: List of exercise dicts with at least "name" key
        """
        self._garmin_exercises = list(exercises)

    # =========================================================================
    # ExerciseMatchRepository Protocol Methods
    # =========================================================================

    def find_match(
        self,
        exercise_name: str,
        *,
        threshold: float = 0.3,
    ) -> Tuple[Optional[str], float]:
        """Find the best matching Garmin exercise for a name."""
        normalized = exercise_name.lower().strip()
        if normalized in self._matches:
            garmin_name, confidence = self._matches[normalized]
            if confidence >= threshold:
                return (garmin_name, confidence)
        return (None, 0.0)

    def get_suggestions(
        self,
        exercise_name: str,
        *,
        limit: int = 5,
        score_cutoff: float = 0.3,
    ) -> List[Tuple[str, float]]:
        """Get suggested Garmin exercises for a name."""
        normalized = exercise_name.lower().strip()

        # Check seeded suggestions first
        if normalized in self._suggestions:
            suggestions = [
                s for s in self._suggestions[normalized]
                if s[1] >= score_cutoff
            ]
            return suggestions[:limit]

        # Fall back to single match as suggestion
        if normalized in self._matches:
            garmin_name, confidence = self._matches[normalized]
            if confidence >= score_cutoff:
                return [(garmin_name, confidence)]

        return []

    def find_similar(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find similar exercises to the given name."""
        # Use seeded Garmin exercises if available
        if self._garmin_exercises:
            # Simple substring matching for tests
            name_lower = exercise_name.lower()
            similar = [
                e for e in self._garmin_exercises
                if name_lower in e.get("name", "").lower()
                or any(
                    word in e.get("name", "").lower()
                    for word in name_lower.split()
                    if len(word) > 3
                )
            ]
            return similar[:limit]
        return []

    def find_by_type(
        self,
        exercise_name: str,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Find exercises of the same type."""
        category = self.categorize(exercise_name)
        if not category or not self._garmin_exercises:
            return []

        # Filter by category keywords
        keywords = self._CATEGORIES.get(category, [])
        matching = [
            e for e in self._garmin_exercises
            if any(kw in e.get("name", "").lower() for kw in keywords)
        ]
        return matching[:limit]

    def categorize(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """Get the category/type of an exercise."""
        name_lower = exercise_name.lower()
        for category, keywords in self._CATEGORIES.items():
            if any(kw in name_lower for kw in keywords):
                return category
        return None
