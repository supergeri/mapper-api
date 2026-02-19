"""
Unit tests for api/routers/account.py

Part of AMA-598: Write unit tests for account router

Tests cover:
- GET /account/deletion-preview endpoint
- DELETE /account endpoint
- Mocked database functions for isolated testing
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from api.routers.account import router
from api.deps import get_current_user


# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_USER_ID = "test-user-AMA-598"


# ---------------------------------------------------------------------------
# Auth mock
# ---------------------------------------------------------------------------


def _mock_get_current_user() -> str:
    return TEST_USER_ID


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def account_client():
    """
    TestClient wired to a minimal FastAPI app that only includes the
    account router. This allows isolated testing of account endpoints.
    """
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_current_user] = _mock_get_current_user
    return TestClient(test_app)


# ---------------------------------------------------------------------------
# GET /account/deletion-preview
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeletionPreview:
    """Tests for GET /account/deletion-preview."""

    def test_deletion_preview_returns_data(self, account_client):
        """GET /account/deletion-preview should return preview data with counts."""
        mock_preview = {
            "workouts": 5,
            "workout_completions": 10,
            "programs": 2,
            "tags": 8,
            "follow_along_workouts": 3,
            "paired_devices": 1,
            "voice_settings": True,
            "voice_corrections": 2,
            "strava_connection": True,
            "garmin_connection": False,
        }

        with patch("api.routers.account.get_account_deletion_preview", return_value=mock_preview):
            resp = account_client.get("/account/deletion-preview")
            assert resp.status_code == 200

            data = resp.json()
            assert data["workouts"] == 5
            assert data["workout_completions"] == 10
            assert data["programs"] == 2
            assert data["tags"] == 8
            assert data["follow_along_workouts"] == 3
            assert data["paired_devices"] == 1
            assert data["voice_settings"] is True
            assert data["voice_corrections"] == 2
            assert data["strava_connection"] is True
            assert data["garmin_connection"] is False

    def test_deletion_preview_returns_empty_counts(self, account_client):
        """GET /account/deletion-preview should return zeros for new users."""
        mock_preview = {
            "workouts": 0,
            "workout_completions": 0,
            "programs": 0,
            "tags": 0,
            "follow_along_workouts": 0,
            "paired_devices": 0,
            "voice_settings": False,
            "voice_corrections": 0,
            "strava_connection": False,
            "garmin_connection": False,
        }

        with patch("api.routers.account.get_account_deletion_preview", return_value=mock_preview):
            resp = account_client.get("/account/deletion-preview")
            assert resp.status_code == 200

            data = resp.json()
            # All counts should be zero/false
            assert data["workouts"] == 0
            assert data["voice_settings"] is False
            assert data["strava_connection"] is False
            assert data["garmin_connection"] is False

    def test_deletion_preview_returns_error(self, account_client):
        """GET /account/deletion-preview should handle database errors."""
        mock_preview = {"error": "Database not available"}

        with patch("api.routers.account.get_account_deletion_preview", return_value=mock_preview):
            resp = account_client.get("/account/deletion-preview")
            assert resp.status_code == 500


# ---------------------------------------------------------------------------
# DELETE /account
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeleteAccount:
    """Tests for DELETE /account."""

    def test_delete_account_succeeds(self, account_client):
        """DELETE /account should successfully delete user account."""
        mock_result = {
            "success": True,
            "deleted": {
                "workouts": 5,
                "workout_completions": 10,
                "programs": 2,
                "tags": 8,
            }
        }

        with patch("api.routers.account.delete_user_account", return_value=mock_result):
            resp = account_client.delete("/account")
            assert resp.status_code == 200

            data = resp.json()
            assert data["success"] is True
            assert "deleted" in data

    def test_delete_account_returns_error(self, account_client):
        """DELETE /account should handle deletion failures."""
        mock_result = {"success": False, "error": "Failed to delete account"}

        with patch("api.routers.account.delete_user_account", return_value=mock_result):
            resp = account_client.delete("/account")
            assert resp.status_code == 500

    def test_delete_account_returns_500_on_exception(self, account_client):
        """DELETE /account should return 500 when exception occurs."""

        with patch("api.routers.account.delete_user_account", side_effect=Exception("Database error")):
            resp = account_client.delete("/account")
            assert resp.status_code == 500
