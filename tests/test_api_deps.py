"""
Unit tests for api/deps.py dependency providers.

Part of AMA-386: Create api/deps.py dependency providers
Phase 2 - Dependency Injection

These tests verify that the dependency providers are properly wired and
return the correct types. Uses mocks for external dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

# All tests in this module are pure logic tests with mocks - mark as unit
pytestmark = pytest.mark.unit


# =============================================================================
# Import Tests
# =============================================================================


class TestDepsImports:
    """Test that all dependency providers can be imported."""

    def test_import_get_settings(self):
        """get_settings should be importable from api.deps."""
        from api.deps import get_settings
        assert get_settings is not None

    def test_import_get_supabase_client(self):
        """get_supabase_client should be importable from api.deps."""
        from api.deps import get_supabase_client
        assert get_supabase_client is not None

    def test_import_get_supabase_client_required(self):
        """get_supabase_client_required should be importable from api.deps."""
        from api.deps import get_supabase_client_required
        assert get_supabase_client_required is not None

    def test_import_get_workout_repo(self):
        """get_workout_repo should be importable from api.deps."""
        from api.deps import get_workout_repo
        assert get_workout_repo is not None

    def test_import_get_completion_repo(self):
        """get_completion_repo should be importable from api.deps."""
        from api.deps import get_completion_repo
        assert get_completion_repo is not None

    def test_import_get_device_repo(self):
        """get_device_repo should be importable from api.deps."""
        from api.deps import get_device_repo
        assert get_device_repo is not None

    def test_import_get_user_profile_repo(self):
        """get_user_profile_repo should be importable from api.deps."""
        from api.deps import get_user_profile_repo
        assert get_user_profile_repo is not None

    def test_import_get_user_mapping_repo(self):
        """get_user_mapping_repo should be importable from api.deps."""
        from api.deps import get_user_mapping_repo
        assert get_user_mapping_repo is not None

    def test_import_get_global_mapping_repo(self):
        """get_global_mapping_repo should be importable from api.deps."""
        from api.deps import get_global_mapping_repo
        assert get_global_mapping_repo is not None

    def test_import_get_exercise_match_repo(self):
        """get_exercise_match_repo should be importable from api.deps."""
        from api.deps import get_exercise_match_repo
        assert get_exercise_match_repo is not None

    def test_import_get_current_user(self):
        """get_current_user should be importable from api.deps."""
        from api.deps import get_current_user
        assert get_current_user is not None

    def test_import_get_optional_user(self):
        """get_optional_user should be importable from api.deps."""
        from api.deps import get_optional_user
        assert get_optional_user is not None

    def test_import_from_api_package(self):
        """All providers should be importable from api package."""
        from api import (
            get_settings,
            get_supabase_client,
            get_supabase_client_required,
            get_workout_repo,
            get_completion_repo,
            get_device_repo,
            get_user_profile_repo,
            get_user_mapping_repo,
            get_global_mapping_repo,
            get_exercise_match_repo,
            get_current_user,
            get_optional_user,
        )
        assert all([
            get_settings,
            get_supabase_client,
            get_supabase_client_required,
            get_workout_repo,
            get_completion_repo,
            get_device_repo,
            get_user_profile_repo,
            get_user_mapping_repo,
            get_global_mapping_repo,
            get_exercise_match_repo,
            get_current_user,
            get_optional_user,
        ])


# =============================================================================
# Settings Provider Tests
# =============================================================================


class TestSettingsProvider:
    """Test get_settings provider."""

    def test_returns_settings_instance(self):
        """get_settings should return a Settings instance."""
        from api.deps import get_settings
        from backend.settings import Settings

        settings = get_settings()
        assert isinstance(settings, Settings)

    def test_is_cached(self):
        """get_settings should return the same cached instance."""
        from api.deps import get_settings

        settings1 = get_settings()
        settings2 = get_settings()
        assert settings1 is settings2


# =============================================================================
# Supabase Client Provider Tests
# =============================================================================


class TestSupabaseClientProvider:
    """Test get_supabase_client provider."""

    def test_returns_none_when_not_configured(self):
        """get_supabase_client should return None when credentials are missing."""
        from api.deps import get_supabase_client

        # Clear cache for testing
        get_supabase_client.cache_clear()

        with patch("api.deps._get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                supabase_url=None,
                supabase_key=None,
            )
            result = get_supabase_client()
            assert result is None

        # Restore cache state
        get_supabase_client.cache_clear()

    def test_creates_client_when_configured(self):
        """get_supabase_client should create client when credentials exist."""
        from api.deps import get_supabase_client

        # Clear cache for testing
        get_supabase_client.cache_clear()

        with patch("api.deps._get_settings") as mock_settings:
            mock_settings.return_value = Mock(
                supabase_url="https://test.supabase.co",
                supabase_key="test-key",
            )
            with patch("api.deps.create_client") as mock_create:
                mock_create.return_value = Mock()
                result = get_supabase_client()
                assert result is not None
                mock_create.assert_called_once_with(
                    "https://test.supabase.co", "test-key"
                )

        # Restore cache state
        get_supabase_client.cache_clear()


class TestSupabaseClientRequiredProvider:
    """Test get_supabase_client_required provider."""

    def test_raises_503_when_not_configured(self):
        """get_supabase_client_required should raise 503 when not configured."""
        from api.deps import get_supabase_client_required, get_supabase_client
        from fastapi import HTTPException

        # Clear cache for testing
        get_supabase_client.cache_clear()

        with patch("api.deps.get_supabase_client") as mock_get:
            mock_get.return_value = None
            with pytest.raises(HTTPException) as exc_info:
                get_supabase_client_required()
            assert exc_info.value.status_code == 503
            assert "Database not available" in exc_info.value.detail

    def test_returns_client_when_configured(self):
        """get_supabase_client_required should return client when available."""
        from api.deps import get_supabase_client_required

        mock_client = Mock()
        with patch("api.deps.get_supabase_client") as mock_get:
            mock_get.return_value = mock_client
            result = get_supabase_client_required()
            assert result is mock_client


# =============================================================================
# Repository Provider Tests
# =============================================================================


class TestRepositoryProviders:
    """Test repository provider functions."""

    def test_get_workout_repo_returns_correct_type(self):
        """get_workout_repo should return SupabaseWorkoutRepository."""
        from api.deps import get_workout_repo
        from infrastructure import SupabaseWorkoutRepository

        mock_client = Mock()
        repo = get_workout_repo(mock_client)
        assert isinstance(repo, SupabaseWorkoutRepository)
        assert repo._client is mock_client

    def test_get_completion_repo_returns_correct_type(self):
        """get_completion_repo should return SupabaseCompletionRepository."""
        from api.deps import get_completion_repo
        from infrastructure import SupabaseCompletionRepository

        mock_client = Mock()
        repo = get_completion_repo(mock_client)
        assert isinstance(repo, SupabaseCompletionRepository)
        assert repo._client is mock_client

    def test_get_device_repo_returns_correct_type(self):
        """get_device_repo should return SupabaseDeviceRepository."""
        from api.deps import get_device_repo
        from infrastructure import SupabaseDeviceRepository

        mock_client = Mock()
        repo = get_device_repo(mock_client)
        assert isinstance(repo, SupabaseDeviceRepository)
        assert repo._client is mock_client

    def test_get_user_profile_repo_returns_correct_type(self):
        """get_user_profile_repo should return SupabaseUserProfileRepository."""
        from api.deps import get_user_profile_repo
        from infrastructure import SupabaseUserProfileRepository

        mock_client = Mock()
        repo = get_user_profile_repo(mock_client)
        assert isinstance(repo, SupabaseUserProfileRepository)
        assert repo._client is mock_client

    def test_get_user_mapping_repo_returns_correct_type(self):
        """get_user_mapping_repo should return SupabaseUserMappingRepository."""
        from api.deps import get_user_mapping_repo
        from infrastructure import SupabaseUserMappingRepository

        mock_client = Mock()
        user_id = "test_user_123"
        repo = get_user_mapping_repo(mock_client, user_id)
        assert isinstance(repo, SupabaseUserMappingRepository)
        assert repo._client is mock_client
        assert repo._user_id == user_id

    def test_get_global_mapping_repo_returns_correct_type(self):
        """get_global_mapping_repo should return SupabaseGlobalMappingRepository."""
        from api.deps import get_global_mapping_repo
        from infrastructure import SupabaseGlobalMappingRepository

        mock_client = Mock()
        repo = get_global_mapping_repo(mock_client)
        assert isinstance(repo, SupabaseGlobalMappingRepository)
        assert repo._client is mock_client

    def test_get_exercise_match_repo_returns_correct_type(self):
        """get_exercise_match_repo should return InMemoryExerciseMatchRepository."""
        from api.deps import get_exercise_match_repo
        from infrastructure import InMemoryExerciseMatchRepository

        repo = get_exercise_match_repo()
        assert isinstance(repo, InMemoryExerciseMatchRepository)


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Test that repository providers return Protocol-compatible types."""

    def test_workout_repo_satisfies_protocol(self):
        """WorkoutRepository from provider should satisfy Protocol."""
        from api.deps import get_workout_repo
        from application.ports import WorkoutRepository

        mock_client = Mock()
        repo = get_workout_repo(mock_client)

        # Check all required Protocol methods exist
        required_methods = [
            "save", "get", "get_list", "delete", "update_export_status",
            "toggle_favorite", "track_usage", "update_tags", "get_incoming",
            "get_sync_status", "update_companion_sync"
        ]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_completion_repo_satisfies_protocol(self):
        """CompletionRepository from provider should satisfy Protocol."""
        from api.deps import get_completion_repo
        from application.ports import CompletionRepository

        mock_client = Mock()
        repo = get_completion_repo(mock_client)

        required_methods = [
            "save", "get_by_id", "get_user_completions",
            "save_voice_workout_with_completion", "get_completed_workout_ids"
        ]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_device_repo_satisfies_protocol(self):
        """DeviceRepository from provider should satisfy Protocol."""
        from api.deps import get_device_repo
        from application.ports import DeviceRepository

        mock_client = Mock()
        repo = get_device_repo(mock_client)

        required_methods = [
            "create_pairing_token", "validate_and_use_token", "get_pairing_status",
            "revoke_user_tokens", "get_paired_devices", "revoke_device", "refresh_jwt"
        ]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_user_profile_repo_satisfies_protocol(self):
        """UserProfileRepository from provider should satisfy Protocol."""
        from api.deps import get_user_profile_repo
        from application.ports import UserProfileRepository

        mock_client = Mock()
        repo = get_user_profile_repo(mock_client)

        required_methods = [
            "get_profile", "get_account_deletion_preview", "delete_account", "reset_data"
        ]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_user_mapping_repo_satisfies_protocol(self):
        """UserMappingRepository from provider should satisfy Protocol."""
        from api.deps import get_user_mapping_repo
        from application.ports import UserMappingRepository

        mock_client = Mock()
        repo = get_user_mapping_repo(mock_client, "test_user")

        required_methods = ["add", "remove", "get", "get_all", "clear_all"]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_global_mapping_repo_satisfies_protocol(self):
        """GlobalMappingRepository from provider should satisfy Protocol."""
        from api.deps import get_global_mapping_repo
        from application.ports import GlobalMappingRepository

        mock_client = Mock()
        repo = get_global_mapping_repo(mock_client)

        required_methods = ["record_choice", "get_popular", "get_stats"]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"

    def test_exercise_match_repo_satisfies_protocol(self):
        """ExerciseMatchRepository from provider should satisfy Protocol."""
        from api.deps import get_exercise_match_repo
        from application.ports import ExerciseMatchRepository

        repo = get_exercise_match_repo()

        required_methods = [
            "find_match", "get_suggestions", "find_similar", "find_by_type", "categorize"
        ]
        for method in required_methods:
            assert hasattr(repo, method), f"Missing method: {method}"


# =============================================================================
# Authentication Provider Tests
# =============================================================================


class TestAuthProviders:
    """Test authentication provider functions."""

    @pytest.mark.asyncio
    async def test_get_current_user_wraps_backend_auth(self):
        """get_current_user should delegate to backend.auth."""
        from api.deps import get_current_user

        with patch("api.deps._get_current_user") as mock_auth:
            mock_auth.return_value = "user_123"
            result = await get_current_user(
                authorization="Bearer test_token",
                x_api_key=None,
                x_test_auth=None,
                x_test_user_id=None,
            )
            assert result == "user_123"
            mock_auth.assert_called_once_with(
                authorization="Bearer test_token",
                x_api_key=None,
                x_test_auth=None,
                x_test_user_id=None,
            )

    @pytest.mark.asyncio
    async def test_get_optional_user_wraps_backend_auth(self):
        """get_optional_user should delegate to backend.auth."""
        from api.deps import get_optional_user

        with patch("api.deps._get_optional_user") as mock_auth:
            mock_auth.return_value = "user_456"
            result = await get_optional_user(
                authorization="Bearer test_token",
                x_api_key=None,
                x_test_auth=None,
                x_test_user_id=None,
            )
            assert result == "user_456"

    @pytest.mark.asyncio
    async def test_get_optional_user_returns_none_when_unauthenticated(self):
        """get_optional_user should return None when not authenticated."""
        from api.deps import get_optional_user

        with patch("api.deps._get_optional_user") as mock_auth:
            mock_auth.return_value = None
            result = await get_optional_user(
                authorization=None,
                x_api_key=None,
                x_test_auth=None,
                x_test_user_id=None,
            )
            assert result is None


# =============================================================================
# Exports Test
# =============================================================================


class TestExports:
    """Test __all__ exports are correct."""

    def test_all_exports_exist(self):
        """All items in __all__ should be importable."""
        import api.deps as deps

        for name in deps.__all__:
            assert hasattr(deps, name), f"Missing export: {name}"
            assert getattr(deps, name) is not None
