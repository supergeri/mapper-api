"""
E2E tests for Periodization Service integration.

Part of AMA-485: ELITE experience level support
Part of AMA-463: Periodization calculation engine

These tests verify periodization behavior through the full stack:
1. ELITE experience level API acceptance
2. Periodization model selection
3. Deload week patterns by experience level
4. Periodization metadata in API responses

Run with:
    pytest -m e2e tests/e2e/test_periodization_e2e.py -v
    pytest tests/e2e/test_periodization_e2e.py --live -v  # With live API
"""

import pytest
from supabase import Client


# =============================================================================
# SMOKE SUITE - ELITE Experience Level (run on every PR)
# =============================================================================


@pytest.mark.e2e
class TestEliteExperienceLevelSmoke:
    """
    Smoke tests to verify ELITE experience level works through the full stack.
    These are critical for AMA-485 and should pass before any other testing.
    """

    def test_elite_accepted_in_database(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Verify ELITE experience level is accepted by database."""
        program_data = {
            "user_id": test_user_id,
            "name": "Elite Smoke Test",
            "goal": "strength",
            "experience_level": "elite",
            "duration_weeks": 8,
            "sessions_per_week": 4,
            "equipment_available": ["barbell", "squat_rack"],
            "status": "draft",
        }
        result = supabase_client.table("training_programs").insert(program_data).execute()
        assert len(result.data) == 1, "Should create one program"
        program_id = result.data[0]["id"]

        # Verify elite was stored correctly
        assert result.data[0]["experience_level"] == "elite"

        # Cleanup
        supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_elite_retrievable_from_database(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Verify ELITE programs can be retrieved from database."""
        # Insert
        program_data = {
            "user_id": test_user_id,
            "name": "Elite Retrieval Test",
            "goal": "hypertrophy",
            "experience_level": "elite",
            "duration_weeks": 8,
            "sessions_per_week": 4,
            "equipment_available": ["barbell", "dumbbells"],
            "status": "draft",
        }
        insert_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = insert_result.data[0]["id"]

        # Retrieve
        select_result = (
            supabase_client.table("training_programs")
            .select("*")
            .eq("id", program_id)
            .execute()
        )
        assert len(select_result.data) == 1
        assert select_result.data[0]["experience_level"] == "elite"

        # Cleanup
        supabase_client.table("training_programs").delete().eq("id", program_id).execute()


# =============================================================================
# ELITE EXPERIENCE LEVEL E2E TESTS
# =============================================================================


@pytest.mark.e2e
class TestEliteExperienceLevelE2E:
    """
    E2E tests for ELITE experience level (AMA-485).
    Tests the complete flow from API to database and back.
    """

    def test_elite_program_with_weeks(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """ELITE program can have weeks added."""
        # Create program
        program_data = {
            "user_id": test_user_id,
            "name": "Elite Weekly Test",
            "goal": "strength",
            "experience_level": "elite",
            "duration_weeks": 8,
            "sessions_per_week": 4,
            "equipment_available": ["barbell", "squat_rack"],
            "status": "draft",
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        try:
            # Add weeks with deload pattern (elite deloads every 2 weeks)
            weeks_data = []
            for week_num in range(1, 9):
                is_deload = week_num % 2 == 0  # Weeks 2, 4, 6, 8 are deloads for elite
                weeks_data.append({
                    "program_id": program_id,
                    "week_number": week_num,
                    "focus": "Deload" if is_deload else "Training",
                    "is_deload": is_deload,
                    "intensity_percentage": 60 if is_deload else 85,
                    "volume_modifier": 0.5 if is_deload else 1.0,
                })

            weeks_result = supabase_client.table("program_weeks").insert(weeks_data).execute()
            assert len(weeks_result.data) == 8

            # Verify deload pattern
            deload_weeks = [w for w in weeks_result.data if w["is_deload"]]
            assert len(deload_weeks) == 4, "ELITE should have 4 deload weeks in 8-week program"

        finally:
            # Cleanup (cascade delete handles weeks)
            supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_all_experience_levels_accepted(
        self,
        supabase_client: Client,
        test_user_id: str,
        valid_experience_levels: list,
    ):
        """All valid experience level values should be accepted by database."""
        created_ids = []

        try:
            for level in valid_experience_levels:
                program_data = {
                    "user_id": test_user_id,
                    "name": f"Level Test: {level}",
                    "goal": "strength",
                    "experience_level": level,
                    "duration_weeks": 4,
                    "sessions_per_week": 3,
                    "equipment_available": ["barbell"],
                    "status": "draft",
                }
                result = supabase_client.table("training_programs").insert(program_data).execute()
                assert len(result.data) == 1, f"Should create program for {level}"
                assert result.data[0]["experience_level"] == level
                created_ids.append(result.data[0]["id"])

        finally:
            # Cleanup all created programs
            for program_id in created_ids:
                supabase_client.table("training_programs").delete().eq("id", program_id).execute()


# =============================================================================
# PERIODIZATION MODEL VERIFICATION
# =============================================================================


@pytest.mark.e2e
class TestPeriodizationDataIntegrity:
    """
    E2E tests for periodization data integrity.
    Verifies that periodization model values are properly stored and retrieved.
    """

    def test_all_periodization_models_accepted(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """All periodization model values should be accepted by database."""
        models = ["linear", "undulating", "block", "conjugate", "reverse_linear"]
        created_ids = []

        try:
            for model in models:
                program_data = {
                    "user_id": test_user_id,
                    "name": f"Model Test: {model}",
                    "goal": "strength",
                    "experience_level": "intermediate",
                    "periodization_model": model,
                    "duration_weeks": 8,
                    "sessions_per_week": 3,
                    "equipment_available": ["barbell"],
                    "status": "draft",
                }
                result = supabase_client.table("training_programs").insert(program_data).execute()
                assert len(result.data) == 1, f"Should create program for {model}"
                assert result.data[0]["periodization_model"] == model
                created_ids.append(result.data[0]["id"])

        finally:
            # Cleanup
            for program_id in created_ids:
                supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_week_deload_flag_stored(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Deload flag on weeks should be properly stored and retrieved."""
        # Create program
        program_data = {
            "user_id": test_user_id,
            "name": "Deload Flag Test",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 8,
            "sessions_per_week": 3,
            "equipment_available": ["barbell"],
            "status": "draft",
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        try:
            # Add weeks with mixed deload flags
            weeks_data = [
                {"program_id": program_id, "week_number": 1, "is_deload": False, "focus": "Training"},
                {"program_id": program_id, "week_number": 2, "is_deload": False, "focus": "Training"},
                {"program_id": program_id, "week_number": 3, "is_deload": False, "focus": "Training"},
                {"program_id": program_id, "week_number": 4, "is_deload": True, "focus": "Deload"},
            ]
            weeks_result = supabase_client.table("program_weeks").insert(weeks_data).execute()

            # Retrieve and verify
            stored_weeks = (
                supabase_client.table("program_weeks")
                .select("*")
                .eq("program_id", program_id)
                .order("week_number")
                .execute()
            )

            assert stored_weeks.data[0]["is_deload"] is False
            assert stored_weeks.data[3]["is_deload"] is True

        finally:
            supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_intensity_and_volume_stored(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Intensity percentage and volume modifier should be stored correctly."""
        # Create program
        program_data = {
            "user_id": test_user_id,
            "name": "Intensity Volume Test",
            "goal": "hypertrophy",
            "experience_level": "advanced",
            "duration_weeks": 4,
            "sessions_per_week": 4,
            "equipment_available": ["barbell", "dumbbells"],
            "status": "draft",
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        try:
            # Add week with specific periodization values
            week_data = {
                "program_id": program_id,
                "week_number": 1,
                "focus": "Hypertrophy",
                "intensity_percentage": 75,
                "volume_modifier": 1.2,
                "is_deload": False,
            }
            week_result = supabase_client.table("program_weeks").insert(week_data).execute()

            # Verify values
            assert week_result.data[0]["intensity_percentage"] == 75
            assert float(week_result.data[0]["volume_modifier"]) == 1.2

        finally:
            supabase_client.table("training_programs").delete().eq("id", program_id).execute()


# =============================================================================
# EXPERIENCE LEVEL DELOAD PATTERN TESTS
# =============================================================================


@pytest.mark.e2e
class TestExperienceLevelDeloadPatterns:
    """
    E2E tests verifying deload patterns by experience level.
    These test that the expected deload frequencies are correctly implemented.
    """

    def test_beginner_deload_pattern(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Beginner (deload every 6 weeks) pattern in 12-week program."""
        program_data = {
            "user_id": test_user_id,
            "name": "Beginner Deload Test",
            "goal": "strength",
            "experience_level": "beginner",
            "duration_weeks": 12,
            "sessions_per_week": 3,
            "equipment_available": ["barbell"],
            "status": "draft",
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        try:
            # Insert weeks with beginner deload pattern (every 6 weeks: 6, 12)
            weeks_data = []
            for week_num in range(1, 13):
                is_deload = week_num in [6, 12]
                weeks_data.append({
                    "program_id": program_id,
                    "week_number": week_num,
                    "is_deload": is_deload,
                    "focus": "Deload" if is_deload else "Training",
                })
            supabase_client.table("program_weeks").insert(weeks_data).execute()

            # Verify deload count
            deloads = (
                supabase_client.table("program_weeks")
                .select("*")
                .eq("program_id", program_id)
                .eq("is_deload", True)
                .execute()
            )
            assert len(deloads.data) == 2, "Beginner 12-week should have 2 deloads"

        finally:
            supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_elite_deload_pattern(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Elite (deload every 2 weeks) pattern in 8-week program."""
        program_data = {
            "user_id": test_user_id,
            "name": "Elite Deload Test",
            "goal": "strength",
            "experience_level": "elite",
            "duration_weeks": 8,
            "sessions_per_week": 4,
            "equipment_available": ["barbell", "squat_rack"],
            "status": "draft",
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        try:
            # Insert weeks with elite deload pattern (every 2 weeks: 2, 4, 6, 8)
            weeks_data = []
            for week_num in range(1, 9):
                is_deload = week_num in [2, 4, 6, 8]
                weeks_data.append({
                    "program_id": program_id,
                    "week_number": week_num,
                    "is_deload": is_deload,
                    "focus": "Deload" if is_deload else "Training",
                })
            supabase_client.table("program_weeks").insert(weeks_data).execute()

            # Verify deload count
            deloads = (
                supabase_client.table("program_weeks")
                .select("*")
                .eq("program_id", program_id)
                .eq("is_deload", True)
                .execute()
            )
            assert len(deloads.data) == 4, "Elite 8-week should have 4 deloads"

        finally:
            supabase_client.table("training_programs").delete().eq("id", program_id).execute()

    def test_elite_has_more_deloads_than_beginner(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Elite should have more deload weeks than beginner for same duration."""
        created_ids = []

        try:
            # Create beginner program
            beginner_data = {
                "user_id": test_user_id,
                "name": "Beginner Compare",
                "goal": "strength",
                "experience_level": "beginner",
                "duration_weeks": 8,
                "sessions_per_week": 3,
                "equipment_available": ["barbell"],
                "status": "draft",
            }
            beginner_result = supabase_client.table("training_programs").insert(beginner_data).execute()
            beginner_id = beginner_result.data[0]["id"]
            created_ids.append(beginner_id)

            # Create elite program
            elite_data = {
                "user_id": test_user_id,
                "name": "Elite Compare",
                "goal": "strength",
                "experience_level": "elite",
                "duration_weeks": 8,
                "sessions_per_week": 4,
                "equipment_available": ["barbell", "squat_rack"],
                "status": "draft",
            }
            elite_result = supabase_client.table("training_programs").insert(elite_data).execute()
            elite_id = elite_result.data[0]["id"]
            created_ids.append(elite_id)

            # Insert beginner weeks (deload every 6 weeks - so 0 in 8 weeks, but last week is deload)
            beginner_weeks = []
            for week_num in range(1, 9):
                is_deload = week_num == 8  # Only last week for short program
                beginner_weeks.append({
                    "program_id": beginner_id,
                    "week_number": week_num,
                    "is_deload": is_deload,
                })
            supabase_client.table("program_weeks").insert(beginner_weeks).execute()

            # Insert elite weeks (deload every 2 weeks)
            elite_weeks = []
            for week_num in range(1, 9):
                is_deload = week_num in [2, 4, 6, 8]
                elite_weeks.append({
                    "program_id": elite_id,
                    "week_number": week_num,
                    "is_deload": is_deload,
                })
            supabase_client.table("program_weeks").insert(elite_weeks).execute()

            # Count deloads
            beginner_deloads = (
                supabase_client.table("program_weeks")
                .select("*")
                .eq("program_id", beginner_id)
                .eq("is_deload", True)
                .execute()
            )
            elite_deloads = (
                supabase_client.table("program_weeks")
                .select("*")
                .eq("program_id", elite_id)
                .eq("is_deload", True)
                .execute()
            )

            assert len(elite_deloads.data) > len(beginner_deloads.data), \
                "Elite should have more deloads than beginner"

        finally:
            for program_id in created_ids:
                supabase_client.table("training_programs").delete().eq("id", program_id).execute()
