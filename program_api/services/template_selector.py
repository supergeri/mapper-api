"""
Template selector service for program generation.

Part of AMA-462: Implement ProgramGenerator Service

Selects the best matching program template based on user goals,
experience level, and training parameters.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from application.ports import TemplateRepository
from models.program import ExperienceLevel, ProgramGoal

logger = logging.getLogger(__name__)


@dataclass
class TemplateMatch:
    """Result of template matching with score."""

    template: Dict
    score: float
    match_reasons: List[str]


class TemplateSelector:
    """
    Selects the best program template for a generation request.

    Scoring factors:
    - Goal match (required)
    - Experience level match (required)
    - Sessions per week compatibility
    - Duration compatibility
    - Template popularity (usage count)
    """

    # Scoring weights
    SCORE_SESSIONS_MATCH = 30.0  # Exact sessions match
    SCORE_SESSIONS_CLOSE = 15.0  # Within 1 session
    SCORE_DURATION_MATCH = 25.0  # Exact duration match
    SCORE_DURATION_CLOSE = 10.0  # Within 2 weeks
    SCORE_POPULARITY_MAX = 15.0  # Max bonus for popular templates
    SCORE_BASE = 20.0  # Base score for matching goal + experience

    def __init__(self, template_repo: TemplateRepository):
        """
        Initialize template selector.

        Args:
            template_repo: Repository for template access
        """
        self._template_repo = template_repo

    async def select_best_template(
        self,
        goal: ProgramGoal | str,
        experience_level: ExperienceLevel | str,
        sessions_per_week: int,
        duration_weeks: int,
    ) -> Optional[TemplateMatch]:
        """
        Select the best matching template.

        Args:
            goal: Training goal
            experience_level: User experience level
            sessions_per_week: Desired sessions per week
            duration_weeks: Desired program duration

        Returns:
            Best matching TemplateMatch, or None if no suitable template
        """
        # Convert enums to strings if needed
        goal_str = goal.value if hasattr(goal, "value") else str(goal)
        exp_str = (
            experience_level.value
            if hasattr(experience_level, "value")
            else str(experience_level)
        )

        # Get matching templates from database
        templates = self._template_repo.get_by_criteria(
            goal=goal_str,
            experience_level=exp_str,
            duration_weeks=duration_weeks,
        )

        if not templates:
            logger.info(
                f"No templates found for goal={goal_str}, experience={exp_str}"
            )
            return None

        # Score each template
        scored = []
        for template in templates:
            match = self._score_template(
                template=template,
                sessions_per_week=sessions_per_week,
                duration_weeks=duration_weeks,
            )
            scored.append(match)

        # Sort by score descending
        scored.sort(key=lambda m: m.score, reverse=True)

        best = scored[0]
        logger.info(
            f"Selected template '{best.template.get('name')}' "
            f"with score {best.score:.1f}: {', '.join(best.match_reasons)}"
        )

        return best

    def _score_template(
        self,
        template: Dict,
        sessions_per_week: int,
        duration_weeks: int,
    ) -> TemplateMatch:
        """
        Score a template based on matching criteria.

        Args:
            template: Template dictionary
            sessions_per_week: Desired sessions per week
            duration_weeks: Desired duration

        Returns:
            TemplateMatch with score and reasons
        """
        score = self.SCORE_BASE
        reasons = ["Goal and experience match"]

        # Get template structure
        structure = template.get("structure", {})
        template_duration = template.get("duration_weeks", 0)

        # Score sessions per week match
        template_sessions = self._get_template_sessions(structure)
        if template_sessions == sessions_per_week:
            score += self.SCORE_SESSIONS_MATCH
            reasons.append(f"Exact sessions match ({sessions_per_week}/week)")
        elif abs(template_sessions - sessions_per_week) <= 1:
            score += self.SCORE_SESSIONS_CLOSE
            reasons.append(f"Close sessions match ({template_sessions} vs {sessions_per_week})")

        # Score duration match
        if template_duration == duration_weeks:
            score += self.SCORE_DURATION_MATCH
            reasons.append(f"Exact duration match ({duration_weeks} weeks)")
        elif abs(template_duration - duration_weeks) <= 2:
            score += self.SCORE_DURATION_CLOSE
            reasons.append(f"Close duration ({template_duration} vs {duration_weeks} weeks)")

        # Score popularity (normalize to 0-1 range, cap at 100 uses)
        usage_count = template.get("usage_count", 0)
        popularity_factor = min(usage_count / 100.0, 1.0)
        popularity_score = popularity_factor * self.SCORE_POPULARITY_MAX
        score += popularity_score
        if usage_count > 0:
            reasons.append(f"Used {usage_count} times")

        return TemplateMatch(
            template=template,
            score=score,
            match_reasons=reasons,
        )

    def _get_template_sessions(self, structure: Dict) -> int:
        """
        Get the number of sessions per week from template structure.

        Args:
            structure: Template JSONB structure

        Returns:
            Number of sessions per week (defaults to 3)
        """
        weeks = structure.get("weeks", [])
        if not weeks:
            return 3  # Default

        # Check first week's workout count
        first_week = weeks[0]
        workouts = first_week.get("workouts", [])
        return len(workouts) if workouts else 3

    async def get_default_structure(
        self,
        goal: ProgramGoal | str,
        experience_level: ExperienceLevel | str,
        sessions_per_week: int,
        duration_weeks: int,
    ) -> Dict:
        """
        Generate a default template structure when no template matches.

        This provides a fallback structure based on common workout splits.

        Args:
            goal: Training goal
            experience_level: User experience level
            sessions_per_week: Sessions per week
            duration_weeks: Program duration

        Returns:
            Default template structure dictionary
        """
        # Convert enums to strings
        goal_str = goal.value if hasattr(goal, "value") else str(goal)

        # Select split type based on sessions
        split_configs = {
            2: self._full_body_split(),
            3: self._push_pull_legs_split() if goal_str in ["strength", "hypertrophy"] else self._full_body_split(),
            4: self._upper_lower_split(),
            5: self._ppl_upper_lower_split(),
            6: self._ppl_twice_split(),
            7: self._ppl_twice_plus_split(),
        }

        split = split_configs.get(sessions_per_week, self._full_body_split())

        return {
            "mesocycle_length": min(4, duration_weeks),
            "deload_frequency": 4,
            "split_type": split["name"],
            "weeks": [
                {
                    "week_pattern": 1,
                    "focus": self._get_focus_for_goal(goal_str),
                    "workouts": split["workouts"],
                }
            ],
        }

    def _full_body_split(self) -> Dict:
        """2-3 sessions: Full body each day."""
        return {
            "name": "full_body",
            "workouts": [
                {
                    "day_of_week": 1,
                    "name": "Full Body A",
                    "workout_type": "full_body",
                    "muscle_groups": [
                        "chest", "lats", "quadriceps", "hamstrings",
                        "anterior_deltoid", "biceps", "triceps"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 3,
                    "name": "Full Body B",
                    "workout_type": "full_body",
                    "muscle_groups": [
                        "chest", "rhomboids", "glutes", "quadriceps",
                        "rear_deltoid", "biceps", "triceps"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 5,
                    "name": "Full Body C",
                    "workout_type": "full_body",
                    "muscle_groups": [
                        "chest", "lats", "hamstrings", "calves",
                        "anterior_deltoid", "core"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
            ],
        }

    def _push_pull_legs_split(self) -> Dict:
        """3 sessions: Push/Pull/Legs."""
        return {
            "name": "push_pull_legs",
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
                    "day_of_week": 3,
                    "name": "Pull Day",
                    "workout_type": "pull",
                    "muscle_groups": ["lats", "rhomboids", "rear_deltoid", "biceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 5,
                    "name": "Legs Day",
                    "workout_type": "legs",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
            ],
        }

    def _upper_lower_split(self) -> Dict:
        """4 sessions: Upper/Lower twice."""
        return {
            "name": "upper_lower",
            "workouts": [
                {
                    "day_of_week": 1,
                    "name": "Upper Body A",
                    "workout_type": "upper",
                    "muscle_groups": [
                        "chest", "lats", "anterior_deltoid", "triceps", "biceps"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 2,
                    "name": "Lower Body A",
                    "workout_type": "lower",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 4,
                    "name": "Upper Body B",
                    "workout_type": "upper",
                    "muscle_groups": [
                        "chest", "rhomboids", "rear_deltoid", "triceps", "biceps"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 5,
                    "name": "Lower Body B",
                    "workout_type": "lower",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
            ],
        }

    def _ppl_upper_lower_split(self) -> Dict:
        """5 sessions: PPL + Upper/Lower."""
        return {
            "name": "ppl_upper_lower",
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
                    "muscle_groups": ["lats", "rhomboids", "rear_deltoid", "biceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 3,
                    "name": "Legs Day",
                    "workout_type": "legs",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 5,
                    "name": "Upper Body",
                    "workout_type": "upper",
                    "muscle_groups": [
                        "chest", "lats", "anterior_deltoid", "triceps", "biceps"
                    ],
                    "exercise_slots": 6,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 6,
                    "name": "Lower Body",
                    "workout_type": "lower",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
            ],
        }

    def _ppl_twice_split(self) -> Dict:
        """6 sessions: PPL twice."""
        return {
            "name": "ppl_twice",
            "workouts": [
                {
                    "day_of_week": 1,
                    "name": "Push Day A",
                    "workout_type": "push",
                    "muscle_groups": ["chest", "anterior_deltoid", "triceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 2,
                    "name": "Pull Day A",
                    "workout_type": "pull",
                    "muscle_groups": ["lats", "rhomboids", "rear_deltoid", "biceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 3,
                    "name": "Legs Day A",
                    "workout_type": "legs",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 4,
                    "name": "Push Day B",
                    "workout_type": "push",
                    "muscle_groups": ["chest", "anterior_deltoid", "triceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 5,
                    "name": "Pull Day B",
                    "workout_type": "pull",
                    "muscle_groups": ["lats", "rhomboids", "rear_deltoid", "biceps"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
                {
                    "day_of_week": 6,
                    "name": "Legs Day B",
                    "workout_type": "legs",
                    "muscle_groups": ["quadriceps", "hamstrings", "glutes", "calves"],
                    "exercise_slots": 5,
                    "target_duration_minutes": 60,
                },
            ],
        }

    def _ppl_twice_plus_split(self) -> Dict:
        """7 sessions: PPL twice + arms/active recovery."""
        split = self._ppl_twice_split()
        split["name"] = "ppl_twice_plus"
        split["workouts"].append({
            "day_of_week": 7,
            "name": "Arms & Core",
            "workout_type": "arms",
            "muscle_groups": ["biceps", "triceps", "forearms", "core"],
            "exercise_slots": 6,
            "target_duration_minutes": 45,
        })
        return split

    def _get_focus_for_goal(self, goal: str) -> str:
        """Get training focus text for a goal."""
        focus_map = {
            "strength": "Strength Development",
            "hypertrophy": "Muscle Building",
            "endurance": "Muscular Endurance",
            "weight_loss": "Fat Loss & Conditioning",
            "general_fitness": "General Fitness",
            "sport_specific": "Sport Performance",
            "power": "Power Development",
            "fat_loss": "Fat Loss & Conditioning",
            "rehabilitation": "Rehabilitation & Recovery",
        }
        return focus_map.get(goal, "General Training")
