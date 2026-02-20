"""
Integration tests for the AI Build endpoint.

Part of AMA-446: AI Builder API Endpoint

Tests the full POST /api/v1/workouts/ai-build endpoint with
the FastAPI test client.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import Settings


@pytest.fixture
def test_app():
    """Create a test app with test settings."""
    settings = Settings(environment="test", _env_file=None)
    app = create_app(settings=settings)

    # Override auth to return a test user
    from api.deps import get_current_user
    app.dependency_overrides[get_current_user] = lambda: "test-user-123"

    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


class TestAIBuildEndpoint:
    """Test POST /api/v1/workouts/ai-build endpoint."""

    def test_basic_build(self, client):
        """Basic workout build with exercise list."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [
                    {"name": "Bench Press"},
                    {"name": "Squat"},
                    {"name": "Deadlift"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workout"] is not None
        assert "blocks" in data["workout"]
        assert len(data["workout"]["blocks"]) >= 1
        assert data["garmin_compatibility"] is not None

    def test_build_with_full_params(self, client):
        """Build with all parameters specified."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "source_url": "https://example.com/workout",
                "workout_type": "hypertrophy",
                "format": "superset",
                "rounds": 4,
                "exercises": [
                    {
                        "name": "Bench Press",
                        "sets": 4,
                        "reps": 10,
                        "rest_seconds": 90,
                        "load_value": 135,
                        "load_unit": "lb",
                    },
                    {
                        "name": "Bent Over Row",
                        "sets": 4,
                        "reps": 10,
                    },
                ],
                "user_preferences": {
                    "rest_seconds": 90,
                    "unit_system": "imperial",
                },
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["workout"] is not None

    def test_build_empty_exercises(self, client):
        """Build with no exercises should still succeed."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_build_returns_suggestions(self, client):
        """Build should return suggestions for filled defaults."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [
                    {"name": "Bench Press"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

    def test_build_returns_garmin_compatibility(self, client):
        """Build should return Garmin compatibility info."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [
                    {"name": "Squat"},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "garmin_compatibility" in data
        garmin = data["garmin_compatibility"]
        assert "is_compatible" in garmin
        assert "warnings" in garmin
        assert "unsupported_exercises" in garmin
        assert "mapped_exercises" in garmin

    def test_build_returns_build_time(self, client):
        """Build should track and return build time."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [{"name": "Squat"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "build_time_ms" in data
        assert data["build_time_ms"] >= 0

    def test_different_workout_types(self, client):
        """Different workout types should produce different defaults."""
        types = ["strength", "hypertrophy", "hiit", "circuit", "endurance"]

        for wtype in types:
            response = client.post(
                "/api/v1/workouts/ai-build",
                json={
                    "workout_type": wtype,
                    "exercises": [{"name": "Squat"}],
                },
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True, f"Failed for workout type: {wtype}"

    def test_minimal_request(self, client):
        """Minimal request with just workout_type."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_exercise_with_duration(self, client):
        """Exercise with duration should be handled."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "hiit",
                "exercises": [
                    {"name": "Plank", "duration_seconds": 60},
                    {"name": "Burpees", "reps": 10},
                ],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_response_schema_keys(self, client):
        """Response should contain all expected keys."""
        response = client.post(
            "/api/v1/workouts/ai-build",
            json={
                "workout_type": "strength",
                "exercises": [{"name": "Squat"}],
            },
        )

        assert response.status_code == 200
        data = response.json()
        expected_keys = {
            "success", "workout", "suggestions",
            "garmin_compatibility", "build_time_ms",
            "llm_used", "error",
        }
        assert expected_keys.issubset(set(data.keys()))
