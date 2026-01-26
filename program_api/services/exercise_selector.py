"""
Exercise selector service for intelligent exercise selection.

Part of AMA-472: Exercise Database Integration for Program Generation

This service provides intelligent exercise selection based on equipment
availability, movement patterns, target muscles, and other criteria.
It integrates with the exercise database for fallback mechanisms when
LLM-powered selection is unavailable.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from uuid import uuid4

from application.ports import ExerciseRepository


# Equipment mapping for different gym setups
EQUIPMENT_MAPPING: Dict[str, List[str]] = {
    "full_gym": [
        "barbell",
        "dumbbells",
        "cables",
        "machines",
        "bench",
        "rack",
        "pull_up_bar",
        "leg_press_machine",
        "leg_curl_machine",
        "squat_rack",
    ],
    "home_basic": [
        "dumbbells",
        "bench",
        "resistance_bands",
        "pull_up_bar",
    ],
    "home_advanced": [
        "barbell",
        "dumbbells",
        "bench",
        "rack",
        "cables",
        "squat_rack",
        "pull_up_bar",
    ],
    "bodyweight": [
        "bodyweight",
        "pull_up_bar",
    ],
}

# Equipment aliases for normalization
EQUIPMENT_ALIASES: Dict[str, str] = {
    "dumbbell": "dumbbells",
    "cable": "cables",
    "machine": "machines",
    "power_rack": "rack",
    "squat_rack": "rack",
    "pullup_bar": "pull_up_bar",
    "pull-up_bar": "pull_up_bar",
    "barbell_bench": "bench",
    "flat_bench": "bench",
    "incline_bench": "bench",
}


@dataclass
class SlotRequirements:
    """Requirements for an exercise slot in a workout."""

    movement_pattern: Optional[str] = None
    target_muscles: Optional[List[str]] = None
    category: Optional[str] = None  # compound, isolation
    supports_1rm: Optional[bool] = None
    preferred_equipment: Optional[List[str]] = None


@dataclass
class ExerciseCandidate:
    """A candidate exercise with its score."""

    exercise: Dict
    score: float = 0.0


class ExerciseSelector:
    """
    Service for intelligent exercise selection.

    Provides methods to:
    - Fill exercise slots based on requirements and available equipment
    - Find alternatives for existing exercises
    - Create fallback exercises when no database match exists
    """

    def __init__(self, exercise_repo: ExerciseRepository):
        """
        Initialize the exercise selector.

        Args:
            exercise_repo: Repository for exercise data access
        """
        self._exercise_repo = exercise_repo

    def fill_exercise_slot(
        self,
        requirements: SlotRequirements,
        available_equipment: List[str],
        exclude_exercises: Optional[List[str]] = None,
    ) -> Optional[Dict]:
        """
        Fill an exercise slot based on requirements and constraints.

        Args:
            requirements: The requirements for the exercise slot
            available_equipment: List of available equipment
            exclude_exercises: Exercise IDs to exclude (already selected)

        Returns:
            Best matching exercise dictionary, or None if no match found
        """
        exclude_set = set(exclude_exercises or [])
        normalized_equipment = self._normalize_equipment(available_equipment)

        # Build search criteria
        candidates = self._exercise_repo.search(
            muscle_groups=requirements.target_muscles,
            equipment=list(normalized_equipment) if normalized_equipment else None,
            movement_pattern=requirements.movement_pattern,
            category=requirements.category,
            supports_1rm=requirements.supports_1rm,
            limit=50,
        )

        # Filter out excluded exercises and those requiring unavailable equipment
        filtered_candidates = []
        for ex in candidates:
            if ex.get("id") in exclude_set:
                continue

            ex_equipment = set(ex.get("equipment", []))
            # Bodyweight exercises always match
            if not ex_equipment:
                filtered_candidates.append(ex)
                continue

            # Check if all required equipment is available
            if ex_equipment <= normalized_equipment:
                filtered_candidates.append(ex)

        if not filtered_candidates:
            return self._create_fallback_exercise(requirements)

        # Score and rank candidates
        scored = self._score_candidates(filtered_candidates, requirements)

        if scored:
            return scored[0].exercise

        return self._create_fallback_exercise(requirements)

    def get_alternatives(
        self,
        exercise_id: str,
        available_equipment: List[str],
        limit: int = 5,
    ) -> List[Dict]:
        """
        Get alternative exercises for a given exercise.

        Args:
            exercise_id: The ID of the exercise to find alternatives for
            available_equipment: List of available equipment
            limit: Maximum number of alternatives to return

        Returns:
            List of alternative exercise dictionaries
        """
        normalized_equipment = self._normalize_equipment(available_equipment)

        # Get similar exercises from repository
        similar = self._exercise_repo.get_similar_exercises(
            exercise_id=exercise_id,
            limit=limit * 2,  # Get more to filter by equipment
        )

        # Filter by available equipment
        filtered = []
        for ex in similar:
            ex_equipment = set(ex.get("equipment", []))
            # Bodyweight exercises always match
            if not ex_equipment:
                filtered.append(ex)
                continue

            # Check if all required equipment is available
            if ex_equipment <= normalized_equipment:
                filtered.append(ex)

        return filtered[:limit]

    def _normalize_equipment(self, equipment: List[str]) -> Set[str]:
        """
        Normalize equipment list, handling aliases and preset names.

        Args:
            equipment: Raw equipment list (may include presets or aliases)

        Returns:
            Normalized set of equipment identifiers
        """
        normalized: Set[str] = set()

        for item in equipment:
            item_lower = item.lower().strip()

            # Check if it's a preset
            if item_lower in EQUIPMENT_MAPPING:
                normalized.update(EQUIPMENT_MAPPING[item_lower])
                continue

            # Check if it's an alias
            if item_lower in EQUIPMENT_ALIASES:
                normalized.add(EQUIPMENT_ALIASES[item_lower])
                continue

            # Add as-is
            normalized.add(item_lower)

        return normalized

    def _score_candidates(
        self,
        candidates: List[Dict],
        requirements: SlotRequirements,
    ) -> List[ExerciseCandidate]:
        """
        Score exercise candidates based on how well they match requirements.

        Args:
            candidates: List of candidate exercises
            requirements: The slot requirements

        Returns:
            List of ExerciseCandidate sorted by score (highest first)
        """
        scored = []

        target_muscles = set(requirements.target_muscles or [])
        preferred_equipment = set(requirements.preferred_equipment or [])

        for ex in candidates:
            score = 0.0

            # Muscle match score (0-0.4)
            if target_muscles:
                ex_muscles = set(ex.get("primary_muscles", []))
                overlap = len(ex_muscles & target_muscles)
                score += min(overlap / len(target_muscles), 1.0) * 0.4

            # Category match score (0-0.3)
            if requirements.category and ex.get("category") == requirements.category:
                score += 0.3

            # Movement pattern match score (0-0.2)
            if requirements.movement_pattern:
                if ex.get("movement_pattern") == requirements.movement_pattern:
                    score += 0.2

            # Preferred equipment bonus (0-0.1)
            if preferred_equipment:
                ex_equipment = set(ex.get("equipment", []))
                if ex_equipment & preferred_equipment:
                    score += 0.1

            # 1RM support match (0-0.05)
            if requirements.supports_1rm is not None:
                if ex.get("supports_1rm") == requirements.supports_1rm:
                    score += 0.05

            # Compound exercises get slight priority (0-0.05)
            if ex.get("category") == "compound":
                score += 0.05

            scored.append(ExerciseCandidate(exercise=ex, score=score))

        # Sort by score descending
        scored.sort(key=lambda x: x.score, reverse=True)

        return scored

    def _create_fallback_exercise(
        self,
        requirements: SlotRequirements,
    ) -> Optional[Dict]:
        """
        Create a fallback/placeholder exercise when no database match exists.

        This creates a minimal exercise structure that can be used as a
        placeholder until a proper exercise is selected.

        Args:
            requirements: The slot requirements

        Returns:
            Placeholder exercise dictionary, or None if can't create
        """
        if not requirements.target_muscles and not requirements.movement_pattern:
            return None

        # Generate a placeholder name
        name_parts = []
        if requirements.movement_pattern:
            name_parts.append(requirements.movement_pattern.title())
        if requirements.target_muscles:
            name_parts.append(requirements.target_muscles[0].title())
        name_parts.append("Exercise")

        name = " ".join(name_parts)
        # Use UUID suffix to ensure unique IDs for each fallback
        unique_suffix = str(uuid4())[:8]
        exercise_id = f"{name.lower().replace(' ', '-')}-{unique_suffix}"

        return {
            "id": exercise_id,
            "name": name,
            "primary_muscles": requirements.target_muscles or [],
            "secondary_muscles": [],
            "equipment": [],
            "category": requirements.category or "compound",
            "movement_pattern": requirements.movement_pattern,
            "supports_1rm": requirements.supports_1rm or False,
            "is_placeholder": True,
        }
