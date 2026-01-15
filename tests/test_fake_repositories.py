"""
Unit tests for fake repository implementations.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

These tests verify that fake repositories:
- Correctly implement Protocol interfaces
- Support seeding and reset for test isolation
- Return expected values for all operations
"""
import pytest
from datetime import datetime, timezone

from application.ports import HealthMetricsDTO

# All tests in this module are pure logic tests (no TestClient) - mark as unit
pytestmark = pytest.mark.unit


# =============================================================================
# Import Tests
# =============================================================================


class TestFakeImports:
    """Test that all fake repositories can be imported."""

    def test_import_fake_workout_repository(self):
        """FakeWorkoutRepository should be importable."""
        from tests.fakes import FakeWorkoutRepository
        assert FakeWorkoutRepository is not None

    def test_import_fake_completion_repository(self):
        """FakeCompletionRepository should be importable."""
        from tests.fakes import FakeCompletionRepository
        assert FakeCompletionRepository is not None

    def test_import_fake_device_repository(self):
        """FakeDeviceRepository should be importable."""
        from tests.fakes import FakeDeviceRepository
        assert FakeDeviceRepository is not None

    def test_import_fake_user_profile_repository(self):
        """FakeUserProfileRepository should be importable."""
        from tests.fakes import FakeUserProfileRepository
        assert FakeUserProfileRepository is not None

    def test_import_fake_user_mapping_repository(self):
        """FakeUserMappingRepository should be importable."""
        from tests.fakes import FakeUserMappingRepository
        assert FakeUserMappingRepository is not None

    def test_import_fake_global_mapping_repository(self):
        """FakeGlobalMappingRepository should be importable."""
        from tests.fakes import FakeGlobalMappingRepository
        assert FakeGlobalMappingRepository is not None

    def test_import_fake_exercise_match_repository(self):
        """FakeExerciseMatchRepository should be importable."""
        from tests.fakes import FakeExerciseMatchRepository
        assert FakeExerciseMatchRepository is not None

    def test_import_factory_functions(self):
        """All factory functions should be importable."""
        from tests.fakes import (
            create_workout_repo,
            create_completion_repo,
            create_device_repo,
            create_user_profile_repo,
            create_user_mapping_repo,
            create_global_mapping_repo,
            create_exercise_match_repo,
        )
        assert all([
            create_workout_repo,
            create_completion_repo,
            create_device_repo,
            create_user_profile_repo,
            create_user_mapping_repo,
            create_global_mapping_repo,
            create_exercise_match_repo,
        ])


# =============================================================================
# FakeWorkoutRepository Tests
# =============================================================================


class TestFakeWorkoutRepository:
    """Tests for FakeWorkoutRepository."""

    def test_save_and_get(self):
        """Should save and retrieve a workout."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(
            profile_id="user1",
            workout_data={"title": "Test", "sport": "strength"},
            sources=["test"],
            device="garmin",
            title="Test Workout",
        )

        assert result is not None
        assert result["title"] == "Test Workout"
        assert result["profile_id"] == "user1"

        # Retrieve
        fetched = repo.get(result["id"], "user1")
        assert fetched is not None
        assert fetched["title"] == "Test Workout"

    def test_get_returns_none_for_wrong_user(self):
        """Should not return workout for unauthorized user."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(
            profile_id="user1",
            workout_data={},
            sources=[],
            device="garmin",
        )

        fetched = repo.get(result["id"], "user2")
        assert fetched is None

    def test_get_list_filters_by_device(self):
        """Should filter workouts by device."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")
        repo.save(profile_id="u1", workout_data={}, sources=[], device="apple")
        repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")

        garmin_only = repo.get_list("u1", device="garmin")
        assert len(garmin_only) == 2

    def test_delete(self):
        """Should delete a workout."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")
        workout_id = result["id"]

        deleted = repo.delete(workout_id, "u1")
        assert deleted is True

        fetched = repo.get(workout_id, "u1")
        assert fetched is None

    def test_toggle_favorite(self):
        """Should toggle favorite status."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")

        updated = repo.toggle_favorite(result["id"], "u1", True)
        assert updated["is_favorite"] is True

        updated = repo.toggle_favorite(result["id"], "u1", False)
        assert updated["is_favorite"] is False

    def test_track_usage(self):
        """Should increment times_completed."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")

        updated = repo.track_usage(result["id"], "u1")
        assert updated["times_completed"] == 1
        assert updated["last_used_at"] is not None

        updated = repo.track_usage(result["id"], "u1")
        assert updated["times_completed"] == 2

    def test_update_tags(self):
        """Should update workout tags."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        result = repo.save(profile_id="u1", workout_data={}, sources=[], device="garmin")

        updated = repo.update_tags(result["id"], "u1", ["hiit", "upper"])
        assert updated["tags"] == ["hiit", "upper"]

    def test_seed_and_reset(self):
        """Should support seeding and resetting."""
        from tests.fakes import FakeWorkoutRepository

        repo = FakeWorkoutRepository()
        repo.seed([
            {"id": "w1", "profile_id": "u1", "title": "Seeded"},
        ])

        assert len(repo.get_all()) == 1

        repo.reset()
        assert len(repo.get_all()) == 0


# =============================================================================
# FakeCompletionRepository Tests
# =============================================================================


class TestFakeCompletionRepository:
    """Tests for FakeCompletionRepository."""

    def test_save_and_get(self):
        """Should save and retrieve a completion."""
        from tests.fakes import FakeCompletionRepository

        repo = FakeCompletionRepository()
        result = repo.save(
            user_id="user1",
            started_at="2024-01-01T10:00:00Z",
            ended_at="2024-01-01T10:30:00Z",
            health_metrics=HealthMetricsDTO(avg_heart_rate=120, active_calories=200),
        )

        assert result["success"] is True
        assert "completion_id" in result
        assert result["summary"]["duration_formatted"] == "30:00"

        # Retrieve
        fetched = repo.get_by_id("user1", result["completion_id"])
        assert fetched is not None
        assert fetched["avg_heart_rate"] == 120

    def test_get_user_completions(self):
        """Should return user's completions with pagination."""
        from tests.fakes import FakeCompletionRepository

        repo = FakeCompletionRepository()
        for i in range(5):
            repo.save(
                user_id="u1",
                started_at="2024-01-01T10:00:00Z",
                ended_at="2024-01-01T10:30:00Z",
                health_metrics=HealthMetricsDTO(),
            )

        result = repo.get_user_completions("u1", limit=3)
        assert len(result["completions"]) == 3
        assert result["total"] == 5

    def test_get_completed_workout_ids(self):
        """Should return IDs of completed workouts."""
        from tests.fakes import FakeCompletionRepository

        repo = FakeCompletionRepository()
        repo.save(
            user_id="u1",
            started_at="2024-01-01T10:00:00Z",
            ended_at="2024-01-01T10:30:00Z",
            health_metrics=HealthMetricsDTO(),
            workout_id="w1",
        )
        repo.save(
            user_id="u1",
            started_at="2024-01-01T11:00:00Z",
            ended_at="2024-01-01T11:30:00Z",
            health_metrics=HealthMetricsDTO(),
            workout_id="w2",
        )

        completed = repo.get_completed_workout_ids("u1")
        assert "w1" in completed
        assert "w2" in completed


# =============================================================================
# FakeDeviceRepository Tests
# =============================================================================


class TestFakeDeviceRepository:
    """Tests for FakeDeviceRepository."""

    def test_create_and_validate_token(self):
        """Should create and validate pairing tokens."""
        from tests.fakes import FakeDeviceRepository

        repo = FakeDeviceRepository()
        token_result = repo.create_pairing_token("user1")

        assert "token" in token_result
        assert "short_code" in token_result
        assert "qr_data" in token_result

        # Validate
        validate_result = repo.validate_and_use_token(
            token=token_result["token"],
            device_info={"model": "iPhone 15"},
        )

        assert "jwt" in validate_result
        assert "profile" in validate_result

    def test_token_can_only_be_used_once(self):
        """Should reject already-used tokens."""
        from tests.fakes import FakeDeviceRepository

        repo = FakeDeviceRepository()
        token_result = repo.create_pairing_token("user1")

        # First use succeeds
        repo.validate_and_use_token(token=token_result["token"])

        # Second use fails
        result = repo.validate_and_use_token(token=token_result["token"])
        assert result["error"] == "token_used"

    def test_get_paired_devices(self):
        """Should return list of paired devices."""
        from tests.fakes import FakeDeviceRepository

        repo = FakeDeviceRepository()

        # Create and use a token
        token_result = repo.create_pairing_token("user1")
        repo.validate_and_use_token(
            token=token_result["token"],
            device_info={"device_id": "device1", "model": "iPhone"},
        )

        devices = repo.get_paired_devices("user1")
        assert len(devices) == 1

    def test_revoke_device(self):
        """Should revoke a paired device."""
        from tests.fakes import FakeDeviceRepository

        repo = FakeDeviceRepository()
        repo.seed_devices([{
            "device_id": "d1",
            "user_id": "u1",
        }])

        result = repo.revoke_device("u1", "d1")
        assert result["success"] is True

        # Should no longer appear in paired devices
        devices = repo.get_paired_devices("u1")
        assert len(devices) == 0


# =============================================================================
# FakeUserProfileRepository Tests
# =============================================================================


class TestFakeUserProfileRepository:
    """Tests for FakeUserProfileRepository."""

    def test_get_profile(self):
        """Should return user profile."""
        from tests.fakes import FakeUserProfileRepository

        repo = FakeUserProfileRepository()
        repo.seed([{
            "id": "user1",
            "email": "test@example.com",
            "name": "Test User",
        }])

        profile = repo.get_profile("user1")
        assert profile is not None
        assert profile["email"] == "test@example.com"

    def test_get_account_deletion_preview(self):
        """Should return deletion preview with counts."""
        from tests.fakes import FakeUserProfileRepository

        repo = FakeUserProfileRepository()
        repo.set_data_counts("user1", {
            "workouts": 10,
            "completions": 5,
        })

        preview = repo.get_account_deletion_preview("user1")
        assert preview["workouts"] == 10
        assert preview["completions"] == 5


# =============================================================================
# FakeUserMappingRepository Tests
# =============================================================================


class TestFakeUserMappingRepository:
    """Tests for FakeUserMappingRepository."""

    def test_add_and_get(self):
        """Should add and retrieve mappings."""
        from tests.fakes import FakeUserMappingRepository

        repo = FakeUserMappingRepository("user1")
        repo.add("bench press", "Barbell Bench Press")

        result = repo.get("bench press")
        assert result == "Barbell Bench Press"

    def test_get_all(self):
        """Should return all mappings."""
        from tests.fakes import FakeUserMappingRepository

        repo = FakeUserMappingRepository("user1")
        repo.add("squat", "Barbell Back Squat")
        repo.add("deadlift", "Conventional Deadlift")

        all_mappings = repo.get_all()
        assert len(all_mappings) == 2

    def test_remove(self):
        """Should remove a mapping."""
        from tests.fakes import FakeUserMappingRepository

        repo = FakeUserMappingRepository("user1")
        repo.add("squat", "Barbell Back Squat")

        removed = repo.remove("squat")
        assert removed is True

        result = repo.get("squat")
        assert result is None


# =============================================================================
# FakeGlobalMappingRepository Tests
# =============================================================================


class TestFakeGlobalMappingRepository:
    """Tests for FakeGlobalMappingRepository."""

    def test_record_and_get_popular(self):
        """Should record choices and return popular mappings."""
        from tests.fakes import FakeGlobalMappingRepository

        repo = FakeGlobalMappingRepository()
        repo.record_choice("bench press", "Barbell Bench Press")
        repo.record_choice("bench press", "Barbell Bench Press")
        repo.record_choice("bench press", "Dumbbell Bench Press")

        popular = repo.get_popular("bench press")
        assert len(popular) == 2
        assert popular[0] == ("Barbell Bench Press", 2)
        assert popular[1] == ("Dumbbell Bench Press", 1)

    def test_get_stats(self):
        """Should return popularity statistics."""
        from tests.fakes import FakeGlobalMappingRepository

        repo = FakeGlobalMappingRepository()
        repo.seed({
            "bench press": {"Barbell Bench Press": 100},
            "squat": {"Barbell Back Squat": 80, "Goblet Squat": 20},
        })

        stats = repo.get_stats()
        assert stats["total_choices"] == 200
        assert stats["unique_exercises"] == 2
        assert stats["unique_mappings"] == 3


# =============================================================================
# FakeExerciseMatchRepository Tests
# =============================================================================


class TestFakeExerciseMatchRepository:
    """Tests for FakeExerciseMatchRepository."""

    def test_find_match(self):
        """Should find seeded matches."""
        from tests.fakes import FakeExerciseMatchRepository

        repo = FakeExerciseMatchRepository()
        repo.seed_matches({
            "bench press": ("Barbell Bench Press", 0.95),
        })

        name, confidence = repo.find_match("bench press")
        assert name == "Barbell Bench Press"
        assert confidence == 0.95

    def test_find_match_respects_threshold(self):
        """Should return None if below threshold."""
        from tests.fakes import FakeExerciseMatchRepository

        repo = FakeExerciseMatchRepository()
        repo.seed_matches({
            "weird exercise": ("Something", 0.2),
        })

        name, confidence = repo.find_match("weird exercise", threshold=0.5)
        assert name is None
        assert confidence == 0.0

    def test_categorize(self):
        """Should categorize exercises correctly."""
        from tests.fakes import FakeExerciseMatchRepository

        repo = FakeExerciseMatchRepository()

        assert repo.categorize("Barbell Back Squat") == "squat"
        assert repo.categorize("Bench Press") == "press"
        assert repo.categorize("Push Up") == "push_up"
        assert repo.categorize("Unknown Exercise XYZ") is None


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_workout_repo_empty(self):
        """Should create empty workout repo."""
        from tests.fakes import create_workout_repo

        repo = create_workout_repo()
        assert len(repo.get_all()) == 0

    def test_create_workout_repo_with_data(self):
        """Should create workout repo with sample data."""
        from tests.fakes import create_workout_repo

        repo = create_workout_repo(user_id="user1", num_workouts=5)
        workouts = repo.get_list("user1")
        assert len(workouts) == 5

    def test_create_completion_repo_with_data(self):
        """Should create completion repo with sample data."""
        from tests.fakes import create_completion_repo

        repo = create_completion_repo(user_id="user1", num_completions=3)
        result = repo.get_user_completions("user1")
        assert result["total"] == 3

    def test_create_user_profile_repo(self):
        """Should create profile repo with profile."""
        from tests.fakes import create_user_profile_repo

        repo = create_user_profile_repo(
            user_id="user1",
            email="custom@example.com",
            name="Custom User",
        )

        profile = repo.get_profile("user1")
        assert profile["email"] == "custom@example.com"

    def test_create_user_mapping_repo_with_mappings(self):
        """Should create mapping repo with pre-defined mappings."""
        from tests.fakes import create_user_mapping_repo

        repo = create_user_mapping_repo(
            user_id="user1",
            mappings={"squat": "Barbell Back Squat"},
        )

        result = repo.get("squat")
        assert result == "Barbell Back Squat"

    def test_create_exercise_match_repo_with_matches(self):
        """Should create exercise match repo with matches."""
        from tests.fakes import create_exercise_match_repo

        repo = create_exercise_match_repo(
            matches={"bench": ("Bench Press", 0.9)},
        )

        name, confidence = repo.find_match("bench")
        assert name == "Bench Press"


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Test that fakes implement all Protocol methods."""

    def test_workout_repo_has_all_methods(self):
        """FakeWorkoutRepository should have all Protocol methods."""
        from tests.fakes import FakeWorkoutRepository
        from application.ports import WorkoutRepository

        required = [
            "save", "get", "get_list", "delete", "update_export_status",
            "toggle_favorite", "track_usage", "update_tags", "get_incoming",
            "get_sync_status", "update_companion_sync",
        ]

        for method in required:
            assert hasattr(FakeWorkoutRepository, method), f"Missing: {method}"

    def test_completion_repo_has_all_methods(self):
        """FakeCompletionRepository should have all Protocol methods."""
        from tests.fakes import FakeCompletionRepository

        required = [
            "save", "get_by_id", "get_user_completions",
            "save_voice_workout_with_completion", "get_completed_workout_ids",
        ]

        for method in required:
            assert hasattr(FakeCompletionRepository, method), f"Missing: {method}"

    def test_device_repo_has_all_methods(self):
        """FakeDeviceRepository should have all Protocol methods."""
        from tests.fakes import FakeDeviceRepository

        required = [
            "create_pairing_token", "validate_and_use_token", "get_pairing_status",
            "revoke_user_tokens", "get_paired_devices", "revoke_device", "refresh_jwt",
        ]

        for method in required:
            assert hasattr(FakeDeviceRepository, method), f"Missing: {method}"

    def test_user_profile_repo_has_all_methods(self):
        """FakeUserProfileRepository should have all Protocol methods."""
        from tests.fakes import FakeUserProfileRepository

        required = [
            "get_profile", "get_account_deletion_preview", "delete_account", "reset_data",
        ]

        for method in required:
            assert hasattr(FakeUserProfileRepository, method), f"Missing: {method}"

    def test_user_mapping_repo_has_all_methods(self):
        """FakeUserMappingRepository should have all Protocol methods."""
        from tests.fakes import FakeUserMappingRepository

        required = ["add", "remove", "get", "get_all", "clear_all"]

        for method in required:
            assert hasattr(FakeUserMappingRepository, method), f"Missing: {method}"

    def test_global_mapping_repo_has_all_methods(self):
        """FakeGlobalMappingRepository should have all Protocol methods."""
        from tests.fakes import FakeGlobalMappingRepository

        required = ["record_choice", "get_popular", "get_stats"]

        for method in required:
            assert hasattr(FakeGlobalMappingRepository, method), f"Missing: {method}"

    def test_exercise_match_repo_has_all_methods(self):
        """FakeExerciseMatchRepository should have all Protocol methods."""
        from tests.fakes import FakeExerciseMatchRepository

        required = [
            "find_match", "get_suggestions", "find_similar", "find_by_type", "categorize",
        ]

        for method in required:
            assert hasattr(FakeExerciseMatchRepository, method), f"Missing: {method}"
