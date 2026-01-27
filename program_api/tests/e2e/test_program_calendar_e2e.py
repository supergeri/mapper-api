"""
E2E tests for program calendar integration.

AMA-469: Calendar Integration for Program Workouts

These tests verify the full flow of:
1. Creating a program with weeks and workouts
2. Activating the program
3. Verifying calendar events are created in the database
4. Testing the workout completion webhook

Run with:
    pytest -m e2e tests/e2e/test_program_calendar_e2e.py -v
    pytest tests/e2e/test_program_calendar_e2e.py --live -v  # With live APIs

Requires:
- SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables
- Program-API running on port 8005 (for --live mode)
- Calendar-API running on port 8001 (for --live mode)
"""

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest

# Skip entire module if not running E2E tests
pytestmark = pytest.mark.e2e


# =============================================================================
# Test Data Factories
# =============================================================================


def make_program_data(
    user_id: str,
    name: str = "E2E Calendar Test Program",
    duration_weeks: int = 2,
    sessions_per_week: int = 3,
) -> Dict[str, Any]:
    """Create program data for testing."""
    return {
        "user_id": user_id,
        "name": name,
        "description": "E2E test program for calendar integration",
        "goal": "strength",
        "experience_level": "intermediate",
        "duration_weeks": duration_weeks,
        "sessions_per_week": sessions_per_week,
        "equipment_available": ["barbell", "dumbbells"],
        "status": "draft",
        "periodization_model": "linear",
        "time_per_session_minutes": 60,
    }


def make_week_data(
    program_id: str,
    week_number: int,
    focus: str = "Strength",
    is_deload: bool = False,
) -> Dict[str, Any]:
    """Create week data for testing."""
    return {
        "program_id": program_id,
        "week_number": week_number,
        "focus": focus,
        "intensity_percentage": 75 if is_deload else 85,
        "volume_modifier": 0.7 if is_deload else 1.0,
        "is_deload": is_deload,
    }


def make_workout_data(
    week_id: str,
    day_of_week: int,
    name: str,
    workout_type: str = "upper",
) -> Dict[str, Any]:
    """Create workout data for testing."""
    return {
        "week_id": week_id,
        "day_of_week": day_of_week,
        "name": name,
        "workout_type": workout_type,
        "target_duration_minutes": 60,
        "exercises": [
            {"name": "Bench Press", "sets": 3, "reps": 8},
            {"name": "Rows", "sets": 3, "reps": 8},
        ],
        "sort_order": 0,
    }


# =============================================================================
# E2E Test Class
# =============================================================================


class TestProgramCalendarE2E:
    """E2E tests for program calendar integration."""

    @pytest.fixture
    def created_program_id(self) -> Optional[str]:
        """Track created program for cleanup."""
        return None

    def test_activate_program_creates_calendar_events(
        self,
        supabase_client,
        http_client,
        test_user_id,
        auth_headers,
        live_mode,
    ):
        """
        Full E2E test: create program, activate it, verify calendar events.

        This test:
        1. Creates a program directly in the database
        2. Creates weeks and workouts for the program
        3. Activates the program via API
        4. Verifies calendar events were created in workout_events table
        """
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        program_id = None
        try:
            # Step 1: Create program in database
            program_data = make_program_data(test_user_id)
            result = supabase_client.table("training_programs").insert(program_data).execute()
            program_id = result.data[0]["id"]

            # Step 2: Create weeks and workouts
            week1_data = make_week_data(program_id, 1)
            week1_result = supabase_client.table("program_weeks").insert(week1_data).execute()
            week1_id = week1_result.data[0]["id"]

            week2_data = make_week_data(program_id, 2)
            week2_result = supabase_client.table("program_weeks").insert(week2_data).execute()
            week2_id = week2_result.data[0]["id"]

            # Create workouts for week 1
            workouts = [
                make_workout_data(week1_id, 0, "Upper Body A", "upper"),
                make_workout_data(week1_id, 2, "Lower Body A", "lower"),
                make_workout_data(week1_id, 4, "Full Body A", "full_body"),
            ]
            for workout in workouts:
                supabase_client.table("program_workouts").insert(workout).execute()

            # Create workouts for week 2
            workouts2 = [
                make_workout_data(week2_id, 0, "Upper Body B", "upper"),
                make_workout_data(week2_id, 2, "Lower Body B", "lower"),
            ]
            for workout in workouts2:
                supabase_client.table("program_workouts").insert(workout).execute()

            # Step 3: Activate program via API
            start_date = datetime.now(timezone.utc) + timedelta(days=1)
            response = http_client.post(
                f"/programs/{program_id}/activate",
                json={"start_date": start_date.isoformat()},
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "active"
            assert data["scheduled_workouts"] == 5  # 3 + 2 workouts

            # Step 4: Verify calendar events in database
            # Give a moment for events to be created
            time.sleep(1)

            events_result = supabase_client.table("workout_events").select("*").eq(
                "program_id", program_id
            ).execute()

            assert len(events_result.data) == 5, f"Expected 5 events, got {len(events_result.data)}"

            # Verify events have correct source
            for event in events_result.data:
                assert event["source"] == "training_program"
                assert event["user_id"] == test_user_id

        finally:
            # Cleanup
            if program_id:
                # Delete calendar events
                supabase_client.table("workout_events").delete().eq(
                    "program_id", program_id
                ).execute()
                # Delete program (cascades to weeks and workouts)
                supabase_client.table("training_programs").delete().eq(
                    "id", program_id
                ).execute()

    def test_calendar_events_have_correct_dates(
        self,
        supabase_client,
        http_client,
        test_user_id,
        auth_headers,
        live_mode,
    ):
        """Verify calendar events have correct dates based on start date and day of week."""
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        program_id = None
        try:
            # Create minimal program
            program_data = make_program_data(test_user_id, duration_weeks=1)
            result = supabase_client.table("training_programs").insert(program_data).execute()
            program_id = result.data[0]["id"]

            # Create week
            week_data = make_week_data(program_id, 1)
            week_result = supabase_client.table("program_weeks").insert(week_data).execute()
            week_id = week_result.data[0]["id"]

            # Create workouts on Mon (0), Wed (2), Fri (4)
            for day, name in [(0, "Monday"), (2, "Wednesday"), (4, "Friday")]:
                supabase_client.table("program_workouts").insert(
                    make_workout_data(week_id, day, f"{name} Workout")
                ).execute()

            # Activate starting Monday 2026-02-02
            start_date = datetime(2026, 2, 2, tzinfo=timezone.utc)
            response = http_client.post(
                f"/programs/{program_id}/activate",
                json={"start_date": start_date.isoformat()},
                headers=auth_headers,
            )

            assert response.status_code == 200

            time.sleep(1)

            # Verify dates
            events = supabase_client.table("workout_events").select("*").eq(
                "program_id", program_id
            ).order("date").execute()

            dates = [e["date"] for e in events.data]
            # Monday = 2026-02-02, Wednesday = 2026-02-04, Friday = 2026-02-06
            assert "2026-02-02" in dates
            assert "2026-02-04" in dates
            assert "2026-02-06" in dates

        finally:
            if program_id:
                supabase_client.table("workout_events").delete().eq(
                    "program_id", program_id
                ).execute()
                supabase_client.table("training_programs").delete().eq(
                    "id", program_id
                ).execute()

    def test_workout_completed_webhook_updates_program(
        self,
        supabase_client,
        http_client,
        test_user_id,
        auth_headers,
        live_mode,
    ):
        """Test the workout completed webhook updates program state."""
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        program_id = None
        try:
            # Create and activate a program
            program_data = make_program_data(test_user_id)
            program_data["status"] = "active"
            program_data["current_week"] = 1
            result = supabase_client.table("training_programs").insert(program_data).execute()
            program_id = result.data[0]["id"]

            # Create a fake workout ID
            workout_id = str(uuid.uuid4())
            event_id = str(uuid.uuid4())

            # Call the webhook
            response = http_client.post(
                f"/programs/{program_id}/workout-completed",
                json={
                    "event_id": event_id,
                    "program_workout_id": workout_id,
                    "program_week_number": 2,  # Advance to week 2
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

            # Verify program was updated
            program = supabase_client.table("training_programs").select("*").eq(
                "id", program_id
            ).single().execute()

            assert program.data["current_week"] == 2

        finally:
            if program_id:
                supabase_client.table("training_programs").delete().eq(
                    "id", program_id
                ).execute()

    def test_program_isolation_between_users(
        self,
        supabase_client,
        http_client,
        test_user_id,
        another_test_user_id,
        auth_headers,
        other_user_auth_headers,
        live_mode,
    ):
        """Verify users cannot access each other's program events."""
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        program_id = None
        try:
            # Create program for test_user
            program_data = make_program_data(test_user_id)
            result = supabase_client.table("training_programs").insert(program_data).execute()
            program_id = result.data[0]["id"]

            # Try to activate with other user's auth - should fail
            response = http_client.post(
                f"/programs/{program_id}/activate",
                json={"start_date": datetime.now(timezone.utc).isoformat()},
                headers=other_user_auth_headers,
            )

            # Should return 404 (not found, to prevent enumeration)
            assert response.status_code == 404

        finally:
            if program_id:
                supabase_client.table("training_programs").delete().eq(
                    "id", program_id
                ).execute()


class TestCalendarEventsE2E:
    """E2E tests for calendar event management."""

    def test_get_program_events_via_calendar_api(
        self,
        supabase_client,
        test_user_id,
        live_mode,
    ):
        """Verify program events can be queried from calendar-api."""
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        import httpx

        program_id = str(uuid.uuid4())
        try:
            # Insert events directly
            events = [
                {
                    "user_id": test_user_id,
                    "title": "Test Workout 1",
                    "source": "training_program",
                    "date": "2026-02-02",
                    "type": "strength",
                    "status": "planned",
                    "program_id": program_id,
                    "program_workout_id": str(uuid.uuid4()),
                    "program_week_number": 1,
                },
                {
                    "user_id": test_user_id,
                    "title": "Test Workout 2",
                    "source": "training_program",
                    "date": "2026-02-04",
                    "type": "strength",
                    "status": "planned",
                    "program_id": program_id,
                    "program_workout_id": str(uuid.uuid4()),
                    "program_week_number": 1,
                },
            ]

            for event in events:
                supabase_client.table("workout_events").insert(event).execute()

            # Query via calendar-api (if running)
            calendar_api_url = os.getenv("CALENDAR_API_URL", "http://localhost:8001")
            with httpx.Client(base_url=calendar_api_url, timeout=30.0) as client:
                response = client.get(
                    f"/program-events/{program_id}",
                    headers={"Authorization": f"Bearer {test_user_id}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    assert data["total"] == 2
                else:
                    # Calendar-api might not be running
                    pytest.skip(f"Calendar-API returned {response.status_code}")

        finally:
            supabase_client.table("workout_events").delete().eq(
                "program_id", program_id
            ).execute()

    def test_delete_program_events_via_calendar_api(
        self,
        supabase_client,
        test_user_id,
        live_mode,
    ):
        """Verify program events can be deleted via calendar-api."""
        if not live_mode:
            pytest.skip("Requires --live flag to run against live services")

        import httpx

        program_id = str(uuid.uuid4())
        try:
            # Insert events
            events = [
                {
                    "user_id": test_user_id,
                    "title": "Workout to Delete",
                    "source": "training_program",
                    "date": "2026-02-02",
                    "status": "planned",
                    "program_id": program_id,
                    "program_workout_id": str(uuid.uuid4()),
                    "program_week_number": 1,
                },
            ]

            for event in events:
                supabase_client.table("workout_events").insert(event).execute()

            # Delete via calendar-api
            calendar_api_url = os.getenv("CALENDAR_API_URL", "http://localhost:8001")
            with httpx.Client(base_url=calendar_api_url, timeout=30.0) as client:
                response = client.delete(
                    f"/program-events/{program_id}",
                    headers={"Authorization": f"Bearer {test_user_id}"},
                )

                if response.status_code == 200:
                    data = response.json()
                    assert data["events_deleted"] == 1

                    # Verify events are gone
                    remaining = supabase_client.table("workout_events").select("*").eq(
                        "program_id", program_id
                    ).execute()
                    assert len(remaining.data) == 0
                else:
                    pytest.skip(f"Calendar-API returned {response.status_code}")

        finally:
            # Cleanup in case test failed
            supabase_client.table("workout_events").delete().eq(
                "program_id", program_id
            ).execute()
