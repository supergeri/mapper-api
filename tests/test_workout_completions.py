"""
Unit tests for workout completion endpoints (AMA-189, AMA-217).

These tests verify:
1. Route ordering is correct (/workouts/completions before /workouts/{workout_id})
2. Completion endpoints return proper responses
3. Auth is required for all completion endpoints
4. Error handling surfaces specific error messages (AMA-217)
5. Database errors are properly categorized

Updated in AMA-388 to use dependency overrides instead of patches.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, Mock
import uuid

from backend.app import app
from api.deps import get_completion_repo
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
    mock_repo = Mock()
    mock_repo.get_user_completions.return_value = {
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

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
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
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


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
    mock_repo = Mock()
    mock_repo.get_by_id.return_value = None

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
        completion_id = str(uuid.uuid4())
        resp = client.get(f"/workouts/completions/{completion_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "not found" in data["message"].lower()
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


def test_get_completion_found(client):
    """GET /workouts/completions/{id} returns completion when found."""
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

    mock_repo = Mock()
    mock_repo.get_by_id.return_value = mock_completion

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
        resp = client.get(f"/workouts/completions/{mock_completion['id']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["completion"]["workout_name"] == "HIIT Cardio"
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


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
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": True,
        "id": str(uuid.uuid4()),
        "summary": {"duration_formatted": "45:00", "avg_heart_rate": 142, "calories": 320}
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
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
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


def test_complete_workout_with_follow_along_id(client):
    """POST /workouts/complete accepts follow_along_workout_id."""
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": True,
        "id": str(uuid.uuid4()),
        "summary": {"duration_formatted": "1:00:00", "avg_heart_rate": None, "calories": None}
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
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
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


def test_complete_workout_with_workout_id(client):
    """POST /workouts/complete accepts workout_id (for iOS Companion workouts)."""
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": True,
        "id": str(uuid.uuid4()),
        "summary": {"duration_formatted": "30:00", "avg_heart_rate": 135, "calories": 250}
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
        resp = client.post("/workouts/complete", json={
            "workout_id": str(uuid.uuid4()),
            "started_at": "2025-01-15T14:00:00Z",
            "ended_at": "2025-01-15T14:30:00Z",
            "source": "apple_watch",
            "health_metrics": {
                "avg_heart_rate": 135,
                "active_calories": 250
            }
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "id" in data
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


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
    mock_repo = Mock()
    mock_repo.get_user_completions.return_value = {
        "completions": [],
        "total": 0
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
        resp = client.get("/workouts/completions")

        assert resp.status_code == 200
        data = resp.json()
        assert data["completions"] == []
        assert data["total"] == 0
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


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
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": False,
        "error": "User profile not found. Please ensure your account is fully set up.",
        "error_code": "PROFILE_NOT_FOUND"
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
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
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


def test_complete_endpoint_rls_error_code(client):
    """POST /workouts/complete returns RLS_ERROR code on permission issues."""
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": False,
        "error": "Permission denied. Please contact support.",
        "error_code": "RLS_ERROR"
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
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
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


# =============================================================================
# AMA-236: Filter Completed Workouts from Incoming Endpoints
# =============================================================================


def test_workouts_incoming_route_exists(client):
    """GET /workouts/incoming route is defined and returns success."""
    resp = client.get("/workouts/incoming")

    # Should return 200 or 500 (DB error), not 404
    assert resp.status_code != 404, "/workouts/incoming route not found"
    assert resp.status_code in (200, 500)

    if resp.status_code == 200:
        data = resp.json()
        assert "success" in data
        assert "workouts" in data
        assert "count" in data


def test_workouts_incoming_accepts_limit_param(client):
    """GET /workouts/incoming accepts limit parameter."""
    resp = client.get("/workouts/incoming", params={"limit": 10})

    assert resp.status_code in (200, 500)


def test_ios_companion_pending_excludes_completed_by_default(client):
    """GET /ios-companion/pending excludes completed workouts by default."""
    with patch('backend.app.get_ios_companion_pending_workouts') as mock_get:
        mock_get.return_value = []

        resp = client.get("/ios-companion/pending")

        # Verify exclude_completed=True was passed by default
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.kwargs.get("exclude_completed") is True


def test_ios_companion_pending_can_include_completed(client):
    """GET /ios-companion/pending can include completed workouts with param."""
    with patch('backend.app.get_ios_companion_pending_workouts') as mock_get:
        mock_get.return_value = []

        resp = client.get("/ios-companion/pending", params={"exclude_completed": "false"})

        # Verify exclude_completed=False was passed
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args.kwargs.get("exclude_completed") is False


def test_get_completed_workout_ids_returns_set():
    """get_completed_workout_ids returns a set of workout IDs."""
    from backend.database import get_completed_workout_ids

    with patch('backend.database.get_supabase_client') as mock_client:
        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        # Mock the query chain
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_not = MagicMock()
        mock_eq.not_.is_.return_value = mock_not

        workout_id_1 = str(uuid.uuid4())
        workout_id_2 = str(uuid.uuid4())
        mock_not.execute.return_value = MagicMock(
            data=[
                {"workout_id": workout_id_1},
                {"workout_id": workout_id_2},
                {"workout_id": None},  # Should be filtered out
            ]
        )

        result = get_completed_workout_ids("test-user-123")

        assert isinstance(result, set)
        assert workout_id_1 in result
        assert workout_id_2 in result
        assert None not in result
        assert len(result) == 2


def test_get_ios_companion_pending_filters_completed():
    """get_ios_companion_pending_workouts filters completed workouts."""
    from backend.database import get_ios_companion_pending_workouts

    workout_id_1 = str(uuid.uuid4())
    workout_id_2 = str(uuid.uuid4())
    workout_id_completed = str(uuid.uuid4())

    with patch('backend.database.get_supabase_client') as mock_client, \
         patch('backend.database.get_completed_workout_ids') as mock_completed:

        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        # Mock the workout query
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_chain = MagicMock()
        mock_table.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.not_.is_.return_value = mock_chain
        mock_chain.order.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(
            data=[
                {"id": workout_id_1, "title": "Workout 1"},
                {"id": workout_id_2, "title": "Workout 2"},
                {"id": workout_id_completed, "title": "Completed Workout"},
            ]
        )

        # Mark one workout as completed
        mock_completed.return_value = {workout_id_completed}

        result = get_ios_companion_pending_workouts(
            "test-user-123",
            limit=50,
            exclude_completed=True
        )

        # Should only return the 2 non-completed workouts
        assert len(result) == 2
        result_ids = {w["id"] for w in result}
        assert workout_id_1 in result_ids
        assert workout_id_2 in result_ids
        assert workout_id_completed not in result_ids


def test_get_ios_companion_pending_includes_completed_when_disabled():
    """get_ios_companion_pending_workouts includes completed when exclude_completed=False."""
    from backend.database import get_ios_companion_pending_workouts

    workout_id_1 = str(uuid.uuid4())
    workout_id_completed = str(uuid.uuid4())

    with patch('backend.database.get_supabase_client') as mock_client, \
         patch('backend.database.get_completed_workout_ids') as mock_completed:

        mock_supabase = MagicMock()
        mock_client.return_value = mock_supabase

        # Mock the workout query
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_chain = MagicMock()
        mock_table.select.return_value = mock_chain
        mock_chain.eq.return_value = mock_chain
        mock_chain.not_.is_.return_value = mock_chain
        mock_chain.order.return_value = mock_chain
        mock_chain.limit.return_value = mock_chain
        mock_chain.execute.return_value = MagicMock(
            data=[
                {"id": workout_id_1, "title": "Workout 1"},
                {"id": workout_id_completed, "title": "Completed Workout"},
            ]
        )

        # This should NOT be called when exclude_completed=False
        mock_completed.return_value = {workout_id_completed}

        result = get_ios_companion_pending_workouts(
            "test-user-123",
            limit=50,
            exclude_completed=False
        )

        # Should return all workouts including completed
        assert len(result) == 2
        # get_completed_workout_ids should not be called when exclude_completed=False
        mock_completed.assert_not_called()


# ============================================================================
# AMA-240: workout_structure field tests
# ============================================================================

def test_save_completion_with_workout_structure():
    """save_workout_completion stores workout_structure field (AMA-240)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        workout_structure = [
            {"type": "warmup", "duration": 300},
            {"type": "work", "duration": 600},
            {"type": "cooldown", "duration": 300},
        ]
        request = _make_completion_request(workout_structure=workout_structure)
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify workout_structure was passed to insert
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert record["workout_structure"] == workout_structure


def test_save_completion_with_intervals_backwards_compat():
    """save_workout_completion accepts 'intervals' field for backwards compat (AMA-240)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        intervals = [
            {"type": "warmup", "duration": 300},
            {"type": "work", "duration": 600},
        ]
        # Use 'intervals' instead of 'workout_structure'
        request = _make_completion_request(intervals=intervals)
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify intervals was stored as workout_structure
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert record["workout_structure"] == intervals


def test_get_completion_returns_workout_structure():
    """get_completion_by_id returns stored workout_structure (AMA-240)."""
    from backend.workout_completions import get_completion_by_id

    mock_supabase = MagicMock()
    workout_structure = [{"type": "work", "duration": 600}]

    # Mock completion record with workout_structure
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": "completion-123",
            "user_id": "user-123",
            "started_at": "2026-01-04T10:00:00Z",
            "ended_at": "2026-01-04T10:30:00Z",
            "duration_seconds": 1800,
            "source": "apple_watch",
            "created_at": "2026-01-04T10:30:00Z",
            "workout_structure": workout_structure,
            "workout_id": None,
            "follow_along_workout_id": None,
            "workout_event_id": None,
        }
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        result = get_completion_by_id("user-123", "completion-123")

        assert result is not None
        assert result["workout_structure"] == workout_structure
        assert result["intervals"] == workout_structure  # Backwards compat alias


# ============================================================================
# AMA-281: set_logs field tests for weight tracking
# ============================================================================

def test_set_log_model_structure():
    """Test SetLog and SetEntry models accept valid data."""
    from backend.workout_completions import SetLog, SetEntry

    entry = SetEntry(set_number=1, weight=135.0, unit="lbs", completed=True)
    assert entry.set_number == 1
    assert entry.weight == 135.0
    assert entry.unit == "lbs"
    assert entry.completed is True

    log = SetLog(
        exercise_name="Bench Press",
        exercise_index=2,
        sets=[entry]
    )
    assert log.exercise_name == "Bench Press"
    assert log.exercise_index == 2
    assert len(log.sets) == 1


def test_set_entry_allows_null_weight():
    """Test SetEntry allows null weight for skipped weight entries."""
    from backend.workout_completions import SetEntry

    entry = SetEntry(set_number=1, weight=None, unit=None, completed=True)
    assert entry.weight is None
    assert entry.unit is None
    assert entry.completed is True


def test_save_completion_with_set_logs():
    """save_workout_completion stores set_logs field (AMA-281)."""
    from backend.workout_completions import SetLog, SetEntry

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        set_logs = [
            SetLog(
                exercise_name="Bench Press",
                exercise_index=2,
                sets=[
                    SetEntry(set_number=1, weight=135.0, unit="lbs", completed=True),
                    SetEntry(set_number=2, weight=135.0, unit="lbs", completed=True),
                    SetEntry(set_number=3, weight=None, unit=None, completed=True),
                ]
            )
        ]
        request = _make_completion_request(set_logs=set_logs)
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify set_logs was passed to insert
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert "set_logs" in record
        assert len(record["set_logs"]) == 1
        assert record["set_logs"][0]["exercise_name"] == "Bench Press"
        assert len(record["set_logs"][0]["sets"]) == 3


def test_save_completion_without_set_logs():
    """save_workout_completion works without set_logs field (backwards compat)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        request = _make_completion_request()  # No set_logs
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify set_logs was NOT included in the record
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert "set_logs" not in record


def test_get_completion_returns_set_logs():
    """get_completion_by_id returns stored set_logs (AMA-281)."""
    from backend.workout_completions import get_completion_by_id

    mock_supabase = MagicMock()
    set_logs = [
        {
            "exercise_name": "Squat",
            "exercise_index": 0,
            "sets": [
                {"set_number": 1, "weight": 185.0, "unit": "lbs", "completed": True},
                {"set_number": 2, "weight": 185.0, "unit": "lbs", "completed": True},
            ]
        }
    ]

    # Mock completion record with set_logs
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": "completion-123",
            "user_id": "user-123",
            "started_at": "2026-01-08T10:00:00Z",
            "ended_at": "2026-01-08T10:30:00Z",
            "duration_seconds": 1800,
            "source": "apple_watch",
            "created_at": "2026-01-08T10:30:00Z",
            "workout_structure": None,
            "set_logs": set_logs,
            "workout_id": None,
            "follow_along_workout_id": None,
            "workout_event_id": None,
        }
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        result = get_completion_by_id("user-123", "completion-123")

        assert result is not None
        assert result["set_logs"] == set_logs
        assert result["set_logs"][0]["exercise_name"] == "Squat"
        assert len(result["set_logs"][0]["sets"]) == 2


def test_complete_workout_endpoint_accepts_set_logs(client):
    """POST /workouts/complete accepts set_logs in request body (AMA-281)."""
    mock_repo = Mock()
    mock_repo.save.return_value = {
        "success": True,
        "id": str(uuid.uuid4()),
        "summary": {"duration_formatted": "30:00", "avg_heart_rate": 135, "calories": 250}
    }

    original = app.dependency_overrides.get(get_completion_repo)
    app.dependency_overrides[get_completion_repo] = lambda: mock_repo
    try:
        resp = client.post("/workouts/complete", json={
            "workout_id": str(uuid.uuid4()),
            "started_at": "2026-01-08T14:00:00Z",
            "ended_at": "2026-01-08T14:30:00Z",
            "source": "apple_watch",
            "health_metrics": {
                "avg_heart_rate": 135,
                "active_calories": 250
            },
            "set_logs": [
                {
                    "exercise_name": "Bench Press",
                    "exercise_index": 2,
                    "sets": [
                        {"set_number": 1, "weight": 135, "unit": "lbs", "completed": True},
                        {"set_number": 2, "weight": 140, "unit": "lbs", "completed": True},
                    ]
                }
            ]
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

        # Verify save was called with set_logs
        mock_repo.save.assert_called_once()
        call_kwargs = mock_repo.save.call_args[1]
        assert call_kwargs.get("set_logs") is not None
        assert len(call_kwargs["set_logs"]) == 1
        assert call_kwargs["set_logs"][0]["exercise_name"] == "Bench Press"
    finally:
        if original:
            app.dependency_overrides[get_completion_repo] = original
        elif get_completion_repo in app.dependency_overrides:
            del app.dependency_overrides[get_completion_repo]


# ============================================================================
# AMA-290: execution_log field tests
# ============================================================================

def test_execution_log_models():
    """Test ExecutionLog and related models accept valid data (AMA-290)."""
    from backend.workout_completions import (
        IntervalSetExecution,
        IntervalExecution,
        ExecutionSummary,
        ExecutionLog
    )

    set_exec = IntervalSetExecution(
        set_number=1,
        status="completed",
        weight=135.0,
        unit="lbs"
    )
    assert set_exec.set_number == 1
    assert set_exec.status == "completed"
    assert set_exec.weight == 135.0

    interval = IntervalExecution(
        interval_index=0,
        kind="reps",
        name="Bench Press",
        status="completed",
        sets=[set_exec]
    )
    assert interval.interval_index == 0
    assert interval.kind == "reps"
    assert len(interval.sets) == 1

    summary = ExecutionSummary(
        total_intervals=5,
        completed=4,
        skipped=1,
        completion_percentage=80.0
    )
    assert summary.total_intervals == 5
    assert summary.completion_percentage == 80.0

    log = ExecutionLog(intervals=[interval], summary=summary)
    assert len(log.intervals) == 1
    assert log.summary.completed == 4


def test_merge_set_logs_to_execution_log_basic():
    """Test merge_set_logs_to_execution_log converts set_logs correctly (AMA-290)."""
    from backend.workout_completions import merge_set_logs_to_execution_log

    workout_structure = [
        {"kind": "warmup", "name": "Warmup", "duration": 300},
        {"kind": "reps", "name": "Bench Press", "sets": 3, "reps": 10},
        {"kind": "rest", "name": "Rest", "duration": 60},
    ]

    set_logs = [
        {
            "exercise_name": "Bench Press",
            "exercise_index": 1,
            "sets": [
                {"set_number": 1, "weight": 135.0, "unit": "lbs", "completed": True},
                {"set_number": 2, "weight": 140.0, "unit": "lbs", "completed": True},
            ]
        }
    ]

    result = merge_set_logs_to_execution_log(workout_structure, set_logs)

    assert result is not None
    assert "intervals" in result
    assert "summary" in result
    assert len(result["intervals"]) == 3

    # Check the reps interval has sets merged
    reps_interval = result["intervals"][1]
    assert reps_interval["planned_name"] == "Bench Press"
    assert "sets" in reps_interval
    assert len(reps_interval["sets"]) == 2
    # Weight is now a WeightEntry object with components and display_label (AMA-292)
    assert reps_interval["sets"][0]["weight"]["display_label"] == "135.0 lbs"
    assert reps_interval["sets"][0]["weight"]["components"][0]["value"] == 135.0


def test_merge_set_logs_empty_returns_none():
    """Test merge_set_logs_to_execution_log returns None for empty set_logs."""
    from backend.workout_completions import merge_set_logs_to_execution_log

    result = merge_set_logs_to_execution_log(None, None)
    assert result is None

    result = merge_set_logs_to_execution_log([], [])
    assert result is None


def test_save_completion_with_execution_log():
    """save_workout_completion stores execution_log field directly (AMA-290)."""
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        execution_log = {
            "intervals": [
                {"interval_index": 0, "kind": "reps", "name": "Squat", "status": "completed"}
            ],
            "summary": {"total_intervals": 1, "completed": 1, "skipped": 0}
        }
        request = _make_completion_request(execution_log=execution_log)
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify execution_log was passed to insert
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert "execution_log" in record
        assert record["execution_log"]["intervals"][0]["name"] == "Squat"


def test_save_completion_merges_set_logs_to_execution_log():
    """save_workout_completion merges set_logs to execution_log when not provided (AMA-290)."""
    from backend.workout_completions import SetLog, SetEntry

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "completion-123"}]
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        workout_structure = [
            {"kind": "reps", "name": "Bench Press", "sets": 2, "reps": 10},
        ]
        set_logs = [
            SetLog(
                exercise_name="Bench Press",
                exercise_index=0,
                sets=[
                    SetEntry(set_number=1, weight=135.0, unit="lbs", completed=True),
                ]
            )
        ]
        request = _make_completion_request(
            workout_structure=workout_structure,
            set_logs=set_logs
            # Note: execution_log not provided, should be auto-generated
        )
        result = save_workout_completion("user-123", request)

        assert result["success"] is True
        # Verify execution_log was auto-generated from set_logs
        insert_call = mock_supabase.table.return_value.insert.call_args
        record = insert_call[0][0]
        assert "execution_log" in record
        assert len(record["execution_log"]["intervals"]) == 1
        # Weight is now a WeightEntry object with components and display_label (AMA-292)
        weight_obj = record["execution_log"]["intervals"][0]["sets"][0]["weight"]
        assert weight_obj["display_label"] == "135.0 lbs"
        assert weight_obj["components"][0]["value"] == 135.0


def test_get_completion_returns_execution_log():
    """get_completion_by_id returns stored execution_log (AMA-290)."""
    from backend.workout_completions import get_completion_by_id

    mock_supabase = MagicMock()
    execution_log = {
        "intervals": [
            {"interval_index": 0, "kind": "reps", "name": "Deadlift", "status": "completed"}
        ],
        "summary": {"total_intervals": 1, "completed": 1, "skipped": 0}
    }

    # Mock completion record with execution_log
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
        data={
            "id": "completion-123",
            "user_id": "user-123",
            "started_at": "2026-01-09T10:00:00Z",
            "ended_at": "2026-01-09T10:30:00Z",
            "duration_seconds": 1800,
            "source": "apple_watch",
            "created_at": "2026-01-09T10:30:00Z",
            "workout_structure": None,
            "set_logs": None,
            "execution_log": execution_log,
            "workout_id": None,
            "follow_along_workout_id": None,
            "workout_event_id": None,
        }
    )

    with patch('backend.workout_completions.get_supabase_client', return_value=mock_supabase):
        result = get_completion_by_id("user-123", "completion-123")

        assert result is not None
        # Check execution_log structure is preserved
        # Note: _fix_execution_log_names adds planned_name field (AMA-292)
        assert result["execution_log"]["intervals"][0]["name"] == "Deadlift"
        assert result["execution_log"]["intervals"][0]["interval_index"] == 0
        assert result["execution_log"]["intervals"][0]["status"] == "completed"
        assert result["execution_log"]["summary"]["total_intervals"] == 1
