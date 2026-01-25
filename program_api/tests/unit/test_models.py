"""
Model validation unit tests.

Part of AMA-461: Create program-api service scaffold

Tests Pydantic model validation rules and constraints.
"""

import pytest
from pydantic import ValidationError

from models.program import (
    ProgramGoal,
    ExperienceLevel,
    ProgramStatus,
    TrainingProgramCreate,
    TrainingProgramUpdate,
)
from models.generation import GenerateProgramRequest


# ---------------------------------------------------------------------------
# ProgramGoal Enum Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgramGoal:
    """Tests for ProgramGoal enum."""

    def test_valid_goals(self):
        """All expected goal values are valid."""
        valid_goals = [
            "strength",
            "hypertrophy",
            "endurance",
            "weight_loss",
            "general_fitness",
            "sport_specific",
        ]
        for goal in valid_goals:
            assert ProgramGoal(goal) == goal

    def test_invalid_goal_raises(self):
        """Invalid goal values raise ValueError."""
        with pytest.raises(ValueError):
            ProgramGoal("invalid_goal")


# ---------------------------------------------------------------------------
# ExperienceLevel Enum Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExperienceLevel:
    """Tests for ExperienceLevel enum."""

    def test_valid_levels(self):
        """All expected experience levels are valid."""
        valid_levels = ["beginner", "intermediate", "advanced"]
        for level in valid_levels:
            assert ExperienceLevel(level) == level

    def test_invalid_level_raises(self):
        """Invalid experience level values raise ValueError."""
        with pytest.raises(ValueError):
            ExperienceLevel("expert")


# ---------------------------------------------------------------------------
# TrainingProgramCreate Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTrainingProgramCreate:
    """Tests for TrainingProgramCreate model."""

    def test_valid_minimal_program(self):
        """Minimal valid program can be created."""
        program = TrainingProgramCreate(
            name="Test Program",
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.BEGINNER,
            duration_weeks=4,
            sessions_per_week=3,
        )

        assert program.name == "Test Program"
        assert program.goal == ProgramGoal.STRENGTH
        assert program.equipment_available == []

    def test_valid_full_program(self):
        """Full program with all fields can be created."""
        program = TrainingProgramCreate(
            name="Complete Program",
            description="A full training program",
            goal=ProgramGoal.HYPERTROPHY,
            experience_level=ExperienceLevel.ADVANCED,
            duration_weeks=12,
            sessions_per_week=5,
            equipment_available=["barbell", "dumbbells", "cables"],
        )

        assert program.description == "A full training program"
        assert len(program.equipment_available) == 3

    def test_duration_weeks_minimum(self):
        """Duration weeks must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            TrainingProgramCreate(
                name="Test",
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.BEGINNER,
                duration_weeks=0,
                sessions_per_week=3,
            )

        errors = exc_info.value.errors()
        assert any("duration_weeks" in str(e["loc"]) for e in errors)

    def test_duration_weeks_maximum(self):
        """Duration weeks must not exceed 52."""
        with pytest.raises(ValidationError) as exc_info:
            TrainingProgramCreate(
                name="Test",
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.BEGINNER,
                duration_weeks=53,
                sessions_per_week=3,
            )

        errors = exc_info.value.errors()
        assert any("duration_weeks" in str(e["loc"]) for e in errors)

    def test_sessions_per_week_minimum(self):
        """Sessions per week must be at least 1."""
        with pytest.raises(ValidationError) as exc_info:
            TrainingProgramCreate(
                name="Test",
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.BEGINNER,
                duration_weeks=4,
                sessions_per_week=0,
            )

        errors = exc_info.value.errors()
        assert any("sessions_per_week" in str(e["loc"]) for e in errors)

    def test_sessions_per_week_maximum(self):
        """Sessions per week must not exceed 7."""
        with pytest.raises(ValidationError) as exc_info:
            TrainingProgramCreate(
                name="Test",
                goal=ProgramGoal.STRENGTH,
                experience_level=ExperienceLevel.BEGINNER,
                duration_weeks=4,
                sessions_per_week=8,
            )

        errors = exc_info.value.errors()
        assert any("sessions_per_week" in str(e["loc"]) for e in errors)

    def test_missing_required_fields(self):
        """Missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            TrainingProgramCreate()

        errors = exc_info.value.errors()
        required_fields = ["name", "goal", "experience_level", "duration_weeks", "sessions_per_week"]
        for field in required_fields:
            assert any(field in str(e["loc"]) for e in errors)


# ---------------------------------------------------------------------------
# TrainingProgramUpdate Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTrainingProgramUpdate:
    """Tests for TrainingProgramUpdate model."""

    def test_all_fields_optional(self):
        """All fields are optional for updates."""
        update = TrainingProgramUpdate()
        assert update.name is None
        assert update.goal is None

    def test_partial_update(self):
        """Partial updates are valid."""
        update = TrainingProgramUpdate(name="New Name")
        assert update.name == "New Name"
        assert update.goal is None
        assert update.duration_weeks is None

    def test_status_can_be_updated(self):
        """Status field can be set."""
        update = TrainingProgramUpdate(status=ProgramStatus.ACTIVE)
        assert update.status == ProgramStatus.ACTIVE

    def test_duration_validation_on_update(self):
        """Duration validation applies to updates."""
        with pytest.raises(ValidationError):
            TrainingProgramUpdate(duration_weeks=0)

        with pytest.raises(ValidationError):
            TrainingProgramUpdate(duration_weeks=53)


# ---------------------------------------------------------------------------
# GenerateProgramRequest Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGenerateProgramRequest:
    """Tests for GenerateProgramRequest model."""

    def test_valid_minimal_request(self):
        """Minimal valid generation request."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert request.goal == ProgramGoal.STRENGTH
        assert request.equipment_available == []
        assert request.focus_areas == []
        assert request.limitations == []
        assert request.preferences is None

    def test_valid_full_request(self):
        """Full generation request with all fields."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=12,
            sessions_per_week=5,
            experience_level=ExperienceLevel.ADVANCED,
            equipment_available=["barbell", "dumbbells"],
            focus_areas=["chest", "back"],
            limitations=["lower back injury"],
            preferences="Prefer compound movements",
        )

        assert len(request.equipment_available) == 2
        assert len(request.focus_areas) == 2
        assert request.preferences == "Prefer compound movements"

    def test_duration_constraints(self):
        """Duration constraints are enforced."""
        with pytest.raises(ValidationError):
            GenerateProgramRequest(
                goal=ProgramGoal.STRENGTH,
                duration_weeks=0,
                sessions_per_week=4,
                experience_level=ExperienceLevel.BEGINNER,
            )

        with pytest.raises(ValidationError):
            GenerateProgramRequest(
                goal=ProgramGoal.STRENGTH,
                duration_weeks=53,
                sessions_per_week=4,
                experience_level=ExperienceLevel.BEGINNER,
            )

    def test_sessions_constraints(self):
        """Sessions per week constraints are enforced."""
        with pytest.raises(ValidationError):
            GenerateProgramRequest(
                goal=ProgramGoal.STRENGTH,
                duration_weeks=8,
                sessions_per_week=0,
                experience_level=ExperienceLevel.BEGINNER,
            )

        with pytest.raises(ValidationError):
            GenerateProgramRequest(
                goal=ProgramGoal.STRENGTH,
                duration_weeks=8,
                sessions_per_week=8,
                experience_level=ExperienceLevel.BEGINNER,
            )
