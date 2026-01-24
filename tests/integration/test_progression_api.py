"""
Integration tests for Progression API endpoints.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

Tests cover:
- Exercise history endpoint
- Last weight endpoint
- Personal records endpoint
- Volume analytics endpoint
"""
import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient

from backend.main import create_app
from api.deps import (
    get_current_user,
    get_progression_repo,
    get_exercises_repo,
)
from tests.fakes import FakeProgressionRepository, FakeExercisesRepository


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def exercises_repo():
    """Create a fake exercises repository with test data."""
    return FakeExercisesRepository(exercises=[
        {
            "id": "barbell-bench-press",
            "name": "Barbell Bench Press",
            "aliases": ["Bench Press"],
            "primary_muscles": ["chest"],
            "secondary_muscles": ["triceps", "shoulders"],
            "equipment": ["barbell", "bench"],
            "supports_1rm": True,
            "one_rm_formula": "brzycki",
            "category": "compound",
        },
        {
            "id": "barbell-squat",
            "name": "Barbell Squat",
            "aliases": ["Back Squat"],
            "primary_muscles": ["quadriceps"],
            "secondary_muscles": ["glutes", "hamstrings"],
            "equipment": ["barbell"],
            "supports_1rm": True,
            "one_rm_formula": "brzycki",
            "category": "compound",
        },
    ])


@pytest.fixture
def progression_repo():
    """Create a fake progression repository with test data."""
    repo = FakeProgressionRepository()

    # Add bench press sessions
    repo.seed_sessions("test_user", [
        {
            "completion_id": "comp_1",
            "workout_date": "2024-01-15",
            "workout_name": "Push Day",
            "exercise_id": "barbell-bench-press",
            "exercise_name": "Barbell Bench Press",
            "sets": [
                {"set_number": 1, "weight": 185, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
                {"set_number": 2, "weight": 185, "weight_unit": "lbs", "reps_completed": 7, "status": "completed"},
                {"set_number": 3, "weight": 185, "weight_unit": "lbs", "reps_completed": 6, "status": "completed"},
            ],
        },
        {
            "completion_id": "comp_2",
            "workout_date": "2024-01-08",
            "workout_name": "Push Day",
            "exercise_id": "barbell-bench-press",
            "exercise_name": "Barbell Bench Press",
            "sets": [
                {"set_number": 1, "weight": 175, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
                {"set_number": 2, "weight": 175, "weight_unit": "lbs", "reps_completed": 8, "status": "completed"},
            ],
        },
    ])

    # Add squat sessions
    repo.seed_sessions("test_user", [
        {
            "completion_id": "comp_3",
            "workout_date": "2024-01-16",
            "workout_name": "Leg Day",
            "exercise_id": "barbell-squat",
            "exercise_name": "Barbell Squat",
            "sets": [
                {"set_number": 1, "weight": 225, "weight_unit": "lbs", "reps_completed": 5, "status": "completed"},
            ],
        },
    ])

    # Add exercise metadata
    repo.seed_exercise_metadata("barbell-bench-press", {
        "id": "barbell-bench-press",
        "name": "Barbell Bench Press",
        "primary_muscles": ["chest"],
    })
    repo.seed_exercise_metadata("barbell-squat", {
        "id": "barbell-squat",
        "name": "Barbell Squat",
        "primary_muscles": ["quadriceps"],
    })

    return repo


@pytest.fixture
def client(progression_repo, exercises_repo):
    """Create a test client with fake dependencies."""
    app = create_app()

    # Override dependencies
    async def mock_user():
        return "test_user"

    def mock_exercises_repo():
        return exercises_repo

    def mock_progression_repo():
        return progression_repo

    app.dependency_overrides[get_current_user] = mock_user
    app.dependency_overrides[get_exercises_repo] = mock_exercises_repo
    app.dependency_overrides[get_progression_repo] = mock_progression_repo

    yield TestClient(app)

    # Cleanup: clear dependency overrides
    app.dependency_overrides.clear()


# =============================================================================
# Exercise History Tests
# =============================================================================


@pytest.mark.integration
class TestExerciseHistoryEndpoint:
    """Tests for GET /progression/exercises/{exercise_id}/history."""

    def test_returns_exercise_history(self, client):
        """Successfully returns exercise history."""
        response = client.get("/progression/exercises/barbell-bench-press/history")

        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] == "barbell-bench-press"
        assert data["exercise_name"] == "Barbell Bench Press"
        assert len(data["sessions"]) == 2

    def test_includes_1rm_calculations(self, client):
        """Response includes 1RM calculations."""
        response = client.get("/progression/exercises/barbell-bench-press/history")

        data = response.json()
        assert data["supports_1rm"] is True
        assert data["one_rm_formula"] == "brzycki"

        # Check first set has estimated 1RM
        first_set = data["sessions"][0]["sets"][0]
        assert first_set["estimated_1rm"] is not None
        assert first_set["estimated_1rm"] > 200  # 185 x 8 ≈ 230

    def test_includes_session_metrics(self, client):
        """Sessions include best 1RM and volume metrics."""
        response = client.get("/progression/exercises/barbell-bench-press/history")

        data = response.json()
        session = data["sessions"][0]
        assert session["session_best_1rm"] is not None
        assert session["session_max_weight"] == 185

    def test_includes_all_time_best(self, client):
        """Response includes all-time best metrics."""
        response = client.get("/progression/exercises/barbell-bench-press/history")

        data = response.json()
        assert data["all_time_best_1rm"] is not None
        assert data["all_time_max_weight"] == 185

    def test_respects_limit_parameter(self, client):
        """Limit parameter restricts results."""
        response = client.get("/progression/exercises/barbell-bench-press/history?limit=1")

        data = response.json()
        assert len(data["sessions"]) == 1
        assert data["total_sessions"] == 2  # Total is still 2

    def test_respects_offset_parameter(self, client):
        """Offset parameter skips results."""
        response = client.get("/progression/exercises/barbell-bench-press/history?offset=1")

        data = response.json()
        assert len(data["sessions"]) == 1
        # Should be the older session
        assert data["sessions"][0]["workout_date"] == "2024-01-08"

    def test_returns_404_for_unknown_exercise(self, client):
        """Returns 404 for non-existent exercise."""
        response = client.get("/progression/exercises/unknown-exercise/history")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_validates_exercise_id_format(self, client):
        """Rejects invalid exercise ID format."""
        response = client.get("/progression/exercises/INVALID ID!/history")

        assert response.status_code == 400
        assert "Invalid exercise_id format" in response.json()["detail"]


# =============================================================================
# Last Weight Tests
# =============================================================================


@pytest.mark.integration
class TestLastWeightEndpoint:
    """Tests for GET /progression/exercises/{exercise_id}/last-weight."""

    def test_returns_last_weight(self, client):
        """Successfully returns last weight used."""
        response = client.get("/progression/exercises/barbell-bench-press/last-weight")

        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] == "barbell-bench-press"
        assert data["weight"] == 185
        assert data["weight_unit"] == "lbs"
        assert data["reps_completed"] == 8

    def test_returns_404_for_no_history(self, client, progression_repo):
        """Returns 404 when no weight history exists."""
        progression_repo.reset()

        response = client.get("/progression/exercises/barbell-bench-press/last-weight")

        assert response.status_code == 404
        assert "No weight history found" in response.json()["detail"]

    def test_returns_404_for_unknown_exercise(self, client):
        """Returns 404 for non-existent exercise."""
        response = client.get("/progression/exercises/unknown-exercise/last-weight")

        assert response.status_code == 404


# =============================================================================
# Personal Records Tests
# =============================================================================


@pytest.mark.integration
class TestPersonalRecordsEndpoint:
    """Tests for GET /progression/records."""

    def test_returns_all_records(self, client):
        """Returns records for all exercises."""
        response = client.get("/progression/records")

        assert response.status_code == 200
        data = response.json()
        assert len(data["records"]) > 0

    def test_filters_by_record_type(self, client):
        """Can filter to specific record type."""
        response = client.get("/progression/records?record_type=1rm")

        data = response.json()
        for record in data["records"]:
            assert record["record_type"] == "1rm"

    def test_filters_by_exercise(self, client):
        """Can filter to specific exercise."""
        response = client.get("/progression/records?exercise_id=barbell-bench-press")

        data = response.json()
        for record in data["records"]:
            assert record["exercise_id"] == "barbell-bench-press"

    def test_1rm_records_include_details(self, client):
        """1RM records include weight/reps details."""
        response = client.get("/progression/records?record_type=1rm")

        data = response.json()
        for record in data["records"]:
            assert "details" in record
            if record["details"]:
                assert "weight" in record["details"]
                assert "reps" in record["details"]

    def test_respects_limit_parameter(self, client):
        """Limit parameter restricts results."""
        response = client.get("/progression/records?limit=1")

        data = response.json()
        assert len(data["records"]) <= 1


# =============================================================================
# Volume Analytics Tests
# =============================================================================


@pytest.mark.integration
class TestVolumeAnalyticsEndpoint:
    """Tests for GET /progression/volume."""

    def test_returns_volume_data(self, client):
        """Returns volume analytics data."""
        response = client.get("/progression/volume")

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "summary" in data
        assert "period" in data
        assert data["granularity"] == "daily"

    def test_respects_date_range(self, client):
        """Filters by date range parameters."""
        response = client.get("/progression/volume?start_date=2024-01-01&end_date=2024-01-31")

        data = response.json()
        assert data["period"]["start_date"] == "2024-01-01"
        assert data["period"]["end_date"] == "2024-01-31"

    def test_respects_granularity(self, client):
        """Changes aggregation granularity."""
        response = client.get("/progression/volume?granularity=weekly")

        data = response.json()
        assert data["granularity"] == "weekly"

    def test_filters_by_muscle_groups(self, client):
        """Filters to specific muscle groups."""
        response = client.get("/progression/volume?muscle_groups=chest,quadriceps")

        assert response.status_code == 200


# =============================================================================
# Exercises With History Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesWithHistoryEndpoint:
    """Tests for GET /progression/exercises."""

    def test_returns_exercises_list(self, client):
        """Returns list of exercises user has performed."""
        response = client.get("/progression/exercises")

        assert response.status_code == 200
        data = response.json()
        assert "exercises" in data
        assert "total" in data
        assert len(data["exercises"]) > 0

    def test_includes_session_counts(self, client):
        """Exercises include session count."""
        response = client.get("/progression/exercises")

        data = response.json()
        for exercise in data["exercises"]:
            assert "exercise_id" in exercise
            assert "exercise_name" in exercise
            assert "session_count" in exercise
            assert exercise["session_count"] > 0

    def test_respects_limit_parameter(self, client):
        """Limit parameter restricts results."""
        response = client.get("/progression/exercises?limit=1")

        data = response.json()
        assert len(data["exercises"]) <= 1


# =============================================================================
# Authentication Tests
# =============================================================================


@pytest.mark.integration
class TestProgressionAuthentication:
    """Tests for authentication on progression endpoints."""

    def test_requires_authentication(self, exercises_repo, progression_repo):
        """All progression endpoints require authentication."""
        app = create_app()

        # Override only the repositories, not the auth
        def mock_exercises_repo():
            return exercises_repo

        def mock_progression_repo():
            return progression_repo

        app.dependency_overrides[get_exercises_repo] = mock_exercises_repo
        app.dependency_overrides[get_progression_repo] = mock_progression_repo

        unauthenticated_client = TestClient(app)

        # All endpoints should return 401 without auth
        endpoints = [
            "/progression/exercises",
            "/progression/exercises/barbell-bench-press/history",
            "/progression/exercises/barbell-bench-press/last-weight",
            "/progression/records",
            "/progression/volume",
        ]

        for endpoint in endpoints:
            response = unauthenticated_client.get(endpoint)
            assert response.status_code == 401, f"Expected 401 for {endpoint}, got {response.status_code}"
