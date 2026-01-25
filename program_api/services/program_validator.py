"""
Program validator service for ensuring program quality and safety.

Part of AMA-462: Implement ProgramGenerator Service

Validates generated programs against:
- Equipment constraints
- Volume limits by experience level
- Exercise uniqueness
- Muscle balance
- User limitations
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from models.program import ExperienceLevel

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    """Severity level for validation issues."""

    ERROR = "error"  # Must be fixed before saving
    WARNING = "warning"  # Should be reviewed
    INFO = "info"  # Informational only


@dataclass
class ValidationIssue:
    """A single validation issue."""

    message: str
    severity: ValidationSeverity
    location: Optional[str] = None  # e.g., "Week 3, Day 1"
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of program validation."""

    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: Optional[str] = None

    @property
    def errors(self) -> List[ValidationIssue]:
        """Get error-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.ERROR]

    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get warning-level issues."""
        return [i for i in self.issues if i.severity == ValidationSeverity.WARNING]


class ProgramValidator:
    """
    Validates generated training programs.

    Checks:
    1. Equipment - All exercises use available equipment
    2. Volume - Weekly volume within experience-appropriate limits
    3. Uniqueness - No duplicate exercises on same day
    4. Balance - Push/pull muscle balance
    5. Limitations - User limitations respected
    """

    # Weekly volume limits by experience (sets per muscle group)
    VOLUME_LIMITS = {
        ExperienceLevel.BEGINNER: {"min_sets": 8, "max_sets": 12},
        ExperienceLevel.INTERMEDIATE: {"min_sets": 12, "max_sets": 18},
        ExperienceLevel.ADVANCED: {"min_sets": 16, "max_sets": 25},
    }

    # Default for unknown experience levels
    DEFAULT_VOLUME_LIMITS = {"min_sets": 10, "max_sets": 20}

    # Muscle group balance requirements (opposing pairs)
    MUSCLE_BALANCE_PAIRS = [
        ({"chest", "anterior_deltoid"}, {"lats", "rhomboids", "rear_deltoid"}),  # Push/Pull
        ({"quadriceps"}, {"hamstrings", "glutes"}),  # Quad/Hamstring
        ({"biceps"}, {"triceps"}),  # Bicep/Tricep
    ]

    # Muscle groups affected by common limitations
    LIMITATION_MUSCLE_MAP = {
        "shoulder": {"anterior_deltoid", "rear_deltoid", "lateral_deltoid"},
        "back": {"lats", "rhomboids", "erector_spinae", "lower_back"},
        "knee": {"quadriceps", "hamstrings"},
        "hip": {"hip_flexors", "glutes", "adductors"},
        "wrist": {"forearms"},
        "elbow": {"biceps", "triceps", "forearms"},
        "ankle": {"calves", "tibialis"},
    }

    def __init__(self):
        """Initialize the validator."""
        pass

    def validate_program(
        self,
        program_data: Dict,
        available_equipment: List[str],
        experience_level: ExperienceLevel | str,
        limitations: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Validate a complete program.

        Args:
            program_data: Program dictionary with weeks and workouts
            available_equipment: List of available equipment
            experience_level: User's experience level
            limitations: Optional list of user limitations

        Returns:
            ValidationResult with any issues found
        """
        issues: List[ValidationIssue] = []

        # Convert experience level if string
        if isinstance(experience_level, str):
            try:
                experience_level = ExperienceLevel(experience_level)
            except ValueError:
                experience_level = ExperienceLevel.INTERMEDIATE

        weeks = program_data.get("weeks", [])

        # Run all validators
        issues.extend(self._validate_equipment(weeks, available_equipment))
        issues.extend(self._validate_volume(weeks, experience_level))
        issues.extend(self._validate_uniqueness(weeks))
        issues.extend(self._validate_balance(weeks))

        if limitations:
            issues.extend(self._validate_limitations(weeks, limitations))

        # Determine validity (no errors = valid)
        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        # Generate summary
        error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        warning_count = len([i for i in issues if i.severity == ValidationSeverity.WARNING])

        if is_valid and not issues:
            summary = "Program validated successfully with no issues."
        elif is_valid:
            summary = f"Program valid with {warning_count} warning(s)."
        else:
            summary = f"Program invalid: {error_count} error(s), {warning_count} warning(s)."

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            summary=summary,
        )

    def _validate_equipment(
        self,
        weeks: List[Dict],
        available_equipment: List[str],
    ) -> List[ValidationIssue]:
        """
        Validate all exercises use available equipment.

        Args:
            weeks: List of week dictionaries
            available_equipment: Available equipment list

        Returns:
            List of equipment-related issues
        """
        issues = []
        equipment_set = set(available_equipment)

        for week in weeks:
            week_num = week.get("week_number", "?")

            for workout in week.get("workouts", []):
                workout_name = workout.get("name", "Unknown")
                location = f"Week {week_num}, {workout_name}"

                for exercise in workout.get("exercises", []):
                    exercise_equipment = set(exercise.get("equipment", []))
                    exercise_name = exercise.get("exercise_name", exercise.get("exercise_id", "Unknown"))

                    # Check if exercise requires equipment we don't have
                    missing = exercise_equipment - equipment_set

                    # Skip if exercise has no equipment (bodyweight) or equipment matches
                    if exercise_equipment and missing and exercise_equipment:
                        issues.append(
                            ValidationIssue(
                                message=f"Exercise '{exercise_name}' requires unavailable equipment: {', '.join(missing)}",
                                severity=ValidationSeverity.ERROR,
                                location=location,
                                suggestion=f"Replace with an exercise using: {', '.join(equipment_set & exercise_equipment) if equipment_set & exercise_equipment else 'bodyweight'}",
                            )
                        )

        return issues

    def _validate_volume(
        self,
        weeks: List[Dict],
        experience_level: ExperienceLevel,
    ) -> List[ValidationIssue]:
        """
        Validate weekly volume is within appropriate limits.

        Args:
            weeks: List of week dictionaries
            experience_level: User experience level

        Returns:
            List of volume-related issues
        """
        issues = []
        limits = self.VOLUME_LIMITS.get(experience_level, self.DEFAULT_VOLUME_LIMITS)

        for week in weeks:
            week_num = week.get("week_number", "?")
            is_deload = week.get("is_deload", False)

            # Track sets per muscle group
            muscle_sets: Dict[str, int] = {}

            for workout in week.get("workouts", []):
                for exercise in workout.get("exercises", []):
                    sets = exercise.get("sets", 3)
                    primary_muscles = exercise.get("primary_muscles", [])

                    for muscle in primary_muscles:
                        muscle_sets[muscle] = muscle_sets.get(muscle, 0) + sets

            # Check each major muscle group
            major_muscles = [
                "chest", "lats", "quadriceps", "hamstrings",
                "glutes", "anterior_deltoid"
            ]

            for muscle in major_muscles:
                sets = muscle_sets.get(muscle, 0)
                location = f"Week {week_num}"

                # Adjust limits for deload
                min_sets = limits["min_sets"] // 2 if is_deload else limits["min_sets"]
                max_sets = limits["max_sets"] // 2 if is_deload else limits["max_sets"]

                if sets > 0 and sets < min_sets:
                    issues.append(
                        ValidationIssue(
                            message=f"Low volume for {muscle}: {sets} sets (minimum: {min_sets})",
                            severity=ValidationSeverity.WARNING,
                            location=location,
                            suggestion=f"Consider adding more {muscle} exercises",
                        )
                    )
                elif sets > max_sets:
                    issues.append(
                        ValidationIssue(
                            message=f"High volume for {muscle}: {sets} sets (maximum: {max_sets})",
                            severity=ValidationSeverity.WARNING,
                            location=location,
                            suggestion=f"Consider reducing {muscle} volume to prevent overtraining",
                        )
                    )

        return issues

    def _validate_uniqueness(self, weeks: List[Dict]) -> List[ValidationIssue]:
        """
        Validate no duplicate exercises on the same day.

        Args:
            weeks: List of week dictionaries

        Returns:
            List of uniqueness-related issues
        """
        issues = []

        for week in weeks:
            week_num = week.get("week_number", "?")

            for workout in week.get("workouts", []):
                workout_name = workout.get("name", "Unknown")
                location = f"Week {week_num}, {workout_name}"

                # Track exercise IDs in this workout
                seen_exercises: Set[str] = set()
                exercises = workout.get("exercises", [])

                for exercise in exercises:
                    exercise_id = exercise.get("exercise_id", "")

                    if exercise_id in seen_exercises:
                        exercise_name = exercise.get("exercise_name", exercise_id)
                        issues.append(
                            ValidationIssue(
                                message=f"Duplicate exercise '{exercise_name}' in same workout",
                                severity=ValidationSeverity.ERROR,
                                location=location,
                                suggestion="Replace duplicate with a variation or different exercise",
                            )
                        )
                    else:
                        seen_exercises.add(exercise_id)

        return issues

    def _validate_balance(self, weeks: List[Dict]) -> List[ValidationIssue]:
        """
        Validate push/pull muscle balance across the program.

        Args:
            weeks: List of week dictionaries

        Returns:
            List of balance-related issues
        """
        issues = []

        # Aggregate sets across all weeks
        total_muscle_sets: Dict[str, int] = {}

        for week in weeks:
            for workout in week.get("workouts", []):
                for exercise in workout.get("exercises", []):
                    sets = exercise.get("sets", 3)
                    primary_muscles = exercise.get("primary_muscles", [])

                    for muscle in primary_muscles:
                        total_muscle_sets[muscle] = total_muscle_sets.get(muscle, 0) + sets

        # Check balance for each pair
        for push_muscles, pull_muscles in self.MUSCLE_BALANCE_PAIRS:
            push_total = sum(total_muscle_sets.get(m, 0) for m in push_muscles)
            pull_total = sum(total_muscle_sets.get(m, 0) for m in pull_muscles)

            # Allow up to 30% imbalance
            if push_total > 0 and pull_total > 0:
                ratio = max(push_total, pull_total) / min(push_total, pull_total)
                if ratio > 1.5:
                    dominant = "push" if push_total > pull_total else "pull"
                    issues.append(
                        ValidationIssue(
                            message=f"Muscle imbalance detected: {push_total} push sets vs {pull_total} pull sets",
                            severity=ValidationSeverity.WARNING,
                            location="Program-wide",
                            suggestion=f"Consider adding more {'pull' if dominant == 'push' else 'push'} exercises",
                        )
                    )

        return issues

    def _validate_limitations(
        self,
        weeks: List[Dict],
        limitations: List[str],
    ) -> List[ValidationIssue]:
        """
        Validate user limitations are respected.

        Args:
            weeks: List of week dictionaries
            limitations: User limitations (e.g., ["shoulder", "lower back"])

        Returns:
            List of limitation-related issues
        """
        issues = []

        # Build set of muscles to avoid
        muscles_to_avoid: Set[str] = set()
        for limitation in limitations:
            limitation_lower = limitation.lower()
            for key, muscles in self.LIMITATION_MUSCLE_MAP.items():
                if key in limitation_lower:
                    muscles_to_avoid.update(muscles)

        if not muscles_to_avoid:
            return issues

        for week in weeks:
            week_num = week.get("week_number", "?")

            for workout in week.get("workouts", []):
                workout_name = workout.get("name", "Unknown")

                for exercise in workout.get("exercises", []):
                    exercise_name = exercise.get("exercise_name", exercise.get("exercise_id", "Unknown"))
                    primary_muscles = set(exercise.get("primary_muscles", []))

                    # Check if exercise targets muscles we should avoid
                    affected = primary_muscles & muscles_to_avoid
                    if affected:
                        issues.append(
                            ValidationIssue(
                                message=f"Exercise '{exercise_name}' may aggravate limitation: targets {', '.join(affected)}",
                                severity=ValidationSeverity.WARNING,
                                location=f"Week {week_num}, {workout_name}",
                                suggestion="Consider replacing with a safer alternative",
                            )
                        )

        return issues

    def validate_workout(
        self,
        workout: Dict,
        available_equipment: List[str],
        limitations: Optional[List[str]] = None,
    ) -> ValidationResult:
        """
        Validate a single workout.

        Args:
            workout: Workout dictionary with exercises
            available_equipment: Available equipment list
            limitations: Optional user limitations

        Returns:
            ValidationResult for the workout
        """
        # Wrap workout in week structure for reuse
        fake_week = {"week_number": 1, "workouts": [workout]}

        issues = []
        issues.extend(self._validate_equipment([fake_week], available_equipment))
        issues.extend(self._validate_uniqueness([fake_week]))

        if limitations:
            issues.extend(self._validate_limitations([fake_week], limitations))

        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            summary=f"Workout {'valid' if is_valid else 'invalid'}: {len(issues)} issue(s)",
        )
