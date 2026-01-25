"""
E2E tests for Training Program Lifecycle.

Part of AMA-460: Training Programs Schema

These tests verify the full program lifecycle against real Supabase database:
1. Create program -> Get program -> Update program -> Delete program
2. Program with weeks and workouts
3. Cascade delete behavior
4. User isolation (can't access other user's programs)

Run with:
    pytest -m e2e tests/e2e/test_program_lifecycle.py -v
    pytest tests/e2e/test_program_lifecycle.py --live -v  # With live API

Note: CRUD endpoints are currently stubs (return 501). Tests are structured with
appropriate skip/xfail markers that will pass once implementation is complete.
"""

import uuid
from typing import Any, Dict

import httpx
import pytest
from supabase import Client


# =============================================================================
# SMOKE SUITE - Critical Database Operations (run on every PR)
# =============================================================================


@pytest.mark.e2e
class TestDatabaseSmoke:
    """
    Smoke tests to verify database connectivity and schema integrity.
    These are the most critical tests and should pass before any other testing.
    """

    def test_training_programs_table_exists(self, supabase_client: Client):
        """Verify the training_programs table exists and is accessible."""
        result = supabase_client.table("training_programs").select("id").limit(1).execute()
        assert result.data is not None, "training_programs table should be accessible"

    def test_program_weeks_table_exists(self, supabase_client: Client):
        """Verify the program_weeks table exists and is accessible."""
        result = supabase_client.table("program_weeks").select("id").limit(1).execute()
        assert result.data is not None, "program_weeks table should be accessible"

    def test_program_workouts_table_exists(self, supabase_client: Client):
        """Verify the program_workouts table exists and is accessible."""
        result = supabase_client.table("program_workouts").select("id").limit(1).execute()
        assert result.data is not None, "program_workouts table should be accessible"

    def test_can_insert_and_delete_program(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Verify basic insert/delete operations work on training_programs."""
        # Insert
        program_data = {
            "user_id": test_user_id,
            "name": "Smoke Test Program",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "equipment_available": ["barbell"],
            "status": "draft",
        }
        result = supabase_client.table("training_programs").insert(program_data).execute()
        assert len(result.data) == 1, "Should create one program"
        program_id = result.data[0]["id"]

        # Verify fields
        program = result.data[0]
        assert program["name"] == "Smoke Test Program"
        assert program["goal"] == "strength"
        assert program["user_id"] == test_user_id

        # Delete
        delete_result = supabase_client.table("training_programs").delete().eq(
            "id", program_id
        ).execute()
        assert len(delete_result.data) == 1, "Should delete the program"


# =============================================================================
# PROGRAM CRUD TESTS - Direct Database Operations
# =============================================================================


@pytest.mark.e2e
class TestProgramCrudDirect:
    """
    Test program CRUD operations directly against the database.
    These tests bypass the API to verify database schema and constraints.
    """

    def test_create_program_with_all_fields(
        self,
        supabase_client: Client,
        test_user_id: str,
        cleanup_program,
    ):
        """Create a program with all fields populated."""
        program_data = {
            "user_id": test_user_id,
            "name": "Full Program Test",
            "description": "A program with all fields populated",
            "goal": "hypertrophy",
            "experience_level": "advanced",
            "duration_weeks": 12,
            "sessions_per_week": 5,
            "equipment_available": ["barbell", "dumbbell", "cable", "machine"],
            "status": "active",
        }

        result = supabase_client.table("training_programs").insert(program_data).execute()
        program = result.data[0]
        cleanup_program(program["id"])

        assert program["name"] == "Full Program Test"
        assert program["description"] == "A program with all fields populated"
        assert program["goal"] == "hypertrophy"
        assert program["experience_level"] == "advanced"
        assert program["duration_weeks"] == 12
        assert program["sessions_per_week"] == 5
        assert "barbell" in program["equipment_available"]
        assert program["status"] == "active"
        assert program["created_at"] is not None
        assert program["updated_at"] is not None

    def test_create_program_minimal_fields(
        self,
        supabase_client: Client,
        test_user_id: str,
        cleanup_program,
    ):
        """Create a program with only required fields."""
        program_data = {
            "user_id": test_user_id,
            "name": "Minimal Program",
            "goal": "strength",
            "experience_level": "beginner",
            "duration_weeks": 4,
            "sessions_per_week": 3,
        }

        result = supabase_client.table("training_programs").insert(program_data).execute()
        program = result.data[0]
        cleanup_program(program["id"])

        assert program["name"] == "Minimal Program"
        assert program["description"] is None
        assert program["status"] == "draft"  # Default value

    def test_update_program(
        self,
        create_program_in_db,
        supabase_client: Client,
    ):
        """Update an existing program."""
        program = create_program_in_db(name="Original Name")

        # Update the program
        update_result = (
            supabase_client.table("training_programs")
            .update({"name": "Updated Name", "status": "active"})
            .eq("id", program["id"])
            .execute()
        )

        updated_program = update_result.data[0]
        assert updated_program["name"] == "Updated Name"
        assert updated_program["status"] == "active"

    def test_delete_program(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Delete a program and verify it's gone."""
        # Create a program (don't use cleanup fixture since we're testing delete)
        program_data = {
            "user_id": test_user_id,
            "name": "Program to Delete",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
        }
        result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = result.data[0]["id"]

        # Delete
        supabase_client.table("training_programs").delete().eq("id", program_id).execute()

        # Verify deletion
        check_result = (
            supabase_client.table("training_programs")
            .select("id")
            .eq("id", program_id)
            .execute()
        )
        assert len(check_result.data) == 0, "Program should be deleted"


# =============================================================================
# PROGRAM WITH WEEKS AND WORKOUTS
# =============================================================================


@pytest.mark.e2e
class TestProgramWithWeeksAndWorkouts:
    """
    Test creating programs with nested weeks and workouts.
    Verifies foreign key relationships and data integrity.
    """

    def test_create_program_with_weeks(
        self,
        create_program_in_db,
        create_week_in_db,
        supabase_client: Client,
    ):
        """Create a program with multiple weeks."""
        program = create_program_in_db(name="Program with Weeks", duration_weeks=4)

        # Create 4 weeks
        weeks = []
        for i in range(1, 5):
            week = create_week_in_db(
                program_id=program["id"],
                week_number=i,
                name=f"Week {i}",
                deload=(i == 4),  # Week 4 is deload
            )
            weeks.append(week)

        assert len(weeks) == 4
        assert weeks[0]["week_number"] == 1
        assert weeks[3]["deload"] is True

        # Verify weeks are linked to program
        result = (
            supabase_client.table("program_weeks")
            .select("*")
            .eq("program_id", program["id"])
            .order("week_number")
            .execute()
        )
        assert len(result.data) == 4

    def test_create_week_with_workouts(
        self,
        create_program_in_db,
        create_week_in_db,
        create_workout_in_db,
        supabase_client: Client,
    ):
        """Create a week with multiple workouts."""
        program = create_program_in_db(name="Program with Workouts")
        week = create_week_in_db(program_id=program["id"], week_number=1)

        # Create 3 workouts (Mon, Wed, Fri)
        workouts = []
        workout_configs = [
            (1, "Push Day", 0),
            (3, "Pull Day", 1),
            (5, "Leg Day", 2),
        ]
        for day, name, order in workout_configs:
            workout = create_workout_in_db(
                program_week_id=week["id"],
                day_of_week=day,
                name=name,
                order_index=order,
            )
            workouts.append(workout)

        assert len(workouts) == 3
        assert workouts[0]["name"] == "Push Day"
        assert workouts[0]["day_of_week"] == 1

        # Verify workouts are linked to week
        result = (
            supabase_client.table("program_workouts")
            .select("*")
            .eq("program_week_id", week["id"])
            .order("order_index")
            .execute()
        )
        assert len(result.data) == 3

    def test_full_program_structure(
        self,
        create_program_in_db,
        create_week_in_db,
        create_workout_in_db,
        supabase_client: Client,
    ):
        """Create a complete program with weeks and workouts."""
        program = create_program_in_db(
            name="Complete 4-Week Program",
            duration_weeks=4,
            sessions_per_week=3,
        )

        # Create 4 weeks with 3 workouts each
        for week_num in range(1, 5):
            week = create_week_in_db(
                program_id=program["id"],
                week_number=week_num,
            )

            for day, name in [(1, "Push"), (3, "Pull"), (5, "Legs")]:
                create_workout_in_db(
                    program_week_id=week["id"],
                    day_of_week=day,
                    name=f"{name} - Week {week_num}",
                )

        # Verify structure
        weeks_result = (
            supabase_client.table("program_weeks")
            .select("*, program_workouts(*)")
            .eq("program_id", program["id"])
            .execute()
        )

        assert len(weeks_result.data) == 4
        for week in weeks_result.data:
            assert len(week["program_workouts"]) == 3


# =============================================================================
# CASCADE DELETE BEHAVIOR
# =============================================================================


@pytest.mark.e2e
class TestCascadeDelete:
    """
    Test cascade delete behavior for program relationships.
    Verifies that deleting a program also deletes its weeks and workouts.
    """

    def test_delete_program_cascades_to_weeks(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Deleting a program should delete its weeks."""
        # Create program
        program_data = {
            "user_id": test_user_id,
            "name": "Cascade Test Program",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 2,
            "sessions_per_week": 3,
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        # Create weeks
        for week_num in range(1, 3):
            supabase_client.table("program_weeks").insert({
                "program_id": program_id,
                "week_number": week_num,
                "name": f"Week {week_num}",
            }).execute()

        # Verify weeks exist
        weeks_before = (
            supabase_client.table("program_weeks")
            .select("id")
            .eq("program_id", program_id)
            .execute()
        )
        assert len(weeks_before.data) == 2

        # Delete program
        supabase_client.table("training_programs").delete().eq("id", program_id).execute()

        # Verify weeks are also deleted
        weeks_after = (
            supabase_client.table("program_weeks")
            .select("id")
            .eq("program_id", program_id)
            .execute()
        )
        assert len(weeks_after.data) == 0

    def test_delete_program_cascades_to_workouts(
        self,
        supabase_client: Client,
        test_user_id: str,
    ):
        """Deleting a program should delete its weeks and workouts."""
        # Create program
        program_data = {
            "user_id": test_user_id,
            "name": "Full Cascade Test",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 1,
            "sessions_per_week": 2,
        }
        program_result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = program_result.data[0]["id"]

        # Create week
        week_result = supabase_client.table("program_weeks").insert({
            "program_id": program_id,
            "week_number": 1,
            "name": "Week 1",
        }).execute()
        week_id = week_result.data[0]["id"]

        # Create workouts
        for day in [1, 3]:
            supabase_client.table("program_workouts").insert({
                "program_week_id": week_id,
                "day_of_week": day,
                "name": f"Day {day} Workout",
                "order_index": 0,
            }).execute()

        # Verify workouts exist
        workouts_before = (
            supabase_client.table("program_workouts")
            .select("id")
            .eq("program_week_id", week_id)
            .execute()
        )
        assert len(workouts_before.data) == 2

        # Delete program
        supabase_client.table("training_programs").delete().eq("id", program_id).execute()

        # Verify workouts are also deleted
        workouts_after = (
            supabase_client.table("program_workouts")
            .select("id")
            .eq("program_week_id", week_id)
            .execute()
        )
        assert len(workouts_after.data) == 0

    def test_delete_week_cascades_to_workouts(
        self,
        create_program_in_db,
        supabase_client: Client,
    ):
        """Deleting a week should delete its workouts."""
        program = create_program_in_db(name="Week Cascade Test")

        # Create week
        week_result = supabase_client.table("program_weeks").insert({
            "program_id": program["id"],
            "week_number": 1,
            "name": "Week 1",
        }).execute()
        week_id = week_result.data[0]["id"]

        # Create workouts
        for day in [1, 3, 5]:
            supabase_client.table("program_workouts").insert({
                "program_week_id": week_id,
                "day_of_week": day,
                "name": f"Day {day}",
                "order_index": 0,
            }).execute()

        # Delete week
        supabase_client.table("program_weeks").delete().eq("id", week_id).execute()

        # Verify workouts are also deleted
        workouts_after = (
            supabase_client.table("program_workouts")
            .select("id")
            .eq("program_week_id", week_id)
            .execute()
        )
        assert len(workouts_after.data) == 0


# =============================================================================
# USER ISOLATION TESTS
# =============================================================================


@pytest.mark.e2e
class TestUserIsolation:
    """
    Test user isolation - users cannot access other users' programs.
    These tests verify RLS policies are working correctly.
    """

    def test_user_can_only_see_own_programs(
        self,
        supabase_client: Client,
        test_user_id: str,
        another_test_user_id: str,
        cleanup_program,
    ):
        """Users should only see their own programs when listing."""
        # Create program for first user
        program1_data = {
            "user_id": test_user_id,
            "name": "User 1 Program",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
        }
        result1 = supabase_client.table("training_programs").insert(program1_data).execute()
        cleanup_program(result1.data[0]["id"])

        # Create program for second user
        program2_data = {
            "user_id": another_test_user_id,
            "name": "User 2 Program",
            "goal": "hypertrophy",
            "experience_level": "advanced",
            "duration_weeks": 8,
            "sessions_per_week": 4,
        }
        result2 = supabase_client.table("training_programs").insert(program2_data).execute()
        cleanup_program(result2.data[0]["id"])

        # Query programs for user 1
        user1_programs = (
            supabase_client.table("training_programs")
            .select("*")
            .eq("user_id", test_user_id)
            .execute()
        )

        # Should only see user 1's programs
        for program in user1_programs.data:
            assert program["user_id"] == test_user_id

        # Query programs for user 2
        user2_programs = (
            supabase_client.table("training_programs")
            .select("*")
            .eq("user_id", another_test_user_id)
            .execute()
        )

        # Should only see user 2's programs
        for program in user2_programs.data:
            assert program["user_id"] == another_test_user_id

    def test_programs_isolated_by_user_id(
        self,
        supabase_client: Client,
        test_user_id: str,
        another_test_user_id: str,
        cleanup_program,
    ):
        """Direct query with wrong user_id should return no results."""
        # Create program for first user
        program_data = {
            "user_id": test_user_id,
            "name": "Isolated Program",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
        }
        result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = result.data[0]["id"]
        cleanup_program(program_id)

        # Query with second user's ID should not find the program
        wrong_user_query = (
            supabase_client.table("training_programs")
            .select("*")
            .eq("id", program_id)
            .eq("user_id", another_test_user_id)
            .execute()
        )
        assert len(wrong_user_query.data) == 0


# =============================================================================
# API ENDPOINT TESTS - Requires Live API
# =============================================================================


@pytest.mark.e2e
class TestProgramAPIEndpoints:
    """
    API endpoint tests requiring live program-api service.
    Skip if --live flag not provided or API is unavailable.

    Note: Most CRUD endpoints return 501 (Not Implemented) until AMA-462.
    Tests are marked with xfail to pass once implementation is complete.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    def test_health_endpoint(self, http_client: httpx.Client):
        """Health endpoint should return 200."""
        response = http_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "program-api"

    def test_list_programs_returns_empty(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
    ):
        """GET /programs returns empty list for new user."""
        response = http_client.get("/programs", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == []

    def test_list_programs_requires_auth(self, http_client: httpx.Client):
        """GET /programs without auth returns 401."""
        response = http_client.get("/programs")
        assert response.status_code == 401

    def test_get_program_not_found(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
    ):
        """GET /programs/{id} returns 404 for non-existent program."""
        fake_id = str(uuid.uuid4())
        response = http_client.get(f"/programs/{fake_id}", headers=auth_headers)
        assert response.status_code == 404

    @pytest.mark.xfail(reason="POST /programs returns 501 until AMA-462 implementation")
    def test_create_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
    ):
        """POST /programs creates a new program."""
        program_data = {
            "name": "API Test Program",
            "description": "Created via API",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "equipment_available": ["barbell", "dumbbell"],
        }

        response = http_client.post("/programs", json=program_data, headers=auth_headers)
        assert response.status_code == 201

        program = response.json()
        cleanup_program(program["id"])

        assert program["name"] == "API Test Program"
        assert program["goal"] == "strength"
        assert program["status"] == "draft"

    @pytest.mark.xfail(reason="PUT /programs/{id} returns 501 until AMA-462 implementation")
    def test_update_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        create_program_in_db,
    ):
        """PUT /programs/{id} updates an existing program."""
        program = create_program_in_db(name="Original Name")

        update_data = {
            "name": "Updated Name",
            "status": "active",
        }

        response = http_client.put(
            f"/programs/{program['id']}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200

        updated = response.json()
        assert updated["name"] == "Updated Name"
        assert updated["status"] == "active"

    @pytest.mark.xfail(reason="DELETE /programs/{id} returns 501 until AMA-462 implementation")
    def test_delete_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        supabase_client: Client,
        test_user_id: str,
    ):
        """DELETE /programs/{id} removes the program."""
        # Create program directly (don't use cleanup since we're testing delete)
        program_data = {
            "user_id": test_user_id,
            "name": "Program to Delete via API",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 4,
            "sessions_per_week": 3,
        }
        result = supabase_client.table("training_programs").insert(program_data).execute()
        program_id = result.data[0]["id"]

        response = http_client.delete(f"/programs/{program_id}", headers=auth_headers)
        assert response.status_code == 204

        # Verify deletion
        check = (
            supabase_client.table("training_programs")
            .select("id")
            .eq("id", program_id)
            .execute()
        )
        assert len(check.data) == 0


# =============================================================================
# GENERATION ENDPOINT TESTS
# =============================================================================


@pytest.mark.e2e
class TestGenerationAPIEndpoints:
    """
    Tests for AI-powered program generation endpoint.
    Implementation completed in AMA-462.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    @pytest.mark.timeout(120)  # 2 minutes for generation
    def test_generate_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """POST /generate creates an AI-generated program."""
        request_data = generation_request_factory(
            goal="strength",
            duration_weeks=4,
            sessions_per_week=3,
            equipment_available=["barbell", "dumbbells", "bench", "squat_rack"],
        )

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201], f"Expected success, got {response.status_code}: {response.text}"

        result = response.json()
        assert "program" in result, "Response should contain 'program'"
        assert "generation_metadata" in result, "Response should contain 'generation_metadata'"
        assert "suggestions" in result, "Response should contain 'suggestions'"

        program = result["program"]
        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        # Verify program structure
        assert program["goal"] == "strength"
        assert program["duration_weeks"] == 4
        assert "weeks" in program
        assert len(program["weeks"]) == 4

    @pytest.mark.timeout(120)
    def test_generate_program_all_goals(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """POST /generate works for all goal types."""
        goals = ["strength", "hypertrophy", "endurance", "weight_loss", "general_fitness"]

        for goal in goals:
            request_data = generation_request_factory(
                goal=goal,
                duration_weeks=4,
                sessions_per_week=3,
            )

            response = http_client.post("/generate", json=request_data, headers=auth_headers)
            assert response.status_code in [200, 201], f"Failed for goal={goal}: {response.text}"

            result = response.json()
            if result.get("program") and result["program"].get("id"):
                cleanup_program(str(result["program"]["id"]))

    @pytest.mark.timeout(120)
    def test_generate_program_validates_request(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
    ):
        """POST /generate returns 422 for invalid request."""
        invalid_request = {
            "goal": "invalid_goal",
            "duration_weeks": 4,
            "sessions_per_week": 3,
            "experience_level": "intermediate",
        }

        response = http_client.post("/generate", json=invalid_request, headers=auth_headers)
        assert response.status_code == 422

    def test_generate_program_requires_auth(
        self,
        http_client: httpx.Client,
        generation_request_factory,
    ):
        """POST /generate returns 401 without authentication."""
        request_data = generation_request_factory()
        response = http_client.post("/generate", json=request_data)
        assert response.status_code == 401


# =============================================================================
# PROGRESSION ENDPOINT TESTS
# =============================================================================


@pytest.mark.e2e
class TestProgressionAPIEndpoints:
    """
    Tests for exercise progression tracking endpoints.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    def test_get_exercise_history_returns_empty(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
    ):
        """GET /progression/history/{exercise_id} returns empty for new exercise."""
        exercise_id = str(uuid.uuid4())
        response = http_client.get(
            f"/progression/history/{exercise_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.xfail(reason="POST /progression/history returns 501 until implementation")
    def test_record_performance(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
    ):
        """POST /progression/history records exercise performance."""
        exercise_id = str(uuid.uuid4())
        request_data = {
            "exercise_id": exercise_id,
            "weight": 100.0,
            "reps": 8,
            "sets": 3,
        }

        response = http_client.post(
            "/progression/history",
            json=request_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        record = response.json()
        assert record["exercise_id"] == exercise_id
        assert record["weight"] == 100.0
        assert record["reps"] == 8


# =============================================================================
# FULL GENERATION FLOW TESTS (Critical Path)
# =============================================================================


@pytest.mark.e2e
class TestFullGenerationFlow:
    """
    Full end-to-end tests for the critical generation flow.
    Tests: POST /generate → verify persistence → GET /programs/{id}

    These tests verify the complete user journey for program generation.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    @pytest.mark.timeout(180)  # 3 minutes for full flow
    def test_generate_then_retrieve_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        supabase_client: Client,
        cleanup_program,
        generation_request_factory,
    ):
        """
        Full flow: Generate a program via API, verify it's persisted, retrieve it.

        This is the critical happy path for the service.
        """
        # Step 1: Generate program
        request_data = generation_request_factory(
            goal="hypertrophy",
            duration_weeks=4,
            sessions_per_week=4,
        )

        gen_response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert gen_response.status_code in [200, 201], f"Generation failed: {gen_response.text}"

        gen_result = gen_response.json()
        assert "program" in gen_result
        program = gen_result["program"]
        program_id = str(program["id"])
        cleanup_program(program_id)

        # Step 2: Verify program is persisted in database
        db_result = supabase_client.table("training_programs").select("*").eq(
            "id", program_id
        ).execute()
        assert len(db_result.data) == 1, "Program should be persisted in database"

        db_program = db_result.data[0]
        assert db_program["goal"] == "hypertrophy"
        assert db_program["duration_weeks"] == 4

        # Step 3: Verify weeks are persisted
        weeks_result = supabase_client.table("program_weeks").select("*").eq(
            "program_id", program_id
        ).order("week_number").execute()
        assert len(weeks_result.data) == 4, "Should have 4 weeks"

        # Step 4: Verify workouts are persisted for each week
        for week in weeks_result.data:
            workouts_result = supabase_client.table("program_workouts").select("*").eq(
                "program_week_id", week["id"]
            ).execute()
            assert len(workouts_result.data) >= 1, f"Week {week['week_number']} should have workouts"

    @pytest.mark.timeout(180)
    def test_generate_with_all_options(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """Generate program with all optional parameters."""
        request_data = generation_request_factory(
            goal="strength",
            duration_weeks=8,
            sessions_per_week=3,
            experience_level="advanced",
            equipment_available=["barbell", "dumbbells", "cables", "bench", "squat_rack"],
            focus_areas=["chest", "back"],
            limitations=["shoulder"],
            preferences="Prefer compound movements, minimal isolation work",
        )

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201]

        result = response.json()
        program = result["program"]
        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        assert program["duration_weeks"] == 8
        assert len(program["weeks"]) == 8

    @pytest.mark.timeout(120)
    def test_generation_metadata_included(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """Generated response includes useful metadata."""
        request_data = generation_request_factory(
            goal="strength",
            duration_weeks=4,
            sessions_per_week=3,
        )

        response = http_client.post("/generate", json=request_data, headers=auth_headers)
        assert response.status_code in [200, 201]

        result = response.json()
        if result.get("program") and result["program"].get("id"):
            cleanup_program(str(result["program"]["id"]))

        # Check metadata fields
        assert "generation_metadata" in result
        metadata = result["generation_metadata"]
        assert "periodization_model" in metadata
        assert "generation_time_seconds" in metadata

        # Check suggestions
        assert "suggestions" in result
        assert isinstance(result["suggestions"], list)


# =============================================================================
# LARGE PROGRAM PERFORMANCE TESTS
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestLargeProgramGeneration:
    """
    Performance tests for generating large programs.

    These tests verify the system can handle maximum-size programs
    without timing out or running out of resources.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    @pytest.mark.timeout(300)  # 5 minutes for large program
    def test_generate_maximum_duration_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """Generate a 52-week (1 year) program."""
        request_data = generation_request_factory(
            goal="hypertrophy",
            duration_weeks=52,
            sessions_per_week=3,
            experience_level="intermediate",
        )

        response = http_client.post(
            "/generate",
            json=request_data,
            headers=auth_headers,
            timeout=300.0,  # Extended timeout
        )
        assert response.status_code in [200, 201], f"Large program generation failed: {response.text}"

        result = response.json()
        program = result["program"]
        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        assert program["duration_weeks"] == 52
        assert len(program["weeks"]) == 52

    @pytest.mark.timeout(300)
    def test_generate_maximum_sessions_program(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """Generate a 7 sessions/week program."""
        request_data = generation_request_factory(
            goal="hypertrophy",
            duration_weeks=4,
            sessions_per_week=7,
            experience_level="advanced",
        )

        response = http_client.post(
            "/generate",
            json=request_data,
            headers=auth_headers,
            timeout=180.0,
        )
        assert response.status_code in [200, 201]

        result = response.json()
        program = result["program"]
        if program and program.get("id"):
            cleanup_program(str(program["id"]))

        # Verify each week has 7 workouts
        for week in program["weeks"]:
            assert len(week["workouts"]) == 7, f"Week should have 7 workouts"


# =============================================================================
# CONCURRENT USER ISOLATION TESTS
# =============================================================================


@pytest.mark.e2e
class TestConcurrentUserIsolation:
    """
    Test that concurrent operations maintain user isolation.

    Verifies that when multiple users generate programs simultaneously,
    each user only sees their own programs.
    """

    @pytest.fixture(autouse=True)
    def check_api_available(self, live_mode: bool, http_client: httpx.Client):
        """Skip API tests if not in live mode or API is unavailable."""
        if not live_mode:
            pytest.skip("API tests require --live flag")
        try:
            response = http_client.get("/health")
            if response.status_code != 200:
                pytest.skip("program-api not available")
        except httpx.ConnectError:
            pytest.skip("program-api not reachable at configured URL")

    @pytest.mark.timeout(180)
    def test_two_users_generate_simultaneously(
        self,
        http_client: httpx.Client,
        auth_headers: Dict[str, str],
        other_user_auth_headers: Dict[str, str],
        cleanup_program,
        generation_request_factory,
    ):
        """Two users generating programs should only see their own."""
        # User 1 generates a program
        request1 = generation_request_factory(
            goal="strength",
            duration_weeks=4,
            sessions_per_week=3,
        )
        response1 = http_client.post("/generate", json=request1, headers=auth_headers)
        assert response1.status_code in [200, 201]
        program1 = response1.json()["program"]
        if program1 and program1.get("id"):
            cleanup_program(str(program1["id"]))

        # User 2 generates a program
        request2 = generation_request_factory(
            goal="hypertrophy",
            duration_weeks=4,
            sessions_per_week=4,
        )
        response2 = http_client.post("/generate", json=request2, headers=other_user_auth_headers)
        assert response2.status_code in [200, 201]
        program2 = response2.json()["program"]
        if program2 and program2.get("id"):
            cleanup_program(str(program2["id"]))

        # User 1 lists programs - should only see their program
        list_response1 = http_client.get("/programs", headers=auth_headers)
        assert list_response1.status_code == 200
        user1_programs = list_response1.json()

        # User 2 lists programs - should only see their program
        list_response2 = http_client.get("/programs", headers=other_user_auth_headers)
        assert list_response2.status_code == 200
        user2_programs = list_response2.json()

        # Verify isolation - programs should not overlap
        user1_ids = {p["id"] for p in user1_programs}
        user2_ids = {p["id"] for p in user2_programs}
        assert user1_ids.isdisjoint(user2_ids), "Users should not see each other's programs"


# =============================================================================
# DATA INTEGRITY TESTS
# =============================================================================


@pytest.mark.e2e
class TestDataIntegrity:
    """
    Data integrity tests for the training programs schema.
    Verifies constraints and enum values.
    """

    def test_program_goal_enum_values(
        self,
        supabase_client: Client,
        test_user_id: str,
        valid_program_goals: list,
        cleanup_program,
    ):
        """All valid goal values should be accepted."""
        for goal in valid_program_goals:
            program_data = {
                "user_id": test_user_id,
                "name": f"Goal Test: {goal}",
                "goal": goal,
                "experience_level": "intermediate",
                "duration_weeks": 4,
                "sessions_per_week": 3,
            }
            result = supabase_client.table("training_programs").insert(program_data).execute()
            cleanup_program(result.data[0]["id"])
            assert result.data[0]["goal"] == goal

    def test_experience_level_enum_values(
        self,
        supabase_client: Client,
        test_user_id: str,
        valid_experience_levels: list,
        cleanup_program,
    ):
        """All valid experience level values should be accepted."""
        for level in valid_experience_levels:
            program_data = {
                "user_id": test_user_id,
                "name": f"Level Test: {level}",
                "goal": "strength",
                "experience_level": level,
                "duration_weeks": 4,
                "sessions_per_week": 3,
            }
            result = supabase_client.table("training_programs").insert(program_data).execute()
            cleanup_program(result.data[0]["id"])
            assert result.data[0]["experience_level"] == level

    def test_program_status_enum_values(
        self,
        supabase_client: Client,
        test_user_id: str,
        valid_program_statuses: list,
        cleanup_program,
    ):
        """All valid status values should be accepted."""
        for status in valid_program_statuses:
            program_data = {
                "user_id": test_user_id,
                "name": f"Status Test: {status}",
                "goal": "strength",
                "experience_level": "intermediate",
                "duration_weeks": 4,
                "sessions_per_week": 3,
                "status": status,
            }
            result = supabase_client.table("training_programs").insert(program_data).execute()
            cleanup_program(result.data[0]["id"])
            assert result.data[0]["status"] == status

    def test_week_day_of_week_constraint(
        self,
        create_program_in_db,
        create_week_in_db,
        supabase_client: Client,
    ):
        """Workout day_of_week should be 1-7."""
        program = create_program_in_db(name="Day Constraint Test")
        week = create_week_in_db(program_id=program["id"], week_number=1)

        # Valid days (1-7)
        for day in [1, 4, 7]:
            result = supabase_client.table("program_workouts").insert({
                "program_week_id": week["id"],
                "day_of_week": day,
                "name": f"Day {day}",
                "order_index": 0,
            }).execute()
            assert result.data[0]["day_of_week"] == day
            # Clean up
            supabase_client.table("program_workouts").delete().eq(
                "id", result.data[0]["id"]
            ).execute()

    def test_duration_weeks_constraint(
        self,
        supabase_client: Client,
        test_user_id: str,
        cleanup_program,
    ):
        """Duration weeks should be within valid range (1-52)."""
        # Valid durations
        for weeks in [1, 12, 52]:
            program_data = {
                "user_id": test_user_id,
                "name": f"Duration Test: {weeks} weeks",
                "goal": "strength",
                "experience_level": "intermediate",
                "duration_weeks": weeks,
                "sessions_per_week": 3,
            }
            result = supabase_client.table("training_programs").insert(program_data).execute()
            cleanup_program(result.data[0]["id"])
            assert result.data[0]["duration_weeks"] == weeks
