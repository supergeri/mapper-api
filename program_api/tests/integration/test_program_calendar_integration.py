"""
Integration tests for program calendar integration.

AMA-469: Calendar Integration for Program Workouts

Tests the activate_program endpoint with calendar integration,
verifying that calendar events are created correctly when a program
is activated.
"""

from datetime import datetime, timezone
from uuid import UUID

import pytest

from tests.fakes import FakeCalendarClient


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------


TEST_USER_ID = "test-user-123"
PROGRAM_ID = "550e8400-e29b-41d4-a716-446655440000"


def make_auth_header(user_id: str = TEST_USER_ID) -> dict:
    """Create authorization header for requests."""
    return {"Authorization": f"Bearer {user_id}"}


# ---------------------------------------------------------------------------
# Program Activation with Calendar Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestProgramActivationWithCalendar:
    """Tests for activating programs with calendar integration."""

    def test_activate_program_creates_calendar_events(
        self,
        client_with_seeded_calendar_repo,
        fake_calendar_client,
        sample_program_with_weeks,
    ):
        """Activating a program creates calendar events for all workouts."""
        program_id = sample_program_with_weeks["program"]["id"]

        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

        # Verify calendar events were created
        # 3 workouts total: 2 in week 1, 1 in week 2
        events = fake_calendar_client.get_events_for_program(UUID(program_id))
        assert len(events) == 3

    def test_activate_program_events_have_correct_dates(
        self,
        client_with_seeded_calendar_repo,
        fake_calendar_client,
        sample_program_with_weeks,
    ):
        """Calendar events have correct dates based on start_date and day_of_week."""
        program_id = sample_program_with_weeks["program"]["id"]

        # Start on Monday 2026-02-02
        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200

        events = fake_calendar_client.get_events_for_program(UUID(program_id))
        events_by_title = {e.title: e for e in events}

        # Week 1, Day 0 (Monday) = 2026-02-02
        assert "Upper Body A" in events_by_title
        assert events_by_title["Upper Body A"].date.isoformat() == "2026-02-02"

        # Week 1, Day 2 (Wednesday) = 2026-02-04
        assert "Lower Body A" in events_by_title
        assert events_by_title["Lower Body A"].date.isoformat() == "2026-02-04"

        # Week 2, Day 0 (Monday) = 2026-02-09
        assert "Upper Body B" in events_by_title
        assert events_by_title["Upper Body B"].date.isoformat() == "2026-02-09"

    def test_activate_program_events_have_correct_metadata(
        self,
        client_with_seeded_calendar_repo,
        fake_calendar_client,
        sample_program_with_weeks,
    ):
        """Calendar events include correct program metadata in json_payload."""
        program_id = sample_program_with_weeks["program"]["id"]

        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200

        events = fake_calendar_client.get_events_for_program(UUID(program_id))
        upper_body_event = next(e for e in events if e.title == "Upper Body A")

        # Check metadata
        assert upper_body_event.program_week_number == 1
        assert upper_body_event.type == "strength"
        assert upper_body_event.primary_muscle == "upper"
        assert upper_body_event.json_payload is not None
        assert "program_name" in upper_body_event.json_payload

    def test_activate_program_returns_scheduled_count(
        self,
        client_with_seeded_calendar_repo,
        sample_program_with_weeks,
    ):
        """Response includes count of scheduled workouts."""
        program_id = sample_program_with_weeks["program"]["id"]

        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scheduled_workouts"] == 3

    def test_activate_program_uses_current_date_if_no_start_date(
        self,
        client_with_seeded_calendar_repo,
        fake_calendar_client,
        sample_program_with_weeks,
    ):
        """If no start_date provided, uses current date."""
        program_id = sample_program_with_weeks["program"]["id"]

        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            headers=make_auth_header(),
        )

        assert response.status_code == 200

        # Events should be created with dates based on current date
        events = fake_calendar_client.get_events_for_program(UUID(program_id))
        assert len(events) == 3


@pytest.mark.integration
class TestProgramActivationCalendarFailure:
    """Tests for program activation when calendar service fails."""

    def test_activate_succeeds_when_calendar_unavailable(
        self,
        client_with_failing_calendar,
        fake_program_repo,
        sample_program_with_weeks,
    ):
        """Program activation succeeds even if calendar service is unavailable."""
        # Seed the program data
        program = sample_program_with_weeks["program"]
        weeks = sample_program_with_weeks["weeks"]
        fake_program_repo.seed([program])
        for week in weeks:
            workouts = week.pop("workouts", [])
            fake_program_repo._weeks[week["id"]] = week
            for workout in workouts:
                fake_program_repo._workouts[workout["id"]] = workout

        program_id = program["id"]

        response = client_with_failing_calendar.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        # Activation should succeed despite calendar failure
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        # But scheduled_workouts should be 0 or indicate partial success
        assert data["scheduled_workouts"] == 0

    def test_activate_updates_program_status_despite_calendar_failure(
        self,
        client_with_failing_calendar,
        fake_program_repo,
        sample_program_with_weeks,
    ):
        """Program status is updated even if calendar events fail."""
        # Seed the program data
        program = sample_program_with_weeks["program"]
        weeks = sample_program_with_weeks["weeks"]
        fake_program_repo.seed([program])
        for week in weeks:
            workouts = week.pop("workouts", [])
            fake_program_repo._weeks[week["id"]] = week
            for workout in workouts:
                fake_program_repo._workouts[workout["id"]] = workout

        program_id = program["id"]

        response = client_with_failing_calendar.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200

        # Verify program status was updated
        updated_program = fake_program_repo.get_by_id(program_id)
        assert updated_program["status"] == "active"
        assert updated_program["current_week"] == 1


@pytest.mark.integration
class TestProgramActivationValidation:
    """Tests for program activation validation."""

    def test_cannot_activate_already_active_program(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Cannot activate a program that is already active."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/activate",
            headers=make_auth_header(),
        )

        assert response.status_code == 422
        assert "already active" in response.json()["detail"].lower()

    def test_cannot_activate_completed_program(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Cannot activate a completed program."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Completed Program",
            "status": "completed",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/activate",
            headers=make_auth_header(),
        )

        assert response.status_code == 422
        assert "completed" in response.json()["detail"].lower()

    def test_cannot_activate_archived_program(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Cannot activate an archived program."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Archived Program",
            "status": "archived",
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/activate",
            headers=make_auth_header(),
        )

        assert response.status_code == 422
        assert "archived" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Workout Completed Webhook Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestWorkoutCompletedWebhook:
    """Tests for the workout completed webhook endpoint."""

    def test_webhook_records_completion(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Webhook endpoint records workout completion."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "current_week": 1,
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_webhook_advances_current_week(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Webhook advances current_week when completing a future week workout."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "current_week": 1,
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        # Complete a workout from week 3
        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 3,
                "completed_at": "2026-02-16T18:00:00Z",
            },
            headers=make_auth_header(),
        )

        assert response.status_code == 200

        # Verify current_week was advanced
        updated_program = fake_program_repo.get_by_id(PROGRAM_ID)
        assert updated_program["current_week"] == 3

    def test_webhook_requires_valid_program(
        self,
        client_with_calendar,
    ):
        """Webhook returns 404 for non-existent program."""
        response = client_with_calendar.post(
            "/programs/550e8400-e29b-41d4-a716-446655440099/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            headers=make_auth_header(),
        )

        assert response.status_code == 404

    def test_webhook_accepts_x_user_id_header(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Webhook accepts X-User-Id header for service-to-service calls."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "current_week": 1,
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        # Use X-User-Id header instead of Authorization
        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# Calendar Event Mapping Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCalendarEventMapping:
    """Tests for calendar event ID mapping in activation response."""

    def test_activation_returns_event_mapping(
        self,
        client_with_seeded_calendar_repo,
        fake_calendar_client,
        sample_program_with_weeks,
    ):
        """Activation response includes mapping of workout IDs to event IDs."""
        program_id = sample_program_with_weeks["program"]["id"]

        response = client_with_seeded_calendar_repo.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()

        # Should have event mapping
        assert "calendar_event_mapping" in data
        assert data["calendar_event_mapping"] is not None
        assert len(data["calendar_event_mapping"]) == 3  # 3 workouts

        # Each mapping should have workout_id and event_id
        for mapping in data["calendar_event_mapping"]:
            assert "program_workout_id" in mapping
            assert "calendar_event_id" in mapping

    def test_activation_mapping_empty_when_calendar_fails(
        self,
        client_with_failing_calendar,
        fake_program_repo,
        sample_program_with_weeks,
    ):
        """Event mapping is None when calendar service fails."""
        # Seed the program data
        program = sample_program_with_weeks["program"]
        weeks = sample_program_with_weeks["weeks"]
        fake_program_repo.seed([program])
        for week in weeks:
            workouts = week.pop("workouts", [])
            fake_program_repo._weeks[week["id"]] = week
            for workout in workouts:
                fake_program_repo._workouts[workout["id"]] = workout

        program_id = program["id"]

        response = client_with_failing_calendar.post(
            f"/programs/{program_id}/activate",
            json={"start_date": "2026-02-02T00:00:00Z"},
            headers=make_auth_header(),
        )

        assert response.status_code == 200
        data = response.json()

        # Event mapping should be None when calendar fails
        assert data["calendar_event_mapping"] is None
        assert data["scheduled_workouts"] == 0


# ---------------------------------------------------------------------------
# Service Token Authentication Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestServiceTokenAuthentication:
    """Tests for service-to-service authentication on webhook endpoint."""

    def test_webhook_requires_user_identification(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Webhook returns 401 when no user identification is provided."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "current_week": 1,
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        # No Authorization or X-User-Id header
        response = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            # No headers - missing user identification
        )

        assert response.status_code == 401
        assert "user identification" in response.json()["detail"].lower()

    def test_webhook_works_with_both_auth_methods(
        self,
        client_with_calendar,
        fake_program_repo,
    ):
        """Webhook works with either Authorization or X-User-Id header."""
        fake_program_repo.seed([{
            "id": PROGRAM_ID,
            "user_id": TEST_USER_ID,
            "name": "Active Program",
            "status": "active",
            "current_week": 1,
            "goal": "strength",
            "experience_level": "intermediate",
            "duration_weeks": 12,
            "sessions_per_week": 4,
        }])

        # Test with Authorization header
        response1 = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            headers={"Authorization": f"Bearer {TEST_USER_ID}"},
        )
        assert response1.status_code == 200

        # Test with X-User-Id header
        response2 = client_with_calendar.post(
            f"/programs/{PROGRAM_ID}/workout-completed",
            json={
                "event_id": "550e8400-e29b-41d4-a716-446655440001",
                "program_workout_id": "550e8400-e29b-41d4-a716-446655440002",
                "program_week_number": 1,
                "completed_at": "2026-02-02T18:00:00Z",
            },
            headers={"X-User-Id": TEST_USER_ID},
        )
        assert response2.status_code == 200
