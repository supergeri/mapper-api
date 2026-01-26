"""
E2E tests for Exercise Selection and Fallback Behavior.

Part of AMA-472: Exercise Database Integration for Program Generation

These tests verify:
1. Exercise selection with limited equipment works correctly
2. Fallback mechanism creates usable programs
3. Similar exercise lookup returns valid alternatives
4. Equipment constraints are respected in production

Run with:
    pytest -m e2e tests/e2e/test_exercise_selection.py -v
    pytest tests/e2e/test_exercise_selection.py --live -v  # With live API
"""

from typing import Dict, List

import pytest
from supabase import Client

from infrastructure.db.exercise_repository import SupabaseExerciseRepository


# =============================================================================
# EXERCISE DATABASE SMOKE TESTS
# =============================================================================


@pytest.mark.e2e
class TestExerciseDatabaseSmoke:
    """
    Smoke tests to verify exercise database connectivity and data.
    """

    def test_exercises_table_exists(self, supabase_client: Client):
        """Verify the exercises table exists and is accessible."""
        result = supabase_client.table("exercises").select("id").limit(1).execute()
        assert result.data is not None, "exercises table should be accessible"

    def test_exercises_table_has_data(self, supabase_client: Client):
        """Verify the exercises table has seeded data."""
        result = supabase_client.table("exercises").select("id").limit(10).execute()
        assert len(result.data) > 0, "exercises table should have data"

    def test_exercises_have_required_fields(self, supabase_client: Client):
        """Verify exercises have all required fields for selection."""
        result = (
            supabase_client.table("exercises")
            .select("id, name, primary_muscles, equipment, movement_pattern, category")
            .limit(5)
            .execute()
        )

        for ex in result.data:
            assert ex.get("id"), "Exercise should have id"
            assert ex.get("name"), "Exercise should have name"
            assert ex.get("primary_muscles") is not None, "Exercise should have primary_muscles"
            assert ex.get("equipment") is not None, "Exercise should have equipment"


# =============================================================================
# EXERCISE REPOSITORY TESTS
# =============================================================================


@pytest.mark.e2e
class TestExerciseRepositoryE2E:
    """
    E2E tests for ExerciseRepository methods against live database.
    """

    @pytest.fixture
    def exercise_repo(self, supabase_client: Client) -> SupabaseExerciseRepository:
        """Create exercise repository with real Supabase client."""
        return SupabaseExerciseRepository(supabase_client)

    def test_get_similar_exercises_returns_alternatives(
        self,
        exercise_repo: SupabaseExerciseRepository,
        supabase_client: Client,
    ):
        """get_similar_exercises returns valid alternatives from live DB."""
        # Get a known exercise ID
        result = (
            supabase_client.table("exercises")
            .select("id, movement_pattern")
            .not_.is_("movement_pattern", "null")
            .limit(1)
            .execute()
        )

        if not result.data:
            pytest.skip("No exercises with movement_pattern in database")

        source_id = result.data[0]["id"]
        source_pattern = result.data[0]["movement_pattern"]

        # Get similar exercises
        similar = exercise_repo.get_similar_exercises(source_id, limit=5)

        # Verify results
        assert isinstance(similar, list)
        for ex in similar:
            assert ex["id"] != source_id, "Should not include source exercise"
            assert ex.get("movement_pattern") == source_pattern, "Should have same pattern"

    def test_get_similar_exercises_handles_unknown_id(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """get_similar_exercises returns empty for unknown exercise."""
        similar = exercise_repo.get_similar_exercises("nonexistent-id-12345")
        assert similar == []

    def test_validate_exercise_name_finds_exercise(
        self,
        exercise_repo: SupabaseExerciseRepository,
        supabase_client: Client,
    ):
        """validate_exercise_name finds exercise by name."""
        # Get a known exercise name
        result = (
            supabase_client.table("exercises")
            .select("id, name")
            .limit(1)
            .execute()
        )

        if not result.data:
            pytest.skip("No exercises in database")

        name = result.data[0]["name"]
        expected_id = result.data[0]["id"]

        # Validate by name
        found = exercise_repo.validate_exercise_name(name)

        assert found is not None
        assert found["id"] == expected_id

    def test_validate_exercise_name_case_insensitive(
        self,
        exercise_repo: SupabaseExerciseRepository,
        supabase_client: Client,
    ):
        """validate_exercise_name is case-insensitive."""
        result = (
            supabase_client.table("exercises")
            .select("id, name")
            .limit(1)
            .execute()
        )

        if not result.data:
            pytest.skip("No exercises in database")

        name = result.data[0]["name"]
        expected_id = result.data[0]["id"]

        # Try different case variations
        found_upper = exercise_repo.validate_exercise_name(name.upper())
        found_lower = exercise_repo.validate_exercise_name(name.lower())

        assert found_upper is not None or found_lower is not None
        if found_upper:
            assert found_upper["id"] == expected_id
        if found_lower:
            assert found_lower["id"] == expected_id

    def test_validate_exercise_name_returns_none_for_unknown(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """validate_exercise_name returns None for unknown name."""
        found = exercise_repo.validate_exercise_name("Completely Fake Exercise Name XYZ123")
        assert found is None

    def test_validate_exercise_name_handles_empty_input(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """validate_exercise_name handles empty/whitespace input."""
        assert exercise_repo.validate_exercise_name("") is None
        assert exercise_repo.validate_exercise_name("   ") is None

    def test_search_by_equipment_returns_matching(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """Search by equipment returns exercises with that equipment."""
        results = exercise_repo.get_by_equipment(["barbell"], limit=10)

        # Should return results (assuming barbell exercises exist)
        # Each result should include barbell in equipment
        for ex in results:
            equipment = ex.get("equipment", [])
            # Allow bodyweight exercises (empty equipment) or barbell
            if equipment:
                assert "barbell" in equipment


# =============================================================================
# EQUIPMENT MAPPING CONSISTENCY TESTS
# =============================================================================


@pytest.mark.e2e
class TestEquipmentMappingConsistency:
    """
    Tests to verify equipment names in database align with EQUIPMENT_MAPPING.
    """

    def test_database_equipment_is_recognized(self, supabase_client: Client):
        """Equipment in database should be recognized by the selector."""
        from services.exercise_selector import EQUIPMENT_MAPPING, EQUIPMENT_ALIASES

        # Get all unique equipment from database
        result = supabase_client.table("exercises").select("equipment").execute()

        all_equipment = set()
        for ex in result.data:
            equipment_list = ex.get("equipment") or []
            all_equipment.update(equipment_list)

        # Build set of known equipment
        known_equipment = set()
        for preset_equipment in EQUIPMENT_MAPPING.values():
            known_equipment.update(preset_equipment)
        known_equipment.update(EQUIPMENT_ALIASES.keys())
        known_equipment.update(EQUIPMENT_ALIASES.values())

        # Common equipment that should always be recognized
        common_equipment = {"barbell", "dumbbells", "cables", "bench", "bodyweight"}

        # Check that common equipment is recognized
        for equip in common_equipment:
            if equip in all_equipment:
                assert equip in known_equipment or equip.lower() in known_equipment, (
                    f"Common equipment '{equip}' should be recognized"
                )


# =============================================================================
# GENERATION WITH FALLBACK TESTS (Requires Live API)
# =============================================================================


@pytest.mark.e2e
class TestGenerationWithFallback:
    """
    Tests for program generation using the fallback exercise selection.
    These verify the complete flow works when LLM is unavailable.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except Exception:
            pytest.skip("program-api not reachable")

    @pytest.mark.timeout(120)
    def test_generate_with_limited_equipment(
        self,
        http_client,
        auth_headers: Dict[str, str],
        cleanup_program,
    ):
        """
        Generate program with limited equipment.
        Verifies fallback creates usable exercises.
        """
        request_data = {
            "goal": "general_fitness",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": ["dumbbells", "bench"],  # Limited equipment
        }

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Generation failed: {response.text}"

        result = response.json()
        program = result.get("program")

        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        assert program is not None
        assert len(program.get("weeks", [])) == 4

        # Verify workouts have exercises
        for week in program["weeks"]:
            for workout in week.get("workouts", []):
                exercises = workout.get("exercises", [])
                assert len(exercises) > 0, "Workout should have exercises"

    @pytest.mark.timeout(120)
    def test_generate_bodyweight_only(
        self,
        http_client,
        auth_headers: Dict[str, str],
        cleanup_program,
    ):
        """
        Generate program with bodyweight only.
        Most constrained equipment scenario.
        """
        request_data = {
            "goal": "general_fitness",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "beginner",
            "equipment_available": ["bodyweight"],
        }

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Generation failed: {response.text}"

        result = response.json()
        program = result.get("program")

        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        assert program is not None

        # Count total exercises
        total_exercises = 0
        for week in program.get("weeks", []):
            for workout in week.get("workouts", []):
                total_exercises += len(workout.get("exercises", []))

        assert total_exercises > 0, "Program should have exercises"

    @pytest.mark.timeout(120)
    def test_generate_with_full_gym_equipment(
        self,
        http_client,
        auth_headers: Dict[str, str],
        cleanup_program,
    ):
        """
        Generate program with full gym equipment.
        Should have most variety in exercise selection.
        """
        request_data = {
            "goal": "strength",
            "duration_weeks": 4,
            "sessions_per_week": 4,
            "experience_level": "intermediate",
            "equipment_available": [
                "barbell", "dumbbells", "cables", "machines",
                "bench", "squat_rack", "pull_up_bar"
            ],
        }

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Generation failed: {response.text}"

        result = response.json()
        program = result.get("program")

        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        assert program is not None
        assert program["goal"] == "strength"

        # Should have unique exercises (not all placeholders)
        exercise_names = set()
        for week in program.get("weeks", []):
            for workout in week.get("workouts", []):
                for ex in workout.get("exercises", []):
                    exercise_names.add(ex.get("exercise_name", ""))

        # Should have variety
        assert len(exercise_names) >= 3, "Should have variety in exercise selection"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


@pytest.mark.e2e
class TestExerciseSelectionErrorHandling:
    """
    Tests for error handling in exercise selection.
    """

    @pytest.fixture
    def exercise_repo(self, supabase_client: Client) -> SupabaseExerciseRepository:
        """Create exercise repository with real Supabase client."""
        return SupabaseExerciseRepository(supabase_client)

    def test_get_similar_exercises_graceful_on_db_error(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """get_similar_exercises returns empty list on errors, not exception."""
        # Pass invalid ID - should return empty, not raise
        result = exercise_repo.get_similar_exercises("invalid-uuid-format")
        assert result == []

    def test_validate_exercise_name_graceful_on_special_chars(
        self,
        exercise_repo: SupabaseExerciseRepository,
    ):
        """validate_exercise_name handles special characters gracefully."""
        # These should return None, not raise exceptions
        assert exercise_repo.validate_exercise_name("'; DROP TABLE exercises; --") is None
        assert exercise_repo.validate_exercise_name("<script>alert('xss')</script>") is None
        assert exercise_repo.validate_exercise_name("exercise\x00name") is None
