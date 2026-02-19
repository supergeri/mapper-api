import pytest

# All tests in this module use api_client (TestClient) - mark as integration tests
pytestmark = pytest.mark.integration

BASE_HEADERS = {}  # placeholder if you later need auth headers


def test_health_endpoint(api_client):
    resp = api_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    if isinstance(data, dict) and "status" in data:
        assert data["status"] == "ok"


@pytest.mark.skip(reason="Auth mock uses backend.main.app but fixture uses backend.app.app - needs auth refactor")
def test_get_workouts_returns_success(api_client):
    """
    /workouts now gets user_id from JWT (mocked in tests).
    profile_id is no longer required as a query param.
    """
    resp = api_client.get("/workouts")
    # Should return 200 (or 500 if DB not available, but not 422)
    assert resp.status_code in (200, 500)


@pytest.mark.skip(reason="Auth mock uses backend.main.app but fixture uses backend.app.app - needs auth refactor")
def test_get_workouts_with_profile_id_param(api_client):
    """
    /workouts with explicit profile_id param should still work.
    """
    resp = api_client.get("/workouts", params={"profile_id": "test-user"})
    assert resp.status_code in (200, 500)


def test_validate_workflow_missing_body_returns_422(api_client):
    """
    POST /workflow/validate expects a BlocksPayload body.
    Sending {} should fail validation.
    """
    resp = api_client.post("/workflow/validate", json={})
    assert resp.status_code == 422


def test_map_final_missing_body_returns_422(api_client):
    """
    POST /map/final expects an IngestPayload body.
    """
    resp = api_client.post("/map/final", json={})
    assert resp.status_code == 422


def test_exercise_suggest_missing_body_returns_422(api_client):
    """
    POST /exercise/suggest expects an ExerciseSuggestionRequest body.
    """
    resp = api_client.post("/exercise/suggest", json={})
    assert resp.status_code == 422


def test_exercise_similar_basic_call_not_422(api_client):
    """
    Simple smoke test for GET /exercise/similar/{exercise_name}.
    We only assert that validation passes (not 422).
    """
    resp = api_client.get("/exercise/similar/squat")
    assert resp.status_code != 422


def test_list_mappings_not_422(api_client):
    """
    GET /mappings has no required params – should at least pass validation.
    """
    resp = api_client.get("/mappings")
    assert resp.status_code != 422


# AMA-206: Test workout update with workout_id parameter
def test_save_workout_with_workout_id_not_422(api_client):
    """
    POST /workouts/save should accept workout_id parameter for updates.
    This verifies the API accepts the parameter (AMA-206 fix).
    """
    payload = {
        "workout_data": {
            "title": "Test Workout",
            "blocks": [
                {
                    "label": "Warm-up",
                    "exercises": [{"name": "Jumping Jacks", "sets": 1, "reps": 20}]
                }
            ]
        },
        "sources": ["text:test"],
        "device": "garmin",
        "title": "Test Workout",
        "workout_id": "existing-workout-uuid-123"  # AMA-206: Pass workout_id for update
    }
    resp = api_client.post("/workouts/save", json=payload)
    # Should not return 422 (validation error) - workout_id should be accepted
    # May return 500 if DB not available in test, but that's fine for this test
    assert resp.status_code != 422, f"API rejected workout_id parameter: {resp.json()}"


def test_save_workout_without_workout_id_not_422(api_client):
    """
    POST /workouts/save should work without workout_id for new workouts.
    """
    payload = {
        "workout_data": {
            "title": "New Workout",
            "blocks": []
        },
        "sources": ["text:test"],
        "device": "garmin",
        "title": "New Workout"
        # No workout_id - this is a new workout
    }
    resp = api_client.post("/workouts/save", json=payload)
    # Should not return 422 (validation error)
    assert resp.status_code != 422
