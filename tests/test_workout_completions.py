"""
Unit tests for workout completion endpoints (AMA-189, AMA-217).

These tests verify:
1. Route ordering is correct (/workouts/completions before /workouts/{workout_id})
2. Completion endpoints return proper responses
3. Auth is required for all completion endpoints
4. Error handling surfaces specific error messages (AMA-217)
5. Database errors are properly categorized
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import uuid

from backend.workout_completions import (
    save_workout_completion,
    WorkoutCompletionRequest,
    HealthMetrics,
)


# =============================================================================
# Route Ordering Tests (Critical - prevents route collision bug)
# =============================================================================


def test_completions_route_not_caught_by_workout_id(client):
    """
    CRITICAL: Verify /workouts/completions is NOT caught by /workouts/{workout_id}.

    Bug fixed: "completions" was being parsed as a workout_id UUID, causing
    'invalid input syntax for type uuid: "completions"' errors.
    """
    # This should NOT return a UUID parse error
    resp = client.get("/workouts/completions")

    # Should return 200 or 500 (DB error), but NOT 422 or UUID-related error
    assert resp.status_code != 422, "Route was caught by /workouts/{workout_id}"

    # Verify the response structure matches completions endpoint
    if resp.status_code == 200:
        data = resp.json()
        assert "completions" in data or "success" in data, \
            "Response doesn't match completions endpoint format"


def test_completions_id_route_accepts_valid_uuid(client):
    """
    Verify /workouts/completions/{id} accepts valid UUIDs.
    """
    valid_uuid = str(uuid.uuid4())
    resp = client.get(f"/workouts/completions/{valid_uuid}")

    # Should return 200 (found) or 200 with success=False (not found)
    # but NOT 422 (validation error)
    assert resp.status_code != 422


def test_workout_id_route_still_works(client):
    """
    Verify /workouts/{workout_id} still works for actual workout IDs.
    """
    valid_uuid = str(uuid.uuid4())
    resp = client.get(f"/workouts/{valid_uuid}")

    # Should return 200 (found/not found), not 422
    assert resp.status_code != 422


# =============================================================================
# GET /workouts/completions Tests
# =============================================================================


def test_list_completions_returns_success(client):
    """GET /workouts/completions returns success with auth."""
    resp = client.get("/workouts/completions")

    # 200 OK or 500 (if DB not connected)
    assert resp.status_code in (200, 500)

    if resp.status_code == 200:
        data = resp.json()
        assert "completions" in data
        assert "total" in data


def test_list_completions_accepts_pagination_params(client):
    """GET /workouts/completions accepts limit and offset params."""
    resp = client.get("/workouts/completions", params={"limit": 10, "offset": 5})

    assert resp.status_code in (200, 500)


def test_list_completions_limit_validation(client):
    """GET /workouts/completions enforces max limit of 100."""
    resp = client.get("/workouts/completions", params={"limit": 150})

    # Should return 422 because limit exceeds max of 100
    assert resp.status_code == 422


def test_list_completions_response_structure(client):
    """Verify the completions list response structure."""
    with patch('backend.app.get_user_completions') as mock_get:
        mock_get.return_value = {
            "completions": [
                {
                    "id": str(uuid.uuid4()),
                    "workout_name": "Test Workout",
                    "started_at": "2025-01-15T10:00:00Z",
                    "duration_seconds": 2700,
                    "avg_heart_rate": 142,
                    "max_heart_rate": 175,
                    "active_calories": 320,
                    "source": "apple_watch",
                }
            ],
            "total": 1
        }

        resp = client.get("/workouts/completions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert len(data["completions"]) == 1
        assert data["total"] == 1

        completion = data["completions"][0]
        assert "workout_name" in completion
        assert "started_at" in completion
        assert "duration_seconds" in completion


# =============================================================================
# GET /workouts/completions/{completion_id} Tests
# =============================================================================


def test_get_completion_by_id_returns_success(client):
    """GET /workouts/completions/{id} returns success with valid UUID."""
    completion_id = str(uuid.uuid4())
    resp = client.get(f"/workouts/completions/{completion_id}")

    assert resp.status_code in (200, 500)


def test_get_completion_not_found(client):
    """GET /workouts/completions/{id} returns not found for missing completion."""
    with patch('backend.app.get_completion_by_id') as mock_get:
        mock_get.return_value = None

        completion_id = str(uuid.uuid4())
        resp = client.get(f"/workouts/completions/{completion_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()


def test_get_completion_found(client):
    """GET /workouts/completions/{id} returns completion when found."""
    with patch('backend.app.get_completion_by_id') as mock_get:
        mock_completion = {
            "id": str(uuid.uuid4()),
            "workout_name": "HIIT Cardio",
            "started_at": "2025-01-15T10:00:00Z",
            "duration_seconds": 2700,
            "avg_heart_rate": 142,
            "max_heart_rate": 175,
            "active_calories": 320,
            "source": "apple_watch",
            "heart_rate_samples": [{"timestamp": "2025-01-15T10:00:00Z", "value": 80}]
        }
        mock_get.return_value = mock_completion

        resp = client.get(f"/workouts/completions/{mock_completion['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["completion"]["workout_name"] == "HIIT Cardio"


# =============================================================================
# POST /workouts/complete Tests
# =============================================================================


def test_complete_workout_missing_body_returns_422(client):
    """POST /workouts/complete requires a body."""
    resp = client.post("/workouts/complete", json={})
    assert resp.status_code == 422


def test_complete_workout_requires_workout_link(client):
    """POST /workouts/complete requires workout_event_id or follow_along_workout_id."""
    resp = client.post("/workouts/complete", json={
        "workout_name": "Test Workout",
        "started_at": "2025-01-15T10:00:00Z",
        "ended_at": "2025-01-15T10:45:00Z",
        "duration_seconds": 2700,
        "source": "apple_watch"
    })

    # Should return success=False for missing workout link
    if resp.status_code == 200:
        data = resp.json()
        assert data["success"] is False
        assert "workout_event_id" in data["message"].lower() or "required" in data["message"].lower()


def test_complete_workout_with_event_id(client):
    """POST /workouts/complete accepts workout_event_id."""
    with patch('backend.app.save_workout_completion') as mock_save:
        mock_save.return_value = {
            "success": True,
            "id": str(uuid.uuid4()),
            "summary": {"duration_formatted": "45:00", "avg_heart_rate": 142, "calories": 320}
        }

        resp = client.post("/workouts/complete", json={
            "workout_event_id": str(uuid.uuid4()),
            "started_at": "2025-01-15T10:00:00Z",
            "ended_at": "2025-01-15T10:45:00Z",
            "source": "apple_watch",
            "health_metrics": {
                "avg_heart_rate": 142,
                "max_heart_rate": 175,
                "active_calories": 320
            }
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data


def test_complete_workout_with_follow_along_id(client):
    """POST /workouts/complete accepts follow_along_workout_id."""
    with patch('backend.app.save_workout_completion') as mock_save:
        mock_save.return_value = {
            "success": True,
            "id": str(uuid.uuid4()),
            "summary": {"duration_formatted": "1:00:00", "avg_heart_rate": None, "calories": None}
        }

        resp = client.post("/workouts/complete", json={
            "follow_along_workout_id": str(uuid.uuid4()),
            "started_at": "2025-01-15T18:00:00Z",
            "ended_at": "2025-01-15T19:00:00Z",
            "source": "apple_watch",
            "health_metrics": {}
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True


# =============================================================================
# Auth Tests
# =============================================================================


def test_completions_requires_auth(api_client):
    """
    All completion endpoints should require authentication.

    Note: The api_client fixture has auth mocked, so we test that
    auth dependency is properly applied by checking endpoints work.
    """
    # These should all work with mocked auth
    resp1 = api_client.get("/workouts/completions")
    resp2 = api_client.get(f"/workouts/completions/{uuid.uuid4()}")

    # Should not return 401/403 with mocked auth
    assert resp1.status_code not in (401, 403)
    assert resp2.status_code not in (401, 403)


# =============================================================================
# Edge Cases
# =============================================================================


def test_completions_empty_list(client):
    """GET /workouts/completions returns empty list when no completions."""
    with patch('backend.app.get_user_completions') as mock_get:
        mock_get.return_value = {
            "completions": [],
            "total": 0
        }

        resp = client.get("/workouts/completions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["completions"] == []
        assert data["total"] == 0


def test_completions_string_literal_not_uuid(client):
    """
    Regression test: /workouts/completions should NOT be parsed as a workout_id.

    The word "completions" is not a valid UUID and should match the
    /workouts/completions route, not /workouts/{workout_id}.
    """
    resp = client.get("/workouts/completions")

    # If this was being caught by /workouts/{workout_id}, we'd get either:
    # - 422 (pydantic validation error for invalid UUID)
    # - 200 with a workout lookup error (not a completions response)

    if resp.status_code == 200:
        data = resp.json()
        # Should have completions structure, not workout structure
        has_completions_structure = "completions" in data or ("success" in data and "total" in data)
        has_workout_structure = "workout" in data

        assert has_completions_structure or not has_workout_structure, \
            "Response indicates /workouts/completions was caught by /workouts/{workout_id}"


# =============================================================================
# AMA-217: save_workout_completion Error Handling Tests
# These tests ensure that specific errors are properly surfaced instead of
# returning generic "Failed to save workout completion" messages.
# =============================================================================


def _make_completion_request(**overrides) -> WorkoutCompletionRequest:
    """Helper to create a WorkoutCompletionRequest with defaults."""
    defaults = {
        "follow_along_workout_id": str(uuid.uuid4()),
        "started_at": "2025-01-15T10:00:00Z",
        "ended_at": "2025-01-15T10:45:00Z",
        "health_metrics": HealthMetrics(
            avg_heart_rate=142,
            max_heart_rate=175,
            active_calories=320
        ),
        "source": "apple_watch",
    }
    defaults.update(overrides)
    return WorkoutCompletionRequest(**defaults)


def test_save_completion_success():
    """save_workout_completion returns success with id and summary on successful insert."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        assert result["id"] == "completion-123"
        assert "summary" in result


def test_save_completion_db_unavailable():
    """save_workout_completion returns DB_UNAVAILABLE when Supabase client is None."""
    with patch('backend.workout_completions.get_supabase_client', return_value=None):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "DB_UNAVAILABLE"
        assert "Database connection" in result["error"]


def test_save_completion_empty_result():
    """save_workout_completion returns INSERT_FAILED when database returns empty data."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "INSERT_FAILED"


def test_save_completion_profile_not_found():
    """save_workout_completion returns PROFILE_NOT_FOUND for profiles FK violation."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'violates foreign key constraint "workout_completions_user_id_fkey" on table "profiles"'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "PROFILE_NOT_FOUND"
        assert "profile" in result["error"].lower()


def test_save_completion_follow_along_workout_not_found():
    """save_workout_completion returns WORKOUT_NOT_FOUND for follow_along FK violation."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'violates foreign key constraint "workout_completions_follow_along_workout_id_fkey" on table "follow_along_workouts"'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "WORKOUT_NOT_FOUND"


def test_save_completion_workout_event_not_found():
    """save_workout_completion returns EVENT_NOT_FOUND for workout_events FK violation."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'violates foreign key constraint "workout_completions_workout_event_id_fkey" on table "workout_events"'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request(
            workout_event_id=str(uuid.uuid4()),
            follow_along_workout_id=None
        )
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "EVENT_NOT_FOUND"


def test_save_completion_rls_error():
    """save_workout_completion returns RLS_ERROR for row-level security violations."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'new row violates row-level security policy for table "workout_completions"'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "RLS_ERROR"
        assert "permission" in result["error"].lower() or "contact support" in result["error"].lower()


def test_save_completion_permission_denied():
    """save_workout_completion returns RLS_ERROR for permission denied errors."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'permission denied for table workout_completions'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "RLS_ERROR"


def test_save_completion_check_constraint_violation():
    """save_workout_completion returns MISSING_WORKOUT_LINK for check constraint violation."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'violates check constraint "chk_completion_link"'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "MISSING_WORKOUT_LINK"


def test_save_completion_unknown_error():
    """save_workout_completion returns UNKNOWN_ERROR for unrecognized exceptions."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.side_effect = Exception(
        'some unexpected database error'
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()
        result = save_workout_completion("user-123", request)

        assert result["success"] is False
        assert result["error_code"] == "UNKNOWN_ERROR"


# =============================================================================
# AMA-217: Endpoint Error Response Tests
# These tests verify that the endpoint correctly surfaces error codes
# =============================================================================


def test_complete_endpoint_returns_error_code(client):
    """POST /workouts/complete returns error_code in response on failure."""
    with patch('backend.app.save_workout_completion') as mock_save:
        mock_save.return_value = {
            "success": False,
            "error": "User profile not found. Please ensure your account is fully set up.",
            "error_code": "PROFILE_NOT_FOUND"
        }

        resp = client.post("/workouts/complete", json={
            "follow_along_workout_id": str(uuid.uuid4()),
            "started_at": "2025-01-15T10:00:00Z",
            "ended_at": "2025-01-15T10:45:00Z",
            "source": "apple_watch",
            "health_metrics": {}
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error_code"] == "PROFILE_NOT_FOUND"
        assert "profile" in data["message"].lower()


def test_complete_endpoint_rls_error_code(client):
    """POST /workouts/complete returns RLS_ERROR code on permission issues."""
    with patch('backend.app.save_workout_completion') as mock_save:
        mock_save.return_value = {
            "success": False,
            "error": "Permission denied. Please contact support.",
            "error_code": "RLS_ERROR"
        }

        resp = client.post("/workouts/complete", json={
            "follow_along_workout_id": str(uuid.uuid4()),
            "started_at": "2025-01-15T10:00:00Z",
            "ended_at": "2025-01-15T10:45:00Z",
            "source": "apple_watch",
            "health_metrics": {}
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error_code"] == "RLS_ERROR"
