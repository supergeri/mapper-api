"""
API contract tests.

Part of AMA-461: Create program-api service scaffold

These tests validate that API responses have the correct shape,
even for stub endpoints that return errors.
"""

import pytest

from tests.contract import assert_response_shape, assert_error_response, assert_list_response


# ---------------------------------------------------------------------------
# Health Endpoint Contracts
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestHealthContract:
    """Contract tests for health endpoint."""

    def test_health_response_shape(self, client):
        """Health endpoint returns expected fields."""
        response = client.get("/health")

        assert response.status_code == 200
        assert_response_shape(
            response.json(),
            {
                "status": str,
                "service": str,
            },
            allow_extra=False,
        )

    def test_health_response_values(self, client):
        """Health endpoint returns correct values."""
        response = client.get("/health")

        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "program-api"


# ---------------------------------------------------------------------------
# Programs Endpoint Contracts
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestProgramsListContract:
    """Contract tests for GET /programs."""

    def test_list_programs_returns_list(self, client):
        """List programs returns an array."""
        response = client.get("/programs")

        assert response.status_code == 200
        assert_list_response(response.json())

    def test_list_programs_empty_is_valid(self, client):
        """Empty list is a valid response."""
        response = client.get("/programs")

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.contract
class TestProgramsGetContract:
    """Contract tests for GET /programs/{id}."""

    def test_get_program_not_found_shape(self, client):
        """Not found response has correct error shape."""
        response = client.get("/programs/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 404
        assert_error_response(response.json(), expected_detail="Program not found")


@pytest.mark.contract
class TestProgramsCreateContract:
    """Contract tests for POST /programs."""

    def test_create_program_stub_returns_501(self, client, sample_program_create):
        """Create endpoint stub returns 501 Not Implemented."""
        response = client.post("/programs", json=sample_program_create)

        assert response.status_code == 501
        assert_error_response(response.json(), expected_detail="Not implemented")

    def test_create_program_validation_error_shape(self, client):
        """Validation errors have correct shape."""
        response = client.post("/programs", json={})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)


@pytest.mark.contract
class TestProgramsUpdateContract:
    """Contract tests for PUT /programs/{id}."""

    def test_update_program_stub_returns_501(self, client):
        """Update endpoint stub returns 501 Not Implemented."""
        response = client.put(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 501
        assert_error_response(response.json(), expected_detail="Not implemented")


@pytest.mark.contract
class TestProgramsDeleteContract:
    """Contract tests for DELETE /programs/{id}."""

    def test_delete_program_stub_returns_501(self, client):
        """Delete endpoint stub returns 501 Not Implemented."""
        response = client.delete("/programs/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 501
        assert_error_response(response.json(), expected_detail="Not implemented")


# ---------------------------------------------------------------------------
# Generation Endpoint Contracts
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestGenerationContract:
    """Contract tests for POST /generate."""

    def test_generate_returns_success(self, client_with_all_fakes, sample_generation_request):
        """Generate endpoint returns success with program."""
        response = client_with_all_fakes.post("/generate", json=sample_generation_request)

        # Endpoint is now implemented, returns 200 or 201
        assert response.status_code in [200, 201]
        data = response.json()
        assert "program" in data
        assert "generation_metadata" in data
        assert "suggestions" in data

    def test_generate_validation_error_shape(self, client_with_all_fakes):
        """Validation errors have correct shape."""
        response = client_with_all_fakes.post("/generate", json={})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)


# ---------------------------------------------------------------------------
# Progression Endpoint Contracts
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestProgressionHistoryContract:
    """Contract tests for GET /progression/history/{exercise_id}."""

    def test_get_history_returns_list(self, client):
        """History endpoint returns a list."""
        response = client.get(
            "/progression/history/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 200
        assert_list_response(response.json())

    def test_get_history_empty_is_valid(self, client):
        """Empty history list is valid."""
        response = client.get(
            "/progression/history/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.contract
class TestProgressionRecordContract:
    """Contract tests for POST /progression/history."""

    def test_record_performance_stub_returns_501(self, client):
        """Record performance stub returns 501 Not Implemented."""
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
        assert_error_response(response.json(), expected_detail="Not implemented")

    def test_record_performance_validation_error_shape(self, client):
        """Validation errors have correct shape."""
        response = client.post("/progression/history", json={})

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)


# ---------------------------------------------------------------------------
# Authentication Contract Tests
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestAuthenticationContract:
    """Contract tests for authentication errors."""

    def test_missing_auth_returns_401(self, app):
        """Endpoints requiring auth return 401 without token."""
        from fastapi.testclient import TestClient

        # Create client without auth override
        app.dependency_overrides.clear()
        unauthenticated_client = TestClient(app)

        response = unauthenticated_client.get("/programs")

        assert response.status_code == 401
        assert_error_response(response.json())
