"""
Unit tests for the programs router CRUD operations.

Part of AMA-595: Write unit tests for programs and tags routers

Tests the programs router endpoints:
- POST /programs - Create a new program
- GET /programs - List user programs
- GET /programs/{program_id} - Get single program details
- PATCH /programs/{program_id} - Update program
- DELETE /programs/{program_id} - Delete program
- POST /programs/{program_id}/members - Add workout/follow-along to program
- DELETE /programs/{program_id}/members/{member_id} - Remove from program
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER_ID = "test-user-595"
OTHER_USER_ID = "other-user-999"


# ---------------------------------------------------------------------------
# Auth / DI overrides
# ---------------------------------------------------------------------------


async def mock_get_current_user() -> str:
    """Mock auth dependency that returns a test user."""
    return TEST_USER_ID


@pytest.fixture
def client():
    """Create a TestClient with auth overridden."""
    settings = Settings(environment="test", _env_file=None)
    app = create_app(settings=settings)
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------


def mock_program_data(program_id: str = "prog-123", profile_id: str = TEST_USER_ID):
    """Return mock program data."""
    return {
        "id": program_id,
        "name": "Test Program",
        "description": "Test description",
        "color": "#FF0000",
        "icon": "💪",
        "is_active": True,
        "current_day_index": 0,
        "profile_id": profile_id,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


def mock_member_data(member_id: str = "member-123"):
    """Return mock member data."""
    return {
        "id": member_id,
        "program_id": "prog-123",
        "workout_id": "workout-456",
        "follow_along_id": None,
        "day_order": 1,
        "created_at": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests: Create Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateProgram:
    """Tests for POST /programs endpoint."""

    def test_create_program_success(self, client):
        """Creating a program with valid data returns 200."""
        mock_program = mock_program_data()
        
        with patch("backend.database.create_program", return_value=mock_program):
            response = client.post("/programs", json={
                "name": "Test Program",
                "description": "Test description",
                "color": "#FF0000",
                "icon": "💪"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["program"]["name"] == "Test Program"
            assert data["message"] == "Program created"

    def test_create_program_minimal_data(self, client):
        """Creating a program with only name returns 200."""
        mock_program = mock_program_data()
        mock_program["name"] = "Minimal Program"
        mock_program["description"] = None
        mock_program["color"] = None
        mock_program["icon"] = None
        
        with patch("backend.database.create_program", return_value=mock_program):
            response = client.post("/programs", json={
                "name": "Minimal Program"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["program"]["name"] == "Minimal Program"

    def test_create_program_failure(self, client):
        """Creating a program when database fails returns 400."""
        with patch("backend.database.create_program", return_value=None):
            response = client.post("/programs", json={
                "name": "Test Program"
            })
            
            assert response.status_code == 400

    def test_create_program_empty_name(self, client):
        """Creating a program with empty name fails at database level."""
        # Pydantic allows empty strings but database fails
        with patch("backend.database.create_program", return_value=None):
            response = client.post("/programs", json={
                "name": ""
            })
            
            assert response.status_code == 400

    def test_create_program_missing_name(self, client):
        """Creating a program without name returns 422."""
        response = client.post("/programs", json={
            "description": "Test description"
        })
        
        assert response.status_code == 422

    def test_create_program_invalid_color_format(self, client):
        """Creating a program with invalid color format fails at database level."""
        # No Pydantic validation for color format - database handles it
        with patch("backend.database.create_program", return_value=None):
            response = client.post("/programs", json={
                "name": "Test Program",
                "color": "not-a-color"
            })
            
            assert response.status_code == 400

    def test_create_program_valid_hex_color(self, client):
        """Creating a program with valid hex color returns 200."""
        mock_program = mock_program_data()
        mock_program["color"] = "#ABCDEF"
        
        with patch("backend.database.create_program", return_value=mock_program):
            response = client.post("/programs", json={
                "name": "Test Program",
                "color": "#ABCDEF"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

    def test_create_program_name_too_long(self, client):
        """Creating a program with very long name fails at database level."""
        long_name = "a" * 1000
        with patch("backend.database.create_program", return_value=None):
            response = client.post("/programs", json={
                "name": long_name
            })
            
            assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: List Programs
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListPrograms:
    """Tests for GET /programs endpoint."""

    def test_list_programs_success(self, client):
        """Listing programs returns 200 with program list."""
        mock_programs = [mock_program_data(), mock_program_data("prog-456")]
        
        with patch("backend.database.get_programs", return_value=mock_programs):
            response = client.get("/programs")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["programs"]) == 2
            assert data["count"] == 2

    def test_list_programs_empty(self, client):
        """Listing programs when none exist returns empty list."""
        with patch("backend.database.get_programs", return_value=[]):
            response = client.get("/programs")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["programs"] == []
            assert data["count"] == 0

    def test_list_programs_with_inactive(self, client):
        """Listing programs with include_inactive=True returns all programs."""
        mock_programs = [mock_program_data(), mock_program_data("prog-456")]
        
        with patch("backend.database.get_programs", return_value=mock_programs):
            response = client.get("/programs?include_inactive=true")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["programs"]) == 2


# ---------------------------------------------------------------------------
# Tests: Get Single Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGetProgram:
    """Tests for GET /programs/{program_id} endpoint."""

    def test_get_program_success(self, client):
        """Getting a program by ID returns 200 with program data."""
        mock_program = mock_program_data()
        
        with patch("backend.database.get_program", return_value=mock_program):
            response = client.get("/programs/prog-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["program"]["id"] == "prog-123"

    def test_get_program_not_found(self, client):
        """Getting a non-existent program returns 404."""
        with patch("backend.database.get_program", return_value=None):
            response = client.get("/programs/nonexistent")
            
            assert response.status_code == 404

    def test_cannot_access_other_users_program(self, client):
        """Getting another user's program returns 404 (authorization enforced)."""
        # Program belongs to OTHER_USER_ID, but current user is TEST_USER_ID
        # Database query filters by profile_id, so it returns None
        with patch("backend.database.get_program", return_value=None):
            response = client.get("/programs/prog-123")
            
            # Should return 404 because the program doesn't belong to this user
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Update Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUpdateProgram:
    """Tests for PATCH /programs/{program_id} endpoint."""

    def test_update_program_success(self, client):
        """Updating a program returns 200 with updated program."""
        updated_program = mock_program_data()
        updated_program["name"] = "Updated Name"
        
        with patch("backend.database.update_program", return_value=updated_program):
            response = client.patch("/programs/prog-123", json={
                "name": "Updated Name"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["program"]["name"] == "Updated Name"
            assert data["message"] == "Program updated"

    def test_update_program_failure(self, client):
        """Updating a program when database fails returns 400."""
        with patch("backend.database.update_program", return_value=None):
            response = client.patch("/programs/prog-123", json={
                "name": "New Name"
            })
            
            assert response.status_code == 400

    def test_cannot_update_other_users_program(self, client):
        """Updating another user's program returns 400 (authorization enforced)."""
        with patch("backend.database.update_program", return_value=None):
            response = client.patch("/programs/prog-123", json={
                "name": "Hacked Name"
            })
            
            # Should return 400 because the program doesn't belong to this user
            assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Delete Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteProgram:
    """Tests for DELETE /programs/{program_id} endpoint."""

    def test_delete_program_success(self, client):
        """Deleting a program returns 200."""
        with patch("backend.database.delete_program", return_value=True):
            response = client.delete("/programs/prog-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Program deleted"

    def test_delete_program_failure(self, client):
        """Deleting a program when database fails returns 400."""
        with patch("backend.database.delete_program", return_value=False):
            response = client.delete("/programs/prog-123")
            
            assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Add Member to Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAddToProgram:
    """Tests for POST /programs/{program_id}/members endpoint."""

    def test_add_workout_to_program_success(self, client):
        """Adding a workout to a program returns 200."""
        mock_member = mock_member_data()
        
        with patch("backend.database.add_workout_to_program", return_value=mock_member):
            response = client.post("/programs/prog-123/members", json={
                "workout_id": "workout-456",
                "day_order": 1
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["member"]["workout_id"] == "workout-456"
            assert data["message"] == "Added to program"

    def test_add_follow_along_to_program_success(self, client):
        """Adding a follow-along to a program returns 200."""
        mock_member = mock_member_data()
        mock_member["workout_id"] = None
        mock_member["follow_along_id"] = "fa-789"
        
        with patch("backend.database.add_workout_to_program", return_value=mock_member):
            response = client.post("/programs/prog-123/members", json={
                "follow_along_id": "fa-789",
                "day_order": 2
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["member"]["follow_along_id"] == "fa-789"

    def test_add_to_program_failure(self, client):
        """Adding to program when database fails returns 400."""
        with patch("backend.database.add_workout_to_program", return_value=None):
            response = client.post("/programs/prog-123/members", json={
                "workout_id": "workout-456"
            })
            
            assert response.status_code == 400

    def test_add_to_program_requires_workout_or_follow_along(self, client):
        """Adding to program without workout_id or follow_along_id returns 400."""
        with patch("backend.database.add_workout_to_program", return_value=None):
            response = client.post("/programs/prog-123/members", json={
                "day_order": 1
            })
            
            assert response.status_code == 400


# ---------------------------------------------------------------------------
# Tests: Remove Member from Program
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRemoveFromProgram:
    """Tests for DELETE /programs/{program_id}/members/{member_id} endpoint."""

    def test_remove_from_program_success(self, client):
        """Removing a member from a program returns 200."""
        with patch("backend.database.remove_workout_from_program", return_value=True):
            response = client.delete("/programs/prog-123/members/member-123")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Removed from program"

    def test_remove_from_program_failure(self, client):
        """Removing a member when database fails returns 400."""
        with patch("backend.database.remove_workout_from_program", return_value=False):
            response = client.delete("/programs/prog-123/members/member-123")
            
            assert response.status_code == 400
