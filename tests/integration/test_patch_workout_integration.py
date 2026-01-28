"""
Integration tests for PATCH /workouts/{id} endpoint.

Part of AMA-433: PATCH /workouts/{id} endpoint implementation

These tests verify:
- Full request/response cycle with FastAPI TestClient
- Dependency injection with fake/mock use cases
- HTTP status codes and error responses
- Response body shape validation
- Request validation via Pydantic
"""

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from backend.app import app
from api.deps import get_patch_workout_use_case, get_current_user
from application.use_cases.patch_workout import PatchWorkoutUseCase, PatchWorkoutResult
from domain.models.patch_operation import PatchOperation


# =============================================================================
# Auth Mock
# =============================================================================

TEST_USER_ID = "test-user-integration"


async def mock_get_current_user() -> str:
    """Mock auth dependency for integration tests."""
    return TEST_USER_ID


# =============================================================================
# Fake Use Cases for Testing
# =============================================================================


class FakePatchWorkoutUseCase:
    """Controllable fake for testing endpoint behavior."""

    def __init__(self, result: PatchWorkoutResult):
        self.result = result
        self.calls = []

    def execute(self, workout_id: str, user_id: str, operations: list):
        self.calls.append({
            "workout_id": workout_id,
            "user_id": user_id,
            "operations": operations,
        })
        return self.result


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def success_use_case():
    """Use case that returns successful result."""
    return FakePatchWorkoutUseCase(PatchWorkoutResult(
        success=True,
        workout={
            "id": "w-123",
            "title": "Updated Title",
            "workout_data": {"title": "Updated Title", "blocks": []},
        },
        changes_applied=2,
        embedding_regeneration="queued",
    ))


@pytest.fixture
def not_found_use_case():
    """Use case that returns not found error."""
    return FakePatchWorkoutUseCase(PatchWorkoutResult(
        success=False,
        error="Workout not found or not owned by user",
    ))


@pytest.fixture
def validation_error_use_case():
    """Use case that returns validation errors."""
    return FakePatchWorkoutUseCase(PatchWorkoutResult(
        success=False,
        error="Patch operation validation failed",
        validation_errors=["Invalid path: /invalid", "Exercise name required"],
    ))


@pytest.fixture
def business_rule_error_use_case():
    """Use case that returns business rule validation error."""
    return FakePatchWorkoutUseCase(PatchWorkoutResult(
        success=False,
        error="Business validation failed",
        validation_errors=["Workout must have at least one block"],
    ))


@pytest.fixture
def patch_client():
    """Test client with auth mocked for PATCH endpoint tests."""
    app.dependency_overrides[get_current_user] = mock_get_current_user
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# =============================================================================
# Success Path Tests
# =============================================================================


@pytest.mark.integration
class TestPatchWorkoutSuccess:
    """Tests for successful patch operations."""

    def test_successful_patch_returns_200(self, patch_client, success_use_case):
        """Successful patch returns 200 with workout data."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/title", "value": "New Title"}]},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["changes_applied"] == 2
            assert data["embedding_regeneration"] == "queued"
            assert data["workout"]["title"] == "Updated Title"
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_passes_workout_id_to_use_case(self, patch_client, success_use_case):
        """Workout ID from URL is passed to use case."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            patch_client.patch(
                "/workouts/my-workout-id-456",
                json={"operations": [{"op": "replace", "path": "/title", "value": "Test"}]},
            )
            assert len(success_use_case.calls) == 1
            assert success_use_case.calls[0]["workout_id"] == "my-workout-id-456"
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_passes_operations_to_use_case(self, patch_client, success_use_case):
        """Operations from request are passed to use case."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            patch_client.patch(
                "/workouts/w-123",
                json={
                    "operations": [
                        {"op": "replace", "path": "/title", "value": "New"},
                        {"op": "add", "path": "/tags/-", "value": "strength"},
                    ]
                },
            )
            assert len(success_use_case.calls) == 1
            operations = success_use_case.calls[0]["operations"]
            assert len(operations) == 2
            assert operations[0].op == "replace"
            assert operations[0].path == "/title"
            assert operations[1].op == "add"
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_multiple_operations_accepted(self, patch_client, success_use_case):
        """Multiple operations in single request are accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={
                    "operations": [
                        {"op": "replace", "path": "/title", "value": "Title"},
                        {"op": "replace", "path": "/description", "value": "Desc"},
                        {"op": "add", "path": "/tags/-", "value": "tag1"},
                        {"op": "replace", "path": "/exercises/0/sets", "value": 5},
                    ]
                },
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)


# =============================================================================
# Error Response Tests
# =============================================================================


@pytest.mark.integration
class TestPatchWorkoutErrors:
    """Tests for error responses."""

    def test_not_found_returns_404(self, patch_client, not_found_use_case):
        """Missing workout returns 404."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: not_found_use_case
        try:
            response = patch_client.patch(
                "/workouts/nonexistent-id",
                json={"operations": [{"op": "replace", "path": "/title", "value": "X"}]},
            )
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"]["message"].lower()
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_validation_error_returns_422(self, patch_client, validation_error_use_case):
        """Validation failure returns 422 with error details."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: validation_error_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/invalid", "value": "X"}]},
            )
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
            assert "validation_errors" in data["detail"]
            assert len(data["detail"]["validation_errors"]) == 2
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_business_rule_error_returns_422(self, patch_client, business_rule_error_use_case):
        """Business rule validation failure returns 422."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: business_rule_error_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "remove", "path": "/blocks/0"}]},
            )
            assert response.status_code == 422
            data = response.json()
            assert "at least one block" in str(data["detail"]["validation_errors"])
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)


# =============================================================================
# Request Validation Tests (Pydantic)
# =============================================================================


@pytest.mark.integration
class TestPatchWorkoutRequestValidation:
    """Tests for request validation via Pydantic."""

    def test_empty_operations_rejected(self, patch_client):
        """Empty operations array is rejected by Pydantic."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": []},
        )
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_missing_operations_rejected(self, patch_client):
        """Missing operations field is rejected."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={},
        )
        assert response.status_code == 422

    def test_invalid_operation_type_rejected(self, patch_client):
        """Invalid op type is rejected by Pydantic."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": [{"op": "move", "path": "/title", "value": "X"}]},
        )
        assert response.status_code == 422

    def test_path_without_slash_rejected(self, patch_client):
        """Path without leading / is rejected."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": [{"op": "replace", "path": "title", "value": "X"}]},
        )
        assert response.status_code == 422

    def test_empty_path_rejected(self, patch_client):
        """Empty path is rejected."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": [{"op": "replace", "path": "", "value": "X"}]},
        )
        assert response.status_code == 422

    def test_missing_op_field_rejected(self, patch_client):
        """Missing op field is rejected."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": [{"path": "/title", "value": "X"}]},
        )
        assert response.status_code == 422

    def test_missing_path_field_rejected(self, patch_client):
        """Missing path field is rejected."""
        response = patch_client.patch(
            "/workouts/w-123",
            json={"operations": [{"op": "replace", "value": "X"}]},
        )
        assert response.status_code == 422


# =============================================================================
# Operation Type Tests
# =============================================================================


@pytest.mark.integration
class TestPatchOperationTypes:
    """Tests for different operation types."""

    def test_replace_operation_accepted(self, patch_client, success_use_case):
        """Replace operation is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/title", "value": "New"}]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_add_operation_accepted(self, patch_client, success_use_case):
        """Add operation is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "add", "path": "/tags/-", "value": "strength"}]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_remove_operation_accepted(self, patch_client, success_use_case):
        """Remove operation is accepted (no value needed)."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "remove", "path": "/exercises/0"}]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_remove_with_value_accepted(self, patch_client, success_use_case):
        """Remove operation with value is accepted (value ignored)."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "remove", "path": "/exercises/0", "value": "ignored"}]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)


# =============================================================================
# Complex Value Tests
# =============================================================================


@pytest.mark.integration
class TestPatchComplexValues:
    """Tests for complex values in operations."""

    def test_array_value_accepted(self, patch_client, success_use_case):
        """Array value for tags replacement is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [
                    {"op": "replace", "path": "/tags", "value": ["tag1", "tag2", "tag3"]}
                ]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_object_value_accepted(self, patch_client, success_use_case):
        """Object value for exercise is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [
                    {"op": "add", "path": "/exercises/-", "value": {
                        "name": "New Exercise",
                        "sets": 3,
                        "reps": 10,
                    }}
                ]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_null_value_accepted(self, patch_client, success_use_case):
        """Null value for clearing description is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [
                    {"op": "replace", "path": "/description", "value": None}
                ]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_numeric_value_accepted(self, patch_client, success_use_case):
        """Numeric value for sets/reps is accepted."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [
                    {"op": "replace", "path": "/exercises/0/sets", "value": 5}
                ]},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)


# =============================================================================
# Response Shape Tests
# =============================================================================


@pytest.mark.integration
class TestPatchResponseShape:
    """Tests for response body shape."""

    def test_success_response_has_required_fields(self, patch_client, success_use_case):
        """Success response contains all required fields."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: success_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/title", "value": "X"}]},
            )
            data = response.json()

            assert "success" in data
            assert "workout" in data
            assert "changes_applied" in data
            assert "embedding_regeneration" in data

            assert isinstance(data["success"], bool)
            assert isinstance(data["workout"], dict)
            assert isinstance(data["changes_applied"], int)
            assert isinstance(data["embedding_regeneration"], str)
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_error_response_has_detail(self, patch_client, not_found_use_case):
        """Error response contains detail with message."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: not_found_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/title", "value": "X"}]},
            )
            data = response.json()

            assert "detail" in data
            assert "message" in data["detail"]
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)

    def test_validation_error_response_has_errors_list(self, patch_client, validation_error_use_case):
        """Validation error response contains errors list."""
        app.dependency_overrides[get_patch_workout_use_case] = lambda: validation_error_use_case
        try:
            response = patch_client.patch(
                "/workouts/w-123",
                json={"operations": [{"op": "replace", "path": "/invalid", "value": "X"}]},
            )
            data = response.json()

            assert "detail" in data
            assert "validation_errors" in data["detail"]
            assert isinstance(data["detail"]["validation_errors"], list)
        finally:
            app.dependency_overrides.pop(get_patch_workout_use_case, None)
