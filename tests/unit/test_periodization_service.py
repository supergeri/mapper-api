"""
Unit tests for PeriodizationService.

Part of AMA-463: Implement periodization calculation engine

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
- Error handling
- Model selection for all goals
"""

import pytest

from backend.core.periodization_service import (
    BlockPhase,
    EffortType,
    ExperienceLevel,
    PeriodizationModel,
    PeriodizationService,
    ProgramGoal,
    TrainingFocus,
    WeekParameters,
)


@pytest.fixture
def service():
    """Create a PeriodizationService instance."""
    return PeriodizationService()


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
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


@pytest.mark.unit
class TestRepRanges:
    """Tests for rep range calculation from intensity."""

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


@pytest.mark.unit
class TestTrainingFocus:
    """Tests for training focus determination."""

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

    def test_max_effort_strength_focus(self):
        """Max effort type should override to strength focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.70,
            is_deload=False,
            effort_type=EffortType.MAX_EFFORT,
        )
        assert focus == TrainingFocus.STRENGTH


@pytest.mark.unit
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


@pytest.mark.unit
class TestEdgeCases:
    """Tests for edge cases (short/long programs)."""

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


# =============================================================================
# Additional Tests from Testing Strategist Review
# =============================================================================


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling and validation."""

    def test_block_progression_invalid_week_zero_raises_error(self, service):
        """Block progression should raise ValueError for week 0."""
        with pytest.raises(ValueError):
            service.calculate_block_progression(week=0, total_weeks=10)

    def test_block_progression_invalid_week_exceeds_total_raises_error(self, service):
        """Block progression should raise ValueError for week > total."""
        with pytest.raises(ValueError):
            service.calculate_block_progression(week=11, total_weeks=10)

    def test_reverse_linear_invalid_week_zero_raises_error(self, service):
        """Reverse linear should raise ValueError for week 0."""
        with pytest.raises(ValueError):
            service.calculate_reverse_linear_progression(week=0, total_weeks=8)

    def test_reverse_linear_invalid_week_exceeds_total_raises_error(self, service):
        """Reverse linear should raise ValueError for week > total."""
        with pytest.raises(ValueError):
            service.calculate_reverse_linear_progression(week=10, total_weeks=8)

    def test_undulating_session_exceeds_total_raises_error(self, service):
        """Undulating should raise ValueError for session > total_sessions."""
        with pytest.raises(ValueError):
            service.calculate_undulating_progression(week=1, session=4, total_sessions=3)


@pytest.mark.unit
class TestGetIntensityTarget:
    """Tests for get_intensity_target method."""

    def test_returns_scaled_intensity_for_strength_goal(self, service):
        """Intensity should be scaled to strength-specific range."""
        intensity = service.get_intensity_target(
            week_number=4, total_weeks=8, goal=ProgramGoal.STRENGTH
        )
        min_int, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.STRENGTH]
        assert min_int <= intensity <= max_int

    def test_returns_scaled_intensity_for_hypertrophy_goal(self, service):
        """Intensity should be scaled to hypertrophy-specific range."""
        intensity = service.get_intensity_target(
            week_number=4, total_weeks=8, goal=ProgramGoal.HYPERTROPHY
        )
        min_int, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.HYPERTROPHY]
        assert min_int <= intensity <= max_int

    def test_intensity_increases_over_weeks(self, service):
        """Intensity should increase over the program duration."""
        week1 = service.get_intensity_target(1, 8, ProgramGoal.HYPERTROPHY)
        week8 = service.get_intensity_target(8, 8, ProgramGoal.HYPERTROPHY)
        assert week8 > week1

    def test_first_week_at_minimum_range(self, service):
        """First week intensity should be at or near minimum for goal."""
        intensity = service.get_intensity_target(1, 8, ProgramGoal.ENDURANCE)
        min_int, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.ENDURANCE]
        # First week should be in lower portion of range (below midpoint)
        midpoint = (min_int + max_int) / 2
        assert intensity < midpoint

    def test_last_week_at_maximum_range(self, service):
        """Last week intensity should be at or near maximum for goal."""
        intensity = service.get_intensity_target(8, 8, ProgramGoal.STRENGTH)
        _, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.STRENGTH]
        # Last week should be close to maximum
        assert intensity >= max_int - 0.05


@pytest.mark.unit
class TestTrainingFocusExtended:
    """Extended tests for training focus determination."""

    def test_dynamic_effort_power_focus(self):
        """Dynamic effort type should return power focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.55,
            is_deload=False,
            effort_type=EffortType.DYNAMIC_EFFORT,
        )
        assert focus == TrainingFocus.POWER

    def test_repetition_effort_hypertrophy_focus(self):
        """Repetition effort type should return hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.70,
            is_deload=False,
            effort_type=EffortType.REPETITION_EFFORT,
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_low_intensity_endurance_focus(self):
        """Low intensity (< 65%) should return endurance focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.60, is_deload=False
        )
        assert focus == TrainingFocus.ENDURANCE

    def test_moderate_intensity_hypertrophy_focus(self):
        """Moderate intensity (65-74%) should return hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.68, is_deload=False
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_boundary_85_strength_focus(self):
        """Exactly 85% intensity should return strength focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.85, is_deload=False
        )
        assert focus == TrainingFocus.STRENGTH

    def test_boundary_75_power_focus(self):
        """Exactly 75% intensity should return power focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.75, is_deload=False
        )
        assert focus == TrainingFocus.POWER

    def test_boundary_65_hypertrophy_focus(self):
        """Exactly 65% intensity should return hypertrophy focus."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.65, is_deload=False
        )
        assert focus == TrainingFocus.HYPERTROPHY

    def test_deload_overrides_effort_type(self):
        """Deload should override even if effort_type is set."""
        focus = WeekParameters.determine_focus(
            intensity_percent=0.90,
            is_deload=True,
            effort_type=EffortType.MAX_EFFORT,
        )
        assert focus == TrainingFocus.DELOAD


@pytest.mark.unit
class TestModelSelectionExtended:
    """Extended tests for model selection logic."""

    def test_weight_loss_uses_linear(self, service):
        """Weight loss goal should use linear periodization."""
        model = service.select_periodization_model(
            goal=ProgramGoal.WEIGHT_LOSS,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.LINEAR

    def test_general_fitness_uses_linear(self, service):
        """General fitness should default to linear."""
        model = service.select_periodization_model(
            goal=ProgramGoal.GENERAL_FITNESS,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.LINEAR

    def test_sport_specific_long_uses_block(self, service):
        """Long sport-specific programs should use block."""
        model = service.select_periodization_model(
            goal=ProgramGoal.SPORT_SPECIFIC,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=12,
        )
        assert model == PeriodizationModel.BLOCK

    def test_sport_specific_short_uses_undulating(self, service):
        """Short sport-specific programs should use undulating."""
        model = service.select_periodization_model(
            goal=ProgramGoal.SPORT_SPECIFIC,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING

    def test_hypertrophy_intermediate_uses_undulating(self, service):
        """Intermediate hypertrophy should use undulating."""
        model = service.select_periodization_model(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING

    def test_hypertrophy_advanced_uses_undulating(self, service):
        """Advanced hypertrophy should use undulating."""
        model = service.select_periodization_model(
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            duration_weeks=8,
        )
        assert model == PeriodizationModel.UNDULATING

    def test_strength_short_uses_linear(self, service):
        """Short strength programs should use linear."""
        model = service.select_periodization_model(
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            duration_weeks=6,
        )
        assert model == PeriodizationModel.LINEAR


@pytest.mark.unit
class TestGetWeekParameters:
    """Tests for the main get_week_parameters entry point."""

    def test_undulating_model_via_main_entry(self, service):
        """Undulating model should work through get_week_parameters."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.UNDULATING,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
            session=1,
        )
        assert params.week_number == 1
        assert 0 < params.intensity_percent < 1

    def test_conjugate_model_via_main_entry(self, service):
        """Conjugate model should work through get_week_parameters."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=1,
        )
        assert params.effort_type is not None
        assert params.effort_type == EffortType.MAX_EFFORT

    def test_reverse_linear_model_via_main_entry(self, service):
        """Reverse linear model should work through get_week_parameters."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.REVERSE_LINEAR,
            goal=ProgramGoal.ENDURANCE,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.week_number == 1
        assert 0 < params.intensity_percent < 1

    def test_deload_week_has_reduced_intensity(self, service):
        """Deload week should have reduced intensity and volume."""
        # Week 4 is a deload for intermediate
        params = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.is_deload is True
        assert params.focus == TrainingFocus.DELOAD

    def test_deload_week_has_recovery_note(self, service):
        """Deload week should have recovery note."""
        params = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        assert params.notes == "Deload week - reduce weights and focus on recovery"

    def test_all_models_produce_valid_output(self, service):
        """All periodization models should produce valid output."""
        for model in PeriodizationModel:
            params = service.get_week_parameters(
                week=4,
                total_weeks=8,
                model=model,
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.INTERMEDIATE,
            )
            assert params is not None
            assert params.week_number == 4
            assert 0 < params.intensity_percent <= 1
            assert params.volume_modifier > 0


@pytest.mark.unit
class TestPlanProgression:
    """Tests for plan_progression method."""

    def test_auto_selects_model_when_none_provided(self, service):
        """Should auto-select appropriate model when none specified."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
            model=None,
        )
        assert len(weeks) == 8
        # All weeks should have valid parameters
        for week in weeks:
            assert week.intensity_percent > 0
            assert week.volume_modifier > 0

    def test_uses_provided_model(self, service):
        """Should use provided model instead of auto-selecting."""
        weeks = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
            model=PeriodizationModel.UNDULATING,  # Override default LINEAR
        )
        assert len(weeks) == 8

    def test_all_weeks_have_correct_numbers(self, service):
        """All weeks should have sequential week numbers."""
        weeks = service.plan_progression(
            duration_weeks=12,
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        for i, week in enumerate(weeks, 1):
            assert week.week_number == i

    def test_includes_deload_weeks(self, service):
        """Plan should include appropriate deload weeks."""
        weeks = service.plan_progression(
            duration_weeks=12,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        deload_weeks = [w for w in weeks if w.is_deload]
        assert len(deload_weeks) >= 1


@pytest.mark.unit
class TestWeekNotes:
    """Tests for week notes generation."""

    def test_accumulation_phase_has_volume_note(self, service):
        """Accumulation phase should have note about volume."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
        )
        assert params.phase == BlockPhase.ACCUMULATION
        assert "volume" in params.notes.lower()

    def test_transmutation_phase_has_intensity_note(self, service):
        """Transmutation phase should have note about intensity."""
        params = service.get_week_parameters(
            week=5,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
        )
        assert params.phase == BlockPhase.TRANSMUTATION
        assert "intensity" in params.notes.lower()

    def test_realization_phase_has_peak_note(self, service):
        """Realization phase should have note about peaking."""
        # Use week 9 with beginner (deload at 6) so week 9 is realization but not deload
        params = service.get_week_parameters(
            week=9,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert params.phase == BlockPhase.REALIZATION
        assert "peak" in params.notes.lower()

    def test_max_effort_has_heavy_note(self, service):
        """Max effort should have note about heavy work."""
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

    def test_dynamic_effort_has_speed_note(self, service):
        """Dynamic effort should have note about speed."""
        params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=2,
        )
        assert params.effort_type == EffortType.DYNAMIC_EFFORT
        assert "speed" in params.notes.lower() or "explosive" in params.notes.lower()

    def test_repetition_effort_has_hypertrophy_note(self, service):
        """Repetition effort should have note about hypertrophy."""
        params = service.get_week_parameters(
            week=2,
            total_weeks=8,
            model=PeriodizationModel.CONJUGATE,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.ADVANCED,
            session=3,
        )
        assert params.effort_type == EffortType.REPETITION_EFFORT
        assert "hypertrophy" in params.notes.lower()

    def test_first_week_has_baseline_note(self, service):
        """First week should have baseline establishment note."""
        params = service.get_week_parameters(
            week=1,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert "baseline" in params.notes.lower()

    def test_final_week_has_progress_note_when_not_deload(self, service):
        """Final week should have progress note when not a deload."""
        # Use 5 weeks with beginner (deload at 6) so week 5 is final but not deload
        params = service.get_week_parameters(
            week=5,
            total_weeks=5,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert params.notes is not None
        assert "progress" in params.notes.lower() or "final" in params.notes.lower()


@pytest.mark.unit
class TestConjugateSessionCycling:
    """Tests for conjugate session cycling behavior."""

    def test_session_4_cycles_to_max_effort(self, service):
        """Session 4 should cycle back to max effort."""
        _, _, effort = service.calculate_conjugate_progression(week=1, session=4)
        assert effort == EffortType.MAX_EFFORT

    def test_session_5_cycles_to_max_effort(self, service):
        """Session 5 should cycle back to max effort (4-element rotation)."""
        # Rotation is [MAX, DYNAMIC, REPETITION, MAX], so session 5 = index 4 % 4 = 0 = MAX
        _, _, effort = service.calculate_conjugate_progression(week=1, session=5)
        assert effort == EffortType.MAX_EFFORT

    def test_session_6_cycles_to_dynamic_effort(self, service):
        """Session 6 should cycle to dynamic effort."""
        # Session 6 = index 5 % 4 = 1 = DYNAMIC
        _, _, effort = service.calculate_conjugate_progression(week=1, session=6)
        assert effort == EffortType.DYNAMIC_EFFORT

    def test_wave_loading_varies_intensity(self, service):
        """Wave loading should vary intensity across 3-week cycles."""
        int_w1, _, _ = service.calculate_conjugate_progression(week=1, session=1)
        int_w2, _, _ = service.calculate_conjugate_progression(week=2, session=1)
        int_w3, _, _ = service.calculate_conjugate_progression(week=3, session=1)

        # Wave pattern should show variation
        intensities = [int_w1, int_w2, int_w3]
        assert len(set(intensities)) > 1  # Not all the same


@pytest.mark.unit
class TestUndulatingSessionCycling:
    """Tests for undulating session cycling and weekly bonus."""

    def test_session_4_cycles_to_heavy(self, service):
        """Session 4 should cycle back to heavy pattern."""
        intensity, volume = service.calculate_undulating_progression(
            week=1, session=4, total_sessions=6
        )
        # Should match session 1 pattern (heavy)
        assert intensity >= 0.85
        assert volume < 1.0

    def test_weekly_bonus_caps_at_10_percent(self, service):
        """Weekly intensity bonus should cap at 10%."""
        # At week 10, bonus would be 0.02 * 9 = 0.18, but should cap at 0.10
        intensity_w1, _ = service.calculate_undulating_progression(week=1, session=1)
        intensity_w10, _ = service.calculate_undulating_progression(week=10, session=1)

        # Difference should not exceed 0.10
        assert intensity_w10 - intensity_w1 <= 0.11  # Small margin for rounding


@pytest.mark.unit
class TestDeloadEdgeCases:
    """Tests for deload edge cases."""

    def test_short_program_no_deload(self, service):
        """Very short programs may have no deload weeks."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=3,
            experience_level=ExperienceLevel.BEGINNER,
        )
        # 3-week beginner program: deload every 6, so no deloads
        assert len(deloads) == 0

    def test_program_exactly_at_deload_boundary(self, service):
        """Program exactly at deload boundary should include deload."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=6,
            experience_level=ExperienceLevel.BEGINNER,
        )
        # 6-week beginner: deload at week 6
        assert 6 in deloads

    def test_last_week_deload_added_for_long_program(self, service):
        """Last week should be added as deload for 6+ week programs."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=7,
            experience_level=ExperienceLevel.BEGINNER,
        )
        # Week 7 should be added as final deload
        assert 7 in deloads


@pytest.mark.unit
class TestBlockDeloadBehavior:
    """Tests for Block periodization deload behavior."""

    def test_block_no_final_week_deload(self, service):
        """Block periodization should not add final week as deload."""
        deloads = service.calculate_deload_weeks(
            duration_weeks=10,
            experience_level=ExperienceLevel.BEGINNER,
            model=PeriodizationModel.BLOCK,
        )
        # Only phase transitions at 4 and 8, NOT week 10
        assert 10 not in deloads
        assert 4 in deloads
        assert 8 in deloads

    def test_block_final_week_is_realization_not_deload(self, service):
        """Block periodization final week should be Realization phase, not deload."""
        params = service.get_week_parameters(
            week=10,
            total_weeks=10,
            model=PeriodizationModel.BLOCK,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
        )
        assert params.phase == BlockPhase.REALIZATION
        assert params.is_deload is False
        assert "peak" in params.notes.lower()


@pytest.mark.unit
class TestGetVolumeLimits:
    """Tests for get_volume_limits method."""

    def test_beginner_volume_limits(self, service):
        """Beginner should have lower volume limits."""
        limits = service.get_volume_limits(ExperienceLevel.BEGINNER)
        assert limits["min"] == 10
        assert limits["max"] == 12

    def test_intermediate_volume_limits(self, service):
        """Intermediate should have moderate volume limits."""
        limits = service.get_volume_limits(ExperienceLevel.INTERMEDIATE)
        assert limits["min"] == 12
        assert limits["max"] == 18

    def test_advanced_volume_limits(self, service):
        """Advanced should have higher volume limits."""
        limits = service.get_volume_limits(ExperienceLevel.ADVANCED)
        assert limits["min"] == 16
        assert limits["max"] == 25

    def test_returns_copy_not_reference(self, service):
        """Should return a copy to prevent mutation of class constant."""
        limits = service.get_volume_limits(ExperienceLevel.BEGINNER)
        limits["min"] = 999
        # Original should be unchanged
        original = service.get_volume_limits(ExperienceLevel.BEGINNER)
        assert original["min"] == 10


@pytest.mark.unit
class TestTotalWeeksValidation:
    """Tests for total_weeks validation."""

    def test_linear_rejects_zero_total_weeks(self, service):
        """Linear progression should reject total_weeks < 1."""
        with pytest.raises(ValueError, match="Total weeks must be at least 1"):
            service.calculate_linear_progression(week=1, total_weeks=0)

    def test_block_rejects_zero_total_weeks(self, service):
        """Block progression should reject total_weeks < 1."""
        with pytest.raises(ValueError, match="Total weeks must be at least 1"):
            service.calculate_block_progression(week=1, total_weeks=0)

    def test_reverse_linear_rejects_zero_total_weeks(self, service):
        """Reverse linear progression should reject total_weeks < 1."""
        with pytest.raises(ValueError, match="Total weeks must be at least 1"):
            service.calculate_reverse_linear_progression(week=1, total_weeks=0)

    def test_linear_rejects_negative_total_weeks(self, service):
        """Linear progression should reject negative total_weeks."""
        with pytest.raises(ValueError, match="Total weeks must be at least 1"):
            service.calculate_linear_progression(week=1, total_weeks=-5)

    def test_get_intensity_target_rejects_zero_total_weeks(self, service):
        """get_intensity_target should reject total_weeks < 1."""
        with pytest.raises(ValueError, match="Total weeks must be at least 1"):
            service.get_intensity_target(week_number=1, total_weeks=0, goal=ProgramGoal.STRENGTH)

    def test_get_intensity_target_rejects_invalid_week(self, service):
        """get_intensity_target should reject week out of range."""
        with pytest.raises(ValueError, match="Week 10 out of range"):
            service.get_intensity_target(week_number=10, total_weeks=8, goal=ProgramGoal.STRENGTH)


@pytest.mark.unit
class TestIntensityScaling:
    """Tests for intensity scaling to goal-specific bounds."""

    def test_intensity_stays_within_strength_bounds(self, service):
        """Intensity should stay within strength goal bounds."""
        min_int, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.STRENGTH]
        for week in range(1, 9):
            params = service.get_week_parameters(
                week=week,
                total_weeks=8,
                model=PeriodizationModel.LINEAR,
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.BEGINNER,
            )
            if not params.is_deload:
                assert min_int <= params.intensity_percent <= max_int

    def test_intensity_stays_within_endurance_bounds(self, service):
        """Intensity should stay within endurance goal bounds."""
        min_int, max_int = PeriodizationService.INTENSITY_RANGES[ProgramGoal.ENDURANCE]
        for week in range(1, 9):
            params = service.get_week_parameters(
                week=week,
                total_weeks=8,
                model=PeriodizationModel.LINEAR,
                goal=ProgramGoal.ENDURANCE,
                experience_level=ExperienceLevel.BEGINNER,
            )
            if not params.is_deload:
                assert min_int <= params.intensity_percent <= max_int

    def test_deload_intensity_is_reduced(self, service):
        """Deload intensity should be 60% of normal."""
        # Get a non-deload week first
        regular = service.get_week_parameters(
            week=3,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )
        # Week 4 is deload for intermediate
        deload = service.get_week_parameters(
            week=4,
            total_weeks=8,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        # Deload should have significantly lower intensity
        assert deload.intensity_percent < regular.intensity_percent * 0.7
