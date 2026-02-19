"""
Test Fixtures and Helpers for Fake Repositories.

Part of AMA-366: Add in-memory fake repositories for tests
Phase 2.4 - Dependency Injection Helpers

This module provides pytest fixtures and helper functions for easily overriding
FastAPI dependencies with fake repository implementations.

Usage:
    # In your test file
    from tests.fakes import FakeWorkoutRepository

    def test_something(override_deps):
        # override_deps is a fixture that resets and provides dependency override helper
        override_deps(get_workout_repo, FakeWorkoutRepository())

        # Now the API will use your fake
        response = client.get("/workouts")
        assert response.status_code == 200

Or use the standalone functions:
    from tests.fakes.conftest import override_dependency, reset_overrides

    def test_something():
        reset_overrides()  # Clear any previous overrides
        override_dependency(get_workout_repo, FakeWorkoutRepository())

        # Test code here...

        reset_overrides()  # Clean up after test
"""

from typing import Any, Callable, Dict, Optional, Type
from unittest.mock import MagicMock

import pytest

from application.ports import (
    WorkoutRepository,
    CompletionRepository,
    DeviceRepository,
    UserProfileRepository,
    UserMappingRepository,
    GlobalMappingRepository,
    ExerciseMatchRepository,
    ExercisesRepository,
    ProgressionRepository,
    SearchRepository,
    EmbeddingService,
)

# Import the dependency getter functions from api/deps
from api import deps


# =============================================================================
# Type alias for dependency override functions
# =============================================================================

# Type for repository dependency getters
RepoGetter = Callable[..., Any]


# =============================================================================
# Reset and Override Functions
# =============================================================================


def reset_overrides() -> None:
    """
    Reset all FastAPI dependency overrides.

    Call this in test setup/teardown to ensure clean state.
    """
    from backend.app import app

    app.dependency_overrides.clear()


def override_dependency(
    getter: RepoGetter,
    implementation: Any,
) -> None:
    """
    Override a FastAPI dependency with a fake implementation.

    Args:
        getter: The dependency getter function (e.g., get_workout_repo)
        implementation: The fake implementation instance or factory

    Example:
        repo = FakeWorkoutRepository()
        override_dependency(get_workout_repo, lambda: repo)
    """
    from backend.app import app

    # Handle both direct instances and factory functions
    if callable(implementation) and not isinstance(implementation, type):
        # It's a factory function, use it directly
        app.dependency_overrides[getter] = implementation
    else:
        # It's an instance, wrap in a lambda
        app.dependency_overrides[getter] = lambda: implementation


def override_with_fake(
    getter: RepoGetter,
    fake_class: Type,
    **kwargs,
) -> Any:
    """
    Create and override with a fake repository instance.

    Args:
        getter: The dependency getter function
        fake_class: The fake class to instantiate
        **kwargs: Arguments to pass to the fake constructor

    Returns:
        The created fake instance (for seeding data etc.)

    Example:
        repo = override_with_fake(get_workout_repo, FakeWorkoutRepository)
        repo.seed([{"id": "1", ...}])
    """
    fake_instance = fake_class(**kwargs)
    override_dependency(getter, fake_instance)
    return fake_instance


# =============================================================================
# pytest Fixtures
# =============================================================================


@pytest.fixture
def override_deps() -> Callable[[RepoGetter, Any], None]:
    """
    Fixture that provides a dependency override helper.

    Automatically resets overrides before each test and cleans up after.

    Usage:
        def test_something(override_deps):
            fake = override_deps(get_workout_repo, FakeWorkoutRepository())
            # Use the fake...

    Returns:
        Function that accepts (getter, implementation) and returns the implementation
    """
    # Reset before test
    reset_overrides()

    def _override(getter: RepoGetter, implementation: Any) -> Any:
        override_dependency(getter, implementation)
        return implementation

    yield _override

    # Reset after test
    reset_overrides()


@pytest.fixture
def clean_app() -> None:
    """
    Fixture that ensures clean dependency override state.

    Use this when you just need to ensure no leftover overrides
    without doing explicit overrides in the test.

    Usage:
        def test_something(clean_app):
            # App is clean...
    """
    reset_overrides()
    yield
    reset_overrides()


# =============================================================================
# Convenience Fixtures for Common Repositories
# =============================================================================


@pytest.fixture
def fake_workout_repo() -> WorkoutRepository:
    """
    Fixture providing a fresh FakeWorkoutRepository.

    Returns:
        A new FakeWorkoutRepository instance
    """
    from tests.fakes import FakeWorkoutRepository
    return FakeWorkoutRepository()


@pytest.fixture
def fake_completion_repo() -> CompletionRepository:
    """
    Fixture providing a fresh FakeCompletionRepository.

    Returns:
        A new FakeCompletionRepository instance
    """
    from tests.fakes import FakeCompletionRepository
    return FakeCompletionRepository()


@pytest.fixture
def fake_device_repo() -> DeviceRepository:
    """
    Fixture providing a fresh FakeDeviceRepository.

    Returns:
        A new FakeDeviceRepository instance
    """
    from tests.fakes import FakeDeviceRepository
    return FakeDeviceRepository()


@pytest.fixture
def fake_user_profile_repo() -> UserProfileRepository:
    """
    Fixture providing a fresh FakeUserProfileRepository.

    Returns:
        A new FakeUserProfileRepository instance
    """
    from tests.fakes import FakeUserProfileRepository
    return FakeUserProfileRepository()


@pytest.fixture
def fake_exercises_repo() -> ExercisesRepository:
    """
    Fixture providing a fresh FakeExercisesRepository.

    Returns:
        A new FakeExercisesRepository instance
    """
    from tests.fakes import FakeExercisesRepository
    return FakeExercisesRepository()


@pytest.fixture
def fake_progression_repo() -> ProgressionRepository:
    """
    Fixture providing a fresh FakeProgressionRepository.

    Returns:
        A new FakeProgressionRepository instance
    """
    from tests.fakes import FakeProgressionRepository
    return FakeProgressionRepository()


@pytest.fixture
def fake_exercise_match_repo() -> ExerciseMatchRepository:
    """
    Fixture providing a fresh FakeExerciseMatchRepository.

    Returns:
        A new FakeExerciseMatchRepository instance
    """
    from tests.fakes import FakeExerciseMatchRepository
    return FakeExerciseMatchRepository()


@pytest.fixture
def fake_user_mapping_repo() -> UserMappingRepository:
    """
    Fixture providing a fresh FakeUserMappingRepository.

    Note: Requires user_id to be set. Use create_user_mapping_repo factory
    or manually set user_id after creation.

    Returns:
        A new FakeUserMappingRepository instance
    """
    from tests.fakes import FakeUserMappingRepository
    return FakeUserMappingRepository(user_id="test-user")


@pytest.fixture
def fake_global_mapping_repo() -> GlobalMappingRepository:
    """
    Fixture providing a fresh FakeGlobalMappingRepository.

    Returns:
        A new FakeGlobalMappingRepository instance
    """
    from tests.fakes import FakeGlobalMappingRepository
    return FakeGlobalMappingRepository()


# =============================================================================
# Full App Override Fixtures
# =============================================================================


@pytest.fixture
def app_with_fake_repos(
    fake_workout_repo: WorkoutRepository,
    fake_completion_repo: CompletionRepository,
    fake_device_repo: DeviceRepository,
    fake_user_profile_repo: UserProfileRepository,
    fake_exercises_repo: ExercisesRepository,
    fake_progression_repo: ProgressionRepository,
    fake_exercise_match_repo: ExerciseMatchRepository,
) -> Dict[str, Any]:
    """
    Fixture that overrides all main repository dependencies with fakes.

    Returns a dict with the fake instances for seeding test data.

    Usage:
        def test_full_flow(app_with_fake_repos):
            app_with_fake_repos["workout_repo"].seed([...])
            # Test code...

    Returns:
        Dict mapping dependency names to fake instances
    """
    # Reset first
    reset_overrides()

    # Override all main repositories
    override_dependency(deps.get_workout_repo, fake_workout_repo)
    override_dependency(deps.get_completion_repo, fake_completion_repo)
    override_dependency(deps.get_device_repo, fake_device_repo)
    override_dependency(deps.get_user_profile_repo, fake_user_profile_repo)
    override_dependency(deps.get_exercises_repo, fake_exercises_repo)
    override_dependency(deps.get_progression_repo, fake_progression_repo)
    override_dependency(deps.get_exercise_match_repo, fake_exercise_match_repo)

    yield {
        "workout_repo": fake_workout_repo,
        "completion_repo": fake_completion_repo,
        "device_repo": fake_device_repo,
        "user_profile_repo": fake_user_profile_repo,
        "exercises_repo": fake_exercises_repo,
        "progression_repo": fake_progression_repo,
        "exercise_match_repo": fake_exercise_match_repo,
    }

    # Cleanup
    reset_overrides()


# =============================================================================
# Mock Embedding Service for Search Tests
# =============================================================================


class FakeEmbeddingService:
    """
    Fake EmbeddingService for testing without OpenAI API calls.
    """

    def __init__(self, embedding_dim: int = 1536):
        self.embedding_dim = embedding_dim
        self._calls: list[str] = []

    def generate_query_embedding(self, text: str) -> list[float]:
        """
        Generate a deterministic fake embedding based on text hash.

        Args:
            text: Input text

        Returns:
            Fake embedding vector
        """
        self._calls.append(text)
        # Generate deterministic but varied embedding based on text
        hash_val = hash(text) % 10000
        embedding = [0.0] * self.embedding_dim
        embedding[hash_val % self.embedding_dim] = 1.0
        # Add some variation
        for i in range(min(10, self.embedding_dim)):
            embedding[i] = (hash_val + i) / 10000
        return embedding

    @property
    def call_count(self) -> int:
        """Number of times generate_query_embedding was called."""
        return len(self._calls)

    @property
    def last_query(self) -> Optional[str]:
        """Last query text passed to generate_query_embedding."""
        return self._calls[-1] if self._calls else None


@pytest.fixture
def fake_embedding_service() -> FakeEmbeddingService:
    """
    Fixture providing a FakeEmbeddingService.

    Returns:
        A new FakeEmbeddingService instance
    """
    return FakeEmbeddingService()


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Functions
    "reset_overrides",
    "override_dependency",
    "override_with_fake",
    # Fixtures
    "override_deps",
    "clean_app",
    "fake_workout_repo",
    "fake_completion_repo",
    "fake_device_repo",
    "fake_user_profile_repo",
    "fake_exercises_repo",
    "fake_progression_repo",
    "fake_exercise_match_repo",
    "fake_user_mapping_repo",
    "fake_global_mapping_repo",
    "app_with_fake_repos",
    "fake_embedding_service",
    # Classes
    "FakeEmbeddingService",
]
