"""
Fake template repository for testing.

Part of AMA-462: Implement ProgramGenerator Service

This fake implementation stores data in memory and provides
helper methods for test setup and verification.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class FakeTemplateRepository:
    """
    In-memory fake implementation of TemplateRepository.

    Provides the same interface as SupabaseTemplateRepository
    but stores data in dictionaries for fast, isolated testing.
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._templates: Dict[str, Dict] = {}

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    def seed(self, templates: List[Dict]) -> None:
        """
        Seed the repository with test data.

        Args:
            templates: List of template dictionaries to add
        """
        for template in templates:
            template_id = template.get("id", str(uuid4()))
            self._templates[template_id] = {**template, "id": template_id}

    def seed_default_templates(self) -> None:
        """Seed with common default templates for testing."""
        templates = [
            {
                "id": str(uuid4()),
                "name": "PPL Hypertrophy 4x",
                "goal": "hypertrophy",
                "periodization_model": "undulating",
                "experience_level": "intermediate",
                "duration_weeks": 8,
                "is_system_template": True,
                "usage_count": 150,
                "structure": {
                    "mesocycle_length": 4,
                    "split_type": "push_pull_legs",
                    "weeks": [
                        {
                            "week_pattern": 1,
                            "workouts": [
                                {
                                    "day_of_week": 1,
                                    "name": "Push Day",
                                    "workout_type": "push",
                                    "muscle_groups": ["chest", "anterior_deltoid", "triceps"],
                                    "exercise_slots": 5,
                                    "target_duration_minutes": 60,
                                },
                                {
                                    "day_of_week": 2,
                                    "name": "Pull Day",
                                    "workout_type": "pull",
                                    "muscle_groups": ["lats", "rhomboids", "biceps"],
                                    "exercise_slots": 5,
                                    "target_duration_minutes": 60,
                                },
                                {
                                    "day_of_week": 4,
                                    "name": "Legs Day",
                                    "workout_type": "legs",
                                    "muscle_groups": ["quadriceps", "hamstrings", "glutes"],
                                    "exercise_slots": 5,
                                    "target_duration_minutes": 60,
                                },
                                {
                                    "day_of_week": 5,
                                    "name": "Upper Day",
                                    "workout_type": "upper",
                                    "muscle_groups": ["chest", "lats", "anterior_deltoid"],
                                    "exercise_slots": 6,
                                    "target_duration_minutes": 60,
                                },
                            ],
                        }
                    ],
                },
            },
            {
                "id": str(uuid4()),
                "name": "Strength Block 3x",
                "goal": "strength",
                "periodization_model": "block",
                "experience_level": "intermediate",
                "duration_weeks": 12,
                "is_system_template": True,
                "usage_count": 80,
                "structure": {
                    "mesocycle_length": 4,
                    "split_type": "full_body",
                    "weeks": [
                        {
                            "week_pattern": 1,
                            "workouts": [
                                {
                                    "day_of_week": 1,
                                    "name": "Full Body A",
                                    "workout_type": "full_body",
                                    "muscle_groups": ["chest", "lats", "quadriceps"],
                                    "exercise_slots": 6,
                                    "target_duration_minutes": 75,
                                },
                                {
                                    "day_of_week": 3,
                                    "name": "Full Body B",
                                    "workout_type": "full_body",
                                    "muscle_groups": ["anterior_deltoid", "hamstrings", "biceps"],
                                    "exercise_slots": 6,
                                    "target_duration_minutes": 75,
                                },
                                {
                                    "day_of_week": 5,
                                    "name": "Full Body C",
                                    "workout_type": "full_body",
                                    "muscle_groups": ["chest", "lats", "glutes"],
                                    "exercise_slots": 6,
                                    "target_duration_minutes": 75,
                                },
                            ],
                        }
                    ],
                },
            },
        ]
        self.seed(templates)

    def reset(self) -> None:
        """Clear all stored data."""
        self._templates.clear()

    def get_all(self) -> List[Dict]:
        """Get all stored templates (for test verification)."""
        return list(self._templates.values())

    def count(self) -> int:
        """Get count of stored templates."""
        return len(self._templates)

    # -------------------------------------------------------------------------
    # Repository Interface Implementation
    # -------------------------------------------------------------------------

    def get_by_id(self, template_id: str) -> Optional[Dict]:
        """
        Get a template by its ID.

        Args:
            template_id: The template's UUID as string

        Returns:
            Template dictionary if found, None otherwise
        """
        return self._templates.get(template_id)

    def get_by_criteria(
        self,
        goal: str,
        experience_level: str,
        sessions_per_week: Optional[int] = None,
        duration_weeks: Optional[int] = None,
    ) -> List[Dict]:
        """
        Find templates matching specified criteria.

        Args:
            goal: Training goal
            experience_level: User experience level
            sessions_per_week: Optional filter for session count
            duration_weeks: Optional filter for duration

        Returns:
            List of matching template dictionaries, ordered by usage_count
        """
        matches = []

        for template in self._templates.values():
            if template.get("goal") != goal:
                continue
            if template.get("experience_level") != experience_level:
                continue

            # Duration filter (within ±2 weeks)
            if duration_weeks is not None:
                t_duration = template.get("duration_weeks", 0)
                if abs(t_duration - duration_weeks) > 2:
                    continue

            # Sessions per week filter
            if sessions_per_week is not None:
                structure = template.get("structure", {})
                weeks = structure.get("weeks", [])
                if weeks:
                    workouts = weeks[0].get("workouts", [])
                    if len(workouts) != sessions_per_week:
                        continue

            matches.append(template)

        # Sort by usage_count descending
        return sorted(matches, key=lambda t: t.get("usage_count", 0), reverse=True)

    def get_system_templates(self) -> List[Dict]:
        """
        Get all system-provided templates.

        Returns:
            List of system template dictionaries
        """
        return [
            t for t in self._templates.values()
            if t.get("is_system_template", True)
        ]

    def get_user_templates(self, user_id: str) -> List[Dict]:
        """
        Get all templates created by a specific user.

        Args:
            user_id: The user's ID

        Returns:
            List of user template dictionaries
        """
        return [
            t for t in self._templates.values()
            if t.get("created_by") == user_id
            and not t.get("is_system_template", True)
        ]

    def create(self, data: Dict) -> Dict:
        """
        Create a new template.

        Args:
            data: Template data dictionary

        Returns:
            Created template dictionary with generated ID
        """
        template_id = data.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat() + "Z"
        template = {
            **data,
            "id": template_id,
            "created_at": data.get("created_at", now),
            "usage_count": data.get("usage_count", 0),
        }
        self._templates[template_id] = template
        return template

    def increment_usage_count(self, template_id: str) -> bool:
        """
        Increment the usage count for a template.

        Args:
            template_id: The template's UUID as string

        Returns:
            True if updated, False if not found
        """
        if template_id in self._templates:
            self._templates[template_id]["usage_count"] = (
                self._templates[template_id].get("usage_count", 0) + 1
            )
            return True
        return False
