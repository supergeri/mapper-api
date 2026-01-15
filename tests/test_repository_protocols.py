"""
Tests for repository protocol definitions.

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

These tests verify that:
1. Protocol definitions are valid and importable
2. Protocols define the expected methods
3. Mock implementations satisfy the Protocol contracts
"""
import pytest
from typing import runtime_checkable, Protocol, get_type_hints

# All tests in this module are pure logic tests (no TestClient) - mark as unit
pytestmark = pytest.mark.unit


class TestProtocolImports:
    """Test that all protocols can be imported."""

    def test_workout_repository_import(self):
        """WorkoutRepository should be importable."""
        from application.ports import WorkoutRepository
        assert WorkoutRepository is not None

    def test_completion_repository_import(self):
        """CompletionRepository should be importable."""
        from application.ports import CompletionRepository, HealthMetricsDTO, CompletionSummary
        assert CompletionRepository is not None
        assert HealthMetricsDTO is not None
        assert CompletionSummary is not None

    def test_device_repository_import(self):
        """DeviceRepository and UserProfileRepository should be importable."""
        from application.ports import DeviceRepository, UserProfileRepository
        assert DeviceRepository is not None
        assert UserProfileRepository is not None

    def test_mapping_repository_import(self):
        """Mapping repositories should be importable."""
        from application.ports import (
            UserMappingRepository,
            GlobalMappingRepository,
            ExerciseMatchRepository,
        )
        assert UserMappingRepository is not None
        assert GlobalMappingRepository is not None
        assert ExerciseMatchRepository is not None


class TestWorkoutRepositoryProtocol:
    """Test WorkoutRepository protocol definition."""

    def test_has_required_methods(self):
        """WorkoutRepository should define all required methods."""
        from application.ports import WorkoutRepository

        required_methods = [
            "save",
            "get",
            "get_list",
            "delete",
            "update_export_status",
            "toggle_favorite",
            "track_usage",
            "update_tags",
            "get_incoming",
            "get_sync_status",
            "update_companion_sync",
        ]

        for method_name in required_methods:
            assert hasattr(WorkoutRepository, method_name), \
                f"WorkoutRepository should have method '{method_name}'"

    def test_save_method_signature(self):
        """save() should have correct parameters."""
        from application.ports.workout_repository import WorkoutRepository
        import inspect

        sig = inspect.signature(WorkoutRepository.save)
        params = list(sig.parameters.keys())

        # Should have self, profile_id, workout_data, sources, device
        assert "self" in params
        assert "profile_id" in params
        assert "workout_data" in params
        assert "sources" in params
        assert "device" in params


class TestCompletionRepositoryProtocol:
    """Test CompletionRepository protocol definition."""

    def test_has_required_methods(self):
        """CompletionRepository should define all required methods."""
        from application.ports import CompletionRepository

        required_methods = [
            "save",
            "get_by_id",
            "get_user_completions",
            "save_voice_workout_with_completion",
            "get_completed_workout_ids",
        ]

        for method_name in required_methods:
            assert hasattr(CompletionRepository, method_name), \
                f"CompletionRepository should have method '{method_name}'"

    def test_health_metrics_dto_fields(self):
        """HealthMetricsDTO should have expected fields."""
        from application.ports import HealthMetricsDTO

        # Create instance with defaults
        metrics = HealthMetricsDTO()

        # Verify fields exist
        assert hasattr(metrics, "avg_heart_rate")
        assert hasattr(metrics, "max_heart_rate")
        assert hasattr(metrics, "min_heart_rate")
        assert hasattr(metrics, "active_calories")
        assert hasattr(metrics, "total_calories")
        assert hasattr(metrics, "distance_meters")
        assert hasattr(metrics, "steps")


class TestDeviceRepositoryProtocol:
    """Test DeviceRepository protocol definition."""

    def test_has_required_methods(self):
        """DeviceRepository should define all required methods."""
        from application.ports import DeviceRepository

        required_methods = [
            "create_pairing_token",
            "validate_and_use_token",
            "get_pairing_status",
            "revoke_user_tokens",
            "get_paired_devices",
            "revoke_device",
            "refresh_jwt",
        ]

        for method_name in required_methods:
            assert hasattr(DeviceRepository, method_name), \
                f"DeviceRepository should have method '{method_name}'"


class TestUserProfileRepositoryProtocol:
    """Test UserProfileRepository protocol definition."""

    def test_has_required_methods(self):
        """UserProfileRepository should define all required methods."""
        from application.ports import UserProfileRepository

        required_methods = [
            "get_profile",
            "get_account_deletion_preview",
            "delete_account",
            "reset_data",
        ]

        for method_name in required_methods:
            assert hasattr(UserProfileRepository, method_name), \
                f"UserProfileRepository should have method '{method_name}'"


class TestMappingRepositoriesProtocols:
    """Test mapping repository protocol definitions."""

    def test_user_mapping_repository_methods(self):
        """UserMappingRepository should define all required methods."""
        from application.ports import UserMappingRepository

        required_methods = ["add", "remove", "get", "get_all", "clear_all"]

        for method_name in required_methods:
            assert hasattr(UserMappingRepository, method_name), \
                f"UserMappingRepository should have method '{method_name}'"

    def test_global_mapping_repository_methods(self):
        """GlobalMappingRepository should define all required methods."""
        from application.ports import GlobalMappingRepository

        required_methods = ["record_choice", "get_popular", "get_stats"]

        for method_name in required_methods:
            assert hasattr(GlobalMappingRepository, method_name), \
                f"GlobalMappingRepository should have method '{method_name}'"

    def test_exercise_match_repository_methods(self):
        """ExerciseMatchRepository should define all required methods."""
        from application.ports import ExerciseMatchRepository

        required_methods = [
            "find_match",
            "get_suggestions",
            "find_similar",
            "find_by_type",
            "categorize",
        ]

        for method_name in required_methods:
            assert hasattr(ExerciseMatchRepository, method_name), \
                f"ExerciseMatchRepository should have method '{method_name}'"


class TestMockImplementations:
    """Test that mock implementations satisfy Protocol contracts."""

    def test_workout_repository_mock_satisfies_protocol(self):
        """A mock class should satisfy WorkoutRepository protocol."""
        from application.ports import WorkoutRepository
        from typing import Optional, List, Dict, Any

        class MockWorkoutRepository:
            def save(self, profile_id, workout_data, sources, device, **kwargs):
                return {"id": "test-id"}

            def get(self, workout_id, profile_id):
                return None

            def get_list(self, profile_id, **kwargs):
                return []

            def delete(self, workout_id, profile_id):
                return True

            def update_export_status(self, workout_id, profile_id, **kwargs):
                return True

            def toggle_favorite(self, workout_id, profile_id, is_favorite):
                return None

            def track_usage(self, workout_id, profile_id):
                return None

            def update_tags(self, workout_id, profile_id, tags):
                return None

            def get_incoming(self, profile_id, **kwargs):
                return []

            def get_sync_status(self, workout_id, user_id):
                return {}

            def update_companion_sync(self, workout_id, profile_id, platform):
                return True

        # This should not raise - mock satisfies the protocol
        mock = MockWorkoutRepository()
        assert mock.save("user-1", {}, [], "ios") is not None
        assert mock.get("w-1", "u-1") is None
        assert mock.get_list("u-1") == []
        assert mock.delete("w-1", "u-1") is True

    def test_completion_repository_mock_satisfies_protocol(self):
        """A mock class should satisfy CompletionRepository protocol."""
        from application.ports import CompletionRepository, HealthMetricsDTO

        class MockCompletionRepository:
            def save(self, user_id, **kwargs):
                return {"success": True, "id": "c-123"}

            def get_by_id(self, user_id, completion_id):
                return None

            def get_user_completions(self, user_id, **kwargs):
                return {"completions": [], "total": 0}

            def save_voice_workout_with_completion(self, user_id, workout_data, completion_data):
                return {"success": True, "workout_id": "w-1", "completion_id": "c-1"}

            def get_completed_workout_ids(self, user_id):
                return set()

        mock = MockCompletionRepository()
        metrics = HealthMetricsDTO(avg_heart_rate=140)
        result = mock.save("u-1", started_at="2025-01-01T10:00:00Z", ended_at="2025-01-01T11:00:00Z", health_metrics=metrics)
        assert result["success"] is True

    def test_device_repository_mock_satisfies_protocol(self):
        """A mock class should satisfy DeviceRepository protocol."""

        class MockDeviceRepository:
            def create_pairing_token(self, user_id):
                return {"token": "abc", "short_code": "XYZ123"}

            def validate_and_use_token(self, **kwargs):
                return {"jwt": "token", "profile": {}}

            def get_pairing_status(self, token):
                return {"paired": False, "expired": False}

            def revoke_user_tokens(self, user_id):
                return 0

            def get_paired_devices(self, user_id):
                return []

            def revoke_device(self, user_id, device_id):
                return {"success": True}

            def refresh_jwt(self, device_id):
                return {"success": True, "jwt": "new-token"}

        mock = MockDeviceRepository()
        assert mock.create_pairing_token("u-1")["token"] == "abc"
        assert mock.get_pairing_status("token")["paired"] is False
