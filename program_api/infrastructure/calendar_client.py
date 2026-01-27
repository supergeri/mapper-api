"""
HTTP client for Calendar-API integration.

AMA-469: Calendar Integration for Program Workouts

This client handles communication with the Calendar-API service for
creating, retrieving, and deleting program workout events on the user's
calendar.
"""

import logging
from dataclasses import dataclass
from datetime import date, time
from typing import Any, Optional
from uuid import UUID

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProgramEventData:
    """Data for a single program calendar event."""

    title: str
    date: date
    program_workout_id: UUID
    program_week_number: int
    type: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    primary_muscle: Optional[str] = None
    intensity: int = 1
    json_payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API request."""
        data = {
            "title": self.title,
            "date": self.date.isoformat(),
            "program_workout_id": str(self.program_workout_id),
            "program_week_number": self.program_week_number,
            "intensity": self.intensity,
        }

        if self.type:
            data["type"] = self.type
        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.end_time:
            data["end_time"] = self.end_time.isoformat()
        if self.primary_muscle:
            data["primary_muscle"] = self.primary_muscle
        if self.json_payload:
            data["json_payload"] = self.json_payload

        return data


@dataclass
class BulkCreateResult:
    """Result from bulk creating program events."""

    program_id: UUID
    events_created: int
    event_ids: list[UUID]
    event_mapping: dict[str, str]  # program_workout_id -> calendar_event_id


@dataclass
class ProgramEventsResult:
    """Result from fetching program events."""

    program_id: UUID
    events: list[dict[str, Any]]
    total: int


class CalendarClientError(Exception):
    """Base exception for calendar client errors."""

    pass


class CalendarAPIUnavailable(CalendarClientError):
    """Raised when Calendar-API is unavailable."""

    pass


class CalendarAPIError(CalendarClientError):
    """Raised when Calendar-API returns an error."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class CalendarClient:
    """
    HTTP client for Calendar-API communication.

    Handles program event creation, retrieval, and deletion via the
    Calendar-API's /program-events endpoints.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
    ):
        """
        Initialize the calendar client.

        Args:
            base_url: Base URL of the Calendar-API (e.g., "http://calendar-api:8001")
            timeout: Request timeout in seconds
        """
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def bulk_create_program_events(
        self,
        program_id: UUID,
        events: list[ProgramEventData],
        auth_token: str,
    ) -> BulkCreateResult:
        """
        Create calendar events for a training program.

        Args:
            program_id: The training program UUID
            events: List of events to create
            auth_token: User's authorization token (JWT)

        Returns:
            BulkCreateResult with count and IDs of created events

        Raises:
            CalendarAPIUnavailable: If Calendar-API is not reachable
            CalendarAPIError: If Calendar-API returns an error response
        """
        url = f"{self._base_url}/program-events/bulk-create"

        payload = {
            "program_id": str(program_id),
            "events": [event.to_dict() for event in events],
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 201:
                    data = response.json()
                    return BulkCreateResult(
                        program_id=UUID(data["program_id"]),
                        events_created=data["events_created"],
                        event_ids=[UUID(eid) for eid in data["event_ids"]],
                        event_mapping=data.get("event_mapping", {}),
                    )
                else:
                    logger.error(
                        f"Calendar-API error: {response.status_code} - {response.text}"
                    )
                    raise CalendarAPIError(
                        f"Failed to create program events: {response.text}",
                        response.status_code,
                    )

        except httpx.ConnectError as e:
            logger.error(f"Calendar-API unavailable: {e}")
            raise CalendarAPIUnavailable(
                f"Calendar-API is not available at {self._base_url}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Calendar-API timeout: {e}")
            raise CalendarAPIUnavailable(
                "Calendar-API request timed out"
            ) from e

    async def get_program_events(
        self,
        program_id: UUID,
        auth_token: str,
    ) -> ProgramEventsResult:
        """
        Get all calendar events for a training program.

        Args:
            program_id: The training program UUID
            auth_token: User's authorization token (JWT)

        Returns:
            ProgramEventsResult with list of events

        Raises:
            CalendarAPIUnavailable: If Calendar-API is not reachable
            CalendarAPIError: If Calendar-API returns an error response
        """
        url = f"{self._base_url}/program-events/{program_id}"

        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return ProgramEventsResult(
                        program_id=UUID(data["program_id"]),
                        events=data["events"],
                        total=data["total"],
                    )
                else:
                    logger.error(
                        f"Calendar-API error: {response.status_code} - {response.text}"
                    )
                    raise CalendarAPIError(
                        f"Failed to get program events: {response.text}",
                        response.status_code,
                    )

        except httpx.ConnectError as e:
            logger.error(f"Calendar-API unavailable: {e}")
            raise CalendarAPIUnavailable(
                f"Calendar-API is not available at {self._base_url}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Calendar-API timeout: {e}")
            raise CalendarAPIUnavailable(
                "Calendar-API request timed out"
            ) from e

    async def delete_program_events(
        self,
        program_id: UUID,
        auth_token: str,
    ) -> int:
        """
        Delete all calendar events for a training program.

        Args:
            program_id: The training program UUID
            auth_token: User's authorization token (JWT)

        Returns:
            Number of events deleted

        Raises:
            CalendarAPIUnavailable: If Calendar-API is not reachable
            CalendarAPIError: If Calendar-API returns an error response
        """
        url = f"{self._base_url}/program-events/{program_id}"

        headers = {
            "Authorization": f"Bearer {auth_token}",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.delete(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    return data.get("events_deleted", 0)
                else:
                    logger.error(
                        f"Calendar-API error: {response.status_code} - {response.text}"
                    )
                    raise CalendarAPIError(
                        f"Failed to delete program events: {response.text}",
                        response.status_code,
                    )

        except httpx.ConnectError as e:
            logger.error(f"Calendar-API unavailable: {e}")
            raise CalendarAPIUnavailable(
                f"Calendar-API is not available at {self._base_url}"
            ) from e
        except httpx.TimeoutException as e:
            logger.error(f"Calendar-API timeout: {e}")
            raise CalendarAPIUnavailable(
                "Calendar-API request timed out"
            ) from e
