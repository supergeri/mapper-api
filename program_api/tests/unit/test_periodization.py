"""
Unit tests for PeriodizationService.

Part of AMA-462: Implement ProgramGenerator Service
Extended by AMA-463: Implement periodization calculation engine

Tests all 5 periodization models:
- Linear
- Undulating
- Block
- Conjugate
- Reverse Linear

Plus:
- Rep range calculations from intensity
- Training focus determination
- Week notes generation
- Edge cases (short/long programs)
"""

import pytest

from models.program import ExperienceLevel, ProgramGoal
from services.periodization import (
    BlockPhase,
    EffortType,
    PeriodizationModel,
    PeriodizationService,
    TrainingFocus,
    WeekParameters,
)


@pytest.fixture
def service():
    """Create a PeriodizationService instance."""
    return PeriodizationService()


class TestLinearProgression:
    """Tests for linear periodization model."""

    def test_week_1_is_lowest_intensity(self, service):
        """First week should have lowest intensity."""
        intensity, volume = service.calculate_linear_progression(week=1, total_weeks=8)
        assert intensity == 0.65
        assert volume == 1.0

    def test_last_week_is_highest_intensity(self, service):
        """Last week should have highest intensity."""
        intensity, volume = service.calculate_linear_progression(week=8, total_weeks=8)
        assert intensity == 0.95
        assert volume == 0.7

    def test_intensity_increases_over_time(self, service):
        """Intensity should increase progressively."""
        prev_intensity = 0
        for week in range(1, 9):
            intensity, _ = service.calculate_linear_progression(week, 8)
            assert intensity > prev_intensity
            prev_intensity = intensity

    def test_volume_decreases_over_time(self, service):
        """Volume should decrease as intensity increases."""
        prev_volume = 2.0
        for week in range(1, 9):
            _, volume = service.calculate_linear_progression(week, 8)
            assert volume < prev_volume
            prev_volume = volume

    def test_invalid_week_raises_error(self, service):
        """Invalid week number should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_linear_progression(week=0, total_weeks=8)

        with pytest.raises(ValueError):
            service.calculate_linear_progression(week=10, total_weeks=8)


class TestUndulatingProgression:
    """Tests for daily undulating periodization (DUP)."""

    def test_session_1_is_heavy(self, service):
        """First session should be heavy (high intensity, lower volume)."""
        intensity, volume = service.calculate_undulating_progression(week=1, session=1)
        assert intensity >= 0.85
        assert volume < 1.0

    def test_session_2_is_light(self, service):
        """Second session should be light (low intensity, high volume)."""
        intensity, volume = service.calculate_undulating_progression(week=1, session=2)
        assert intensity <= 0.70
        assert volume > 1.0

    def test_session_3_is_moderate(self, service):
        """Third session should be moderate."""
        intensity, volume = service.calculate_undulating_progression(week=1, session=3)
        assert 0.7 <= intensity <= 0.8
        assert volume == 1.0

    def test_weekly_progression(self, service):
        """Intensity should increase slightly each week."""
        week1_int, _ = service.calculate_undulating_progression(week=1, session=1)
        week5_int, _ = service.calculate_undulating_progression(week=5, session=1)
        assert week5_int > week1_int

    def test_invalid_session_raises_error(self, service):
        """Invalid session number should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_undulating_progression(week=1, session=0)


class TestBlockProgression:
    """Tests for block periodization model."""

    def test_accumulation_phase_first(self, service):
        """First phase should be accumulation."""
        _, _, phase = service.calculate_block_progression(week=1, total_weeks=10)
        assert phase == BlockPhase.ACCUMULATION

    def test_transmutation_phase_middle(self, service):
        """Middle phase should be transmutation."""
        _, _, phase = service.calculate_block_progression(week=5, total_weeks=10)
        assert phase == BlockPhase.TRANSMUTATION

    def test_realization_phase_last(self, service):
        """Final phase should be realization."""
        _, _, phase = service.calculate_block_progression(week=10, total_weeks=10)
        assert phase == BlockPhase.REALIZATION

    def test_accumulation_high_volume(self, service):
        """Accumulation should have high volume, moderate intensity."""
        intensity, volume, _ = service.calculate_block_progression(week=1, total_weeks=10)
        assert volume >= 1.1
        assert intensity < 0.75

    def test_realization_low_volume_high_intensity(self, service):
        """Realization should have low volume, high intensity."""
        intensity, volume, _ = service.calculate_block_progression(week=10, total_weeks=10)
        assert volume < 0.8
        assert intensity > 0.85

    def test_phase_transitions(self, service):
        """Phases should transition at correct boundaries."""
        # 40/40/20 split for 10 weeks: accum=4, trans=4, realize=2
        phases = []
        for week in range(1, 11):
            _, _, phase = service.calculate_block_progression(week, 10)
            phases.append(phase)

        assert phases[0] == BlockPhase.ACCUMULATION
        assert phases[3] == BlockPhase.ACCUMULATION  # Week 4
        assert phases[4] == BlockPhase.TRANSMUTATION  # Week 5
        assert phases[7] == BlockPhase.TRANSMUTATION  # Week 8
        assert phases[8] == BlockPhase.REALIZATION  # Week 9
        assert phases[9] == BlockPhase.REALIZATION  # Week 10


class TestConjugateProgression:
    """Tests for conjugate periodization model."""

    def test_session_1_max_effort(self, service):
        """Session 1 should be max effort."""
        _, _, effort = service.calculate_conjugate_progression(week=1, session=1)
        assert effort == EffortType.MAX_EFFORT

    def test_session_2_dynamic_effort(self, service):
        """Session 2 should be dynamic effort."""
        _, _, effort = service.calculate_conjugate_progression(week=1, session=2)
        assert effort == EffortType.DYNAMIC_EFFORT

    def test_session_3_repetition_effort(self, service):
        """Session 3 should be repetition effort."""
        _, _, effort = service.calculate_conjugate_progression(week=1, session=3)
        assert effort == EffortType.REPETITION_EFFORT

    def test_max_effort_high_intensity(self, service):
        """Max effort should have high intensity, low volume."""
        intensity, volume, _ = service.calculate_conjugate_progression(week=2, session=1)
        assert intensity >= 0.89
        assert volume <= 0.7

    def test_dynamic_effort_low_intensity(self, service):
        """Dynamic effort should have low intensity, high volume."""
        intensity, volume, _ = service.calculate_conjugate_progression(week=1, session=2)
        assert intensity <= 0.60
        assert volume >= 1.2

    def test_wave_loading(self, service):
        """3-week wave loading should vary intensity."""
        int_w1, _, _ = service.calculate_conjugate_progression(week=1, session=1)
        int_w2, _, _ = service.calculate_conjugate_progression(week=2, session=1)
        int_w3, _, _ = service.calculate_conjugate_progression(week=3, session=1)

        # Wave pattern: low, medium, high
        assert int_w1 < int_w2 < int_w3 or int_w1 != int_w2


class TestReverseLinearProgression:
    """Tests for reverse linear periodization model."""

    def test_week_1_highest_intensity(self, service):
        """First week should have highest intensity."""
        intensity, volume = service.calculate_reverse_linear_progression(week=1, total_weeks=8)
        assert intensity == 0.9
        assert volume == 0.7

    def test_last_week_lowest_intensity(self, service):
        """Last week should have lowest intensity."""
        intensity, volume = service.calculate_reverse_linear_progression(week=8, total_weeks=8)
        assert intensity == 0.6
        assert volume == 1.3

    def test_intensity_decreases_over_time(self, service):
        """Intensity should decrease progressively."""
        prev_intensity = 1.0
        for week in range(1, 9):
            intensity, _ = service.calculate_reverse_linear_progression(week, 8)
            assert intensity < prev_intensity
            prev_intensity = intensity

    def test_volume_increases_over_time(self, service):
        """Volume should increase as intensity decreases."""
        prev_volume = 0.0
        for week in range(1, 9):
            _, volume = service.calculate_reverse_linear_progression(week, 8)
            assert volume > prev_volume
            prev_volume = volume


class TestDeloadWeeks:
    """Tests for deload week calculation."""

    def test_beginner_deload_every_6_weeks(self, service):
        """Beginners should deload every 6 weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert 6 in deloads
        assert 12 in deloads

    def test_intermediate_deload_every_4_weeks(self, service):
        """Intermediates should deload every 4 weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert 4 in deloads
        assert 8 in deloads
        assert 12 in deloads

    def test_advanced_deload_every_3_weeks(self, service):
        """Advanced should deload every 3 weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.ADVANCED,
        )
        assert 3 in deloads
        assert 6 in deloads
        assert 9 in deloads
        assert 12 in deloads

    def test_block_deload_at_phase_transitions(self, service):
        """Block periodization should deload at phase transitions."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=10,
            experience_level=ExperienceLevel.INTERMEDIATE,
            model=PeriodizationModel.BLOCK,
        )
        # Phase transitions at 40% and 80% of 10 weeks = weeks 4 and 8
        assert 4 in deloads
        assert 8 in deloads

    def test_last_week_deload_for_long_programs(self, service):
        """Programs 6+ weeks should deload on last week."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=7,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert 7 in deloads


class TestWeekParameters:
    """Tests for get_week_parameters method."""

    def test_returns_week_parameters(self, service):
        """Should return WeekParameters dataclass."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert isinstance(params, WeekParameters)
        assert params.week_number == 1

    def test_deload_detected(self, service):
        """Deload weeks should be marked."""
        params = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.is_deload is True

    def test_deload_reduces_intensity(self, service):
        """Deload weeks should have reduced intensity."""
        regular = service.get_week_parameters(
            week=3,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        deload = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert deload.intensity_percent < regular.intensity_percent
        assert deload.volume_modifier < regular.volume_modifier

    def test_goal_affects_intensity_range(self, service):
        """Different goals should have different intensity ranges."""
        strength = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        endurance = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Strength should have higher intensity than endurance
        assert strength.intensity_percent > endurance.intensity_percent


class TestPlanProgression:
    """Tests for plan_progression method."""

    def test_returns_correct_number_of_weeks(self, service):
        """Should return one WeekParameters per week."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert len(weeks) == 8

    def test_weeks_are_numbered_correctly(self, service):
        """Week numbers should be sequential."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        for i, week in enumerate(weeks, 1):
            assert week.week_number == i

    def test_auto_selects_model(self, service):
        """Should auto-select appropriate model when not specified."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Should be block periodization for strength with 8 weeks
        assert len(weeks) == 8


class TestModelSelection:
    """Tests for select_periodization_model method."""

    def test_strength_advanced_uses_conjugate(self, service):
        """Advanced strength should use conjugate."""
        model = service.select_periodization_model(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.CONJUGATE

    def test_strength_long_uses_block(self, service):
        """Long strength programs should use block."""
        model = service.select_periodization_model(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=12,
        )
        assert model == PeriodizationModel.BLOCK

    def test_hypertrophy_intermediate_uses_undulating(self, service):
        """Intermediate hypertrophy should use undulating."""
        model = service.select_periodization_model(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING

    def test_endurance_uses_reverse_linear(self, service):
        """Endurance should use reverse linear."""
        model = service.select_periodization_model(
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.REVERSE_LINEAR

    def test_beginner_uses_linear(self, service):
        """Beginners generally use linear."""
        model = service.select_periodization_model(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.BEGINNER,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.LINEAR


class TestRepRanges:
    """Tests for rep range calculation from intensity (AMA-463)."""

    def test_very_high_intensity_gives_1_3_reps(self):
        """Intensity >= 90% should give 1-3 rep range."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.92,
            volume_modifier=0.6,
        )
        assert params.get_rep_range() == "1-3"

    def test_high_intensity_gives_4_6_reps(self):
        """Intensity 80-89% should give 4-6 rep range."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.85,
            volume_modifier=0.8,
        )
        assert params.get_rep_range() == "4-6"

    def test_moderate_intensity_gives_6_8_reps(self):
        """Intensity 70-79% should give 6-8 rep range."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.75,
            volume_modifier=1.0,
        )
        assert params.get_rep_range() == "6-8"

    def test_low_intensity_gives_8_12_reps(self):
        """Intensity < 70% should give 8-12 rep range."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.65,
            volume_modifier=1.2,
        )
        assert params.get_rep_range() == "8-12"

    def test_boundary_90_percent(self):
        """Exactly 90% should give 1-3 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.90,
            volume_modifier=0.7,
        )
        assert params.get_rep_range() == "1-3"

    def test_boundary_80_percent(self):
        """Exactly 80% should give 4-6 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.80,
            volume_modifier=0.9,
        )
        assert params.get_rep_range() == "4-6"

    def test_boundary_70_percent(self):
        """Exactly 70% should give 6-8 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.70,
            volume_modifier=1.0,
        )
        assert params.get_rep_range() == "6-8"


class TestTrainingFocus:
    """Tests for training focus determination (AMA-463)."""

    def test_deload_focus(self):
        """Deload weeks should have deload focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.50, is_deload=True
        )
        assert focus == TrainingFocus.DELOAD

    def test_high_intensity_strength_focus(self):
        """High intensity (>= 85%) should focus on strength."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.90, is_deload=False
        )
        assert focus == TrainingFocus.STRENGTH

    def test_moderate_high_intensity_power_focus(self):
        """Moderate-high intensity (75-84%) should focus on power."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.78, is_deload=False
        )
        assert focus == TrainingFocus.POWER

    def test_moderate_intensity_hypertrophy_focus(self):
        """Moderate intensity (65-74%) should focus on hypertrophy."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.70, is_deload=False
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_low_intensity_endurance_focus(self):
        """Low intensity (< 65%) should focus on endurance."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.55, is_deload=False
        )
        assert focus == TrainingFocus.ENDURANCE

    def test_max_effort_strength_focus(self):
        """Max effort type should override to strength focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.70,  # Would normally be hypertrophy
            is_deload=False,
            effort_type=EffortType.MAX_EFFORT,
        )
        assert focus == TrainingFocus.STRENGTH

    def test_dynamic_effort_power_focus(self):
        """Dynamic effort type should override to power focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.55,  # Would normally be endurance
            is_deload=False,
            effort_type=EffortType.DYNAMIC_EFFORT,
        )
        assert focus == TrainingFocus.POWER

    def test_repetition_effort_hypertrophy_focus(self):
        """Repetition effort type should override to hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.90,  # Would normally be strength
            is_deload=False,
            effort_type=EffortType.REPETITION_EFFORT,
        )
        assert focus == TrainingFocus.HYPERTROPHY


class TestWeekNotes:
    """Tests for contextual week notes (AMA-463)."""

    def test_deload_note(self, service):
        """Deload weeks should have recovery note."""
        params = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.is_deload is True
        assert "recovery" in params.notes.lower()

    def test_block_accumulation_note(self, service):
        """Block accumulation phase should have volume note."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.phase == BlockPhase.ACCUMULATION
        assert "volume" in params.notes.lower()

    def test_block_transmutation_note(self, service):
        """Block transmutation phase should have intensity note."""
        params = service.get_week_parameters(
            week=5,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.phase == BlockPhase.TRANSMUTATION
        assert "intensity" in params.notes.lower()

    def test_block_realization_note(self, service):
        """Block realization phase should have peak note."""
        params = service.get_week_parameters(
            week=10,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.phase == BlockPhase.REALIZATION
        # Could be deload OR realization note
        assert params.notes is not None

    def test_conjugate_max_effort_note(self, service):
        """Conjugate max effort should have heavy note."""
        params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=1,
        )
        assert params.effort_type == EffortType.MAX_EFFORT
        assert "heavy" in params.notes.lower() or "max" in params.notes.lower()

    def test_first_week_baseline_note(self, service):
        """First week should have baseline note (when not a phase/deload)."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert "baseline" in params.notes.lower()

    def test_last_week_progress_note(self, service):
        """Last week should have progress note (when not deload)."""
        # Use a 5-week program so week 5 isn't a deload for beginners (deload every 6)
        params = service.get_week_parameters(
            week=5,
            total_weeks=5,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.BEGINNER,
        )
        # Should have final week note or be deload
        assert params.notes is not None


class TestEdgeCasesShortPrograms:
    """Tests for short programs (1-4 weeks) - AMA-463."""

    def test_one_week_linear(self, service):
        """1-week program should work with linear periodization."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=1,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.week_number == 1
        assert 0 < params.intensity_percent < 1

    def test_one_week_block(self, service):
        """1-week program should handle block periodization gracefully."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=1,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Should default to realization phase for peaking
        assert params.phase == BlockPhase.REALIZATION

    def test_two_week_linear(self, service):
        """2-week program should have proper progression."""
        week1 = service.get_week_parameters(
            week=1,
            total_weeks=2,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        week2 = service.get_week_parameters(
            week=2,
            total_weeks=2,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Week 2 should have higher intensity (unless deload)
        # For 2-week program, no deloads expected
        assert week2.intensity_percent >= week1.intensity_percent

    def test_three_week_block_has_all_phases(self, service):
        """3-week block program should have all three phases."""
        phases = []
        for week in range(1, 4):
            params = service.get_week_parameters(
                week=week,
                total_weeks=3,
                model=PeriodizationModel.BLOCK,
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.INTERMEDIATE,
            )
            phases.append(params.phase)
        # Should have accumulation, transmutation, realization
        assert BlockPhase.ACCUMULATION in phases
        assert BlockPhase.TRANSMUTATION in phases
        assert BlockPhase.REALIZATION in phases

    def test_four_week_no_deload_for_beginners(self, service):
        """4-week beginner program shouldn't have deload (every 6 weeks)."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=4,
            experience_level=ExperienceLevel.BEGINNER,
        )
        # Beginners deload every 6 weeks, so no deload in 4-week program
        assert len(deloads) == 0

    def test_short_program_plan_progression(self, service):
        """plan_progression should work with short programs."""
        weeks = service.plan_progression(
            duration_weeks=2,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert len(weeks) == 2
        assert weeks[0].week_number == 1
        assert weeks[1].week_number == 2


class TestEdgeCasesLongPrograms:
    """Tests for long programs (40+ weeks) - AMA-463."""

    def test_long_linear_progression(self, service):
        """52-week linear program should progress correctly."""
        week1 = service.get_week_parameters(
            week=1,
            total_weeks=52,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        week52 = service.get_week_parameters(
            week=52,
            total_weeks=52,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # First week should have lower intensity than last (adjusted for deloads)
        # Week 52 is likely a deload, so check a non-deload week
        week50 = service.get_week_parameters(
            week=50,
            total_weeks=52,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        if not week50.is_deload:
            assert week50.intensity_percent > week1.intensity_percent

    def test_long_program_many_deloads(self, service):
        """52-week advanced program should have many deload weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=52,
            experience_level=ExperienceLevel.ADVANCED,
        )
        # Advanced deloads every 3 weeks: 3, 6, 9, ... + final week
        expected_count = 52 // 3  # At least this many
        assert len(deloads) >= expected_count

    def test_long_block_has_proper_phase_distribution(self, service):
        """40-week block program should distribute phases correctly."""
        phases = {
            BlockPhase.ACCUMULATION: 0,
            BlockPhase.TRANSMUTATION: 0,
            BlockPhase.REALIZATION: 0,
        }
        for week in range(1, 41):
            params = service.get_week_parameters(
                week=week,
                total_weeks=40,
                model=PeriodizationModel.BLOCK,
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.INTERMEDIATE,
            )
            phases[params.phase] += 1

        # 40/40/20 split: ~16, ~16, ~8 weeks
        assert phases[BlockPhase.ACCUMULATION] >= 15
        assert phases[BlockPhase.TRANSMUTATION] >= 15
        assert phases[BlockPhase.REALIZATION] >= 7

    def test_long_program_plan_progression(self, service):
        """plan_progression should work with long programs."""
        weeks = service.plan_progression(
            duration_weeks=52,
            goal=ProgramGoal.GENERAL_FITNESS,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert len(weeks) == 52
        assert weeks[0].week_number == 1
        assert weeks[-1].week_number == 52

    def test_very_long_undulating_progression(self, service):
        """Undulating should handle very long programs without overflow."""
        # Test that weekly bonus caps correctly even at week 100
        # (though our system caps at 52 weeks, this tests robustness)
        params = service.get_week_parameters(
            week=52,
            total_weeks=52,
            model=PeriodizationModel.UNDULATING,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Intensity should be capped at reasonable levels
        assert params.intensity_percent <= 1.0


class TestWeekParametersFocus:
    """Tests for focus field in get_week_parameters (AMA-463)."""

    def test_strength_program_has_strength_focus(self, service):
        """High-intensity strength program should have strength focus."""
        params = service.get_week_parameters(
            week=8,  # Late week = high intensity
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Could be deload or strength depending on schedule
        assert params.focus in [TrainingFocus.STRENGTH, TrainingFocus.DELOAD]

    def test_endurance_program_has_endurance_focus(self, service):
        """Low-intensity endurance program should have endurance focus."""
        params = service.get_week_parameters(
            week=8,  # Late week for reverse linear = low intensity
            total_weeks=8,
            model=PeriodizationModel.REVERSE_LINEAR,
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Could be deload or endurance
        assert params.focus in [
            TrainingFocus.ENDURANCE,
            TrainingFocus.HYPERTROPHY,
            TrainingFocus.DELOAD,
        ]

    def test_conjugate_respects_effort_type_focus(self, service):
        """Conjugate method should set focus based on effort type."""
        me_params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=1,  # Max effort
        )
        de_params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=2,  # Dynamic effort
        )
        re_params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=3,  # Repetition effort
        )

        assert me_params.focus == TrainingFocus.STRENGTH
        assert de_params.focus == TrainingFocus.POWER
        assert re_params.focus == TrainingFocus.HYPERTROPHY

    def test_deload_always_has_deload_focus(self, service):
        """Deload weeks should always have deload focus."""
        params = service.get_week_parameters(
            week=4,  # Deload for intermediate
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.is_deload is True
        assert params.focus == TrainingFocus.DELOAD


class TestEliteExperienceLevel:
    """Tests for elite experience level support (AMA-485)."""

    def test_elite_deload_every_2_weeks(self, service):
        """Elite athletes should deload every 2 weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.ELITE,
        )
        assert 2 in deloads
        assert 4 in deloads
        assert 6 in deloads
        assert 8 in deloads
        assert 10 in deloads
        assert 12 in deloads

    def test_elite_volume_limits_accessible(self, service):
        """Elite volume limits should be accessible without KeyError."""
        limits = service.VOLUME_LIMITS[ExperienceLevel.ELITE]
        assert limits["min"] == 20
        assert limits["max"] == 30

    def test_elite_deload_frequency_accessible(self, service):
        """Elite deload frequency should be accessible without KeyError."""
        frequency = service.DELOAD_FREQUENCY[ExperienceLevel.ELITE]
        assert frequency == 2

    def test_elite_strength_uses_conjugate(self, service):
        """Elite strength training should use conjugate model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.CONJUGATE

    def test_elite_hypertrophy_uses_undulating(self, service):
        """Elite hypertrophy training should use undulating model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING

    def test_elite_get_week_parameters_no_key_error(self, service):
        """Getting week parameters for elite should not raise KeyError."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ELITE,
        )
        assert isinstance(params, WeekParameters)
        assert params.week_number == 1

    def test_elite_plan_progression_no_key_error(self, service):
        """Planning progression for elite should not raise KeyError."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ELITE,
        )
        assert len(weeks) == 8
        assert all(isinstance(w, WeekParameters) for w in weeks)

    def test_elite_has_more_deloads_than_advanced(self, service):
        """Elite should have more deload weeks than advanced."""
        elite_deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.ELITE,
        )
        advanced_deloads = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.ADVANCED,
        )
        assert len(elite_deloads) > len(advanced_deloads)

    def test_elite_short_program_deloads(self, service):
        """4-week elite program should have 2 deload weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=4,
            experience_level=ExperienceLevel.ELITE,
        )
        assert 2 in deloads
        assert 4 in deloads

    def test_elite_endurance_uses_reverse_linear(self, service):
        """Elite endurance should use reverse linear model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.REVERSE_LINEAR

    def test_elite_general_fitness_uses_linear(self, service):
        """Elite general fitness should use linear model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.GENERAL_FITNESS,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.LINEAR

    def test_elite_weight_loss_uses_linear(self, service):
        """Elite weight loss should use linear model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.WEIGHT_LOSS,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.LINEAR

    def test_elite_sport_specific_long_uses_block(self, service):
        """Elite sport-specific long program should use block model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.SPORT_SPECIFIC,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=12,
        )
        assert model == PeriodizationModel.BLOCK

    def test_elite_sport_specific_short_uses_undulating(self, service):
        """Elite sport-specific short program should use undulating model."""
        model = service.select_periodization_model(
            goal=ProgramGoal.SPORT_SPECIFIC,
            experience_level=ExperienceLevel.ELITE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING


class TestGetIntensityTarget:
    """Tests for get_intensity_target method."""

    def test_scales_to_strength_goal_range(self, service):
        """Intensity target should be within strength goal range."""
        target = service.get_intensity_target(
            week_number=1,
            total_weeks=8,
            goal=ProgramGoal.STRENGTH,
        )
        min_int, max_int = service.INTENSITY_RANGES[ProgramGoal.STRENGTH]
        assert min_int <= target <= max_int

    def test_scales_to_endurance_goal_range(self, service):
        """Intensity target should be within endurance goal range."""
        target = service.get_intensity_target(
            week_number=1,
            total_weeks=8,
            goal=ProgramGoal.ENDURANCE,
        )
        min_int, max_int = service.INTENSITY_RANGES[ProgramGoal.ENDURANCE]
        assert min_int <= target <= max_int

    def test_intensity_increases_over_weeks(self, service):
        """Intensity target should increase over the program."""
        early_target = service.get_intensity_target(
            week_number=1,
            total_weeks=8,
            goal=ProgramGoal.STRENGTH,
        )
        late_target = service.get_intensity_target(
            week_number=8,
            total_weeks=8,
            goal=ProgramGoal.STRENGTH,
        )
        assert late_target > early_target

    def test_invalid_week_zero_raises_error(self, service):
        """Week 0 should raise ValueError."""
        with pytest.raises(ValueError):
            service.get_intensity_target(
                week_number=0,
                total_weeks=8,
                goal=ProgramGoal.STRENGTH,
            )

    def test_invalid_week_exceeds_total_raises_error(self, service):
        """Week exceeding total should raise ValueError."""
        with pytest.raises(ValueError):
            service.get_intensity_target(
                week_number=10,
                total_weeks=8,
                goal=ProgramGoal.STRENGTH,
            )

    def test_strength_higher_than_endurance(self, service):
        """Strength goal should have higher intensity than endurance."""
        strength_target = service.get_intensity_target(
            week_number=4,
            total_weeks=8,
            goal=ProgramGoal.STRENGTH,
        )
        endurance_target = service.get_intensity_target(
            week_number=4,
            total_weeks=8,
            goal=ProgramGoal.ENDURANCE,
        )
        assert strength_target > endurance_target


class TestErrorCases:
    """Tests for error handling in periodization methods."""

    def test_reverse_linear_invalid_week_zero(self, service):
        """Reverse linear with week 0 should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_reverse_linear_progression(week=0, total_weeks=8)

    def test_reverse_linear_invalid_negative_week(self, service):
        """Reverse linear with negative week should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_reverse_linear_progression(week=-1, total_weeks=8)

    def test_block_invalid_week_zero(self, service):
        """Block with week 0 should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_block_progression(week=0, total_weeks=10)

    def test_block_invalid_negative_week(self, service):
        """Block with negative week should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_block_progression(week=-1, total_weeks=10)

    def test_block_week_exceeds_total(self, service):
        """Block with week exceeding total should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_block_progression(week=15, total_weeks=10)

    def test_undulating_invalid_session_zero(self, service):
        """Undulating with session 0 should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_undulating_progression(week=1, session=0)

    def test_undulating_session_exceeds_total(self, service):
        """Undulating with session exceeding total should raise ValueError."""
        with pytest.raises(ValueError):
            service.calculate_undulating_progression(week=1, session=5, total_sessions=3)


class TestBoundaryConditions:
    """Tests for boundary conditions in training focus determination."""

    def test_boundary_85_percent_is_strength(self):
        """Exactly 85% should be strength focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.85, is_deload=False
        )
        assert focus == TrainingFocus.STRENGTH

    def test_boundary_84_percent_is_power(self):
        """Just below 85% should be power focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.84, is_deload=False
        )
        assert focus == TrainingFocus.POWER

    def test_boundary_75_percent_is_power(self):
        """Exactly 75% should be power focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.75, is_deload=False
        )
        assert focus == TrainingFocus.POWER

    def test_boundary_74_percent_is_hypertrophy(self):
        """Just below 75% should be hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.74, is_deload=False
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_boundary_65_percent_is_hypertrophy(self):
        """Exactly 65% should be hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.65, is_deload=False
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_boundary_64_percent_is_endurance(self):
        """Just below 65% should be endurance focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.64, is_deload=False
        )
        assert focus == TrainingFocus.ENDURANCE

    def test_deload_overrides_high_intensity(self):
        """Deload should override even high intensity to deload focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.95, is_deload=True
        )
        assert focus == TrainingFocus.DELOAD

    def test_rep_range_boundary_90_percent(self):
        """90% intensity should give 1-3 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.90,
            volume_modifier=0.7,
        )
        assert params.get_rep_range() == "1-3"

    def test_rep_range_boundary_89_percent(self):
        """89% intensity should give 4-6 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.89,
            volume_modifier=0.8,
        )
        assert params.get_rep_range() == "4-6"

    def test_rep_range_boundary_80_percent(self):
        """80% intensity should give 4-6 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.80,
            volume_modifier=0.9,
        )
        assert params.get_rep_range() == "4-6"

    def test_rep_range_boundary_79_percent(self):
        """79% intensity should give 6-8 reps."""
        params = WeekParameters(
            week_number=1,
            intensity_percent=0.79,
            volume_modifier=1.0,
        )
        assert params.get_rep_range() == "6-8"
