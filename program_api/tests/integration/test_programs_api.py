"""
Integration tests for programs API.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-464: Tests for implemented CRUD endpoints

Tests programs CRUD endpoints with fake repository.
"""

import pytest

from tests.conftest import TEST_USER_ID, OTHER_USER_ID


# ---------------------------------------------------------------------------
# List Programs Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestListPrograms:
    """Integration tests for GET /programs."""

    def test_list_programs_empty(self, client_with_fake_repo):
        """Returns empty list when user has no programs."""
        response = client_with_fake_repo.get("/programs")

        assert response.status_code == 200
        data = response.json()
        assert data["programs"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_list_programs_returns_user_programs(self, client_with_seeded_repo):
        """Returns programs belonging to the authenticated user."""
        response = client_with_seeded_repo.get("/programs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 3
        assert data["total"] == 3
        assert all(p["user_id"] == TEST_USER_ID for p in data["programs"])

    def test_list_programs_excludes_other_users(self, app, fake_program_repo):
        """Does not return programs belonging to other users."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        # Seed with programs from different users
        fake_program_repo.seed([
            {
                "id": "prog-1",
                "user_id": TEST_USER_ID,
                "name": "My Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            },
            {
                "id": "prog-2",
                "user_id": OTHER_USER_ID,
                "name": "Other User Program",
                "goal": "hypertrophy",
                "experience_level": "advanced",
                "duration_weeks": 8,
                "sessions_per_week": 5,
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.get("/programs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 1
        assert data["programs"][0]["name"] == "My Program"

        app.dependency_overrides.clear()

    def test_list_programs_filter_by_status(self, app, fake_program_repo):
        """Filters programs by status."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "prog-1",
                "user_id": TEST_USER_ID,
                "name": "Draft Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": "draft",
            },
            {
                "id": "prog-2",
                "user_id": TEST_USER_ID,
                "name": "Active Program",
                "goal": "hypertrophy",
                "experience_level": "intermediate",
                "duration_weeks": 8,
                "sessions_per_week": 4,
                "status": "active",
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.get("/programs?status=active")

        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 1
        assert data["programs"][0]["name"] == "Active Program"

        app.dependency_overrides.clear()

    def test_list_programs_pagination(self, app, fake_program_repo):
        """Supports limit and offset pagination."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        # Seed with 5 programs
        fake_program_repo.seed([
            {
                "id": f"prog-{i}",
                "user_id": TEST_USER_ID,
                "name": f"Program {i}",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            }
            for i in range(5)
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        # Get first page
        response = client.get("/programs?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True

        # Get second page
        response = client.get("/programs?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 2
        assert data["has_more"] is True

        # Get last page
        response = client.get("/programs?limit=2&offset=4")
        assert response.status_code == 200
        data = response.json()
        assert len(data["programs"]) == 1
        assert data["has_more"] is False

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Get Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGetProgram:
    """Integration tests for GET /programs/{id}."""

    def test_get_program_not_found(self, client_with_fake_repo):
        """Returns 404 for non-existent program."""
        response = client_with_fake_repo.get(
            "/programs/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_program_success(self, client_with_seeded_repo):
        """Returns program with full details."""
        response = client_with_seeded_repo.get(
            "/programs/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert data["name"] == "Test Program"
        assert data["user_id"] == TEST_USER_ID

    def test_get_program_access_denied(self, app, fake_program_repo):
        """Returns 404 when accessing another user's program (prevents enumeration)."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": OTHER_USER_ID,
                "name": "Other User Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.get("/programs/550e8400-e29b-41d4-a716-446655440000")

        # Returns 404 (not 403) to prevent resource enumeration attacks
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Create Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCreateProgram:
    """Integration tests for POST /programs."""

    def test_create_program_success(self, client_with_fake_repo, sample_program_create):
        """Creates a program and returns 201."""
        response = client_with_fake_repo.post("/programs", json=sample_program_create)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_program_create["name"]
        assert data["goal"] == sample_program_create["goal"]
        assert data["status"] == "draft"
        assert data["user_id"] == TEST_USER_ID
        assert "id" in data

    def test_create_program_validation_error(self, client_with_fake_repo):
        """Invalid payload returns 422."""
        response = client_with_fake_repo.post(
            "/programs",
            json={"name": "Test"},  # Missing required fields
        )

        assert response.status_code == 422

    def test_create_program_invalid_goal(self, client_with_fake_repo):
        """Invalid goal value returns 422."""
        response = client_with_fake_repo.post(
            "/programs",
            json={
                "name": "Test",
                "goal": "invalid_goal",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            },
        )

        assert response.status_code == 422

    def test_create_program_minimal(self, client_with_fake_repo, sample_program_minimal):
        """Creates program with minimal required fields."""
        response = client_with_fake_repo.post("/programs", json=sample_program_minimal)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_program_minimal["name"]
        assert data["equipment_available"] == []


# ---------------------------------------------------------------------------
# Update Program Tests (PATCH)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestUpdateProgram:
    """Integration tests for PATCH /programs/{id}."""

    def test_update_program_name(self, client_with_seeded_repo):
        """Updates program name."""
        response = client_with_seeded_repo.patch(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "Updated Name"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    def test_update_program_status(self, client_with_seeded_repo):
        """Updates program status."""
        response = client_with_seeded_repo.patch(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"status": "active"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "active"

    def test_update_program_not_found(self, client_with_fake_repo):
        """Returns 404 for non-existent program."""
        response = client_with_fake_repo.patch(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "Updated"},
        )

        assert response.status_code == 404

    def test_update_program_no_changes(self, client_with_seeded_repo):
        """Returns existing program when no changes provided."""
        response = client_with_seeded_repo.patch(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Test Program"


# ---------------------------------------------------------------------------
# Replace Program Tests (PUT)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestReplaceProgram:
    """Integration tests for PUT /programs/{id}."""

    def test_replace_program_success(self, client_with_seeded_repo):
        """Replaces program fields."""
        response = client_with_seeded_repo.put(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "Replaced Name", "goal": "hypertrophy"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Replaced Name"
        assert data["goal"] == "hypertrophy"

    def test_replace_program_no_fields(self, client_with_seeded_repo):
        """Returns 422 when no fields provided."""
        response = client_with_seeded_repo.put(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Activate Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestActivateProgram:
    """Integration tests for POST /programs/{id}/activate."""

    def test_activate_program_success(self, client_with_seeded_repo):
        """Activates a draft program."""
        response = client_with_seeded_repo.post(
            "/programs/550e8400-e29b-41d4-a716-446655440000/activate",
            json={},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert "scheduled_workouts" in data
        assert "start_date" in data

    def test_activate_program_with_start_date(self, client_with_seeded_repo):
        """Activates with custom start date."""
        response = client_with_seeded_repo.post(
            "/programs/550e8400-e29b-41d4-a716-446655440000/activate",
            json={"start_date": "2025-02-01T00:00:00Z"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "2025-02-01" in data["start_date"]

    def test_activate_already_active(self, app, fake_program_repo):
        """Returns 422 when program is already active."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": TEST_USER_ID,
                "name": "Active Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": "active",
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.post(
            "/programs/550e8400-e29b-41d4-a716-446655440000/activate",
            json={},
        )

        assert response.status_code == 422
        assert "already active" in response.json()["detail"].lower()

        app.dependency_overrides.clear()

    def test_activate_archived_program(self, app, fake_program_repo):
        """Returns 422 when trying to activate archived program."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": TEST_USER_ID,
                "name": "Archived Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": "archived",
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.post(
            "/programs/550e8400-e29b-41d4-a716-446655440000/activate",
            json={},
        )

        assert response.status_code == 422
        assert "archived" in response.json()["detail"].lower()

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Delete Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDeleteProgram:
    """Integration tests for DELETE /programs/{id}."""

    def test_delete_program_success(self, app, fake_program_repo):
        """Soft deletes (archives) a program."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": TEST_USER_ID,
                "name": "Program to Delete",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": "draft",
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.delete("/programs/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 204

        # Verify program was archived (not hard deleted)
        program = fake_program_repo.get_by_id("550e8400-e29b-41d4-a716-446655440000")
        assert program is not None
        assert program["status"] == "archived"

        app.dependency_overrides.clear()

    def test_delete_program_not_found(self, client_with_fake_repo):
        """Returns 404 for non-existent program."""
        response = client_with_fake_repo.delete(
            "/programs/550e8400-e29b-41d4-a716-446655440000"
        )

        assert response.status_code == 404

    def test_delete_program_idempotent(self, app, fake_program_repo):
        """Deleting already archived program is idempotent."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": TEST_USER_ID,
                "name": "Already Archived",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": "archived",
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.delete("/programs/550e8400-e29b-41d4-a716-446655440000")

        assert response.status_code == 204

        app.dependency_overrides.clear()

    def test_delete_program_access_denied(self, app, fake_program_repo):
        """Returns 404 when trying to delete another user's program (prevents enumeration)."""
        from fastapi.testclient import TestClient
        from api.deps import get_current_user, get_program_repo
        from tests.conftest import mock_get_current_user

        fake_program_repo.seed([
            {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": OTHER_USER_ID,
                "name": "Other User Program",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            },
        ])

        app.dependency_overrides[get_current_user] = mock_get_current_user
        app.dependency_overrides[get_program_repo] = lambda: fake_program_repo
        client = TestClient(app)

        response = client.delete("/programs/550e8400-e29b-41d4-a716-446655440000")

        # Returns 404 (not 403) to prevent resource enumeration attacks
        assert response.status_code == 404

        app.dependency_overrides.clear()
