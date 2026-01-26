"""
Service unit tests.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Full implementation tests
Updated in AMA-472: Added fallback exercise selection tests

Tests service layer logic.
"""

import pytest

from services.program_generator import ProgramGenerator
from services.exercise_selector import ExerciseSelector
from services.periodization import PeriodizationService, PeriodizationModel
from services.progression_engine import ProgressionEngine
from models.program import ProgramGoal, ExperienceLevel
from models.generation import GenerateProgramRequest


# ---------------------------------------------------------------------------
# ProgramGenerator Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgramGenerator:
    """Tests for ProgramGenerator service."""

    def test_initialization_with_repositories(
        self, fake_program_repo, fake_template_repo, fake_exercise_repo
    ):
        """Generator can be initialized with repositories."""
        generator = ProgramGenerator(
            program_repo=fake_program_repo,
            template_repo=fake_template_repo,
            exercise_repo=fake_exercise_repo,
        )
        assert generator._program_repo is fake_program_repo
        assert generator._template_repo is fake_template_repo
        assert generator._exercise_repo is fake_exercise_repo

    def test_initialization_with_api_key(
        self, fake_program_repo, fake_template_repo, fake_exercise_repo
    ):
        """Generator can be initialized with OpenAI API key."""
        generator = ProgramGenerator(
            program_repo=fake_program_repo,
            template_repo=fake_template_repo,
            exercise_repo=fake_exercise_repo,
            openai_api_key="sk-test-openai",
        )
        # Exercise selector should be created when API key provided
        assert generator._exercise_selector is not None

    @pytest.mark.asyncio
    async def test_generate_returns_response(self, program_generator):
        """Generate method returns a valid response."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        response = await program_generator.generate(request, "user-123")

        assert response.program is not None
        assert response.program.goal == ProgramGoal.STRENGTH
        assert response.program.duration_weeks == 4
        assert len(response.program.weeks) == 4

    @pytest.mark.asyncio
    async def test_generate_persists_program(self, program_generator, fake_program_repo):
        """Generate method persists the program."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.BEGINNER,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        assert fake_program_repo.count() == 0
        await program_generator.generate(request, "user-123")
        assert fake_program_repo.count() == 1

    def test_has_db_exercise_selector(
        self, fake_program_repo, fake_template_repo, fake_exercise_repo
    ):
        """Generator initializes with DB exercise selector for fallback."""
        generator = ProgramGenerator(
            program_repo=fake_program_repo,
            template_repo=fake_template_repo,
            exercise_repo=fake_exercise_repo,
        )

        assert generator._db_exercise_selector is not None
        assert isinstance(generator._db_exercise_selector, ExerciseSelector)


# ---------------------------------------------------------------------------
# ProgramGenerator Fallback Selection Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgramGeneratorFallback:
    """Tests for ProgramGenerator fallback exercise selection."""

    @pytest.fixture
    def generator_no_llm(
        self, fake_program_repo, fake_template_repo, fake_exercise_repo
    ):
        """Generator without LLM (uses fallback)."""
        return ProgramGenerator(
            program_repo=fake_program_repo,
            template_repo=fake_template_repo,
            exercise_repo=fake_exercise_repo,
            openai_api_key=None,  # No LLM
        )

    def test_fallback_uses_exercise_selector(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback selection uses ExerciseSelector when equipment provided."""
        available = list(fake_exercise_repo._exercises.values())

        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=3,
            goal="strength",
            is_deload=False,
            equipment=["barbell", "dumbbells", "bench"],
            workout_type="push",
            muscle_groups=["chest"],
        )

        assert len(exercises) <= 3
        # Should have exercise structure
        for ex in exercises:
            assert "exercise_id" in ex
            assert "exercise_name" in ex
            assert "sets" in ex
            assert "reps" in ex

    def test_fallback_respects_goal_rep_scheme(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback applies correct rep scheme based on goal."""
        available = list(fake_exercise_repo._exercises.values())

        strength = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=2,
            goal="strength",
            is_deload=False,
        )

        hypertrophy = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=2,
            goal="hypertrophy",
            is_deload=False,
        )

        # Strength: 3-5 reps, Hypertrophy: 8-12 reps
        assert strength[0]["reps"] == "3-5"
        assert hypertrophy[0]["reps"] == "8-12"

    def test_fallback_reduces_sets_on_deload(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback reduces sets during deload weeks."""
        available = list(fake_exercise_repo._exercises.values())

        normal = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=2,
            goal="hypertrophy",
            is_deload=False,
        )

        deload = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=2,
            goal="hypertrophy",
            is_deload=True,
        )

        # Deload should have fewer sets
        assert deload[0]["sets"] < normal[0]["sets"]

    def test_fallback_returns_unique_exercises(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback returns exercises with unique IDs."""
        available = list(fake_exercise_repo._exercises.values())

        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=5,
            goal="hypertrophy",
            is_deload=False,
            equipment=["barbell", "dumbbells", "cables", "bench"],
            workout_type="push",
        )

        ids = [ex["exercise_id"] for ex in exercises]
        assert len(ids) == len(set(ids)), "Duplicate exercise IDs found"

    def test_fallback_without_equipment_uses_simple_sort(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Without equipment, fallback uses simple compound-first sorting."""
        available = list(fake_exercise_repo._exercises.values())

        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=3,
            goal="strength",
            is_deload=False,
            equipment=None,  # No equipment specified
        )

        # Should still return exercises
        assert len(exercises) > 0

    def test_fallback_with_empty_available_returns_empty(self, generator_no_llm):
        """Fallback with no available exercises returns empty list."""
        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=[],
            exercise_count=3,
            goal="strength",
            is_deload=False,
        )

        assert exercises == []

    def test_fallback_includes_order_field(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback exercises include order field starting at 1."""
        available = list(fake_exercise_repo._exercises.values())

        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=3,
            goal="hypertrophy",
            is_deload=False,
        )

        orders = [ex["order"] for ex in exercises]
        assert orders == [1, 2, 3]

    def test_fallback_includes_muscle_and_equipment_info(
        self, generator_no_llm, fake_exercise_repo
    ):
        """Fallback exercises include muscle and equipment info."""
        available = list(fake_exercise_repo._exercises.values())

        exercises = generator_no_llm._fallback_exercise_selection(
            available_exercises=available,
            exercise_count=2,
            goal="strength",
            is_deload=False,
        )

        for ex in exercises:
            assert "primary_muscles" in ex
            assert "equipment" in ex
            assert isinstance(ex["primary_muscles"], list)
            assert isinstance(ex["equipment"], list)


# ---------------------------------------------------------------------------
# PeriodizationService Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPeriodizationService:
    """Tests for PeriodizationService."""

    def test_instantiation(self):
        """Service can be instantiated."""
        service = PeriodizationService()
        assert service is not None

    def test_plan_progression_returns_week_parameters(self):
        """plan_progression returns week parameters for each week."""
        service = PeriodizationService()

        result = service.plan_progression(
            duration_weeks=8,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert len(result) == 8
        for week_params in result:
            assert hasattr(week_params, "intensity_percent")
            assert hasattr(week_params, "volume_modifier")
            assert hasattr(week_params, "is_deload")

    def test_calculate_deload_weeks_returns_list(self):
        """calculate_deload_weeks returns list of week numbers."""
        service = PeriodizationService()

        result = service.calculate_deload_weeks(
            duration_weeks=12,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert isinstance(result, list)
        # Intermediate should have deload every 4 weeks
        assert 4 in result or 8 in result or 12 in result

    def test_get_week_parameters_returns_valid_values(self):
        """get_week_parameters returns intensity and volume."""
        service = PeriodizationService()

        result = service.get_week_parameters(
            week=4,
            total_weeks=12,
            model=PeriodizationModel.LINEAR,
            goal=ProgramGoal.STRENGTH,
            experience_level=ExperienceLevel.INTERMEDIATE,
        )

        assert 0.0 <= result.intensity_percent <= 1.0
        assert 0.0 <= result.volume_modifier <= 2.0


# ---------------------------------------------------------------------------
# ProgressionEngine Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgressionEngine:
    """Tests for ProgressionEngine."""

    def test_instantiation(self):
        """Engine can be instantiated."""
        engine = ProgressionEngine()
        assert engine is not None

    def test_calculate_1rm_raises_not_implemented(self):
        """calculate_1rm raises NotImplementedError (stub)."""
        engine = ProgressionEngine()

        with pytest.raises(NotImplementedError):
            engine.calculate_1rm(weight=100.0, reps=10)

    def test_calculate_1rm_accepts_formula_parameter(self):
        """calculate_1rm accepts formula parameter (for when implemented)."""
        engine = ProgressionEngine()

        # These should all raise NotImplementedError for now
        for formula in ["epley", "brzycki", "lombardi"]:
            with pytest.raises(NotImplementedError):
                engine.calculate_1rm(weight=100.0, reps=10, formula=formula)

    def test_get_progression_suggestion_raises_not_implemented(self):
        """get_progression_suggestion raises NotImplementedError (stub)."""
        engine = ProgressionEngine()
        from uuid import uuid4

        with pytest.raises(NotImplementedError):
            engine.get_progression_suggestion("user-123", uuid4())

    def test_detect_personal_records_raises_not_implemented(self):
        """detect_personal_records raises NotImplementedError (stub)."""
        engine = ProgressionEngine()
        from uuid import uuid4

        with pytest.raises(NotImplementedError):
            engine.detect_personal_records(
                "user-123",
                uuid4(),
                {"weight": 225, "reps": 5},
            )

    def test_get_volume_analytics_raises_not_implemented(self):
        """get_volume_analytics raises NotImplementedError (stub)."""
        engine = ProgressionEngine()

        with pytest.raises(NotImplementedError):
            engine.get_volume_analytics("user-123")


# ---------------------------------------------------------------------------
# Fake Repository Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFakeProgramRepository:
    """Tests for FakeProgramRepository (testing infrastructure)."""

    def test_seed_and_get_by_user(self, fake_program_repo):
        """Can seed programs and retrieve by user."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Program 1"},
            {"id": "prog-2", "user_id": "user-1", "name": "Program 2"},
            {"id": "prog-3", "user_id": "user-2", "name": "Program 3"},
        ])

        user_1_programs = fake_program_repo.get_by_user("user-1")
        assert len(user_1_programs) == 2

        user_2_programs = fake_program_repo.get_by_user("user-2")
        assert len(user_2_programs) == 1

    def test_get_by_id(self, fake_program_repo):
        """Can retrieve program by ID."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Program 1"},
        ])

        program = fake_program_repo.get_by_id("prog-1")
        assert program is not None
        assert program["name"] == "Program 1"

        not_found = fake_program_repo.get_by_id("nonexistent")
        assert not_found is None

    def test_create(self, fake_program_repo):
        """Can create new programs."""
        program = fake_program_repo.create({
            "user_id": "user-1",
            "name": "New Program",
        })

        assert program["id"] is not None
        assert program["name"] == "New Program"
        assert program["created_at"] is not None
        assert fake_program_repo.count() == 1

    def test_update(self, fake_program_repo):
        """Can update existing programs."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Original Name"},
        ])

        updated = fake_program_repo.update("prog-1", {"name": "Updated Name"})

        assert updated["name"] == "Updated Name"
        assert updated["id"] == "prog-1"  # ID preserved

    def test_update_nonexistent_raises(self, fake_program_repo):
        """Updating nonexistent program raises KeyError."""
        with pytest.raises(KeyError):
            fake_program_repo.update("nonexistent", {"name": "Test"})

    def test_delete(self, fake_program_repo):
        """Can delete programs."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Program 1"},
        ])

        result = fake_program_repo.delete("prog-1")
        assert result is True
        assert fake_program_repo.count() == 0

        result = fake_program_repo.delete("nonexistent")
        assert result is False

    def test_reset(self, fake_program_repo):
        """Can reset all data."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Program 1"},
            {"id": "prog-2", "user_id": "user-1", "name": "Program 2"},
        ])

        assert fake_program_repo.count() == 2
        fake_program_repo.reset()
        assert fake_program_repo.count() == 0

    def test_weeks_and_workouts(self, fake_program_repo):
        """Can manage weeks and workouts."""
        fake_program_repo.seed([
            {"id": "prog-1", "user_id": "user-1", "name": "Program 1"},
        ])

        week = fake_program_repo.create_week("prog-1", {
            "week_number": 1,
            "name": "Week 1",
        })
        assert week["program_id"] == "prog-1"

        workout = fake_program_repo.create_workout(week["id"], {
            "day_of_week": 1,
            "name": "Push Day",
            "order_index": 0,
        })
        assert workout["program_week_id"] == week["id"]

        weeks = fake_program_repo.get_weeks("prog-1")
        assert len(weeks) == 1
        assert len(weeks[0]["workouts"]) == 1
