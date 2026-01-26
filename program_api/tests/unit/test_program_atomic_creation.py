"""
Tests for atomic program creation.

Part of AMA-489: Add Transaction Handling for Program Creation

Tests the atomic creation functionality that ensures programs,
weeks, and workouts are created in a single transaction.
"""

import pytest

from application.exceptions import ProgramCreationError
from models.generation import GenerateProgramRequest
from models.program import ExperienceLevel, ProgramGoal
from services.program_generator import ProgramGenerator, ProgramGenerationError
from tests.fakes import FakeProgramRepository


# ---------------------------------------------------------------------------
# FakeProgramRepository Atomic Creation Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFakeProgramRepositoryAtomic:
    """Tests for FakeProgramRepository atomic creation."""

    def test_create_program_atomic_returns_all_ids(self, fake_program_repo):
        """Atomic creation returns program, week, and workout IDs."""
        program_data = {
            "user_id": "user-123",
            "name": "Test Program",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "intermediate",
            "equipment_available": ["barbell"],
            "status": "draft",
        }

        weeks_data = [
            {
                "week_number": 1,
                "focus": "Strength",
                "intensity_percentage": 70,
                "volume_modifier": 1.0,
                "is_deload": False,
                "workouts": [
                    {
                        "day_of_week": 1,
                        "name": "Push Day",
                        "workout_type": "push",
                        "target_duration_minutes": 60,
                        "exercises": [],
                        "sort_order": 0,
                    },
                    {
                        "day_of_week": 3,
                        "name": "Pull Day",
                        "workout_type": "pull",
                        "target_duration_minutes": 60,
                        "exercises": [],
                        "sort_order": 1,
                    },
                ],
            },
            {
                "week_number": 2,
                "focus": "Strength",
                "intensity_percentage": 75,
                "volume_modifier": 1.0,
                "is_deload": False,
                "workouts": [
                    {
                        "day_of_week": 1,
                        "name": "Push Day",
                        "workout_type": "push",
                        "target_duration_minutes": 60,
                        "exercises": [],
                        "sort_order": 0,
                    },
                ],
            },
        ]

        result = fake_program_repo.create_program_atomic(program_data, weeks_data)

        # Check structure
        assert "program" in result
        assert "weeks" in result
        assert "workouts" in result

        # Check IDs
        assert result["program"]["id"] is not None
        assert len(result["weeks"]) == 2
        assert len(result["workouts"]) == 3  # 2 workouts in week 1, 1 in week 2

        # Verify data was persisted
        assert fake_program_repo.count() == 1
        weeks = fake_program_repo.get_weeks(result["program"]["id"])
        assert len(weeks) == 2
        assert len(weeks[0]["workouts"]) == 2
        assert len(weeks[1]["workouts"]) == 1

    def test_create_program_atomic_with_empty_weeks(self, fake_program_repo):
        """Atomic creation works with empty weeks list."""
        program_data = {
            "user_id": "user-123",
            "name": "Empty Program",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": [],
            "status": "draft",
        }

        result = fake_program_repo.create_program_atomic(program_data, [])

        assert result["program"]["id"] is not None
        assert result["weeks"] == []
        assert result["workouts"] == []
        assert fake_program_repo.count() == 1

    def test_create_program_atomic_with_weeks_without_workouts(self, fake_program_repo):
        """Atomic creation works with weeks that have no workouts."""
        program_data = {
            "user_id": "user-123",
            "name": "No Workouts Program",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 2,
            "sessions_per_week": 0,
            "experience_level": "beginner",
            "equipment_available": [],
            "status": "draft",
        }

        weeks_data = [
            {
                "week_number": 1,
                "focus": "Rest",
                "intensity_percentage": 50,
                "workouts": [],
            },
            {
                "week_number": 2,
                "focus": "Rest",
                "intensity_percentage": 50,
                # No workouts key at all
            },
        ]

        result = fake_program_repo.create_program_atomic(program_data, weeks_data)

        assert len(result["weeks"]) == 2
        assert result["workouts"] == []

    def test_simulated_failure_leaves_no_orphaned_records(self, fake_program_repo):
        """When atomic creation fails, no records should be created."""
        # Enable failure simulation
        fake_program_repo.simulate_atomic_failure()

        program_data = {
            "user_id": "user-123",
            "name": "Will Fail",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": [],
            "status": "draft",
        }

        weeks_data = [
            {
                "week_number": 1,
                "focus": "Test",
                "workouts": [{"name": "Workout 1", "day_of_week": 1}],
            },
        ]

        with pytest.raises(ProgramCreationError):
            fake_program_repo.create_program_atomic(program_data, weeks_data)

        # Verify nothing was created
        assert fake_program_repo.count() == 0
        assert len(fake_program_repo._weeks) == 0
        assert len(fake_program_repo._workouts) == 0

    def test_simulate_failure_only_affects_next_call(self, fake_program_repo):
        """Failure simulation only affects the immediate next atomic call."""
        # Enable failure simulation
        fake_program_repo.simulate_atomic_failure()

        program_data = {
            "user_id": "user-123",
            "name": "Test",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": [],
            "status": "draft",
        }

        # First call should fail
        with pytest.raises(ProgramCreationError):
            fake_program_repo.create_program_atomic(program_data, [])

        # Second call should succeed (failure flag was reset)
        result = fake_program_repo.create_program_atomic(program_data, [])
        assert result["program"]["id"] is not None


# ---------------------------------------------------------------------------
# ProgramGenerator Atomic Creation Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgramGeneratorAtomic:
    """Tests for ProgramGenerator using atomic creation."""

    @pytest.mark.asyncio
    async def test_generate_uses_atomic_creation(self, program_generator, fake_program_repo):
        """Generate method uses atomic creation to persist program."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells"],
        )

        response = await program_generator.generate(request, "user-123")

        # Verify program was created
        assert response.program is not None
        assert fake_program_repo.count() == 1

        # Verify weeks and workouts were created
        # Note: Convert UUID to string for fake repository lookup
        program_id = str(response.program.id)
        weeks = fake_program_repo.get_weeks(program_id)
        assert len(weeks) == 4  # 4 weeks for duration_weeks=4

        # Each week should have workouts
        for week in weeks:
            assert "workouts" in week

    @pytest.mark.asyncio
    async def test_generate_returns_correct_ids(self, program_generator, fake_program_repo):
        """Generate method returns response with correct IDs from atomic creation."""
        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=2,
            sessions_per_week=2,
            experience_level=ExperienceLevel.BEGINNER,
            equipment_available=["dumbbells"],
        )

        response = await program_generator.generate(request, "user-123")

        # Get the persisted data
        # Note: Convert UUID to string for fake repository lookup
        program_id_str = str(response.program.id)
        stored_program = fake_program_repo.get_by_id(program_id_str)
        assert stored_program is not None
        assert stored_program["name"] == response.program.name

        # Check weeks match
        stored_weeks = fake_program_repo.get_weeks(program_id_str)
        assert len(stored_weeks) == len(response.program.weeks)

        for stored_week, response_week in zip(stored_weeks, response.program.weeks):
            assert stored_week["id"] == str(response_week.id)

    @pytest.mark.asyncio
    async def test_generate_raises_on_atomic_failure(
        self, fake_program_repo, fake_template_repo, fake_exercise_repo
    ):
        """Generate raises ProgramGenerationError when atomic creation fails."""
        generator = ProgramGenerator(
            program_repo=fake_program_repo,
            template_repo=fake_template_repo,
            exercise_repo=fake_exercise_repo,
        )

        # Enable failure simulation
        fake_program_repo.simulate_atomic_failure()

        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell"],
        )

        with pytest.raises(ProgramGenerationError) as exc_info:
            await generator.generate(request, "user-123")

        assert "Failed to persist program" in str(exc_info.value)

        # Verify no orphaned records
        assert fake_program_repo.count() == 0


# ---------------------------------------------------------------------------
# Edge Case Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAtomicCreationEdgeCases:
    """Edge case tests for atomic creation."""

    def test_create_with_custom_program_id(self, fake_program_repo):
        """Atomic creation preserves provided program ID."""
        custom_id = "custom-program-id-123"
        program_data = {
            "id": custom_id,
            "user_id": "user-123",
            "name": "Custom ID Program",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": [],
            "status": "draft",
        }

        result = fake_program_repo.create_program_atomic(program_data, [])

        assert result["program"]["id"] == custom_id

    def test_create_preserves_workout_order(self, fake_program_repo):
        """Atomic creation preserves workout order within weeks."""
        program_data = {
            "user_id": "user-123",
            "name": "Ordered Workouts",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 1,
            "sessions_per_week": 3,
            "experience_level": "intermediate",
            "equipment_available": [],
            "status": "draft",
        }

        weeks_data = [
            {
                "week_number": 1,
                "workouts": [
                    {"name": "First", "day_of_week": 1, "sort_order": 0},
                    {"name": "Second", "day_of_week": 2, "sort_order": 1},
                    {"name": "Third", "day_of_week": 3, "sort_order": 2},
                ],
            },
        ]

        result = fake_program_repo.create_program_atomic(program_data, weeks_data)
        weeks = fake_program_repo.get_weeks(result["program"]["id"])

        # Workouts should be in order
        workout_names = [w["name"] for w in weeks[0]["workouts"]]
        assert workout_names == ["First", "Second", "Third"]

    def test_create_with_exercise_data(self, fake_program_repo):
        """Atomic creation preserves exercise data in workouts."""
        program_data = {
            "user_id": "user-123",
            "name": "With Exercises",
            "goal": "strength",
            "periodization_model": "linear",
            "duration_weeks": 1,
            "sessions_per_week": 1,
            "experience_level": "intermediate",
            "equipment_available": ["barbell"],
            "status": "draft",
        }

        exercises = [
            {"exercise_id": "bench-press", "sets": 4, "reps": "5"},
            {"exercise_id": "squat", "sets": 5, "reps": "5"},
        ]

        weeks_data = [
            {
                "week_number": 1,
                "workouts": [
                    {
                        "name": "Day 1",
                        "day_of_week": 1,
                        "exercises": exercises,
                    },
                ],
            },
        ]

        result = fake_program_repo.create_program_atomic(program_data, weeks_data)
        weeks = fake_program_repo.get_weeks(result["program"]["id"])

        stored_exercises = weeks[0]["workouts"][0]["exercises"]
        assert len(stored_exercises) == 2
        assert stored_exercises[0]["exercise_id"] == "bench-press"
        assert stored_exercises[1]["exercise_id"] == "squat"
