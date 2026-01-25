"""
Integration tests for programs API.

Part of AMA-461: Create program-api service scaffold

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
        assert response.json() == []

    @pytest.mark.xfail(reason="Stub endpoint returns empty list - will pass once CRUD is implemented")
    def test_list_programs_returns_user_programs(self, client_with_seeded_repo):
        """Returns programs belonging to the authenticated user."""
        response = client_with_seeded_repo.get("/programs")

        assert response.status_code == 200
        programs = response.json()
        assert len(programs) == 3
        assert all(p["user_id"] == TEST_USER_ID for p in programs)

    @pytest.mark.xfail(reason="Stub endpoint returns empty list - will pass once CRUD is implemented")
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
        programs = response.json()
        assert len(programs) == 1
        assert programs[0]["name"] == "My Program"

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
        assert response.json()["detail"] == "Program not found"


# ---------------------------------------------------------------------------
# Create Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCreateProgram:
    """Integration tests for POST /programs."""

    def test_create_program_stub(self, client_with_fake_repo, sample_program_create):
        """Create returns 501 (stub implementation)."""
        response = client_with_fake_repo.post("/programs", json=sample_program_create)

        # Currently a stub - will return 201 when implemented
        assert response.status_code == 501

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


# ---------------------------------------------------------------------------
# Update Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestUpdateProgram:
    """Integration tests for PUT /programs/{id}."""

    def test_update_program_stub(self, client_with_seeded_repo):
        """Update returns 501 (stub implementation)."""
        response = client_with_seeded_repo.put(
            "/programs/550e8400-e29b-41d4-a716-446655440000",
            json={"name": "Updated Name"},
        )

        # Currently a stub - will return 200 when implemented
        assert response.status_code == 501


# ---------------------------------------------------------------------------
# Delete Program Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDeleteProgram:
    """Integration tests for DELETE /programs/{id}."""

    def test_delete_program_stub(self, client_with_seeded_repo):
        """Delete returns 501 (stub implementation)."""
        response = client_with_seeded_repo.delete(
            "/programs/550e8400-e29b-41d4-a716-446655440000"
        )

        # Currently a stub - will return 204 when implemented
        assert response.status_code == 501
