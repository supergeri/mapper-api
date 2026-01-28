"""
Unit tests for the semantic search endpoint (AMA-432).

Tests cover:
- Basic semantic search with mocked embedding service and search repo
- Keyword fallback when embedding service is unavailable
- Empty results
- Application-level filter application (workout_type, duration)
- Error handling when embedding generation fails
- Helper function unit tests (_matches_workout_type, _matches_duration)
- Protocol conformance for fakes
- ILIKE sanitization
"""

import inspect

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from api.deps import (
    get_current_user,
    get_search_repo,
    get_embedding_service,
)
from api.routers.workouts import _matches_workout_type, _matches_duration
from application.ports.search_repository import SearchRepository
from infrastructure.db.search_repository import SupabaseSearchRepository

TEST_USER_ID = "test-user-123"


# ---------------------------------------------------------------------------
# Fake Dependencies
# ---------------------------------------------------------------------------


async def mock_get_current_user() -> str:
    return TEST_USER_ID


class FakeSearchRepository:
    """In-memory search repository for testing."""

    def __init__(self, semantic_results=None, keyword_results=None):
        self._semantic_results = semantic_results or []
        self._keyword_results = keyword_results or []
        self.semantic_search_calls = []
        self.keyword_search_calls = []

    def semantic_search(self, profile_id, query_embedding, limit=10, threshold=0.5):
        self.semantic_search_calls.append({
            "profile_id": profile_id,
            "query_embedding": query_embedding,
            "limit": limit,
            "threshold": threshold,
        })
        return self._semantic_results

    def keyword_search(self, profile_id, query, limit=10):
        self.keyword_search_calls.append({
            "profile_id": profile_id,
            "query": query,
            "limit": limit,
        })
        return self._keyword_results


class FakeEmbeddingService:
    """Fake embedding service that returns a fixed vector."""

    def __init__(self, embedding=None, should_raise=False):
        self._embedding = embedding or [0.1] * 1536
        self._should_raise = should_raise
        self.calls = []

    def generate_query_embedding(self, text):
        self.calls.append(text)
        if self._should_raise:
            raise RuntimeError("OpenAI API error")
        return self._embedding


SAMPLE_WORKOUT_ROW = {
    "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "profile_id": TEST_USER_ID,
    "title": "20 Minute HIIT Workout",
    "description": "A quick HIIT session for beginners",
    "workout_data": {"type": "hiit", "duration_minutes": 20},
    "sources": ["ai"],
    "created_at": "2026-01-27T10:00:00+00:00",
    "similarity": 0.89,
}


# ===========================================================================
# Protocol Conformance Tests
# ===========================================================================


class TestFakeConformance:
    """Verify that test fakes conform to the Protocol they replace."""

    def test_fake_search_repo_has_required_methods(self):
        repo = FakeSearchRepository()
        assert hasattr(repo, "semantic_search")
        assert hasattr(repo, "keyword_search")

    def test_fake_semantic_search_matches_protocol_signature(self):
        protocol_sig = inspect.signature(SearchRepository.semantic_search)
        fake_sig = inspect.signature(FakeSearchRepository.semantic_search)
        protocol_params = list(protocol_sig.parameters.keys())
        fake_params = list(fake_sig.parameters.keys())
        assert protocol_params == fake_params, (
            f"Signature mismatch: protocol={protocol_params}, fake={fake_params}"
        )

    def test_fake_keyword_search_matches_protocol_signature(self):
        protocol_sig = inspect.signature(SearchRepository.keyword_search)
        fake_sig = inspect.signature(FakeSearchRepository.keyword_search)
        protocol_params = list(protocol_sig.parameters.keys())
        fake_params = list(fake_sig.parameters.keys())
        assert protocol_params == fake_params, (
            f"Signature mismatch: protocol={protocol_params}, fake={fake_params}"
        )


# ===========================================================================
# Helper Function Unit Tests
# ===========================================================================


class TestMatchesWorkoutType:
    """Unit tests for _matches_workout_type helper."""

    def test_exact_match(self):
        row = {"workout_data": {"type": "hiit"}}
        assert _matches_workout_type(row, "hiit") is True

    def test_case_insensitive(self):
        row = {"workout_data": {"type": "HIIT"}}
        assert _matches_workout_type(row, "hiit") is True

    def test_no_match(self):
        row = {"workout_data": {"type": "strength"}}
        assert _matches_workout_type(row, "hiit") is False

    def test_alternate_key_workout_type(self):
        """Covers the workout_data.workout_type fallback key."""
        row = {"workout_data": {"workout_type": "cardio"}}
        assert _matches_workout_type(row, "cardio") is True

    def test_missing_workout_data_none(self):
        row = {"workout_data": None}
        assert _matches_workout_type(row, "hiit") is False

    def test_missing_workout_data_key(self):
        row = {}
        assert _matches_workout_type(row, "hiit") is False

    def test_empty_workout_data(self):
        row = {"workout_data": {}}
        assert _matches_workout_type(row, "hiit") is False


class TestMatchesDuration:
    """Unit tests for _matches_duration helper."""

    def test_within_range(self):
        row = {"workout_data": {"duration_minutes": 25}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_below_min(self):
        row = {"workout_data": {"duration_minutes": 10}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is False

    def test_above_max(self):
        row = {"workout_data": {"duration_minutes": 60}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is False

    def test_exact_boundary_min(self):
        row = {"workout_data": {"duration_minutes": 15}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_exact_boundary_max(self):
        row = {"workout_data": {"duration_minutes": 30}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_no_duration_in_data_includes_result(self):
        """Workouts without duration info should NOT be filtered out."""
        row = {"workout_data": {}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_none_workout_data(self):
        row = {"workout_data": None}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_alternate_key_duration(self):
        """Covers the workout_data.duration fallback key."""
        row = {"workout_data": {"duration": 20}}
        assert _matches_duration(row, min_duration=15, max_duration=30) is True

    def test_only_min_duration(self):
        row = {"workout_data": {"duration_minutes": 5}}
        assert _matches_duration(row, min_duration=15, max_duration=None) is False

    def test_only_max_duration(self):
        row = {"workout_data": {"duration_minutes": 60}}
        assert _matches_duration(row, min_duration=None, max_duration=30) is False

    def test_no_filters(self):
        row = {"workout_data": {"duration_minutes": 60}}
        assert _matches_duration(row, min_duration=None, max_duration=None) is True

    def test_duration_zero_not_filtered_out(self):
        """duration=0 is a valid value and should not be treated as missing."""
        row = {"workout_data": {"duration": 0}}
        assert _matches_duration(row, min_duration=0, max_duration=10) is True


# ===========================================================================
# ILIKE Sanitization Tests
# ===========================================================================


class TestEscapeIlike:
    """Unit tests for SupabaseSearchRepository._escape_ilike."""

    def test_plain_text_unchanged(self):
        assert SupabaseSearchRepository._escape_ilike("hello world") == "hello world"

    def test_percent_escaped(self):
        assert SupabaseSearchRepository._escape_ilike("100%") == "100\\%"

    def test_underscore_escaped(self):
        assert SupabaseSearchRepository._escape_ilike("a_b") == "a\\_b"

    def test_backslash_escaped(self):
        assert SupabaseSearchRepository._escape_ilike("a\\b") == "a\\\\b"

    def test_all_metacharacters_escaped(self):
        assert SupabaseSearchRepository._escape_ilike("%_\\") == "\\%\\_\\\\"

    def test_comma_replaced_with_space(self):
        assert SupabaseSearchRepository._escape_ilike("a,b") == "a b"

    def test_dot_replaced_with_space(self):
        assert SupabaseSearchRepository._escape_ilike("a.b") == "a b"

    def test_postgrest_delimiters_and_sql_wildcards(self):
        """Combined: SQL wildcards escaped AND PostgREST delimiters stripped."""
        assert SupabaseSearchRepository._escape_ilike("a%b,c.d_e") == "a\\%b c d\\_e"

    def test_empty_string(self):
        assert SupabaseSearchRepository._escape_ilike("") == ""


# ===========================================================================
# Endpoint Tests
# ===========================================================================


class TestSearchEndpoint:
    """Tests for GET /workouts/search"""

    def setup_method(self):
        """Reset dependency overrides before each test."""
        app.dependency_overrides[get_current_user] = mock_get_current_user

    def teardown_method(self):
        """Clean up dependency overrides after each test."""
        app.dependency_overrides.pop(get_search_repo, None)
        app.dependency_overrides.pop(get_embedding_service, None)
        app.dependency_overrides.pop(get_current_user, None)

    def _make_client(self, search_repo=None, embedding_service=None):
        if search_repo is not None:
            app.dependency_overrides[get_search_repo] = lambda: search_repo
        if embedding_service is not None:
            app.dependency_overrides[get_embedding_service] = lambda: embedding_service
        else:
            # Default: no embedding service (keyword fallback)
            app.dependency_overrides[get_embedding_service] = lambda: None
        return TestClient(app)

    # --- Original tests ---

    def test_semantic_search_basic(self):
        """Semantic search returns results when embedding service is available."""
        repo = FakeSearchRepository(semantic_results=[SAMPLE_WORKOUT_ROW])
        emb = FakeEmbeddingService()
        client = self._make_client(search_repo=repo, embedding_service=emb)

        response = client.get("/workouts/search", params={"q": "HIIT for beginners"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["search_type"] == "semantic"
        assert data["query"] == "HIIT for beginners"
        assert data["count"] == 1
        assert len(data["results"]) == 1

        result = data["results"][0]
        assert result["workout_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert result["title"] == "20 Minute HIIT Workout"
        assert result["similarity_score"] == 0.89
        assert result["sources"] == ["ai"]

        # Verify embedding was generated
        assert len(emb.calls) == 1
        assert emb.calls[0] == "HIIT for beginners"

        # Verify semantic search was called (not keyword)
        assert len(repo.semantic_search_calls) == 1
        assert len(repo.keyword_search_calls) == 0

    def test_keyword_fallback_no_embedding_service(self):
        """Falls back to keyword search when embedding service is None."""
        repo = FakeSearchRepository(keyword_results=[SAMPLE_WORKOUT_ROW])
        client = self._make_client(search_repo=repo, embedding_service=None)

        response = client.get("/workouts/search", params={"q": "HIIT"})

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "keyword"
        assert data["count"] == 1
        assert len(repo.keyword_search_calls) == 1
        assert len(repo.semantic_search_calls) == 0

    def test_keyword_fallback_on_embedding_error(self):
        """Falls back to keyword search when embedding generation fails."""
        repo = FakeSearchRepository(keyword_results=[SAMPLE_WORKOUT_ROW])
        emb = FakeEmbeddingService(should_raise=True)
        client = self._make_client(search_repo=repo, embedding_service=emb)

        response = client.get("/workouts/search", params={"q": "HIIT"})

        assert response.status_code == 200
        data = response.json()
        assert data["search_type"] == "keyword"
        assert len(repo.keyword_search_calls) == 1
        assert len(emb.calls) == 1

    def test_empty_results(self):
        """Returns empty results when no workouts match."""
        repo = FakeSearchRepository()
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "nonexistent workout"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["count"] == 0
        assert data["results"] == []

    def test_missing_query_param(self):
        """Returns 422 when query param is missing."""
        repo = FakeSearchRepository()
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search")

        assert response.status_code == 422

    def test_limit_and_offset(self):
        """Respects limit and offset parameters."""
        rows = [
            {**SAMPLE_WORKOUT_ROW, "id": f"id-{i}", "title": f"Workout {i}"}
            for i in range(5)
        ]
        repo = FakeSearchRepository(keyword_results=rows)
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "test", "limit": 2, "offset": 1})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["results"][0]["workout_id"] == "id-1"
        assert data["results"][1]["workout_id"] == "id-2"

    def test_workout_type_filter(self):
        """Filters results by workout_type."""
        rows = [
            {**SAMPLE_WORKOUT_ROW, "id": "match", "workout_data": {"type": "hiit"}},
            {**SAMPLE_WORKOUT_ROW, "id": "no-match", "workout_data": {"type": "strength"}},
        ]
        repo = FakeSearchRepository(keyword_results=rows)
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "test", "workout_type": "hiit"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["workout_id"] == "match"

    def test_duration_filter(self):
        """Filters results by min/max duration."""
        rows = [
            {**SAMPLE_WORKOUT_ROW, "id": "short", "workout_data": {"duration_minutes": 10}},
            {**SAMPLE_WORKOUT_ROW, "id": "medium", "workout_data": {"duration_minutes": 25}},
            {**SAMPLE_WORKOUT_ROW, "id": "long", "workout_data": {"duration_minutes": 60}},
        ]
        repo = FakeSearchRepository(keyword_results=rows)
        client = self._make_client(search_repo=repo)

        response = client.get(
            "/workouts/search",
            params={"q": "test", "min_duration": 15, "max_duration": 30},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["workout_id"] == "medium"

    def test_timing_fields_present(self):
        """Response includes timing metadata."""
        repo = FakeSearchRepository(semantic_results=[SAMPLE_WORKOUT_ROW])
        emb = FakeEmbeddingService()
        client = self._make_client(search_repo=repo, embedding_service=emb)

        response = client.get("/workouts/search", params={"q": "test"})

        data = response.json()
        assert "query_embedding_time_ms" in data
        assert "search_time_ms" in data
        assert data["query_embedding_time_ms"] is not None
        assert data["search_time_ms"] is not None

    def test_limit_max_50(self):
        """Rejects limit above 50."""
        repo = FakeSearchRepository()
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "test", "limit": 100})

        assert response.status_code == 422

    # --- New endpoint-level tests ---

    def test_empty_string_query_rejected(self):
        """Empty string query should be rejected by min_length=1."""
        repo = FakeSearchRepository()
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": ""})

        assert response.status_code == 422

    def test_whitespace_only_query(self):
        """Whitespace-only query passes min_length validation.

        Documents current behavior: the query is forwarded as-is.
        """
        repo = FakeSearchRepository(keyword_results=[])
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "   "})

        assert response.status_code == 200
        assert response.json()["query"] == "   "

    def test_offset_beyond_results_returns_empty(self):
        """Offset past all results should return an empty list."""
        repo = FakeSearchRepository(keyword_results=[SAMPLE_WORKOUT_ROW])
        client = self._make_client(search_repo=repo)

        response = client.get(
            "/workouts/search", params={"q": "test", "offset": 100}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_keyword_results_have_null_similarity(self):
        """Keyword search results should have similarity_score=None."""
        row_no_similarity = {
            "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "profile_id": TEST_USER_ID,
            "title": "Test Workout",
            "description": "A test",
            "workout_data": {},
            "sources": ["manual"],
            "created_at": "2026-01-27T10:00:00+00:00",
        }
        repo = FakeSearchRepository(keyword_results=[row_no_similarity])
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "test"})

        assert response.status_code == 200
        result = response.json()["results"][0]
        assert result["similarity_score"] is None

    def test_sources_null_becomes_empty_list(self):
        """When sources is None in the DB row, response should show []."""
        row = {**SAMPLE_WORKOUT_ROW, "sources": None}
        repo = FakeSearchRepository(keyword_results=[row])
        client = self._make_client(search_repo=repo)

        response = client.get("/workouts/search", params={"q": "test"})

        assert response.status_code == 200
        assert response.json()["results"][0]["sources"] == []

    def test_workout_type_filter_case_insensitive(self):
        """workout_type filter should match case-insensitively."""
        rows = [
            {**SAMPLE_WORKOUT_ROW, "id": "match", "workout_data": {"type": "HIIT"}},
        ]
        repo = FakeSearchRepository(keyword_results=rows)
        client = self._make_client(search_repo=repo)

        response = client.get(
            "/workouts/search", params={"q": "test", "workout_type": "hiit"}
        )

        assert response.status_code == 200
        assert response.json()["count"] == 1

    def test_semantic_search_passes_correct_threshold(self):
        """Verify the hardcoded threshold 0.5 is passed to the repo."""
        repo = FakeSearchRepository(semantic_results=[])
        emb = FakeEmbeddingService()
        client = self._make_client(search_repo=repo, embedding_service=emb)

        client.get("/workouts/search", params={"q": "test"})

        assert repo.semantic_search_calls[0]["threshold"] == 0.5

    def test_semantic_search_limit_includes_offset(self):
        """The repo should receive limit+offset to fetch enough rows."""
        repo = FakeSearchRepository(semantic_results=[])
        emb = FakeEmbeddingService()
        client = self._make_client(search_repo=repo, embedding_service=emb)

        client.get("/workouts/search", params={"q": "test", "limit": 5, "offset": 3})

        assert repo.semantic_search_calls[0]["limit"] == 8  # 5 + 3

    def test_combined_filters_reduce_results(self):
        """Both workout_type and duration filters applied together."""
        rows = [
            {**SAMPLE_WORKOUT_ROW, "id": "1",
             "workout_data": {"type": "hiit", "duration_minutes": 20}},
            {**SAMPLE_WORKOUT_ROW, "id": "2",
             "workout_data": {"type": "hiit", "duration_minutes": 60}},
            {**SAMPLE_WORKOUT_ROW, "id": "3",
             "workout_data": {"type": "strength", "duration_minutes": 20}},
        ]
        repo = FakeSearchRepository(keyword_results=rows)
        client = self._make_client(search_repo=repo)

        response = client.get(
            "/workouts/search",
            params={
                "q": "test",
                "workout_type": "hiit",
                "min_duration": 15,
                "max_duration": 30,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["workout_id"] == "1"

    def test_search_repo_exception_returns_error(self):
        """When the search repo raises, endpoint returns success=false."""

        class FailingSearchRepo:
            def semantic_search(self, *a, **kw):
                raise ConnectionError("Database unavailable")

            def keyword_search(self, *a, **kw):
                raise ConnectionError("Database unavailable")

        client = self._make_client(
            search_repo=FailingSearchRepo(), embedding_service=None
        )

        response = client.get("/workouts/search", params={"q": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["search_type"] == "error"
        assert data["results"] == []
        assert data["count"] == 0
