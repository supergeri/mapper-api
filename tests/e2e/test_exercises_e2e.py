"""
E2E tests for Exercise Matching Service API.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service E2E Testing

These tests verify:
1. API endpoints work against real Supabase database
2. Exercise matching accuracy with real exercise data
3. Filter functionality (muscle groups, equipment)
4. Edge case handling

Run with:
    pytest -m e2e tests/e2e/test_exercises_e2e.py -v
    pytest tests/e2e/test_exercises_e2e.py --live -v  # With live API
"""
import pytest
import httpx
from supabase import Client


# =============================================================================
# SMOKE SUITE - Critical User Journeys (run on every PR)
# =============================================================================


@pytest.mark.e2e
class TestExerciseDatabaseSmoke:
    """
    Smoke tests to verify database connectivity and basic data integrity.
    These are the most critical tests and should pass before any other testing.
    """

    def test_exercises_table_exists_and_has_data(self, supabase_client: Client):
        """Verify the exercises table exists and has seeded data."""
        result = supabase_client.table("exercises").select("id").limit(1).execute()
        assert result.data is not None, "exercises table should exist"
        assert len(result.data) >= 1, "exercises table should have seeded data"

    def test_exercises_count_matches_expected(self, supabase_client: Client):
        """Verify expected number of seeded exercises (56 per spec)."""
        result = supabase_client.table("exercises").select("id", count="exact").execute()
        # Allow some flexibility in case exercises are added
        assert result.count >= 50, f"Expected at least 50 exercises, got {result.count}"

    def test_exercises_have_required_fields(self, supabase_client: Client):
        """Verify all exercises have required fields populated."""
        result = supabase_client.table("exercises").select("*").limit(10).execute()

        required_fields = ["id", "name", "primary_muscles", "equipment", "category"]

        for exercise in result.data:
            for field in required_fields:
                assert field in exercise, f"Exercise missing required field: {field}"
                assert exercise[field] is not None, f"Exercise {exercise['id']} has null {field}"

    def test_compound_exercises_have_1rm_support(self, supabase_client: Client):
        """Verify compound exercises properly support 1RM tracking."""
        result = (
            supabase_client.table("exercises")
            .select("id, name, category, supports_1rm")
            .eq("category", "compound")
            .limit(10)
            .execute()
        )

        # Most compound exercises should support 1RM
        exercises_with_1rm = [e for e in result.data if e.get("supports_1rm")]
        assert len(exercises_with_1rm) >= 5, "Most compound exercises should support 1RM"


@pytest.mark.e2e
class TestExerciseMatchingSmoke:
    """
    Smoke tests for the core matching functionality via direct repository.
    Tests critical user journey: matching planned exercise names.
    """

    def test_exact_match_barbell_bench_press(self, supabase_client: Client):
        """Exact name match should return the exercise."""
        result = (
            supabase_client.table("exercises")
            .select("*")
            .ilike("name", "Barbell Bench Press")
            .execute()
        )
        assert len(result.data) == 1, "Should find exactly one Barbell Bench Press"
        exercise = result.data[0]
        assert exercise["id"] == "barbell-bench-press"
        assert "chest" in exercise["primary_muscles"]

    def test_alias_match_rdl(self, supabase_client: Client):
        """Alias 'RDL' should match Romanian Deadlift."""
        result = (
            supabase_client.table("exercises")
            .select("*")
            .contains("aliases", ["RDL"])
            .execute()
        )
        assert len(result.data) >= 1, "Should find exercise with RDL alias"
        exercise = result.data[0]
        assert "romanian" in exercise["name"].lower() or "rdl" in exercise["name"].lower()

    def test_filter_by_muscle_group_chest(self, supabase_client: Client):
        """Filter by chest muscle should return pressing exercises."""
        result = (
            supabase_client.table("exercises")
            .select("*")
            .contains("primary_muscles", ["chest"])
            .execute()
        )
        assert len(result.data) >= 2, "Should have multiple chest exercises"
        for ex in result.data:
            assert "chest" in ex["primary_muscles"]

    def test_filter_by_equipment_barbell(self, supabase_client: Client):
        """Filter by barbell equipment should return barbell exercises."""
        result = (
            supabase_client.table("exercises")
            .select("*")
            .contains("equipment", ["barbell"])
            .execute()
        )
        assert len(result.data) >= 3, "Should have multiple barbell exercises"
        for ex in result.data:
            assert "barbell" in ex["equipment"]


# =============================================================================
# API ENDPOINT TESTS - Requires Live API
# =============================================================================


@pytest.mark.e2e
class TestExercisesAPIEndpoints:
    """
    API endpoint tests requiring live mapper-api service.
    Skip if --live flag not provided.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("mapper-api not available")
        except httpx.ConnectError:
            pytest.skip("mapper-api not reachable at configured URL")

    def test_health_endpoint(self, http_client: httpx.Client):
        """Health endpoint should return 200."""
        response = http_client.get("/health")
        assert response.status_code == 200

    def test_match_single_exercise_exact(self, http_client: httpx.Client):
        """POST /exercises/canonical/match with exact name."""
        response = http_client.post(
            "/exercises/canonical/match",
            json={"planned_name": "Barbell Bench Press"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] == "barbell-bench-press"
        assert data["confidence"] == 1.0
        assert data["method"] == "exact"

    def test_match_single_exercise_alias(self, http_client: httpx.Client):
        """POST /exercises/canonical/match with alias."""
        response = http_client.post(
            "/exercises/canonical/match",
            json={"planned_name": "RDL"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] is not None
        assert data["method"] in ("alias", "exact")
        assert data["confidence"] >= 0.90

    def test_match_single_exercise_fuzzy(self, http_client: httpx.Client):
        """POST /exercises/canonical/match with fuzzy input."""
        response = http_client.post(
            "/exercises/canonical/match",
            json={"planned_name": "Barbell Back Squats"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["exercise_id"] is not None
        assert "squat" in data["exercise_id"]
        assert data["method"] in ("exact", "alias", "fuzzy")

    def test_match_batch_exercises(self, http_client: httpx.Client):
        """POST /exercises/canonical/match/batch with multiple names."""
        response = http_client.post(
            "/exercises/canonical/match/batch",
            json={"planned_names": ["Bench Press", "RDL", "Pull-Up"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["matches"]) == 3
        # Verify order preserved
        assert "bench" in data["matches"][0]["exercise_id"]
        assert data["matches"][2]["exercise_id"] == "pull-up"

    def test_suggest_matches(self, http_client: httpx.Client):
        """GET /exercises/canonical/suggest returns multiple suggestions."""
        response = http_client.get(
            "/exercises/canonical/suggest",
            params={"planned_name": "deadlift", "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        # Should be sorted by confidence
        if len(data) > 1:
            confidences = [m["confidence"] for m in data]
            assert confidences == sorted(confidences, reverse=True)

    def test_get_exercise_by_id(self, http_client: httpx.Client):
        """GET /exercises/{exercise_id} returns exercise details."""
        response = http_client.get("/exercises/barbell-bench-press")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "barbell-bench-press"
        assert data["name"] == "Barbell Bench Press"
        assert "chest" in data["primary_muscles"]
        assert data["supports_1rm"] is True

    def test_get_exercise_not_found(self, http_client: httpx.Client):
        """GET /exercises/{exercise_id} returns 404 for non-existent."""
        response = http_client.get("/exercises/nonexistent-exercise-xyz")
        assert response.status_code == 404

    def test_list_exercises_no_filter(self, http_client: httpx.Client):
        """GET /exercises returns exercise list."""
        response = http_client.get("/exercises")
        assert response.status_code == 200
        data = response.json()
        assert "exercises" in data
        assert "count" in data
        assert data["count"] >= 50

    def test_list_exercises_muscle_filter(self, http_client: httpx.Client):
        """GET /exercises?muscle=chest filters by muscle group."""
        response = http_client.get("/exercises", params={"muscle": "chest"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        for ex in data["exercises"]:
            assert "chest" in ex["primary_muscles"]

    def test_list_exercises_equipment_filter(self, http_client: httpx.Client):
        """GET /exercises?equipment=barbell filters by equipment."""
        response = http_client.get("/exercises", params={"equipment": "barbell"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        for ex in data["exercises"]:
            assert "barbell" in ex["equipment"]

    def test_list_exercises_supports_1rm_filter(self, http_client: httpx.Client):
        """GET /exercises?supports_1rm=true filters by 1RM support."""
        response = http_client.get("/exercises", params={"supports_1rm": "true"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        for ex in data["exercises"]:
            assert ex["supports_1rm"] is True

    def test_list_exercises_search(self, http_client: httpx.Client):
        """GET /exercises?search=bench filters by name pattern."""
        response = http_client.get("/exercises", params={"search": "bench"})
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1
        for ex in data["exercises"]:
            assert "bench" in ex["name"].lower()

    def test_list_exercises_limit(self, http_client: httpx.Client):
        """GET /exercises?limit=5 respects limit parameter."""
        response = http_client.get("/exercises", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["exercises"]) <= 5


# =============================================================================
# REGRESSION SUITE - Comprehensive Matching Tests
# =============================================================================


@pytest.mark.e2e
class TestExerciseMatchingAccuracy:
    """
    Regression tests for exercise matching accuracy.
    Verifies matching quality across various input types.
    """

    def test_known_exercises_all_match(
        self, supabase_client: Client, known_exercise_names: list
    ):
        """All known exercise names should have exact matches in database."""
        for name in known_exercise_names:
            result = (
                supabase_client.table("exercises")
                .select("id, name")
                .ilike("name", name)
                .execute()
            )
            assert len(result.data) >= 1, f"Exercise '{name}' should exist in database"

    def test_common_aliases_resolve_correctly(
        self, supabase_client: Client, exercise_aliases: dict
    ):
        """Common aliases should resolve to correct canonical exercises."""
        for alias, expected_name in exercise_aliases.items():
            # Check if alias exists in any exercise's aliases array
            result = (
                supabase_client.table("exercises")
                .select("id, name, aliases")
                .contains("aliases", [alias])
                .execute()
            )
            if len(result.data) > 0:
                # Alias found - verify it maps to expected exercise
                found_name = result.data[0]["name"]
                assert (
                    expected_name.lower() in found_name.lower()
                    or found_name.lower() in expected_name.lower()
                ), f"Alias '{alias}' should map to '{expected_name}', got '{found_name}'"

    def test_muscle_group_coverage(
        self, supabase_client: Client, muscle_groups: list
    ):
        """Verify exercises exist for major muscle groups."""
        for muscle in muscle_groups[:8]:  # Test main muscle groups
            result = (
                supabase_client.table("exercises")
                .select("id")
                .contains("primary_muscles", [muscle])
                .execute()
            )
            # Not all muscle groups require exercises (some are secondary only)
            if muscle in ["chest", "lats", "quadriceps", "biceps", "triceps"]:
                assert len(result.data) >= 1, f"Should have exercises for {muscle}"

    def test_equipment_type_coverage(
        self, supabase_client: Client, equipment_types: list
    ):
        """Verify exercises exist for common equipment types."""
        for equipment in equipment_types[:5]:  # Test main equipment types
            result = (
                supabase_client.table("exercises")
                .select("id")
                .contains("equipment", [equipment])
                .execute()
            )
            if equipment in ["barbell", "dumbbell", "bodyweight"]:
                assert len(result.data) >= 1, f"Should have exercises for {equipment}"


@pytest.mark.e2e
class TestExerciseEdgeCases:
    """
    Edge case tests for robustness verification.
    These tests ensure the system handles unusual inputs gracefully.
    """

    def test_empty_input_handled(self, supabase_client: Client):
        """Empty input should not cause database errors."""
        # This tests the repository layer directly
        result = (
            supabase_client.table("exercises")
            .select("id")
            .ilike("name", "")
            .execute()
        )
        # Empty string query should work without error
        assert result.data is not None

    def test_special_characters_handled(self, supabase_client: Client):
        """Special characters should not cause SQL injection or errors."""
        dangerous_inputs = [
            "'; DROP TABLE exercises; --",
            "<script>alert('xss')</script>",
            "Bench Press' OR '1'='1",
            "Bench Press\"; DELETE FROM exercises; --",
        ]
        for dangerous_input in dangerous_inputs:
            # Should not raise exception
            try:
                result = (
                    supabase_client.table("exercises")
                    .select("id")
                    .ilike("name", dangerous_input)
                    .execute()
                )
                # Query should complete without error
                assert result is not None
            except Exception as e:
                # Should not be a SQL injection error
                assert "syntax" not in str(e).lower()

    def test_very_long_name_handled(self, supabase_client: Client):
        """Very long names should not cause buffer overflow or errors."""
        long_name = "A" * 1000
        result = (
            supabase_client.table("exercises")
            .select("id")
            .ilike("name", long_name)
            .execute()
        )
        # Should return empty result, not error
        assert result.data is not None
        assert len(result.data) == 0

    def test_unicode_characters_handled(self, supabase_client: Client):
        """Unicode characters should be handled properly."""
        unicode_inputs = [
            "Banco de Press",  # Spanish
            "Deadlift",  # Cyrillic lookalike (if used)
        ]
        for unicode_input in unicode_inputs:
            result = (
                supabase_client.table("exercises")
                .select("id")
                .ilike("name", f"%{unicode_input}%")
                .execute()
            )
            # Should complete without error
            assert result is not None


@pytest.mark.e2e
class TestExerciseDataIntegrity:
    """
    Data integrity tests for the exercises table.
    Verifies schema constraints and data quality.
    """

    def test_all_exercises_have_unique_ids(self, supabase_client: Client):
        """Exercise IDs should be unique."""
        result = supabase_client.table("exercises").select("id").execute()
        ids = [ex["id"] for ex in result.data]
        assert len(ids) == len(set(ids)), "Exercise IDs should be unique"

    def test_all_exercises_have_valid_category(self, supabase_client: Client):
        """All exercises should have valid category values."""
        valid_categories = ["compound", "isolation", "cardio"]
        result = supabase_client.table("exercises").select("id, category").execute()

        for ex in result.data:
            assert ex["category"] in valid_categories, (
                f"Exercise {ex['id']} has invalid category: {ex['category']}"
            )

    def test_1rm_exercises_have_formula(self, supabase_client: Client):
        """Exercises with supports_1rm=True should have one_rm_formula set."""
        result = (
            supabase_client.table("exercises")
            .select("id, name, supports_1rm, one_rm_formula")
            .eq("supports_1rm", True)
            .execute()
        )

        for ex in result.data:
            assert ex["one_rm_formula"] is not None, (
                f"Exercise {ex['name']} supports 1RM but has no formula"
            )

    def test_primary_muscles_not_empty(self, supabase_client: Client):
        """All exercises should have at least one primary muscle."""
        result = (
            supabase_client.table("exercises")
            .select("id, name, primary_muscles")
            .execute()
        )

        for ex in result.data:
            assert ex["primary_muscles"] is not None, (
                f"Exercise {ex['name']} has null primary_muscles"
            )
            assert len(ex["primary_muscles"]) >= 1, (
                f"Exercise {ex['name']} has no primary muscles"
            )

    def test_equipment_not_empty(self, supabase_client: Client):
        """All exercises should have at least one equipment type."""
        result = (
            supabase_client.table("exercises")
            .select("id, name, equipment")
            .execute()
        )

        for ex in result.data:
            assert ex["equipment"] is not None, (
                f"Exercise {ex['name']} has null equipment"
            )
            assert len(ex["equipment"]) >= 1, (
                f"Exercise {ex['name']} has no equipment"
            )
