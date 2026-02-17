"""
Unit tests for the tags router.

Part of AMA-595: Write unit tests for programs and tags routers

Tests the tags router endpoints:
- GET /tags - Get all tags for a user
- POST /tags - Create a new user tag
- DELETE /tags/{tag_id} - Delete a user tag
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER_ID = "test-user-595"


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
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock Data
# ---------------------------------------------------------------------------


def mock_tag_data(tag_id: str = "tag-123"):
    """Return mock tag data."""
    return {
        "id": tag_id,
        "profile_id": TEST_USER_ID,
        "name": "Test Tag",
        "color": "#00FF00",
        "created_at": "2024-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests: List Tags
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestListTags:
    """Tests for GET /tags endpoint."""

    def test_list_tags_success(self, client):
        """Listing tags returns 200 with tag list."""
        mock_tags = [mock_tag_data(), mock_tag_data("tag-456")]
        
        with patch("api.routers.tags.get_user_tags", return_value=mock_tags):
            response = client.get(f"/tags?profile_id={TEST_USER_ID}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["tags"]) == 2
            assert data["count"] == 2

    def test_list_tags_empty(self, client):
        """Listing tags when none exist returns empty list."""
        with patch("api.routers.tags.get_user_tags", return_value=[]):
            response = client.get(f"/tags?profile_id={TEST_USER_ID}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["tags"] == []
            assert data["count"] == 0

    def test_list_tags_requires_profile_id(self, client):
        """Listing tags without profile_id returns 422."""
        response = client.get("/tags")
        
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Create Tag
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCreateTag:
    """Tests for POST /tags endpoint."""

    def test_create_tag_success(self, client):
        """Creating a tag with valid data returns 200."""
        mock_tag = mock_tag_data()
        
        with patch("api.routers.tags.create_user_tag", return_value=mock_tag):
            response = client.post("/tags", json={
                "profile_id": TEST_USER_ID,
                "name": "Test Tag",
                "color": "#00FF00"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["tag"]["name"] == "Test Tag"
            assert data["message"] == "Tag created"

    def test_create_tag_minimal_data(self, client):
        """Creating a tag with only required fields returns 200."""
        mock_tag = mock_tag_data()
        mock_tag["name"] = "Minimal Tag"
        mock_tag["color"] = None
        
        with patch("api.routers.tags.create_user_tag", return_value=mock_tag):
            response = client.post("/tags", json={
                "profile_id": TEST_USER_ID,
                "name": "Minimal Tag"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["tag"]["name"] == "Minimal Tag"

    def test_create_tag_failure(self, client):
        """Creating a tag when database fails returns success: False."""
        with patch("api.routers.tags.create_user_tag", return_value=None):
            response = client.post("/tags", json={
                "profile_id": TEST_USER_ID,
                "name": "Test Tag"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "Failed to create tag" in data["message"]

    def test_create_duplicate_tag(self, client):
        """Creating a duplicate tag returns success: False."""
        with patch("api.routers.tags.create_user_tag", return_value=None):
            response = client.post("/tags", json={
                "profile_id": TEST_USER_ID,
                "name": "Existing Tag"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False


# ---------------------------------------------------------------------------
# Tests: Delete Tag
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteTag:
    """Tests for DELETE /tags/{tag_id} endpoint."""

    def test_delete_tag_success(self, client):
        """Deleting a tag returns 200."""
        with patch("api.routers.tags.delete_user_tag", return_value=True):
            response = client.delete(f"/tags/tag-123?profile_id={TEST_USER_ID}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["message"] == "Tag deleted"

    def test_delete_tag_failure(self, client):
        """Deleting a tag when database fails returns success: False."""
        with patch("api.routers.tags.delete_user_tag", return_value=False):
            response = client.delete(f"/tags/tag-123?profile_id={TEST_USER_ID}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "Failed to delete tag" in data["message"]

    def test_delete_tag_requires_profile_id(self, client):
        """Deleting a tag without profile_id returns 422."""
        response = client.delete("/tags/tag-123")
        
        assert response.status_code == 422
