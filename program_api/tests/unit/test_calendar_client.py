"""
Unit tests for CalendarClient.

AMA-469: Calendar Integration for Program Workouts

Tests the HTTP client that communicates with Calendar-API for
creating, retrieving, and deleting program workout events.
"""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from infrastructure.calendar_client import (
    BulkCreateResult,
    CalendarAPIError,
    CalendarAPIUnavailable,
    CalendarClient,
    ProgramEventData,
    ProgramEventsResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def calendar_client():
    """Create a CalendarClient instance for testing."""
    return CalendarClient(base_url="http://calendar-api:8001")


@pytest.fixture
def sample_event_data():
    """Create sample ProgramEventData for testing."""
    return ProgramEventData(
        title="Week 1 - Upper Body",
        date=date(2026, 2, 3),
        program_workout_id=uuid4(),
        program_week_number=1,
        type="strength",
        primary_muscle="upper",
        intensity=2,
        json_payload={"exercises": []},
    )


@pytest.fixture
def auth_token():
    """Test authorization token."""
    return "test-auth-token-123"


@pytest.fixture
def program_id():
    """Test program ID."""
    return uuid4()


# ---------------------------------------------------------------------------
# ProgramEventData Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProgramEventData:
    """Tests for ProgramEventData dataclass."""

    def test_to_dict_all_fields(self, sample_event_data):
        """to_dict includes all populated fields."""
        result = sample_event_data.to_dict()

        assert result["title"] == "Week 1 - Upper Body"
        assert result["date"] == "2026-02-03"
        assert result["program_week_number"] == 1
        assert result["type"] == "strength"
        assert result["primary_muscle"] == "upper"
        assert result["intensity"] == 2
        assert result["json_payload"] == {"exercises": []}
        assert "program_workout_id" in result

    def test_to_dict_minimal_fields(self):
        """to_dict excludes None fields."""
        event = ProgramEventData(
            title="Workout",
            date=date(2026, 2, 3),
            program_workout_id=uuid4(),
            program_week_number=1,
        )
        result = event.to_dict()

        assert result["title"] == "Workout"
        assert result["date"] == "2026-02-03"
        assert "type" not in result
        assert "primary_muscle" not in result
        assert "start_time" not in result
        assert "end_time" not in result
        assert "json_payload" not in result


# ---------------------------------------------------------------------------
# CalendarClient Bulk Create Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalendarClientBulkCreate:
    """Tests for bulk_create_program_events."""

    @pytest.mark.asyncio
    async def test_bulk_create_success(
        self, calendar_client, sample_event_data, auth_token, program_id
    ):
        """Successful bulk create returns BulkCreateResult."""
        event_ids = [str(uuid4()), str(uuid4())]
        workout_id = str(sample_event_data.program_workout_id)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "program_id": str(program_id),
            "events_created": 2,
            "event_ids": event_ids,
            "event_mapping": {workout_id: event_ids[0]},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await calendar_client.bulk_create_program_events(
                program_id=program_id,
                events=[sample_event_data, sample_event_data],
                auth_token=auth_token,
            )

        assert isinstance(result, BulkCreateResult)
        assert result.program_id == program_id
        assert result.events_created == 2
        assert len(result.event_ids) == 2

    @pytest.mark.asyncio
    async def test_bulk_create_sends_correct_payload(
        self, calendar_client, sample_event_data, auth_token, program_id
    ):
        """Bulk create sends correct request payload."""
        event_id = str(uuid4())
        workout_id = str(sample_event_data.program_workout_id)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "program_id": str(program_id),
            "events_created": 1,
            "event_ids": [event_id],
            "event_mapping": {workout_id: event_id},
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await calendar_client.bulk_create_program_events(
                program_id=program_id,
                events=[sample_event_data],
                auth_token=auth_token,
            )

            # Verify the request
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "http://calendar-api:8001/program-events/bulk-create"
            assert "Authorization" in call_args[1]["headers"]
            assert call_args[1]["headers"]["Authorization"] == f"Bearer {auth_token}"

    @pytest.mark.asyncio
    async def test_bulk_create_api_error(
        self, calendar_client, sample_event_data, auth_token, program_id
    ):
        """API error raises CalendarAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CalendarAPIError) as exc_info:
                await calendar_client.bulk_create_program_events(
                    program_id=program_id,
                    events=[sample_event_data],
                    auth_token=auth_token,
                )

            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_bulk_create_connection_error(
        self, calendar_client, sample_event_data, auth_token, program_id
    ):
        """Connection error raises CalendarAPIUnavailable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CalendarAPIUnavailable):
                await calendar_client.bulk_create_program_events(
                    program_id=program_id,
                    events=[sample_event_data],
                    auth_token=auth_token,
                )

    @pytest.mark.asyncio
    async def test_bulk_create_timeout(
        self, calendar_client, sample_event_data, auth_token, program_id
    ):
        """Timeout raises CalendarAPIUnavailable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CalendarAPIUnavailable):
                await calendar_client.bulk_create_program_events(
                    program_id=program_id,
                    events=[sample_event_data],
                    auth_token=auth_token,
                )


# ---------------------------------------------------------------------------
# CalendarClient Get Events Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalendarClientGetEvents:
    """Tests for get_program_events."""

    @pytest.mark.asyncio
    async def test_get_events_success(self, calendar_client, auth_token, program_id):
        """Successful get returns ProgramEventsResult."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "program_id": str(program_id),
            "events": [
                {"id": str(uuid4()), "title": "Workout 1", "date": "2026-02-03"},
                {"id": str(uuid4()), "title": "Workout 2", "date": "2026-02-05"},
            ],
            "total": 2,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await calendar_client.get_program_events(
                program_id=program_id,
                auth_token=auth_token,
            )

        assert isinstance(result, ProgramEventsResult)
        assert result.program_id == program_id
        assert result.total == 2
        assert len(result.events) == 2

    @pytest.mark.asyncio
    async def test_get_events_empty(self, calendar_client, auth_token, program_id):
        """Get events returns empty list when no events exist."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "program_id": str(program_id),
            "events": [],
            "total": 0,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await calendar_client.get_program_events(
                program_id=program_id,
                auth_token=auth_token,
            )

        assert result.total == 0
        assert result.events == []

    @pytest.mark.asyncio
    async def test_get_events_connection_error(
        self, calendar_client, auth_token, program_id
    ):
        """Connection error raises CalendarAPIUnavailable."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CalendarAPIUnavailable):
                await calendar_client.get_program_events(
                    program_id=program_id,
                    auth_token=auth_token,
                )


# ---------------------------------------------------------------------------
# CalendarClient Delete Events Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalendarClientDeleteEvents:
    """Tests for delete_program_events."""

    @pytest.mark.asyncio
    async def test_delete_events_success(self, calendar_client, auth_token, program_id):
        """Successful delete returns count of deleted events."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "program_id": str(program_id),
            "events_deleted": 5,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await calendar_client.delete_program_events(
                program_id=program_id,
                auth_token=auth_token,
            )

        assert result == 5

    @pytest.mark.asyncio
    async def test_delete_events_none_to_delete(
        self, calendar_client, auth_token, program_id
    ):
        """Delete returns 0 when no events to delete."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "program_id": str(program_id),
            "events_deleted": 0,
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await calendar_client.delete_program_events(
                program_id=program_id,
                auth_token=auth_token,
            )

        assert result == 0

    @pytest.mark.asyncio
    async def test_delete_events_api_error(
        self, calendar_client, auth_token, program_id
    ):
        """API error raises CalendarAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.delete = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with pytest.raises(CalendarAPIError) as exc_info:
                await calendar_client.delete_program_events(
                    program_id=program_id,
                    auth_token=auth_token,
                )

            assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# CalendarClient Configuration Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCalendarClientConfiguration:
    """Tests for CalendarClient configuration."""

    def test_base_url_trailing_slash_removed(self):
        """Trailing slash is removed from base URL."""
        client = CalendarClient(base_url="http://calendar-api:8001/")
        assert client._base_url == "http://calendar-api:8001"

    def test_custom_timeout(self):
        """Custom timeout can be set."""
        client = CalendarClient(base_url="http://calendar-api:8001", timeout=60.0)
        assert client._timeout == 60.0

    def test_default_timeout(self):
        """Default timeout is 30 seconds."""
        client = CalendarClient(base_url="http://calendar-api:8001")
        assert client._timeout == 30.0
