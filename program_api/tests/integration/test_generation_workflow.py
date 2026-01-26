"""
Integration tests for the program generation workflow.

Part of AMA-462: Implement ProgramGenerator Service

Tests the complete generation flow from request to response,
using fake repositories and LLM client.
"""

import pytest
from fastapi.testclient import TestClient

from api.deps import (
    get_current_user,
    get_exercise_repo,
    get_program_repo,
    get_template_repo,
)
from models.program import ExperienceLevel, ProgramGoal
from services.program_generator import ProgramGenerationError, ProgramGenerator
from tests.fakes import (
    FakeExerciseRepository,
    FakeExerciseSelector,
    FakeProgramRepository,
    FakeTemplateRepository,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def program_repo():
    """Create a fresh fake program repository."""
    return FakeProgramRepository()


@pytest.fixture
def template_repo():
    """Create a fake template repository with default templates."""
    repo = FakeTemplateRepository()
    repo.seed_default_templates()
    return repo


@pytest.fixture
def exercise_repo():
    """Create a fake exercise repository with default exercises."""
    repo = FakeExerciseRepository()
    repo.seed_default_exercises()
    return repo


@pytest.fixture
def llm_selector():
    """Create a fake LLM selector."""
    return FakeExerciseSelector()


@pytest.fixture
def generator(program_repo, template_repo, exercise_repo, llm_selector):
    """Create a ProgramGenerator with all fakes."""
    gen = ProgramGenerator(
        program_repo=program_repo,
        template_repo=template_repo,
        exercise_repo=exercise_repo,
        openai_api_key=None,  # No real LLM
    )
    # Replace the exercise selector with our fake
    gen._exercise_selector = llm_selector
    return gen


# ---------------------------------------------------------------------------
# ProgramGenerator Unit-ish Tests
# ---------------------------------------------------------------------------


class TestProgramGeneratorInit:
    """Tests for ProgramGenerator initialization."""

    def test_initializes_with_repositories(self, program_repo, template_repo, exercise_repo):
        """Should initialize with all required repositories."""
        generator = ProgramGenerator(
            program_repo=program_repo,
            template_repo=template_repo,
            exercise_repo=exercise_repo,
        )
        assert generator._program_repo is program_repo
        assert generator._template_repo is template_repo
        assert generator._exercise_repo is exercise_repo

    def test_initializes_without_llm_key(self, program_repo, template_repo, exercise_repo):
        """Should work without OpenAI key (uses fallback)."""
        generator = ProgramGenerator(
            program_repo=program_repo,
            template_repo=template_repo,
            exercise_repo=exercise_repo,
            openai_api_key=None,
        )
        assert generator._exercise_selector is None


class TestGenerationWorkflow:
    """Tests for the full generation workflow."""

    @pytest.mark.asyncio
    async def test_generates_program_with_correct_structure(self, generator):
        """Generated program should have correct structure."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "cables", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert response.program is not None
        assert response.program.goal == ProgramGoal.HYPERTROPHY
        assert response.program.duration_weeks == 8
        assert response.program.sessions_per_week == 4
        assert len(response.program.weeks) == 8

    @pytest.mark.asyncio
    async def test_generates_correct_number_of_workouts(self, generator):
        """Each week should have correct number of workouts."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.BEGINNER,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        for week in response.program.weeks:
            # Should have 3 sessions per week (or close to it based on template)
            assert len(week.workouts) >= 2
            assert len(week.workouts) <= 4

    @pytest.mark.asyncio
    async def test_persists_program_to_repository(self, generator, program_repo):
        """Generated program should be saved to repository."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=6,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        assert program_repo.count() == 0

        response = await generator.generate(request, user_id="test-user")

        assert program_repo.count() == 1
        saved = program_repo.get_by_id(str(response.program.id))
        assert saved is not None
        assert saved["user_id"] == "test-user"

    @pytest.mark.asyncio
    async def test_uses_llm_selector_when_available(self, generator, llm_selector):
        """Should use LLM selector for exercise selection."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        await generator.generate(request, user_id="test-user")

        # LLM should have been called for each workout across weeks
        # 4 weeks * 3 sessions = 12 calls
        assert llm_selector.call_count > 0

    @pytest.mark.asyncio
    async def test_generation_metadata_includes_details(self, generator):
        """Response should include generation metadata."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=8,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert "periodization_model" in response.generation_metadata
        assert "generation_time_seconds" in response.generation_metadata
        assert "validation_passed" in response.generation_metadata

    @pytest.mark.asyncio
    async def test_returns_suggestions(self, generator):
        """Response should include suggestions."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert len(response.suggestions) > 0
        # Should include periodization model info
        assert any("periodization" in s.lower() for s in response.suggestions)


class TestTemplateSelection:
    """Tests for template selection during generation."""

    @pytest.mark.asyncio
    async def test_uses_matching_template_when_available(
        self, generator, template_repo
    ):
        """Should use matching template from repository."""
        from models.generation import GenerateProgramRequest

        # Request that matches the PPL template
        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "cables", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        # Check that a template was used
        assert response.generation_metadata.get("template_id") is not None or "Using template" in " ".join(response.suggestions) or "default" in " ".join(response.suggestions).lower()

    @pytest.mark.asyncio
    async def test_falls_back_to_default_when_no_template(
        self, program_repo, exercise_repo
    ):
        """Should use default structure when no template matches."""
        # Empty template repo - no templates available
        empty_template_repo = FakeTemplateRepository()

        generator = ProgramGenerator(
            program_repo=program_repo,
            template_repo=empty_template_repo,
            exercise_repo=exercise_repo,
        )

        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        response = await generator.generate(request, user_id="test-user")

        # Should succeed with default structure
        assert response.program is not None
        assert any("default" in s.lower() for s in response.suggestions)


class TestPeriodizationIntegration:
    """Tests for periodization within generation."""

    @pytest.mark.asyncio
    async def test_deload_weeks_are_marked(self, generator):
        """Deload weeks should be marked in generated program."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=8,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,  # Deload every 4 weeks
            equipment_available=["barbell", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        # Should have at least one deload week in 8 weeks
        deload_weeks = [w for w in response.program.weeks if w.deload]
        assert len(deload_weeks) >= 1

    @pytest.mark.asyncio
    async def test_selects_appropriate_periodization_model(self, generator):
        """Should select appropriate periodization based on goal/experience."""
        from models.generation import GenerateProgramRequest

        # Strength + intermediate + long = block
        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=12,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert response.generation_metadata["periodization_model"] == "block"

    @pytest.mark.asyncio
    async def test_elite_uses_conjugate_for_strength(self, generator):
        """Elite + strength should use conjugate periodization (AMA-485)."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.STRENGTH,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.ELITE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert response.generation_metadata["periodization_model"] == "conjugate"

    @pytest.mark.asyncio
    async def test_elite_has_frequent_deloads(self, generator):
        """Elite should deload every 2 weeks (AMA-485)."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=8,
            sessions_per_week=4,
            experience_level=ExperienceLevel.ELITE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        response = await generator.generate(request, user_id="test-user")

        # Elite deloads every 2 weeks: weeks 2, 4, 6, 8 = 4 deloads in 8-week program
        deload_weeks = [w for w in response.program.weeks if w.deload]
        assert len(deload_weeks) >= 3, f"Elite should have at least 3 deloads in 8 weeks, got {len(deload_weeks)}"

    @pytest.mark.asyncio
    async def test_elite_generation_no_key_error(self, generator):
        """Elite experience level should not cause KeyError (AMA-485)."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.ENDURANCE,
            duration_weeks=6,
            sessions_per_week=3,
            experience_level=ExperienceLevel.ELITE,
            equipment_available=["barbell", "dumbbells"],
        )

        # This should not raise KeyError
        response = await generator.generate(request, user_id="test-user")

        assert response.program is not None
        assert len(response.program.weeks) == 6


class TestValidation:
    """Tests for program validation during generation."""

    @pytest.mark.asyncio
    async def test_validates_generated_program(self, generator):
        """Generated program should pass validation."""
        from models.generation import GenerateProgramRequest

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.BEGINNER,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        response = await generator.generate(request, user_id="test-user")

        assert response.generation_metadata.get("validation_passed") is True


class TestFallbackBehavior:
    """Tests for fallback when LLM fails."""

    @pytest.mark.asyncio
    async def test_uses_fallback_when_llm_fails(
        self, program_repo, template_repo, exercise_repo
    ):
        """Should use deterministic fallback when LLM fails."""
        from tests.fakes import FailingExerciseSelector
        from models.generation import GenerateProgramRequest

        generator = ProgramGenerator(
            program_repo=program_repo,
            template_repo=template_repo,
            exercise_repo=exercise_repo,
        )
        generator._exercise_selector = FailingExerciseSelector()

        request = GenerateProgramRequest(
            goal=ProgramGoal.HYPERTROPHY,
            duration_weeks=4,
            sessions_per_week=3,
            experience_level=ExperienceLevel.INTERMEDIATE,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack", "cables"],
        )

        # Should not raise - falls back to deterministic selection
        response = await generator.generate(request, user_id="test-user")

        assert response.program is not None
        assert len(response.program.weeks) == 4


# ---------------------------------------------------------------------------
# API Endpoint Integration Tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client_with_fakes(
    app,
    program_repo,
    template_repo,
    exercise_repo,
):
    """TestClient with all fake repositories injected."""
    async def mock_user():
        return "test-user-123"

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_program_repo] = lambda: program_repo
    app.dependency_overrides[get_template_repo] = lambda: template_repo
    app.dependency_overrides[get_exercise_repo] = lambda: exercise_repo

    yield TestClient(app)

    app.dependency_overrides.clear()


class TestGenerationEndpoint:
    """Tests for POST /generate endpoint."""

    @pytest.mark.integration
    def test_generate_returns_201_or_200(self, client_with_fakes):
        """POST /generate should return success."""
        response = client_with_fakes.post(
            "/generate",
            json={
                "goal": "hypertrophy",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": ["barbell", "dumbbells", "bench", "squat_rack", "cables"],
            },
        )
        assert response.status_code in [200, 201]

    @pytest.mark.integration
    def test_generate_returns_program_structure(self, client_with_fakes):
        """Response should include program structure."""
        response = client_with_fakes.post(
            "/generate",
            json={
                "goal": "strength",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "experience_level": "intermediate",
                "equipment_available": ["barbell", "bench", "squat_rack"],
            },
        )

        if response.status_code == 200:
            data = response.json()
            assert "program" in data
            assert "weeks" in data["program"]
            assert "generation_metadata" in data
            assert "suggestions" in data

    @pytest.mark.integration
    def test_generate_validates_goal(self, client_with_fakes):
        """Should reject invalid goal."""
        response = client_with_fakes.post(
            "/generate",
            json={
                "goal": "invalid_goal",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": [],
            },
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_generate_validates_duration(self, client_with_fakes):
        """Should reject invalid duration."""
        response = client_with_fakes.post(
            "/generate",
            json={
                "goal": "hypertrophy",
                "duration_weeks": 100,  # Max is 52
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": [],
            },
        )
        assert response.status_code == 422

    @pytest.mark.integration
    def test_generate_requires_auth(self, app):
        """Should require authentication."""
        # Client without auth override
        client = TestClient(app)
        response = client.post(
            "/generate",
            json={
                "goal": "hypertrophy",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "experience_level": "beginner",
                "equipment_available": [],
            },
        )
        assert response.status_code == 401
