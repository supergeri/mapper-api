"""
Periodization Service for Training Programs.

Part of AMA-463: Implement periodization calculation engine

This module provides business logic for training program periodization:
- 5 periodization models (Linear, Undulating, Block, Conjugate, Reverse Linear)
- Automatic deload week calculation
- Rep range recommendations from intensity
- Training focus determination
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


# =============================================================================
# Enums
# =============================================================================


class ProgramGoal(str, Enum):
    """Training program goals."""

    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"
    ENDURANCE = "endurance"
    WEIGHT_LOSS = "weight_loss"
    GENERAL_FITNESS = "general_fitness"
    SPORT_SPECIFIC = "sport_specific"


class ExperienceLevel(str, Enum):
    """User experience levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PeriodizationModel(str, Enum):
    """Available periodization models."""

    LINEAR = "linear"
    UNDULATING = "undulating"
    BLOCK = "block"
    CONJUGATE = "conjugate"
    REVERSE_LINEAR = "reverse_linear"


class BlockPhase(str, Enum):
    """Block periodization phases."""

    ACCUMULATION = "accumulation"  # High volume, moderate intensity
    TRANSMUTATION = "transmutation"  # Moderate volume, high intensity
    REALIZATION = "realization"  # Low volume, peak intensity


class EffortType(str, Enum):
    """Conjugate method effort types."""

    MAX_EFFORT = "max_effort"  # 90-100% 1RM, low reps
    DYNAMIC_EFFORT = "dynamic_effort"  # 50-60% 1RM, explosive
    REPETITION_EFFORT = "repetition_effort"  # Moderate weight, higher reps


class TrainingFocus(str, Enum):
    """Training focus for a given week."""

    STRENGTH = "strength"  # Low reps, high intensity (85%+)
    POWER = "power"  # Explosive work (75-85%)
    HYPERTROPHY = "hypertrophy"  # Moderate intensity, higher volume (65-80%)
    ENDURANCE = "endurance"  # Low intensity, high volume (<65%)
    DELOAD = "deload"  # Recovery week


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class WeekParameters:
    """Parameters for a training week."""

    week_number: int
    intensity_percent: float  # 0.0 to 1.0
    volume_modifier: float  # Multiplier (0.5 = half volume, 1.5 = 150%)
    is_deload: bool = False
    phase: Optional[BlockPhase] = None  # For block periodization
    effort_type: Optional[EffortType] = None  # For conjugate periodization
    focus: TrainingFocus = field(default=TrainingFocus.HYPERTROPHY)
    notes: Optional[str] = None

    def get_rep_range(self) -> str:
        """
        Calculate recommended rep range based on intensity.

        Returns:
            Rep range string (e.g., "1-3", "4-6", "6-8", "8-12")
        """
        # Convert to percentage (0-100 scale) if needed
        intensity = (
            self.intensity_percent
            if self.intensity_percent > 1
            else self.intensity_percent * 100
        )

        if intensity >= 90:
            return "1-3"
        elif intensity >= 80:
            return "4-6"
        elif intensity >= 70:
            return "6-8"
        else:
            return "8-12"

    @staticmethod
    def determine_focus(
        intensity_percent: float,
        is_deload: bool,
        effort_type: Optional[EffortType] = None,
    ) -> TrainingFocus:
        """
        Determine training focus based on intensity and context.

        Args:
            intensity_percent: Current intensity (0.0-1.0)
            is_deload: Whether this is a deload week
            effort_type: For conjugate, the effort type

        Returns:
            Appropriate TrainingFocus
        """
        if is_deload:
            return TrainingFocus.DELOAD

        # Special handling for conjugate effort types
        if effort_type == EffortType.MAX_EFFORT:
            return TrainingFocus.STRENGTH
        elif effort_type == EffortType.DYNAMIC_EFFORT:
            return TrainingFocus.POWER
        elif effort_type == EffortType.REPETITION_EFFORT:
            return TrainingFocus.HYPERTROPHY

        # Intensity-based focus
        intensity = (
            intensity_percent
            if intensity_percent > 1
            else intensity_percent * 100
        )

        if intensity >= 85:
            return TrainingFocus.STRENGTH
        elif intensity >= 75:
            return TrainingFocus.POWER
        elif intensity >= 65:
            return TrainingFocus.HYPERTROPHY
        else:
            return TrainingFocus.ENDURANCE


# =============================================================================
# Periodization Service
# =============================================================================


class PeriodizationService:
    """
    Service for planning program periodization.

    Handles the science-based progression of training variables
    across weeks and mesocycles.
    """

    # Base intensity ranges by goal
    INTENSITY_RANGES = {
        ProgramGoal.STRENGTH: (0.75, 0.95),  # Higher intensity
        ProgramGoal.HYPERTROPHY: (0.65, 0.85),  # Moderate intensity
        ProgramGoal.ENDURANCE: (0.50, 0.70),  # Lower intensity, more reps
        ProgramGoal.WEIGHT_LOSS: (0.55, 0.75),  # Moderate intensity
        ProgramGoal.GENERAL_FITNESS: (0.60, 0.80),  # Balanced
        ProgramGoal.SPORT_SPECIFIC: (0.65, 0.90),  # Varies by sport
    }

    # Deload frequency by experience (weeks between deloads)
    DELOAD_FREQUENCY = {
        ExperienceLevel.BEGINNER: 6,  # Every 6 weeks
        ExperienceLevel.INTERMEDIATE: 4,  # Every 4 weeks
        ExperienceLevel.ADVANCED: 3,  # Every 3 weeks
    }

    # Volume limits by experience (weekly sets per muscle group)
    VOLUME_LIMITS = {
        ExperienceLevel.BEGINNER: {"min": 10, "max": 12},
        ExperienceLevel.INTERMEDIATE: {"min": 12, "max": 18},
        ExperienceLevel.ADVANCED: {"min": 16, "max": 25},
    }

    def calculate_linear_progression(
        self, week: int, total_weeks: int
    ) -> Tuple[float, float]:
        """
        Calculate linear periodization parameters.

        Linear periodization progressively increases intensity while
        decreasing volume throughout the program.

        Args:
            week: Current week number (1-indexed)
            total_weeks: Total program duration

        Returns:
            Tuple of (intensity_percent, volume_modifier)
        """
        if total_weeks < 1:
            raise ValueError(f"Total weeks must be at least 1, got {total_weeks}")
        if week < 1 or week > total_weeks:
            raise ValueError(f"Week {week} out of range [1, {total_weeks}]")

        # Linear progression: intensity goes from 0.65 to 0.95
        progress = (week - 1) / max(total_weeks - 1, 1)
        intensity = 0.65 + (0.30 * progress)

        # Volume inversely related: starts at 1.0, decreases to 0.7
        volume_mod = 1.0 - (0.30 * progress)

        return (round(intensity, 3), round(volume_mod, 3))

    def calculate_undulating_progression(
        self, week: int, session: int, total_sessions: int = 3
    ) -> Tuple[float, float]:
        """
        Calculate daily undulating periodization (DUP) parameters.

        DUP varies intensity and volume within each week across sessions.
        Pattern: Heavy -> Light -> Moderate

        Args:
            week: Current week number (1-indexed)
            session: Session number within week (1-indexed)
            total_sessions: Total sessions per week

        Returns:
            Tuple of (intensity_percent, volume_modifier)
        """
        if session < 1 or session > total_sessions:
            raise ValueError(f"Session {session} out of range [1, {total_sessions}]")

        # Session patterns (intensity, volume)
        patterns = {
            1: (0.85, 0.8),  # Heavy day: high intensity, lower volume
            2: (0.65, 1.2),  # Light day: low intensity, high volume
            3: (0.75, 1.0),  # Moderate day: balanced
        }

        # Map session to pattern (cycling if more sessions)
        pattern_idx = ((session - 1) % 3) + 1
        base_intensity, base_volume = patterns[pattern_idx]

        # Small weekly progression (2% intensity increase per week)
        weekly_bonus = min(0.02 * (week - 1), 0.10)
        intensity = min(base_intensity + weekly_bonus, 0.95)

        return (round(intensity, 3), round(base_volume, 3))

    def calculate_block_progression(
        self, week: int, total_weeks: int
    ) -> Tuple[float, float, BlockPhase]:
        """
        Calculate block periodization parameters.

        Block periodization divides training into distinct phases:
        - Accumulation (40%): High volume, moderate intensity
        - Transmutation (40%): Moderate volume, high intensity
        - Realization (20%): Low volume, peak intensity

        Args:
            week: Current week number (1-indexed)
            total_weeks: Total program duration

        Returns:
            Tuple of (intensity_percent, volume_modifier, phase)
        """
        if total_weeks < 1:
            raise ValueError(f"Total weeks must be at least 1, got {total_weeks}")
        if week < 1 or week > total_weeks:
            raise ValueError(f"Week {week} out of range [1, {total_weeks}]")

        # Calculate phase boundaries (40/40/20 split)
        accum_end = int(total_weeks * 0.4)
        trans_end = int(total_weeks * 0.8)

        if week <= accum_end:
            # Accumulation phase: high volume, moderate intensity
            phase = BlockPhase.ACCUMULATION
            phase_progress = (week - 1) / max(accum_end - 1, 1) if accum_end > 1 else 0
            intensity = 0.65 + (0.05 * phase_progress)
            volume_mod = 1.2 - (0.1 * phase_progress)
        elif week <= trans_end:
            # Transmutation phase: moderate volume, high intensity
            phase = BlockPhase.TRANSMUTATION
            phase_start = accum_end + 1
            phase_weeks = trans_end - accum_end
            phase_progress = (
                (week - phase_start) / max(phase_weeks - 1, 1) if phase_weeks > 1 else 0
            )
            intensity = 0.75 + (0.10 * phase_progress)
            volume_mod = 1.0 - (0.15 * phase_progress)
        else:
            # Realization phase: low volume, peak intensity
            phase = BlockPhase.REALIZATION
            phase_start = trans_end + 1
            phase_weeks = total_weeks - trans_end
            phase_progress = (
                (week - phase_start) / max(phase_weeks - 1, 1) if phase_weeks > 1 else 0
            )
            intensity = 0.88 + (0.07 * phase_progress)
            volume_mod = 0.75 - (0.15 * phase_progress)

        return (round(intensity, 3), round(volume_mod, 3), phase)

    def calculate_conjugate_progression(
        self, week: int, session: int
    ) -> Tuple[float, float, EffortType]:
        """
        Calculate conjugate method parameters.

        The conjugate method rotates between:
        - Max Effort (ME): 1-3 rep max attempts
        - Dynamic Effort (DE): Speed work at 50-60%
        - Repetition Effort (RE): Hypertrophy work

        Args:
            week: Current week number (1-indexed)
            session: Session number within week (1-indexed)

        Returns:
            Tuple of (intensity_percent, volume_modifier, effort_type)
        """
        # Rotate effort types based on session number
        effort_rotation = [
            EffortType.MAX_EFFORT,  # Session 1
            EffortType.DYNAMIC_EFFORT,  # Session 2
            EffortType.REPETITION_EFFORT,  # Session 3
            EffortType.MAX_EFFORT,  # Session 4
        ]

        # Parameters for each effort type
        effort_params = {
            EffortType.MAX_EFFORT: (0.92, 0.6),  # High intensity, low volume
            EffortType.DYNAMIC_EFFORT: (0.55, 1.3),  # Low intensity, high volume
            EffortType.REPETITION_EFFORT: (0.70, 1.1),  # Moderate both
        }

        effort_idx = (session - 1) % len(effort_rotation)
        effort_type = effort_rotation[effort_idx]
        intensity, volume = effort_params[effort_type]

        # Wave loading: slight intensity variation across weeks (3-week waves)
        wave_position = (week - 1) % 3
        wave_modifier = [-0.03, 0, 0.03][wave_position]
        intensity = min(max(intensity + wave_modifier, 0.50), 0.98)

        return (round(intensity, 3), round(volume, 3), effort_type)

    def calculate_reverse_linear_progression(
        self, week: int, total_weeks: int
    ) -> Tuple[float, float]:
        """
        Calculate reverse linear periodization parameters.

        Reverse linear starts with high intensity and gradually decreases
        while increasing volume. Good for endurance and hypertrophy goals.

        Args:
            week: Current week number (1-indexed)
            total_weeks: Total program duration

        Returns:
            Tuple of (intensity_percent, volume_modifier)
        """
        if total_weeks < 1:
            raise ValueError(f"Total weeks must be at least 1, got {total_weeks}")
        if week < 1 or week > total_weeks:
            raise ValueError(f"Week {week} out of range [1, {total_weeks}]")

        # Reverse: intensity goes from 0.90 to 0.60
        progress = (week - 1) / max(total_weeks - 1, 1)
        intensity = 0.90 - (0.30 * progress)

        # Volume increases: starts at 0.7, increases to 1.3
        volume_mod = 0.7 + (0.60 * progress)

        return (round(intensity, 3), round(volume_mod, 3))

    def calculate_deload_weeks(
        self,
        duration_weeks: int,
        experience_level: ExperienceLevel,
        model: PeriodizationModel = PeriodizationModel.LINEAR,
    ) -> List[int]:
        """
        Determine which weeks should be deload weeks.

        Args:
            duration_weeks: Total program duration
            experience_level: User's experience level
            model: Periodization model being used

        Returns:
            List of week numbers that should be deloads
        """
        deload_weeks = []
        frequency = self.DELOAD_FREQUENCY[experience_level]

        # Block periodization has deloads at phase transitions
        if model == PeriodizationModel.BLOCK:
            accum_end = int(duration_weeks * 0.4)
            trans_end = int(duration_weeks * 0.8)
            if accum_end > 0 and accum_end <= duration_weeks:
                deload_weeks.append(accum_end)
            if trans_end > 0 and trans_end <= duration_weeks and trans_end != accum_end:
                deload_weeks.append(trans_end)
            # Note: Block doesn't add final week deload - Realization phase is for peaking
        else:
            # Standard deload pattern
            week = frequency
            while week <= duration_weeks:
                deload_weeks.append(week)
                week += frequency

            # Add last week deload for 6+ week programs (except Block model)
            if duration_weeks >= 6 and duration_weeks not in deload_weeks:
                deload_weeks.append(duration_weeks)

        return sorted(deload_weeks)

    def _generate_week_notes(
        self,
        week: int,
        total_weeks: int,
        model: PeriodizationModel,
        is_deload: bool,
        phase: Optional[BlockPhase],
        effort_type: Optional[EffortType],
    ) -> Optional[str]:
        """
        Generate contextual notes for a training week.

        Args:
            week: Current week number
            total_weeks: Total program duration
            model: Periodization model
            is_deload: Whether this is a deload week
            phase: Block phase (if applicable)
            effort_type: Effort type for conjugate (if applicable)

        Returns:
            Contextual note string or None
        """
        if is_deload:
            return "Deload week - reduce weights and focus on recovery"

        if phase == BlockPhase.ACCUMULATION:
            return "Accumulation phase - focus on volume and technique"
        elif phase == BlockPhase.TRANSMUTATION:
            return "Transmutation phase - increase intensity, maintain technique"
        elif phase == BlockPhase.REALIZATION:
            return "Realization phase - peak performance, test maxes"

        if effort_type == EffortType.MAX_EFFORT:
            return "Max effort day - work up to heavy singles/triples"
        elif effort_type == EffortType.DYNAMIC_EFFORT:
            return "Dynamic effort - focus on speed and explosiveness"
        elif effort_type == EffortType.REPETITION_EFFORT:
            return "Repetition effort - hypertrophy focus with controlled tempo"

        # Week position notes
        if week == 1:
            return "Program start - establish baseline weights"
        elif week == total_weeks:
            return "Final week - test progress and reassess goals"

        return None

    def get_week_parameters(
        self,
        week: int,
        total_weeks: int,
        model: PeriodizationModel,
        goal: ProgramGoal,
        experience_level: ExperienceLevel,
        session: int = 1,
    ) -> WeekParameters:
        """
        Get complete parameters for a specific week.

        This is the main entry point that combines periodization model,
        deload detection, and goal-specific adjustments.

        Args:
            week: Current week number (1-indexed)
            total_weeks: Total program duration
            model: Periodization model to use
            goal: Training goal
            experience_level: User's experience level
            session: Session number for undulating/conjugate (default 1)

        Returns:
            WeekParameters with all training parameters
        """
        # Calculate deload weeks
        deload_weeks = self.calculate_deload_weeks(total_weeks, experience_level, model)
        is_deload = week in deload_weeks

        # Get base parameters from periodization model
        phase = None
        effort_type = None

        if model == PeriodizationModel.LINEAR:
            intensity, volume_mod = self.calculate_linear_progression(week, total_weeks)
        elif model == PeriodizationModel.UNDULATING:
            intensity, volume_mod = self.calculate_undulating_progression(week, session)
        elif model == PeriodizationModel.BLOCK:
            intensity, volume_mod, phase = self.calculate_block_progression(
                week, total_weeks
            )
        elif model == PeriodizationModel.CONJUGATE:
            intensity, volume_mod, effort_type = self.calculate_conjugate_progression(
                week, session
            )
        elif model == PeriodizationModel.REVERSE_LINEAR:
            intensity, volume_mod = self.calculate_reverse_linear_progression(
                week, total_weeks
            )
        else:
            raise ValueError(f"Unknown periodization model: {model}")

        # Scale intensity to goal-specific range
        # All models output intensity in roughly 0.50-1.0 range
        # Normalize to 0.0-1.0 then scale to goal-specific bounds
        min_int, max_int = self.INTENSITY_RANGES[goal]
        normalized = (intensity - 0.50) / 0.50  # Maps 0.50->0.0, 1.0->1.0
        normalized = min(max(normalized, 0.0), 1.0)  # Clamp to [0, 1]
        scaled_intensity = min_int + normalized * (max_int - min_int)

        # Apply deload reduction if applicable
        if is_deload:
            scaled_intensity *= 0.6  # 60% of normal intensity
            volume_mod *= 0.5  # 50% of normal volume

        # Determine training focus
        focus = WeekParameters.determine_focus(scaled_intensity, is_deload, effort_type)

        # Generate contextual notes
        notes = self._generate_week_notes(
            week=week,
            total_weeks=total_weeks,
            model=model,
            is_deload=is_deload,
            phase=phase,
            effort_type=effort_type,
        )

        return WeekParameters(
            week_number=week,
            intensity_percent=round(scaled_intensity, 3),
            volume_modifier=round(volume_mod, 3),
            is_deload=is_deload,
            phase=phase,
            effort_type=effort_type,
            focus=focus,
            notes=notes,
        )

    def select_periodization_model(
        self,
        goal: ProgramGoal,
        experience_level: ExperienceLevel,
        duration_weeks: int,
    ) -> PeriodizationModel:
        """
        Recommend a periodization model based on user parameters.

        Args:
            goal: Training goal
            experience_level: User's experience level
            duration_weeks: Program duration

        Returns:
            Recommended PeriodizationModel
        """
        # Strength goals benefit from block or conjugate
        if goal == ProgramGoal.STRENGTH:
            if experience_level == ExperienceLevel.ADVANCED:
                return PeriodizationModel.CONJUGATE
            elif duration_weeks >= 8:
                return PeriodizationModel.BLOCK
            return PeriodizationModel.LINEAR

        # Hypertrophy benefits from undulating or reverse linear
        if goal == ProgramGoal.HYPERTROPHY:
            if experience_level in [
                ExperienceLevel.INTERMEDIATE,
                ExperienceLevel.ADVANCED,
            ]:
                return PeriodizationModel.UNDULATING
            return PeriodizationModel.LINEAR

        # Endurance benefits from reverse linear
        if goal == ProgramGoal.ENDURANCE:
            return PeriodizationModel.REVERSE_LINEAR

        # Weight loss uses linear for simplicity
        if goal == ProgramGoal.WEIGHT_LOSS:
            return PeriodizationModel.LINEAR

        # Sport specific depends on competition timing
        if goal == ProgramGoal.SPORT_SPECIFIC:
            if duration_weeks >= 12:
                return PeriodizationModel.BLOCK
            return PeriodizationModel.UNDULATING

        # General fitness: keep it simple
        return PeriodizationModel.LINEAR

    def plan_progression(
        self,
        duration_weeks: int,
        goal: ProgramGoal,
        experience_level: ExperienceLevel,
        model: Optional[PeriodizationModel] = None,
    ) -> List[WeekParameters]:
        """
        Plan the complete periodization structure for a program.

        Args:
            duration_weeks: Total program duration
            goal: Primary training goal
            experience_level: User's experience level
            model: Optional periodization model (auto-selected if None)

        Returns:
            List of WeekParameters for each week
        """
        if model is None:
            model = self.select_periodization_model(goal, experience_level, duration_weeks)

        weeks = []
        for week in range(1, duration_weeks + 1):
            params = self.get_week_parameters(
                week=week,
                total_weeks=duration_weeks,
                model=model,
                goal=goal,
                experience_level=experience_level,
            )
            weeks.append(params)

        return weeks

    def get_volume_limits(
        self,
        experience_level: ExperienceLevel,
    ) -> dict:
        """
        Get volume limits (weekly sets per muscle group) for an experience level.

        Args:
            experience_level: User's experience level

        Returns:
            Dict with 'min' and 'max' weekly set recommendations
        """
        return self.VOLUME_LIMITS[experience_level].copy()

    def get_intensity_target(
        self,
        week_number: int,
        total_weeks: int,
        goal: ProgramGoal,
    ) -> float:
        """
        Calculate target intensity for a given week using linear model.

        Args:
            week_number: Current week (1-indexed)
            total_weeks: Total program duration
            goal: Training goal

        Returns:
            Target intensity as percentage (0.0-1.0)

        Raises:
            ValueError: If total_weeks < 1 or week_number out of range
        """
        if total_weeks < 1:
            raise ValueError(f"Total weeks must be at least 1, got {total_weeks}")
        if week_number < 1 or week_number > total_weeks:
            raise ValueError(f"Week {week_number} out of range [1, {total_weeks}]")

        intensity, _ = self.calculate_linear_progression(week_number, total_weeks)

        # Scale to goal range using same formula as get_week_parameters
        # Normalize from assumed 0.50-1.0 range to 0.0-1.0, then scale to goal bounds
        min_int, max_int = self.INTENSITY_RANGES[goal]
        normalized = (intensity - 0.50) / 0.50  # Maps 0.50->0.0, 1.0->1.0
        normalized = min(max(normalized, 0.0), 1.0)  # Clamp to [0, 1]
        scaled = min_int + normalized * (max_int - min_int)

        return round(scaled, 3)
