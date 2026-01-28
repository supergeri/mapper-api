"""
Contract tests for GET /workouts/search response shape.

Part of AMA-432: Semantic Search Endpoint

Validates that the API response contract is stable for consumers.
Uses FakeSearchRepository and FakeEmbeddingService so no external
services are required. Runs on every PR.
"""

from typing import Optional

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from api.deps import get_current_user, get_search_repo, get_embedding_service
from tests.contract import assert_response_shape


TEST_USER_ID = "contract-test-user"

SAMPLE_ROW = {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "profile_id": TEST_USER_ID,
    "title": "Contract Test Workout",
    "description": "A workout for contract testing",
    "workout_data": {"type": "hiit", "duration_minutes": 20},
    "sources": ["ai"],
    "created_at": "2026-01-27T10:00:00+00:00",
    "similarity": 0.85,
}

SEARCH_RESPONSE_SHAPE = {
    "success": bool,
    "results": list,
    "count": int,
    "query": str,
    "search_type": str,
    "query_embedding_time_ms": Optional[int],
    "search_time_ms": Optional[int],
}

SEARCH_RESULT_ITEM_SHAPE = {
    "workout_id": str,
    "title": Optional[str],
    "description": Optional[str],
    "sources": list,
    "similarity_score": Optional[float],
    "created_at": Optional[str],
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeSearchRepoForContract:
    def semantic_search(self, profile_id, query_embedding, limit=10, threshold=0.5):
        return [SAMPLE_ROW]

    def keyword_search(self, profile_id, query, limit=10):
        return [SAMPLE_ROW]


class FakeEmbeddingForContract:
    def generate_query_embedding(self, text):
        return [0.1] * 1536


class FailingSearchRepo:
    def semantic_search(self, *a, **kw):
        raise RuntimeError("boom")

    def keyword_search(self, *a, **kw):
        raise RuntimeError("boom")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _mock_user():
    return TEST_USER_ID


@pytest.fixture(autouse=True)
def _override_deps():
    app.dependency_overrides[get_current_user] = _mock_user
    app.dependency_overrides[get_search_repo] = lambda: FakeSearchRepoForContract()
    app.dependency_overrides[get_embedding_service] = lambda: FakeEmbeddingForContract()
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_search_repo, None)
    app.dependency_overrides.pop(get_embedding_service, None)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestSearchResponseContract:
    """Validate GET /workouts/search response shape is stable."""

    def test_success_response_shape(self):
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "hiit"})
        assert response.status_code == 200
        data = response.json()
        assert_response_shape(data, SEARCH_RESPONSE_SHAPE)

    def test_result_item_shape(self):
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "hiit"})
        data = response.json()
        assert len(data["results"]) > 0
        assert_response_shape(data["results"][0], SEARCH_RESULT_ITEM_SHAPE)

    def test_empty_results_shape(self):
        app.dependency_overrides[get_search_repo] = lambda: type(
            "Empty", (), {
                "semantic_search": lambda self, *a, **kw: [],
                "keyword_search": lambda self, *a, **kw: [],
            }
        )()
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "nothing"})
        data = response.json()
        assert_response_shape(data, SEARCH_RESPONSE_SHAPE)
        assert data["results"] == []
        assert data["count"] == 0

    def test_error_response_shape(self):
        """When search fails entirely, response must still match shape."""
        app.dependency_overrides[get_search_repo] = lambda: FailingSearchRepo()
        app.dependency_overrides[get_embedding_service] = lambda: None
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "test"})
        data = response.json()
        assert_response_shape(data, SEARCH_RESPONSE_SHAPE)
        assert data["success"] is False
        assert data["search_type"] == "error"

    def test_keyword_fallback_response_has_null_embedding_time(self):
        """When using keyword fallback, query_embedding_time_ms should be null."""
        app.dependency_overrides[get_embedding_service] = lambda: None
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "test"})
        data = response.json()
        assert data["query_embedding_time_ms"] is None
        assert data["search_type"] == "keyword"

    def test_search_type_enum_values(self):
        """search_type must be one of the documented values."""
        client = TestClient(app)
        response = client.get("/workouts/search", params={"q": "test"})
        data = response.json()
        assert data["search_type"] in ("semantic", "keyword", "error")
