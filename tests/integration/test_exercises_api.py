"""
Integration tests for Exercises API endpoints.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

Tests the /exercises/* API endpoints with fake repository dependencies.
"""
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from api.deps import get_exercises_repo, get_exercise_matcher
from tests.fakes import FakeExercisesRepository
from backend.core.exercise_matcher import ExerciseMatchingService


@pytest.fixture
def client_with_fake_repo():
    """TestClient with fake exercises repository."""
    fake_repo = FakeExercisesRepository()
    fake_matcher = ExerciseMatchingService(
        exercises_repository=fake_repo,
        llm_client=None,
        enable_llm_fallback=False,
    )

    app.dependency_overrides[get_exercises_repo] = lambda: fake_repo
    app.dependency_overrides[get_exercise_matcher] = lambda: fake_matcher

    yield TestClient(app)

    app.dependency_overrides.clear()


# =============================================================================
# Match Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesCanonicalMatchEndpoint:
    """Tests for POST /exercises/canonical/match endpoint."""

    def test_match_exact_name_returns_200(self, client_with_fake_repo):
        """Exact name match should return 200 with full confidence."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": "Barbell Bench Press"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] == "barbell-bench-press"
        assert data["exercise_name"] == "Barbell Bench Press"
        assert data["confidence"] == 1.0
        assert data["method"] == "exact"

    def test_match_alias_returns_200(self, client_with_fake_repo):
        """Alias match should return 200 with high confidence."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": "RDL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] == "romanian-deadlift"
        assert data["method"] == "alias"
        assert data["confidence"] >= 0.93

    def test_match_empty_name_returns_no_match(self, client_with_fake_repo):
        """Empty name should return 200 with no match."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] is None
        assert data["confidence"] == 0.0
        assert data["method"] == "none"

    def test_match_whitespace_returns_no_match(self, client_with_fake_repo):
        """Whitespace-only name should return 200 with no match."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": "   "},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] is None
        assert data["method"] == "none"

    def test_match_unknown_exercise_returns_fuzzy_or_none(self, client_with_fake_repo):
        """Unknown exercise should return fuzzy match or none."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": "xyzzy plugh adventure"},
        )
        assert response.status_code == 200
        data = response.json()
        # Should be none or very low confidence fuzzy
        assert data["method"] in ("none", "fuzzy")
        if data["method"] == "none":
            assert data["exercise_id"] is None

    def test_match_missing_field_returns_422(self, client_with_fake_repo):
        """Missing planned_name field should return 422."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={},
        )
        assert response.status_code == 422

    def test_match_response_has_all_fields(self, client_with_fake_repo):
        """Response should have all expected fields."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match",
            json={"planned_name": "Squat"},
        )
        assert response.status_code == 200
        data = response.json()
        # Verify all fields are present
        assert "exercise_id" in data
        assert "exercise_name" in data
        assert "confidence" in data
        assert "method" in data
        assert "reasoning" in data
        assert "suggested_alias" in data


# =============================================================================
# Batch Match Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesCanonicalBatchMatchEndpoint:
    """Tests for POST /exercises/canonical/match/batch endpoint."""

    def test_batch_match_returns_same_order(self, client_with_fake_repo):
        """Batch match should return results in same order as input."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": ["RDL", "Barbell Bench Press", "unknown"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) == 3
        assert data["matches"][0]["exercise_id"] == "romanian-deadlift"
        assert data["matches"][1]["exercise_id"] == "barbell-bench-press"
        assert data["matches"][2]["exercise_id"] is None or data["matches"][2]["method"] == "fuzzy"

    def test_batch_match_single_item(self, client_with_fake_repo):
        """Batch match with single item should work."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": ["Pull-Up"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) == 1
        assert data["matches"][0]["exercise_id"] == "pull-up"

    def test_batch_match_empty_list_returns_422(self, client_with_fake_repo):
        """Empty list should return 422 (min_length=1)."""
        response = client_with_fake_repo.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": []},
        )
        assert response.status_code == 422

    def test_batch_match_max_items(self, client_with_fake_repo):
        """Should accept up to 100 items."""
        names = [f"Exercise {i}" for i in range(100)]
        response = client_with_fake_repo.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": names},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) == 100

    def test_batch_match_over_max_returns_422(self, client_with_fake_repo):
        """Over 100 items should return 422."""
        names = [f"Exercise {i}" for i in range(101)]
        response = client_with_fake_repo.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": names},
        )
        assert response.status_code == 422


# =============================================================================
# Suggest Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesCanonicalSuggestEndpoint:
    """Tests for GET /exercises/canonical/suggest endpoint."""

    def test_suggest_returns_multiple(self, client_with_fake_repo):
        """Suggest should return multiple candidates."""
        response = client_with_fake_repo.get(
            "/exercises/canonical/suggest?planned_name=bench%20press&limit=5"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_suggest_respects_limit(self, client_with_fake_repo):
        """Suggest should respect the limit parameter."""
        response = client_with_fake_repo.get(
            "/exercises/canonical/suggest?planned_name=press&limit=3"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    def test_suggest_sorted_by_confidence(self, client_with_fake_repo):
        """Suggestions should be sorted by confidence descending."""
        response = client_with_fake_repo.get(
            "/exercises/canonical/suggest?planned_name=deadlift&limit=5"
        )
        assert response.status_code == 200
        data = response.json()
        if len(data) > 1:
            confidences = [item["confidence"] for item in data]
            assert confidences == sorted(confidences, reverse=True)

    def test_suggest_missing_param_returns_422(self, client_with_fake_repo):
        """Missing planned_name should return 422."""
        response = client_with_fake_repo.get("/exercises/canonical/suggest")
        assert response.status_code == 422

    def test_suggest_limit_bounds(self, client_with_fake_repo):
        """Limit should be between 1 and 20."""
        # Below min
        response = client_with_fake_repo.get(
            "/exercises/canonical/suggest?planned_name=squat&limit=0"
        )
        assert response.status_code == 422

        # Above max
        response = client_with_fake_repo.get(
            "/exercises/canonical/suggest?planned_name=squat&limit=21"
        )
        assert response.status_code == 422


# =============================================================================
# Lookup Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesLookupEndpoint:
    """Tests for GET /exercises/{exercise_id} endpoint."""

    def test_get_by_id_found(self, client_with_fake_repo):
        """Existing exercise should return 200 with full details."""
        response = client_with_fake_repo.get("/exercises/barbell-bench-press")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "barbell-bench-press"
        assert data["name"] == "Barbell Bench Press"
        assert "chest" in data["primary_muscles"]
        assert data["supports_1rm"] is True

    def test_get_by_id_not_found(self, client_with_fake_repo):
        """Non-existent exercise should return 404."""
        response = client_with_fake_repo.get("/exercises/nonexistent-exercise-xyz")
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    def test_get_by_id_invalid_format(self, client_with_fake_repo):
        """Invalid exercise_id format should return 400."""
        # Test with uppercase (invalid)
        response = client_with_fake_repo.get("/exercises/Barbell-Bench-Press")
        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["detail"].lower()

        # Test with special characters (invalid)
        response = client_with_fake_repo.get("/exercises/bench@press")
        assert response.status_code == 400

    def test_get_by_id_response_has_all_fields(self, client_with_fake_repo):
        """Response should have all expected fields."""
        response = client_with_fake_repo.get("/exercises/conventional-deadlift")
        assert response.status_code == 200
        data = response.json()
        # Verify all fields from ExerciseResponse
        assert "id" in data
        assert "name" in data
        assert "aliases" in data
        assert "primary_muscles" in data
        assert "secondary_muscles" in data
        assert "equipment" in data
        assert "default_weight_source" in data
        assert "supports_1rm" in data
        assert "one_rm_formula" in data
        assert "category" in data
        assert "movement_pattern" in data


# =============================================================================
# List Endpoint Tests
# =============================================================================


@pytest.mark.integration
class TestExercisesListEndpoint:
    """Tests for GET /exercises endpoint."""

    def test_list_all_returns_200(self, client_with_fake_repo):
        """List all should return 200 with exercises."""
        response = client_with_fake_repo.get("/exercises")
        assert response.status_code == 200
        data = response.json()
        assert "exercises" in data
        assert "count" in data
        assert data["count"] > 0

    def test_list_with_muscle_filter(self, client_with_fake_repo):
        """Filter by muscle should return matching exercises."""
        response = client_with_fake_repo.get("/exercises?muscle=chest")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        for ex in data["exercises"]:
            assert "chest" in ex["primary_muscles"]

    def test_list_with_equipment_filter(self, client_with_fake_repo):
        """Filter by equipment should return matching exercises."""
        response = client_with_fake_repo.get("/exercises?equipment=barbell")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        for ex in data["exercises"]:
            assert "barbell" in ex["equipment"]

    def test_list_with_supports_1rm_filter(self, client_with_fake_repo):
        """Filter by supports_1rm should return matching exercises."""
        response = client_with_fake_repo.get("/exercises?supports_1rm=true")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        for ex in data["exercises"]:
            assert ex["supports_1rm"] is True

    def test_list_with_search(self, client_with_fake_repo):
        """Search by name pattern should return matching exercises."""
        response = client_with_fake_repo.get("/exercises?search=bench")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        for ex in data["exercises"]:
            assert "bench" in ex["name"].lower()

    def test_list_respects_limit(self, client_with_fake_repo):
        """List should respect limit parameter."""
        response = client_with_fake_repo.get("/exercises?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data["exercises"]) <= 3

    def test_list_limit_bounds(self, client_with_fake_repo):
        """Limit should be between 1 and 500."""
        # Below min
        response = client_with_fake_repo.get("/exercises?limit=0")
        assert response.status_code == 422

        # Above max
        response = client_with_fake_repo.get("/exercises?limit=501")
        assert response.status_code == 422

    def test_list_with_category_filter(self, client_with_fake_repo):
        """Filter by compound category should return matching exercises."""
        response = client_with_fake_repo.get("/exercises?category=compound")
        assert response.status_code == 200
        data = response.json()
        # All returned exercises should be compound
        for ex in data["exercises"]:
            assert ex["category"] == "compound"
