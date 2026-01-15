"""
Integration tests for infrastructure repository implementations.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

These tests verify that the Supabase repository implementations correctly
implement the protocol interfaces and can be used with dependency injection.

Run integration tests with: pytest -m integration
"""
import pytest
from typing import Dict, Any
from unittest.mock import Mock, MagicMock

# All tests in this module are pure logic tests with mocks - mark as unit
pytestmark = pytest.mark.unit


# ============================================================================
# Unit Tests (no database required)
# ============================================================================

class TestRepositoryImports:
    """Test that all repository classes can be imported."""

    def test_import_workout_repository(self):
        """SupabaseWorkoutRepository should be importable."""
        from infrastructure.db.workout_repository import SupabaseWorkoutRepository
        assert SupabaseWorkoutRepository is not None

    def test_import_completion_repository(self):
        """SupabaseCompletionRepository should be importable."""
        from infrastructure.db.completion_repository import SupabaseCompletionRepository
        assert SupabaseCompletionRepository is not None

    def test_import_device_repository(self):
        """SupabaseDeviceRepository should be importable."""
        from infrastructure.db.device_repository import SupabaseDeviceRepository
        assert SupabaseDeviceRepository is not None

    def test_import_user_profile_repository(self):
        """SupabaseUserProfileRepository should be importable."""
        from infrastructure.db.device_repository import SupabaseUserProfileRepository
        assert SupabaseUserProfileRepository is not None

    def test_import_user_mapping_repository(self):
        """SupabaseUserMappingRepository should be importable."""
        from infrastructure.db.mapping_repository import SupabaseUserMappingRepository
        assert SupabaseUserMappingRepository is not None

    def test_import_global_mapping_repository(self):
        """SupabaseGlobalMappingRepository should be importable."""
        from infrastructure.db.mapping_repository import SupabaseGlobalMappingRepository
        assert SupabaseGlobalMappingRepository is not None

    def test_import_exercise_match_repository(self):
        """InMemoryExerciseMatchRepository should be importable."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        assert InMemoryExerciseMatchRepository is not None

    def test_import_from_infrastructure_package(self):
        """All repositories should be importable from infrastructure package."""
        from infrastructure import (
            SupabaseWorkoutRepository,
            SupabaseCompletionRepository,
            SupabaseDeviceRepository,
            SupabaseUserProfileRepository,
            SupabaseUserMappingRepository,
            SupabaseGlobalMappingRepository,
            InMemoryExerciseMatchRepository,
        )
        assert all([
            SupabaseWorkoutRepository,
            SupabaseCompletionRepository,
            SupabaseDeviceRepository,
            SupabaseUserProfileRepository,
            SupabaseUserMappingRepository,
            SupabaseGlobalMappingRepository,
            InMemoryExerciseMatchRepository,
        ])


class TestRepositoryInstantiation:
    """Test that repositories can be instantiated with mock clients."""

    def test_workout_repository_instantiation(self):
        """SupabaseWorkoutRepository should accept a Supabase client."""
        from infrastructure.db.workout_repository import SupabaseWorkoutRepository
        mock_client = Mock()
        repo = SupabaseWorkoutRepository(mock_client)
        assert repo._client is mock_client

    def test_completion_repository_instantiation(self):
        """SupabaseCompletionRepository should accept a Supabase client."""
        from infrastructure.db.completion_repository import SupabaseCompletionRepository
        mock_client = Mock()
        repo = SupabaseCompletionRepository(mock_client)
        assert repo._client is mock_client

    def test_device_repository_instantiation(self):
        """SupabaseDeviceRepository should accept a Supabase client."""
        from infrastructure.db.device_repository import SupabaseDeviceRepository
        mock_client = Mock()
        repo = SupabaseDeviceRepository(mock_client)
        assert repo._client is mock_client

    def test_user_profile_repository_instantiation(self):
        """SupabaseUserProfileRepository should accept a Supabase client."""
        from infrastructure.db.device_repository import SupabaseUserProfileRepository
        mock_client = Mock()
        repo = SupabaseUserProfileRepository(mock_client)
        assert repo._client is mock_client

    def test_user_mapping_repository_instantiation(self):
        """SupabaseUserMappingRepository should accept client and user_id."""
        from infrastructure.db.mapping_repository import SupabaseUserMappingRepository
        mock_client = Mock()
        repo = SupabaseUserMappingRepository(mock_client, user_id="test_user")
        assert repo._client is mock_client
        assert repo._user_id == "test_user"

    def test_global_mapping_repository_instantiation(self):
        """SupabaseGlobalMappingRepository should accept a Supabase client."""
        from infrastructure.db.mapping_repository import SupabaseGlobalMappingRepository
        mock_client = Mock()
        repo = SupabaseGlobalMappingRepository(mock_client)
        assert repo._client is mock_client

    def test_exercise_match_repository_instantiation(self):
        """InMemoryExerciseMatchRepository should instantiate without client."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        repo = InMemoryExerciseMatchRepository()
        assert repo is not None


class TestProtocolCompliance:
    """Test that implementations match their Protocol interfaces."""

    def test_workout_repository_has_required_methods(self):
        """SupabaseWorkoutRepository should have all Protocol methods."""
        from infrastructure.db.workout_repository import SupabaseWorkoutRepository
        from application.ports.workout_repository import WorkoutRepository

        required_methods = [
            "save", "get", "get_list", "delete", "update_export_status",
            "toggle_favorite", "track_usage", "update_tags", "get_incoming",
            "get_sync_status", "update_companion_sync"
        ]

        for method in required_methods:
            assert hasattr(SupabaseWorkoutRepository, method), f"Missing method: {method}"

    def test_completion_repository_has_required_methods(self):
        """SupabaseCompletionRepository should have all Protocol methods."""
        from infrastructure.db.completion_repository import SupabaseCompletionRepository

        required_methods = [
            "save", "get_by_id", "get_user_completions",
            "save_voice_workout_with_completion", "get_completed_workout_ids"
        ]

        for method in required_methods:
            assert hasattr(SupabaseCompletionRepository, method), f"Missing method: {method}"

    def test_device_repository_has_required_methods(self):
        """SupabaseDeviceRepository should have all Protocol methods."""
        from infrastructure.db.device_repository import SupabaseDeviceRepository

        required_methods = [
            "create_pairing_token", "validate_and_use_token", "get_pairing_status",
            "revoke_user_tokens", "get_paired_devices", "revoke_device", "refresh_jwt"
        ]

        for method in required_methods:
            assert hasattr(SupabaseDeviceRepository, method), f"Missing method: {method}"

    def test_user_profile_repository_has_required_methods(self):
        """SupabaseUserProfileRepository should have all Protocol methods."""
        from infrastructure.db.device_repository import SupabaseUserProfileRepository

        required_methods = [
            "get_profile", "get_account_deletion_preview", "delete_account", "reset_data"
        ]

        for method in required_methods:
            assert hasattr(SupabaseUserProfileRepository, method), f"Missing method: {method}"

    def test_user_mapping_repository_has_required_methods(self):
        """SupabaseUserMappingRepository should have all Protocol methods."""
        from infrastructure.db.mapping_repository import SupabaseUserMappingRepository

        required_methods = ["add", "remove", "get", "get_all", "clear_all"]

        for method in required_methods:
            assert hasattr(SupabaseUserMappingRepository, method), f"Missing method: {method}"

    def test_global_mapping_repository_has_required_methods(self):
        """SupabaseGlobalMappingRepository should have all Protocol methods."""
        from infrastructure.db.mapping_repository import SupabaseGlobalMappingRepository

        required_methods = ["record_choice", "get_popular", "get_stats"]

        for method in required_methods:
            assert hasattr(SupabaseGlobalMappingRepository, method), f"Missing method: {method}"

    def test_exercise_match_repository_has_required_methods(self):
        """InMemoryExerciseMatchRepository should have all Protocol methods."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository

        required_methods = [
            "find_match", "get_suggestions", "find_similar", "find_by_type", "categorize"
        ]

        for method in required_methods:
            assert hasattr(InMemoryExerciseMatchRepository, method), f"Missing method: {method}"


class TestHelperFunctions:
    """Test helper functions in repository modules."""

    def test_format_duration_minutes_seconds(self):
        """format_duration should handle MM:SS format."""
        from infrastructure.db.completion_repository import format_duration
        assert format_duration(65) == "1:05"
        assert format_duration(130) == "2:10"

    def test_format_duration_hours(self):
        """format_duration should handle HH:MM:SS format."""
        from infrastructure.db.completion_repository import format_duration
        assert format_duration(3665) == "1:01:05"
        assert format_duration(7200) == "2:00:00"

    def test_calculate_duration_seconds(self):
        """calculate_duration_seconds should compute time difference."""
        from infrastructure.db.completion_repository import calculate_duration_seconds
        result = calculate_duration_seconds(
            "2024-01-01T10:00:00Z",
            "2024-01-01T10:30:00Z"
        )
        assert result == 1800  # 30 minutes

    def test_generate_pairing_tokens(self):
        """generate_pairing_tokens should create unique tokens."""
        from infrastructure.db.device_repository import generate_pairing_tokens
        token1, code1 = generate_pairing_tokens()
        token2, code2 = generate_pairing_tokens()

        assert len(token1) == 64  # 32 bytes hex
        assert len(code1) == 6  # SHORT_CODE_LENGTH
        assert token1 != token2
        assert code1 != code2

    def test_generate_qr_data(self):
        """generate_qr_data should create valid JSON."""
        import json
        from infrastructure.db.device_repository import generate_qr_data

        qr_data = generate_qr_data("test_token", "https://api.test.com")
        parsed = json.loads(qr_data)

        assert parsed["type"] == "amakaflow_pairing"
        assert parsed["version"] == 1
        assert parsed["token"] == "test_token"
        assert parsed["api_url"] == "https://api.test.com"


class TestExerciseMatchRepository:
    """Test InMemoryExerciseMatchRepository functionality."""

    def test_categorize_squat(self):
        """categorize should identify squat exercises."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        repo = InMemoryExerciseMatchRepository()
        assert repo.categorize("Barbell Back Squat") == "squat"
        assert repo.categorize("goblet squat") == "squat"

    def test_categorize_press(self):
        """categorize should identify press exercises."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        repo = InMemoryExerciseMatchRepository()
        assert repo.categorize("Bench Press") == "press"
        assert repo.categorize("shoulder press") == "press"

    def test_categorize_push_up(self):
        """categorize should identify push-up exercises."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        repo = InMemoryExerciseMatchRepository()
        assert repo.categorize("Push Up") == "push_up"
        assert repo.categorize("push-up") == "push_up"

    def test_categorize_unknown(self):
        """categorize should return None for unknown exercises."""
        from infrastructure.db.mapping_repository import InMemoryExerciseMatchRepository
        repo = InMemoryExerciseMatchRepository()
        assert repo.categorize("xyz unknown exercise") is None


# ============================================================================
# E2E Tests (require real database connection - nightly runs only)
# ============================================================================

def _is_real_supabase_url(url: str) -> bool:
    """Check if URL looks like a real Supabase URL (not a test placeholder)."""
    if not url:
        return False
    # Real Supabase URLs look like: https://<project-id>.supabase.co
    # Test/CI placeholders use things like: https://test.supabase.co
    return (
        url.startswith("https://") and
        ".supabase.co" in url and
        url != "https://test.supabase.co" and
        len(url) > 30  # Real project IDs are long
    )


@pytest.mark.e2e
class TestWorkoutRepositoryIntegration:
    """E2E tests for SupabaseWorkoutRepository (requires real database)."""

    @pytest.fixture
    def supabase_client(self):
        """Get a real Supabase client for e2e tests."""
        import os
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for e2e tests")

        if not _is_real_supabase_url(url):
            pytest.skip("Real Supabase credentials required for e2e tests (not test placeholders)")

        return create_client(url, key)

    def test_save_and_get_workout(self, supabase_client):
        """Test saving and retrieving a workout."""
        from infrastructure.db.workout_repository import SupabaseWorkoutRepository
        import uuid

        repo = SupabaseWorkoutRepository(supabase_client)
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        workout_data = {
            "title": "Test Integration Workout",
            "sport": "strength_training",
            "duration": 1800,
            "intervals": [{"kind": "work", "duration_sec": 30}]
        }

        result = repo.save(
            profile_id=test_user_id,
            workout_data=workout_data,
            sources=["test"],
            device="test_device",
            title="Test Integration Workout"
        )

        assert result is not None
        assert "id" in result

        # Clean up
        if result:
            repo.delete(result["id"], test_user_id)


@pytest.mark.e2e
class TestCompletionRepositoryIntegration:
    """E2E tests for SupabaseCompletionRepository (requires real database)."""

    @pytest.fixture
    def supabase_client(self):
        """Get a real Supabase client for e2e tests."""
        import os
        from supabase import create_client

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not url or not key:
            pytest.skip("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY required for e2e tests")

        if not _is_real_supabase_url(url):
            pytest.skip("Real Supabase credentials required for e2e tests (not test placeholders)")

        return create_client(url, key)

    def test_get_user_completions_empty(self, supabase_client):
        """Test getting completions for a user with no completions."""
        from infrastructure.db.completion_repository import SupabaseCompletionRepository
        import uuid

        repo = SupabaseCompletionRepository(supabase_client)
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        result = repo.get_user_completions(test_user_id)

        assert result["completions"] == []
        assert result["total"] == 0
