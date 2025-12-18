"""
Base Parser

Abstract base class for all file parsers.
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from .models import (
    ParseResult,
    ParsedWorkout,
    ParsedExercise,
    DetectedPatterns,
    DetectedPattern,
    ExerciseFlag,
    FileInfo,
)

logger = logging.getLogger(__name__)


class BaseParser(ABC):
    """Abstract base class for file parsers"""

    # Regex patterns for common workout notations
    SUPERSET_PATTERN = re.compile(r'^(\d+)([a-z])$', re.IGNORECASE)  # "5a", "5b"
    COMPLEX_REP_PATTERN = re.compile(r'^(\d+)\s*[+x]\s*(\d+)$')  # "3+1", "4x4"
    DURATION_PATTERN = re.compile(r'^(\d+)\s*(s|sec|seconds?|m|min|minutes?)$', re.IGNORECASE)
    PERCENTAGE_PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*%$')  # "70%", "85.5%"
    RPE_PATTERN = re.compile(r'@\s*RPE\s*(\d+(?:\.\d+)?)', re.IGNORECASE)  # "@RPE8", "@ RPE 7.5"
    WEIGHT_PATTERN = re.compile(r'^(\d+(?:\.\d+)?)\s*(kg|lbs?|pounds?|kilos?)$', re.IGNORECASE)
    DAY_PATTERN = re.compile(r'day\s*(\d+)', re.IGNORECASE)  # "Day 1", "day 2"
    WEEK_PATTERN = re.compile(r'week\s*(\d+)', re.IGNORECASE)  # "Week 1", "week 2"

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @abstractmethod
    async def parse(self, content: bytes, file_info: FileInfo) -> ParseResult:
        """
        Parse file content and return normalized workout data.

        Args:
            content: Raw file bytes
            file_info: Information about the file

        Returns:
            ParseResult with workouts, patterns, and metadata
        """
        pass

    @abstractmethod
    def can_parse(self, file_info: FileInfo) -> bool:
        """
        Check if this parser can handle the given file.

        Args:
            file_info: Information about the file

        Returns:
            True if this parser can handle the file
        """
        pass

    def detect_patterns(self, workouts: List[ParsedWorkout]) -> DetectedPatterns:
        """Detect patterns across all parsed workouts"""
        patterns = DetectedPatterns()

        superset_examples = []
        complex_examples = []
        duration_examples = []
        percentage_examples = []
        warmup_count = 0

        for workout in workouts:
            for exercise in workout.exercises:
                # Check for superset notation
                if self.SUPERSET_PATTERN.match(exercise.order):
                    superset_examples.append(f"{exercise.order}: {exercise.raw_name}")

                # Check for complex reps
                if self.COMPLEX_REP_PATTERN.match(exercise.reps):
                    complex_examples.append(f"{exercise.raw_name}: {exercise.reps}")

                # Check for duration exercises
                if self.DURATION_PATTERN.match(exercise.reps):
                    duration_examples.append(f"{exercise.raw_name}: {exercise.reps}")

                # Check for percentage weights
                if exercise.weight and self.PERCENTAGE_PATTERN.match(exercise.weight):
                    percentage_examples.append(f"{exercise.raw_name}: {exercise.weight}")

                # Check for warmup flag
                if ExerciseFlag.WARMUP in exercise.flags:
                    warmup_count += 1

        # Build pattern objects
        if superset_examples:
            patterns.supersets = DetectedPattern(
                pattern_type="superset_notation",
                regex=self.SUPERSET_PATTERN.pattern,
                confidence=90,
                examples=superset_examples[:5],
                count=len(superset_examples)
            )

        if complex_examples:
            patterns.complex_movements = DetectedPattern(
                pattern_type="complex_movement",
                regex=self.COMPLEX_REP_PATTERN.pattern,
                confidence=90,
                examples=complex_examples[:5],
                count=len(complex_examples)
            )

        if duration_examples:
            patterns.duration_exercises = DetectedPattern(
                pattern_type="duration_exercise",
                regex=self.DURATION_PATTERN.pattern,
                confidence=90,
                examples=duration_examples[:5],
                count=len(duration_examples)
            )

        if percentage_examples:
            patterns.percentage_weights = DetectedPattern(
                pattern_type="percentage_weight",
                regex=self.PERCENTAGE_PATTERN.pattern,
                confidence=90,
                examples=percentage_examples[:5],
                count=len(percentage_examples)
            )

        if warmup_count > 0:
            patterns.warmup_sets = DetectedPattern(
                pattern_type="warmup_sets",
                confidence=80,
                examples=[],
                count=warmup_count
            )

        return patterns

    def parse_reps(self, reps_str: str) -> Tuple[str, List[ExerciseFlag]]:
        """
        Parse reps string and detect flags.

        Returns:
            Tuple of (normalized_reps, flags)
        """
        reps_str = str(reps_str).strip()
        flags = []

        # Check for complex movement
        if self.COMPLEX_REP_PATTERN.match(reps_str):
            flags.append(ExerciseFlag.COMPLEX)

        # Check for duration
        if self.DURATION_PATTERN.match(reps_str):
            flags.append(ExerciseFlag.DURATION)

        return reps_str, flags

    def parse_weight(self, weight_str: str) -> Tuple[Optional[str], Optional[str], List[ExerciseFlag]]:
        """
        Parse weight string and detect unit and flags.

        Returns:
            Tuple of (weight_value, unit, flags)
        """
        if not weight_str:
            return None, None, []

        weight_str = str(weight_str).strip()
        flags = []

        # Check for percentage
        pct_match = self.PERCENTAGE_PATTERN.match(weight_str)
        if pct_match:
            flags.append(ExerciseFlag.PERCENTAGE)
            return weight_str, None, flags

        # Check for weight with unit
        weight_match = self.WEIGHT_PATTERN.match(weight_str)
        if weight_match:
            value = weight_match.group(1)
            unit_str = weight_match.group(2).lower()
            unit = "kg" if unit_str.startswith("k") else "lbs"
            return value, unit, flags

        # Try to extract just a number
        try:
            float(weight_str)
            return weight_str, None, flags
        except ValueError:
            pass

        return weight_str, None, flags

    def parse_rpe(self, text: str) -> Optional[float]:
        """Extract RPE value from text"""
        match = self.RPE_PATTERN.search(text)
        if match:
            return float(match.group(1))
        return None

    def detect_superset_groups(self, exercises: List[ParsedExercise]) -> List[ParsedExercise]:
        """
        Detect and assign superset groups based on order notation.
        E.g., "5a", "5b" belong to the same group.
        """
        current_group = None
        current_base = None

        for exercise in exercises:
            match = self.SUPERSET_PATTERN.match(exercise.order)
            if match:
                base_num = match.group(1)
                if base_num != current_base:
                    current_base = base_num
                    current_group = f"superset_{base_num}"
                exercise.superset_group = current_group
            else:
                current_group = None
                current_base = None

        return exercises

    def normalize_exercise_name(self, name: str) -> str:
        """Normalize exercise name for consistency"""
        # Remove extra whitespace
        name = " ".join(name.split())

        # Capitalize properly
        name = name.strip()

        return name

    def add_error(self, error: str):
        """Add an error message"""
        self.errors.append(error)
        logger.error(f"Parser error: {error}")

    def add_warning(self, warning: str):
        """Add a warning message"""
        self.warnings.append(warning)
        logger.warning(f"Parser warning: {warning}")
