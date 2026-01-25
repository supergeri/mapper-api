"""
Integration tests for progression API.

Part of AMA-461: Create program-api service scaffold

Tests progression tracking endpoints.
"""

import pytest


# ---------------------------------------------------------------------------
# Get History Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGetExerciseHistory:
    """Integration tests for GET /progression/history/{exercise_id}."""

    def test_get_history_returns_empty_list(self, client):
        """Returns empty list for exercise with no history."""
        response = client.get(
            "/progression/history/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 200
        assert response.json() == []

    def test_get_history_invalid_uuid(self, client):
        """Invalid UUID returns 422."""
        response = client.get("/progression/history/not-a-uuid")

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Record Performance Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestRecordPerformance:
    """Integration tests for POST /progression/history."""

    def test_record_performance_stub(self, client):
        """Record returns 501 (stub implementation)."""
        response = client.post(
            "/progression/history",
            json={
                "exercise_id": "550e8400-e29b-41d4-a716-446655440000",
                "weight": 100.0,
                "reps": 10,
                "sets": 3,
            },
        )

        assert response.status_code == 501
        assert response.json()["detail"] == "Not implemented"

    def test_record_performance_validation_error(self, client):
        """Missing required fields returns 422."""
        response = client.post(
            "/progression/history",
            json={"weight": 100.0},  # Missing exercise_id, reps, sets
        )

        assert response.status_code == 422

    def test_record_performance_invalid_exercise_id(self, client):
        """Invalid UUID returns 422."""
        response = client.post(
            "/progression/history",
            json={
                "exercise_id": "not-a-uuid",
                "weight": 100.0,
                "reps": 10,
                "sets": 3,
            },
        )

        assert response.status_code == 422

    def test_record_performance_valid_payload(self, client):
        """Valid payload passes validation (stub returns 501)."""
        response = client.post(
            "/progression/history",
            json={
                "exercise_id": "550e8400-e29b-41d4-a716-446655440000",
                "weight": 225.5,
                "reps": 5,
                "sets": 5,
            },
        )

        # Validation passed, stub returns 501
        assert response.status_code == 501
