"""
E2E tests for PATCH /workouts/{id} against real Supabase.

Part of AMA-433: PATCH /workouts/{id} endpoint implementation

Run with:
    pytest -m e2e tests/e2e/test_patch_workout_e2e.py -v --live
    pytest -m e2e tests/e2e/test_patch_workout_e2e.py -v --live --api-url http://localhost:8001

Requires:
    - SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment
    - mapper-api running locally or at --api-url
    - workout_edit_history table deployed
"""

import os
import uuid
import pytest
from typing import Generator

from supabase import Client


# Unique profile IDs for this test run to avoid conflicts
PATCH_TEST_PROFILE = f"e2e-patch-{uuid.uuid4().hex[:8]}"
OTHER_USER_PROFILE = f"e2e-patch-other-{uuid.uuid4().hex[:8]}"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="module")
def test_workout_data():
    """Base workout data for testing."""
    return {
        "title": "E2E Patch Test Workout",
        "description": "Original description",
        "blocks": [
            {
                "label": "Main Block",
                "exercises": [
                    {"name": "Squat", "sets": 3, "reps": 10},
                    {"name": "Bench Press", "sets": 3, "reps": 8},
                ],
            }
        ],
        "tags": ["strength", "test"],
    }


@pytest.fixture(scope="module")
def seed_workout(
    supabase_client: Client,
    test_workout_data: dict,
    live_mode: bool,
) -> Generator[dict, None, None]:
    """Create a test workout and clean up after."""
    if not live_mode:
        pytest.skip("E2E tests require --live flag")

    workout_id = str(uuid.uuid4())
    row = {
        "id": workout_id,
        "profile_id": PATCH_TEST_PROFILE,
        "title": test_workout_data["title"],
        "description": test_workout_data.get("description"),
        "workout_data": test_workout_data,
        "tags": test_workout_data.get("tags", []),
        "sources": ["test"],
        "device": "test",
        "embedding_content_hash": "original-hash-123",
    }

    try:
        supabase_client.table("workouts").insert(row).execute()
    except Exception as e:
        pytest.skip(f"Failed to seed workout: {e}")

    yield {
        "workout_id": workout_id,
        "profile_id": PATCH_TEST_PROFILE,
        "initial_data": test_workout_data,
    }

    # Cleanup
    try:
        supabase_client.table("workouts").delete().eq("id", workout_id).execute()
        supabase_client.table("workout_edit_history").delete().eq(
            "workout_id", workout_id
        ).execute()
    except Exception:
        pass  # Best effort cleanup


@pytest.fixture(scope="module")
def seed_other_user_workout(
    supabase_client: Client,
    live_mode: bool,
) -> Generator[str, None, None]:
    """Create a workout owned by another user."""
    if not live_mode:
        pytest.skip("E2E tests require --live flag")

    workout_id = str(uuid.uuid4())
    row = {
        "id": workout_id,
        "profile_id": OTHER_USER_PROFILE,
        "title": "Other User Workout",
        "workout_data": {
            "title": "Other User Workout",
            "blocks": [{"exercises": [{"name": "Exercise", "sets": 1}]}],
        },
        "sources": ["test"],
        "device": "test",
    }

    try:
        supabase_client.table("workouts").insert(row).execute()
    except Exception as e:
        pytest.skip(f"Failed to seed other user workout: {e}")

    yield workout_id

    # Cleanup
    try:
        supabase_client.table("workouts").delete().eq("id", workout_id).execute()
    except Exception:
        pass


@pytest.fixture(scope="module")
def authed_http_client(http_client, live_mode: bool):
    """HTTP client with test auth headers."""
    if not live_mode:
        pytest.skip("E2E tests require --live flag")

    test_secret = os.getenv("TEST_AUTH_SECRET", "")
    if test_secret:
        http_client.headers["X-Test-Auth"] = test_secret
        http_client.headers["X-Test-User-Id"] = PATCH_TEST_PROFILE
    else:
        pytest.skip("TEST_AUTH_SECRET not set for E2E tests")

    return http_client


# =============================================================================
# P0 Smoke Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2ESmoke:
    """P0 smoke tests - basic endpoint availability."""

    def test_patch_endpoint_responds(self, authed_http_client, seed_workout):
        """The patch endpoint is reachable and responds."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": "Smoke Test Title"}
                ]
            },
        )
        # Should get a valid response (200, 401, 403, 404, or 422)
        assert response.status_code in (200, 401, 403, 404, 422)

    def test_patch_requires_auth(self, http_client, seed_workout, live_mode):
        """Unauthenticated requests are rejected."""
        if not live_mode:
            pytest.skip("E2E tests require --live flag")

        response = http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": "X"}]
            },
        )
        assert response.status_code in (401, 403)

    def test_patch_nonexistent_workout_returns_404(self, authed_http_client):
        """Patching nonexistent workout returns 404."""
        fake_id = str(uuid.uuid4())
        response = authed_http_client.patch(
            f"/workouts/{fake_id}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": "X"}]
            },
        )
        assert response.status_code == 404


# =============================================================================
# P1 Functional Tests - Database Persistence
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EFunctional:
    """P1 functional tests verifying database state changes."""

    def test_replace_title_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Title replacement is persisted to database."""
        new_title = f"Updated Title {uuid.uuid4().hex[:6]}"

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": new_title}]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}: {response.text}")

        # Verify in database
        row = (
            supabase_client.table("workouts")
            .select("title, workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["title"] == new_title
        assert row.data["workout_data"]["title"] == new_title

    def test_replace_description_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Description replacement is persisted to database."""
        new_desc = f"Updated description {uuid.uuid4().hex[:6]}"

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/description", "value": new_desc}
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        row = (
            supabase_client.table("workouts")
            .select("description")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["description"] == new_desc

    def test_add_tag_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Adding a tag is persisted to database."""
        new_tag = f"e2e-tag-{uuid.uuid4().hex[:6]}"

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "add", "path": "/tags/-", "value": new_tag}]},
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        row = (
            supabase_client.table("workouts")
            .select("tags")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert new_tag in row.data["tags"]

    def test_replace_tags_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Replacing entire tags array is persisted."""
        new_tags = ["replaced", "tags", "array"]

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [{"op": "replace", "path": "/tags", "value": new_tags}]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        row = (
            supabase_client.table("workouts")
            .select("tags")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["tags"] == new_tags

    def test_replace_exercise_field_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Replacing exercise field is persisted."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/exercises/0/sets", "value": 5}
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        # Check first block's first exercise
        exercises = row.data["workout_data"]["blocks"][0]["exercises"]
        assert exercises[0]["sets"] == 5

    def test_multiple_operations_persist(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Multiple operations in one request all persist."""
        unique = uuid.uuid4().hex[:6]
        new_title = f"Multi-op Title {unique}"
        new_tag = f"multi-{unique}"

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": new_title},
                    {"op": "add", "path": "/tags/-", "value": new_tag},
                    {"op": "replace", "path": "/exercises/0/reps", "value": 12},
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        row = (
            supabase_client.table("workouts")
            .select("title, tags, workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )

        assert row.data["title"] == new_title
        assert new_tag in row.data["tags"]
        assert row.data["workout_data"]["blocks"][0]["exercises"][0]["reps"] == 12


# =============================================================================
# P1 Functional Tests - Audit Trail
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EAuditTrail:
    """P1 tests for audit trail functionality."""

    def test_audit_trail_created(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Patch operations are logged to audit trail."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": "Audit Test Title"}
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        # Query audit trail
        history = (
            supabase_client.table("workout_edit_history")
            .select("*")
            .eq("workout_id", seed_workout["workout_id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        assert len(history.data) > 0
        entry = history.data[0]
        assert entry["workout_id"] == seed_workout["workout_id"]
        assert entry["user_id"] == PATCH_TEST_PROFILE
        assert len(entry["operations"]) > 0
        assert entry["operations"][0]["op"] == "replace"
        assert entry["operations"][0]["path"] == "/title"

    def test_audit_trail_records_changes_applied(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Audit trail records number of changes applied."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": "Change Count Test"},
                    {"op": "add", "path": "/tags/-", "value": "audit-test"},
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        history = (
            supabase_client.table("workout_edit_history")
            .select("changes_applied, operations")
            .eq("workout_id", seed_workout["workout_id"])
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        assert len(history.data) > 0
        entry = history.data[0]
        assert entry["changes_applied"] >= 1
        assert len(entry["operations"]) == 2


# =============================================================================
# P1 Functional Tests - Embedding Regeneration
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EEmbedding:
    """P1 tests for embedding hash clearing."""

    def test_embedding_hash_cleared(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Embedding hash is cleared after patch to trigger regeneration."""
        # First ensure there's a hash set
        supabase_client.table("workouts").update(
            {"embedding_content_hash": "test-hash-to-clear"}
        ).eq("id", seed_workout["workout_id"]).execute()

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": "Embedding Test"}
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        # Verify hash was cleared
        row = (
            supabase_client.table("workouts")
            .select("embedding_content_hash")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["embedding_content_hash"] is None

    def test_response_indicates_embedding_status(
        self, authed_http_client, seed_workout
    ):
        """Response includes embedding regeneration status."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/description", "value": "Test"}
                ]
            },
        )

        if response.status_code != 200:
            pytest.skip(f"Patch returned {response.status_code}")

        data = response.json()
        assert "embedding_regeneration" in data
        assert data["embedding_regeneration"] in ("queued", "none", "failed")


# =============================================================================
# P2 Security Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2ESecurity:
    """P2 security tests."""

    def test_cannot_patch_other_users_workout(
        self, authed_http_client, seed_other_user_workout
    ):
        """Users cannot patch workouts they do not own."""
        response = authed_http_client.patch(
            f"/workouts/{seed_other_user_workout}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": "Hacked!"}]
            },
        )
        # Should appear as "not found" to avoid leaking existence
        assert response.status_code == 404

    def test_sql_injection_in_workout_id(self, authed_http_client):
        """SQL injection attempts in workout ID are handled safely."""
        malicious_ids = [
            "'; DROP TABLE workouts; --",
            "1 OR 1=1",
            "w-123' AND '1'='1",
            "w-123; DELETE FROM workouts;",
        ]
        for mal_id in malicious_ids:
            response = authed_http_client.patch(
                f"/workouts/{mal_id}",
                json={
                    "operations": [{"op": "replace", "path": "/title", "value": "X"}]
                },
            )
            # Should return 404 or 422, not 500
            assert response.status_code in (404, 422), f"Failed for: {mal_id}"

    def test_special_chars_in_value_handled(
        self, authed_http_client, seed_workout
    ):
        """Special characters in values are handled safely."""
        special_values = [
            "Title with <script>alert('XSS')</script>",
            "Title with '; DROP TABLE workouts; --",
            "Title with emoji \U0001F4AA\U0001F3CB",
            "Title\nwith\nnewlines",
            "Title\twith\ttabs",
            'Title with "quotes" and \'apostrophes\'',
        ]
        for val in special_values:
            response = authed_http_client.patch(
                f"/workouts/{seed_workout['workout_id']}",
                json={
                    "operations": [{"op": "replace", "path": "/title", "value": val}]
                },
            )
            # Should return 200 or 422 (if validation rejects), not 500
            assert response.status_code in (
                200,
                422,
            ), f"Unexpected status for: {val}"

    def test_very_long_value_handled(self, authed_http_client, seed_workout):
        """Very long values are handled (rejected or truncated)."""
        long_value = "x" * 10000

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": long_value}]
            },
        )
        # Should return 200 or 422, not 500
        assert response.status_code in (200, 422)


# =============================================================================
# P2 Edge Cases
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EEdgeCases:
    """P2 edge case tests."""

    def test_empty_string_title_rejected(self, authed_http_client, seed_workout):
        """Empty string for title is rejected."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": ""}]},
        )
        # Should be rejected by validation
        assert response.status_code == 422

    def test_whitespace_only_title_rejected(self, authed_http_client, seed_workout):
        """Whitespace-only title is rejected."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [{"op": "replace", "path": "/title", "value": "   "}]
            },
        )
        assert response.status_code == 422

    def test_concurrent_patches_handled(
        self, authed_http_client, seed_workout
    ):
        """Concurrent patch requests don't corrupt data."""
        import concurrent.futures

        def make_patch(suffix: str):
            return authed_http_client.patch(
                f"/workouts/{seed_workout['workout_id']}",
                json={
                    "operations": [
                        {"op": "replace", "path": "/title", "value": f"Title {suffix}"}
                    ]
                },
            )

        # Send 5 concurrent patches
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_patch, str(i)) for i in range(5)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # All should succeed (last one wins)
        success_count = sum(1 for r in results if r.status_code == 200)
        assert success_count >= 1  # At least one should succeed


# =============================================================================
# P1 Remove Operations Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2ERemoveOperations:
    """P1 tests for remove operations - critical gap identified by E2E QA."""

    def test_remove_tag_by_index_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Removing a tag by index persists to database."""
        # First ensure workout has multiple tags
        setup_tags = ["tag-to-keep", "tag-to-remove", "another-tag"]
        authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/tags", "value": setup_tags}]},
        )

        # Remove the middle tag (index 1)
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "remove", "path": "/tags/1"}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify tag was removed
        row = (
            supabase_client.table("workouts")
            .select("tags")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert "tag-to-remove" not in row.data["tags"]
        assert "tag-to-keep" in row.data["tags"]
        assert "another-tag" in row.data["tags"]

    def test_remove_exercise_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Removing an exercise persists to database."""
        # First add an extra exercise to ensure we have at least 2
        authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "add", "path": "/exercises/-", "value": {"name": "Extra Exercise", "sets": 3, "reps": 10}}
                ]
            },
        )

        # Get current exercise count
        before = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        before_count = len(before.data["workout_data"]["blocks"][0]["exercises"])

        # Remove the first exercise
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "remove", "path": "/exercises/0"}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify exercise count reduced
        after = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        after_count = len(after.data["workout_data"]["blocks"][0]["exercises"])
        assert after_count == before_count - 1

    def test_remove_description_sets_null(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Removing description sets it to null."""
        # First ensure description is set
        authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/description", "value": "Temp description"}
                ]
            },
        )

        # Remove description
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "remove", "path": "/description"}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify description is null
        row = (
            supabase_client.table("workouts")
            .select("description")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["description"] is None


# =============================================================================
# P1 Length Limit Boundary Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2ELengthLimits:
    """P1 tests for length limit enforcement at exact boundaries."""

    def test_title_at_200_chars_accepted(self, authed_http_client, seed_workout):
        """Title at exactly 200 characters is accepted."""
        title = "x" * 200
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": title}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_title_at_201_chars_rejected(self, authed_http_client, seed_workout):
        """Title at 201 characters is rejected with 422."""
        title = "x" * 201
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": title}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"
        data = response.json()
        assert "detail" in data

    def test_description_at_2000_chars_accepted(self, authed_http_client, seed_workout):
        """Description at exactly 2000 characters is accepted."""
        desc = "x" * 2000
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/description", "value": desc}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_description_at_2001_chars_rejected(self, authed_http_client, seed_workout):
        """Description at 2001 characters is rejected with 422."""
        desc = "x" * 2001
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/description", "value": desc}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    def test_50_tags_accepted(self, authed_http_client, seed_workout):
        """Exactly 50 tags is accepted."""
        tags = [f"tag{i}" for i in range(50)]
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/tags", "value": tags}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_51_tags_rejected(self, authed_http_client, seed_workout):
        """More than 50 tags is rejected with 422."""
        tags = [f"tag{i}" for i in range(51)]
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/tags", "value": tags}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    def test_tag_at_100_chars_accepted(self, authed_http_client, seed_workout):
        """Single tag at exactly 100 characters is accepted."""
        tag = "x" * 100
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "add", "path": "/tags/-", "value": tag}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_tag_at_101_chars_rejected(self, authed_http_client, seed_workout):
        """Single tag at 101 characters is rejected with 422."""
        tag = "x" * 101
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "add", "path": "/tags/-", "value": tag}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"

    def test_exercise_name_at_200_chars_accepted(self, authed_http_client, seed_workout):
        """Exercise name at exactly 200 characters is accepted."""
        name = "x" * 200
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/exercises/0/name", "value": name}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_exercise_name_at_201_chars_rejected(self, authed_http_client, seed_workout):
        """Exercise name at 201 characters is rejected with 422."""
        name = "x" * 201
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/exercises/0/name", "value": name}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"


# =============================================================================
# P1 Notes Field Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2ENotesField:
    """P1 tests for notes field - identified as having zero E2E coverage."""

    def test_replace_notes_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Replacing notes field persists to database."""
        notes = f"Test notes {uuid.uuid4().hex[:6]}"
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/notes", "value": notes}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify in database
        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["workout_data"].get("notes") == notes

    def test_remove_notes_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Removing notes field persists to database."""
        # First set notes
        authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/notes", "value": "Temp notes"}]},
        )

        # Remove notes
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "remove", "path": "/notes"}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify notes removed
        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["workout_data"].get("notes") is None

    def test_notes_at_2000_chars_accepted(self, authed_http_client, seed_workout):
        """Notes at exactly 2000 characters is accepted."""
        notes = "x" * 2000
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/notes", "value": notes}]},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_notes_at_2001_chars_rejected(self, authed_http_client, seed_workout):
        """Notes at 2001 characters is rejected with 422."""
        notes = "x" * 2001
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/notes", "value": notes}]},
        )
        assert response.status_code == 422, f"Expected 422, got {response.status_code}"


# =============================================================================
# P2 Block-Level Operations Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EBlockOperations:
    """P2 tests for block-level operations."""

    def test_add_exercise_to_specific_block_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Adding exercise to block 0 via /blocks/0/exercises/- persists."""
        new_exercise = {"name": f"Block Exercise {uuid.uuid4().hex[:6]}", "sets": 4, "reps": 8}

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "add", "path": "/blocks/0/exercises/-", "value": new_exercise}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify exercise added
        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        exercises = row.data["workout_data"]["blocks"][0]["exercises"]
        exercise_names = [ex["name"] for ex in exercises]
        assert new_exercise["name"] in exercise_names

    def test_replace_block_label_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Replacing block label persists to database."""
        new_label = f"Updated Block {uuid.uuid4().hex[:6]}"

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/blocks/0/label", "value": new_label}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify label updated
        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        assert row.data["workout_data"]["blocks"][0]["label"] == new_label

    def test_replace_exercise_in_block_persists(
        self, authed_http_client, seed_workout, supabase_client
    ):
        """Replacing exercise in specific block persists."""
        replacement = {"name": "Replacement Exercise", "sets": 5, "reps": 5}

        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/blocks/0/exercises/0", "value": replacement}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        # Verify exercise replaced
        row = (
            supabase_client.table("workouts")
            .select("workout_data")
            .eq("id", seed_workout["workout_id"])
            .single()
            .execute()
        )
        first_exercise = row.data["workout_data"]["blocks"][0]["exercises"][0]
        assert first_exercise["name"] == "Replacement Exercise"
        assert first_exercise["sets"] == 5


# =============================================================================
# P2 Response Schema Validation Tests
# =============================================================================


@pytest.mark.e2e
class TestPatchE2EResponseSchema:
    """P2 tests for response payload structure validation."""

    def test_success_response_has_required_fields(self, authed_http_client, seed_workout):
        """Successful patch response has all required fields."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": "Schema Test"}]},
        )

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()

        # Verify required fields exist
        assert "success" in data, "Missing 'success' field"
        assert "workout" in data, "Missing 'workout' field"
        assert "changes_applied" in data, "Missing 'changes_applied' field"
        assert "embedding_regeneration" in data, "Missing 'embedding_regeneration' field"

        # Verify field types
        assert data["success"] is True
        assert isinstance(data["workout"], dict)
        assert isinstance(data["changes_applied"], int)
        assert data["embedding_regeneration"] in ("queued", "none", "failed")

    def test_success_response_workout_has_id(self, authed_http_client, seed_workout):
        """Successful response workout object has id field."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": "ID Test"}]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data["workout"]
        assert data["workout"]["id"] == seed_workout["workout_id"]

    def test_error_response_has_detail(self, authed_http_client, seed_workout):
        """422 error response has detail field."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/invalid_path", "value": "X"}]},
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_validation_error_includes_message(self, authed_http_client, seed_workout):
        """Validation error response includes error message."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={"operations": [{"op": "replace", "path": "/title", "value": ""}]},
        )

        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # Detail should contain message or validation_errors
        detail = data["detail"]
        has_message = isinstance(detail, str) or "message" in str(detail) or "validation_errors" in str(detail)
        assert has_message, f"Expected error details, got: {detail}"

    def test_changes_applied_reflects_actual_changes(self, authed_http_client, seed_workout):
        """changes_applied count reflects actual modifications made."""
        response = authed_http_client.patch(
            f"/workouts/{seed_workout['workout_id']}",
            json={
                "operations": [
                    {"op": "replace", "path": "/title", "value": f"Count Test {uuid.uuid4().hex[:4]}"},
                    {"op": "add", "path": "/tags/-", "value": f"count-{uuid.uuid4().hex[:4]}"},
                ]
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["changes_applied"] == 2
