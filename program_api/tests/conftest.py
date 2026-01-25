"""
Pytest fixtures for program-api tests.

Part of AMA-461: Create program-api service scaffold
"""

import sys
from pathlib import Path
from typing import Any, Dict, Generator, List

import pytest
from fastapi.testclient import TestClient

# Ensure program-api root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

from backend.main import create_app
from backend.settings import Settings
from api.deps import (
    get_current_user,
    get_exercise_repo,
    get_program_repo,
    get_template_repo,
)


# ---------------------------------------------------------------------------
# Auth Mock
# ---------------------------------------------------------------------------

TEST_USER_ID = "test-user-123"
OTHER_USER_ID = "other-user-456"


async def mock_get_current_user() -> str:
    """Mock auth dependency that returns a test user."""
    return TEST_USER_ID


# ---------------------------------------------------------------------------
# Test App and Client
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Test settings with minimal configuration."""
    return Settings(
        environment="test",
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="test-key",
    )


@pytest.fixture(scope="session")
def app(test_settings):
    """Create test application instance."""
    return create_app(settings=test_settings)


@pytest.fixture(scope="session")
def api_client(app) -> Generator[TestClient, None, None]:
    """
    Shared FastAPI TestClient for program-api endpoints.
    Properly cleans up dependency overrides.
    """
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    """
    Per-test FastAPI TestClient (for tests needing fresh state).
    Properly cleans up dependency overrides after each test.
    """
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock Environment Variables
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Set mock environment variables for tests."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-supabase-key")
    monkeypatch.setenv("ENVIRONMENT", "test")


# ---------------------------------------------------------------------------
# Domain Fixtures - Programs
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_program_create() -> Dict[str, Any]:
    """Valid payload for creating a program."""
    return {
        "name": "12-Week Strength Program",
        "goal": "strength",
        "experience_level": "intermediate",
        "duration_weeks": 12,
        "sessions_per_week": 4,
        "equipment_available": ["barbell", "dumbbells", "cables"],
    }


@pytest.fixture
def sample_program_minimal() -> Dict[str, Any]:
    """Minimal valid payload for creating a program."""
    return {
        "name": "Basic Program",
        "goal": "general_fitness",
        "experience_level": "beginner",
        "duration_weeks": 4,
        "sessions_per_week": 3,
    }


@pytest.fixture
def sample_generation_request() -> Dict[str, Any]:
    """Valid payload for program generation."""
    return {
        "goal": "hypertrophy",
        "duration_weeks": 8,
        "sessions_per_week": 4,
        "experience_level": "intermediate",
        "equipment_available": ["barbell", "dumbbells", "cables", "machines"],
        "focus_areas": ["chest", "back"],
        "limitations": [],
        "preferences": "Prefer compound movements",
    }


@pytest.fixture
def sample_program_data() -> Dict[str, Any]:
    """Complete program data as returned from database."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "user_id": TEST_USER_ID,
        "name": "Test Program",
        "description": "A test training program",
        "goal": "strength",
        "experience_level": "intermediate",
        "duration_weeks": 12,
        "sessions_per_week": 4,
        "status": "draft",
        "equipment_available": ["barbell", "dumbbells"],
        "created_at": "2024-01-15T10:00:00Z",
        "updated_at": "2024-01-15T10:00:00Z",
    }


@pytest.fixture
def sample_programs_list(sample_program_data) -> List[Dict[str, Any]]:
    """List of programs for testing list endpoints."""
    return [
        sample_program_data,
        {
            **sample_program_data,
            "id": "550e8400-e29b-41d4-a716-446655440001",
            "name": "Second Program",
            "goal": "hypertrophy",
        },
        {
            **sample_program_data,
            "id": "550e8400-e29b-41d4-a716-446655440002",
            "name": "Third Program",
            "goal": "endurance",
        },
    ]


# ---------------------------------------------------------------------------
# Fake Repository Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_program_repo():
    """Create a fake program repository for testing."""
    from tests.fakes import FakeProgramRepository
    return FakeProgramRepository()


@pytest.fixture
def seeded_program_repo(fake_program_repo, sample_programs_list):
    """Fake program repository pre-seeded with test data."""
    fake_program_repo.seed(sample_programs_list)
    return fake_program_repo


@pytest.fixture
def client_with_fake_repo(app, fake_program_repo) -> Generator[TestClient, None, None]:
    """TestClient with fake program repository injected."""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_with_seeded_repo(app, seeded_program_repo) -> Generator[TestClient, None, None]:
    """TestClient with seeded fake program repository."""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_program_repo] = lambda: seeded_program_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fake Repository Fixtures - AMA-462 Additions
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_template_repo():
    """Create a fake template repository for testing."""
    from tests.fakes import FakeTemplateRepository
    repo = FakeTemplateRepository()
    repo.seed_default_templates()
    return repo


@pytest.fixture
def fake_exercise_repo():
    """Create a fake exercise repository for testing."""
    from tests.fakes import FakeExerciseRepository
    repo = FakeExerciseRepository()
    repo.seed_default_exercises()
    return repo


@pytest.fixture
def fake_llm_selector():
    """Create a fake LLM selector for testing."""
    from tests.fakes import FakeExerciseSelector
    return FakeExerciseSelector()


@pytest.fixture
def client_with_all_fakes(
    app,
    fake_program_repo,
    fake_template_repo,
    fake_exercise_repo,
) -> Generator[TestClient, None, None]:
    """TestClient with all fake repositories injected."""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
    app.dependency_overrides[get_template_repo] = lambda: fake_template_repo
    app.dependency_overrides[get_exercise_repo] = lambda: fake_exercise_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Service Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def periodization_service():
    """Create a PeriodizationService for testing."""
    from services.periodization import PeriodizationService
    return PeriodizationService()


@pytest.fixture
def program_validator():
    """Create a ProgramValidator for testing."""
    from services.program_validator import ProgramValidator
    return ProgramValidator()


@pytest.fixture
def template_selector(fake_template_repo):
    """Create a TemplateSelector with fake repository."""
    from services.template_selector import TemplateSelector
    return TemplateSelector(fake_template_repo)


@pytest.fixture
def program_generator(
    fake_program_repo,
    fake_template_repo,
    fake_exercise_repo,
    fake_llm_selector,
):
    """Create a ProgramGenerator with all fakes."""
    from services.program_generator import ProgramGenerator
    gen = ProgramGenerator(
        program_repo=fake_program_repo,
        template_repo=fake_template_repo,
        exercise_repo=fake_exercise_repo,
        openai_api_key=None,
    )
    gen._exercise_selector = fake_llm_selector
    return gen
