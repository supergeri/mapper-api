"""
Unit tests for the programs router periodization-plan endpoint.

Part of AMA-567 Phase E: Program pipeline (batched generation)

Tests the POST /programs/periodization-plan endpoint including:
- Happy-path auto-model selection
- Explicit model specification
- Response field validation
- Input validation (duration bounds, invalid enums)
- Deload week presence for long programs
- Week count matching duration
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.settings import Settings
from api.deps import get_current_user
from api.routers.programs import get_periodization_service
from backend.core.periodization_service import PeriodizationService


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_USER_ID = "test-user-programs-567"
ENDPOINT = "/programs/periodization-plan"

VALID_GOALS = [
    "strength",
    "hypertrophy",
    "endurance",
    "weight_loss",
    "general_fitness",
    "sport_specific",
]

VALID_EXPERIENCE_LEVELS = ["beginner", "intermediate", "advanced"]

VALID_FOCUS_VALUES = {"strength", "power", "hypertrophy", "endurance", "deload"}


# ---------------------------------------------------------------------------
# Auth / DI overrides
# ---------------------------------------------------------------------------


async def _mock_current_user() -> str:
    return TEST_USER_ID


def _real_periodization_service() -> PeriodizationService:
    return PeriodizationService()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """
    Create a TestClient with auth overridden but using the real
    PeriodizationService so we exercise the full computation path.
    """
    settings = Settings(environment="test", _env_file=None)
    app = create_app(settings=settings)
    app.dependency_overrides[get_current_user] = _mock_current_user
    app.dependency_overrides[get_periodization_service] = _real_periodization_service
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPeriodizationPlanEndpoint:
    """Tests for POST /programs/periodization-plan."""

    # -- Happy path: auto model selection --------------------------------

    def test_happy_path_auto_model(self, client):
        """POST with valid goal/experience/duration returns 200 with model and weeks."""
        payload = {
            "duration_weeks": 8,
            "goal": "strength",
            "experience_level": "intermediate",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 200, resp.text

        data = resp.json()
        # Response uses alias "model" for the periodization_model field
        assert "model" in data
        assert isinstance(data["model"], str)
        assert len(data["model"]) > 0

        assert "weeks" in data
        assert isinstance(data["weeks"], list)
        assert len(data["weeks"]) == 8

    # -- Explicit model: linear ------------------------------------------

    def test_explicit_model_linear(self, client):
        """Passing model='linear' explicitly should use linear periodization."""
        payload = {
            "duration_weeks": 6,
            "goal": "hypertrophy",
            "experience_level": "beginner",
            "model": "linear",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 200, resp.text

        data = resp.json()
        assert data["model"] == "linear"

    # -- Each week has required fields -----------------------------------

    def test_each_week_has_required_fields(self, client):
        """Every week object must contain week_number, intensity_percent, volume_modifier, is_deload, and focus."""
        payload = {
            "duration_weeks": 6,
            "goal": "general_fitness",
            "experience_level": "beginner",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 200, resp.text

        weeks = resp.json()["weeks"]
        for i, week in enumerate(weeks):
            assert "week_number" in week, f"week {i} missing week_number"
            assert "intensity_percent" in week, f"week {i} missing intensity_percent"
            assert "volume_modifier" in week, f"week {i} missing volume_modifier"
            assert "is_deload" in week, f"week {i} missing is_deload"
            assert "focus" in week, f"week {i} missing focus"

            # Validate value ranges
            assert isinstance(week["week_number"], int)
            assert 0.0 <= week["intensity_percent"] <= 1.0, (
                f"week {i} intensity_percent={week['intensity_percent']} out of [0, 1]"
            )
            assert week["volume_modifier"] > 0, (
                f"week {i} volume_modifier={week['volume_modifier']} should be positive"
            )
            assert isinstance(week["is_deload"], bool)
            assert week["focus"] in VALID_FOCUS_VALUES, (
                f"week {i} focus={week['focus']} not in {VALID_FOCUS_VALUES}"
            )

    # -- Duration below minimum rejected ---------------------------------

    def test_duration_weeks_below_minimum_rejected(self, client):
        """duration_weeks=2 should be rejected with 422 (minimum is 4)."""
        payload = {
            "duration_weeks": 2,
            "goal": "strength",
            "experience_level": "intermediate",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422

    # -- Duration above maximum rejected ---------------------------------

    def test_duration_weeks_above_maximum_rejected(self, client):
        """duration_weeks=100 should be rejected with 422 (maximum is 52)."""
        payload = {
            "duration_weeks": 100,
            "goal": "strength",
            "experience_level": "intermediate",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422

    # -- Invalid goal rejected -------------------------------------------

    def test_invalid_goal_rejected(self, client):
        """An invalid goal value should be rejected with 422."""
        payload = {
            "duration_weeks": 8,
            "goal": "teleportation",
            "experience_level": "intermediate",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422

    # -- Invalid experience level rejected --------------------------------

    def test_invalid_experience_level_rejected(self, client):
        """An invalid experience_level value should be rejected with 422."""
        payload = {
            "duration_weeks": 8,
            "goal": "strength",
            "experience_level": "godlike",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 422

    # -- Deload weeks present for long programs --------------------------

    def test_deload_weeks_present_for_long_programs(self, client):
        """A 12-week program should have at least 1 deload week."""
        payload = {
            "duration_weeks": 12,
            "goal": "strength",
            "experience_level": "intermediate",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 200, resp.text

        weeks = resp.json()["weeks"]
        deload_count = sum(1 for w in weeks if w["is_deload"])
        assert deload_count >= 1, (
            f"Expected at least 1 deload week in a 12-week program, got {deload_count}"
        )

    # -- Week count matches duration -------------------------------------

    def test_week_count_matches_duration(self, client):
        """The number of weeks in the response must equal duration_weeks."""
        for duration in (4, 8, 16, 52):
            payload = {
                "duration_weeks": duration,
                "goal": "hypertrophy",
                "experience_level": "advanced",
            }
            resp = client.post(ENDPOINT, json=payload)
            assert resp.status_code == 200, resp.text

            weeks = resp.json()["weeks"]
            assert len(weeks) == duration, (
                f"Expected {duration} weeks, got {len(weeks)}"
            )

    # -- Block model available -------------------------------------------

    def test_block_model_available(self, client):
        """Explicitly requesting model='block' should return 200."""
        payload = {
            "duration_weeks": 12,
            "goal": "strength",
            "experience_level": "advanced",
            "model": "block",
        }
        resp = client.post(ENDPOINT, json=payload)
        assert resp.status_code == 200, resp.text

        data = resp.json()
        assert data["model"] == "block"
        assert len(data["weeks"]) == 12
