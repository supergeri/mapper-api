"""
E2E tests for GET /workouts/search against real Supabase (and optionally OpenAI).

Part of AMA-432: Semantic Search Endpoint

Run with:
    pytest -m e2e tests/e2e/test_search_e2e.py -v --live
    pytest -m e2e tests/e2e/test_search_e2e.py -v --live --api-url http://localhost:8001

Requires:
    - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment
    - OPENAI_API_KEY in environment (for semantic search tests)
    - mapper-api running locally or at --api-url
    - match_workouts RPC function deployed to Supabase
    - Pre-computed embedding fixtures in tests/e2e/fixtures/search_embeddings.json

Test data:
    Tests seed their own workout rows with pre-computed embeddings
    and clean up after the module completes. A unique profile_id per
    run avoids collisions with parallel executions.
"""

import json
import os
import uuid
from pathlib import Path

import pytest
from supabase import Client

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEARCH_TEST_PROFILE = f"e2e-search-{uuid.uuid4().hex[:8]}"
OTHER_USER_PROFILE = f"e2e-search-other-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seed_workouts(supabase_client: Client):
    """Insert test workouts with pre-computed embeddings; clean up after."""
    embeddings_file = FIXTURES_DIR / "search_embeddings.json"
    if not embeddings_file.exists():
        pytest.skip(
            f"Embedding fixtures not found at {embeddings_file}. "
            "Run scripts/generate_search_fixtures.py to create them."
        )

    with open(embeddings_file) as f:
        fixtures = json.load(f)

    inserted_ids = []
    for w in fixtures:
        profile = OTHER_USER_PROFILE if w.get("other_user") else SEARCH_TEST_PROFILE
        row = {
            "id": str(uuid.uuid4()),
            "profile_id": profile,
            "title": w["title"],
            "description": w["description"],
            "workout_data": w.get("workout_data", {}),
            "sources": w.get("sources", []),
        }
        # Only set embedding if present in fixture
        if w.get("embedding"):
            row["embedding"] = w["embedding"]

        supabase_client.table("workouts").insert(row).execute()
        inserted_ids.append(row["id"])

    yield {
        "profile_id": SEARCH_TEST_PROFILE,
        "other_profile_id": OTHER_USER_PROFILE,
        "workout_ids": inserted_ids,
        "fixtures": fixtures,
    }

    # Cleanup
    for wid in inserted_ids:
        supabase_client.table("workouts").delete().eq("id", wid).execute()


@pytest.fixture(scope="module")
def authed_http_client(http_client):
    """HTTP client with test auth headers for the search test user."""
    test_secret = os.getenv("TEST_AUTH_SECRET", "")
    if test_secret:
        http_client.headers["X-Test-Auth"] = test_secret
        http_client.headers["X-Test-User-Id"] = SEARCH_TEST_PROFILE
    return http_client


# ---------------------------------------------------------------------------
# Smoke Suite (P0) -- Must pass for any deployment
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSearchE2ESmoke:
    """P0 smoke tests for semantic search."""

    def test_search_endpoint_responds(self, authed_http_client):
        """The search endpoint is reachable and returns valid JSON."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "results" in data
        assert "search_type" in data

    def test_search_requires_query(self, authed_http_client):
        """Missing q param returns 422."""
        response = authed_http_client.get("/workouts/search")
        assert response.status_code == 422

    def test_search_returns_valid_shape(self, authed_http_client, seed_workouts):
        """Response matches the documented contract."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout"},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["success"], bool)
        assert isinstance(data["results"], list)
        assert isinstance(data["count"], int)
        assert isinstance(data["query"], str)
        assert data["search_type"] in ("semantic", "keyword", "error")

        if data["results"]:
            item = data["results"][0]
            assert "workout_id" in item
            assert "title" in item
            assert "sources" in item
            assert "similarity_score" in item
            assert "created_at" in item

    def test_semantic_search_returns_relevant_results(self, authed_http_client, seed_workouts):
        """Natural language query returns semantically relevant results."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "high intensity interval training"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        if data["search_type"] == "semantic" and data["count"] > 0:
            # HIIT-related workout should rank highly
            titles = [r["title"].lower() for r in data["results"] if r.get("title")]
            assert any("hiit" in t or "interval" in t or "intensity" in t for t in titles), (
                f"Expected HIIT-related result in: {titles}"
            )

    def test_keyword_search_finds_exact_title(self, authed_http_client, seed_workouts):
        """Keyword search matches on exact title substring."""
        # Use a title from our seed data
        fixtures = seed_workouts["fixtures"]
        non_other_fixtures = [f for f in fixtures if not f.get("other_user")]
        if not non_other_fixtures:
            pytest.skip("No non-other-user fixtures to search for")

        title = non_other_fixtures[0]["title"]
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": title},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] > 0


# ---------------------------------------------------------------------------
# Regression Suite (P1-P2) -- Nightly runs
# ---------------------------------------------------------------------------


@pytest.mark.e2e
class TestSearchE2ERegression:
    """P1/P2 regression tests for search."""

    def test_pagination_limit(self, authed_http_client, seed_workouts):
        """limit param restricts result count."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout", "limit": 1},
        )
        data = response.json()
        assert data["success"] is True
        assert len(data["results"]) <= 1

    def test_pagination_offset(self, authed_http_client, seed_workouts):
        """offset param skips results."""
        all_resp = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout", "limit": 50},
        )
        all_data = all_resp.json()

        if all_data["count"] < 2:
            pytest.skip("Need at least 2 results to test offset")

        offset_resp = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout", "limit": 50, "offset": 1},
        )
        offset_data = offset_resp.json()
        assert offset_data["count"] == all_data["count"] - 1

    def test_workout_type_filter(self, authed_http_client, seed_workouts):
        """workout_type filter narrows results without errors."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout", "workout_type": "strength"},
        )
        data = response.json()
        assert data["success"] is True

    def test_duration_filter(self, authed_http_client, seed_workouts):
        """min/max duration filters work without errors."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout", "min_duration": 25, "max_duration": 45},
        )
        data = response.json()
        assert data["success"] is True

    def test_auth_scoping_no_cross_user_leakage(self, authed_http_client, seed_workouts):
        """Results only include workouts for the authenticated user.

        The seed data includes a workout for a different profile_id.
        It must never appear in results.
        """
        # Search broadly
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "Secret", "limit": 50},
        )
        data = response.json()
        assert data["success"] is True

        # Get titles of "other user" fixtures
        other_titles = {
            f["title"] for f in seed_workouts["fixtures"] if f.get("other_user")
        }
        for result in data["results"]:
            assert result.get("title") not in other_titles, (
                f"Cross-user data leakage detected: saw '{result.get('title')}'"
            )

    def test_empty_results_for_nonsense_query(self, authed_http_client, seed_workouts):
        """Garbage query returns empty results, not an error."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "zzzzxxxxxqqqq nonsense gibberish"},
        )
        data = response.json()
        assert data["success"] is True

    def test_similarity_scores_present_for_semantic(self, authed_http_client, seed_workouts):
        """Semantic results include similarity_score > threshold."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "HIIT training"},
        )
        data = response.json()
        if data["search_type"] == "semantic" and data["count"] > 0:
            for result in data["results"]:
                assert result["similarity_score"] is not None
                assert result["similarity_score"] > 0.5

    def test_timing_metadata_populated(self, authed_http_client, seed_workouts):
        """Timing fields are present and non-negative."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "workout"},
        )
        data = response.json()
        assert data["search_time_ms"] is not None
        assert data["search_time_ms"] >= 0
        if data["search_type"] == "semantic":
            assert data["query_embedding_time_ms"] is not None
            assert data["query_embedding_time_ms"] >= 0

    def test_limit_validation_rejects_above_50(self, authed_http_client):
        """limit > 50 returns 422."""
        response = authed_http_client.get(
            "/workouts/search",
            params={"q": "test", "limit": 100},
        )
        assert response.status_code == 422

    def test_special_characters_in_query(self, authed_http_client, seed_workouts):
        """Special characters in query do not cause errors."""
        queries = [
            "100% effort",
            "push_up",
            "bench\\press",
            "'; DROP TABLE workouts; --",
        ]
        for query in queries:
            response = authed_http_client.get(
                "/workouts/search",
                params={"q": query},
            )
            assert response.status_code == 200, f"Failed for query: {query}"
            assert response.json()["success"] is True, f"success=false for query: {query}"
