"""
Fake calendar client for testing.

AMA-469: Calendar Integration for Program Workouts

This fake implementation stores calendar events in memory and provides
helper methods for test setup and verification.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from infrastructure.calendar_client import (
    BulkCreateResult,
    CalendarAPIError,
    CalendarAPIUnavailable,
    ProgramEventData,
    ProgramEventsResult,
)


@dataclass
class StoredEvent:
    """An event stored in the fake calendar."""

    id: UUID
    user_id: str
    program_id: UUID
    program_workout_id: UUID
    program_week_number: int
    title: str
    date: date
    type: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    primary_muscle: Optional[str] = None
    intensity: int = 1
    json_payload: Optional[Dict[str, Any]] = None
    status: str = "planned"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "program_id": str(self.program_id),
            "program_workout_id": str(self.program_workout_id),
            "program_week_number": self.program_week_number,
            "title": self.title,
            "date": self.date.isoformat(),
            "type": self.type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "primary_muscle": self.primary_muscle,
            "intensity": self.intensity,
            "json_payload": self.json_payload,
            "status": self.status,
            "source": "training_program",
        }


class FakeCalendarClient:
    """
    In-memory fake implementation of CalendarClient.

    Provides the same interface as CalendarClient but stores
    events in memory for fast, isolated testing.
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._events: Dict[UUID, StoredEvent] = {}
        self._user_id: str = "test-user-123"
        self._fail_next_call: bool = False
        self._fail_with_unavailable: bool = False
        self._call_count: int = 0
        self._last_request: Optional[Dict[str, Any]] = None

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    def set_user_id(self, user_id: str) -> None:
        """Set the user ID for created events."""
        self._user_id = user_id

    def seed(self, events: List[Dict[str, Any]]) -> None:
        """
        Seed the fake with existing events.

        Args:
            events: List of event dictionaries to add
        """
        for event in events:
            event_id = UUID(event.get("id", str(uuid4())))
            self._events[event_id] = StoredEvent(
                id=event_id,
                user_id=event.get("user_id", self._user_id),
                program_id=UUID(event["program_id"]),
                program_workout_id=UUID(event["program_workout_id"]),
                program_week_number=event["program_week_number"],
                title=event["title"],
                date=event["date"] if isinstance(event["date"], date) else date.fromisoformat(event["date"]),
                type=event.get("type"),
                primary_muscle=event.get("primary_muscle"),
                intensity=event.get("intensity", 1),
                json_payload=event.get("json_payload"),
                status=event.get("status", "planned"),
            )

    def reset(self) -> None:
        """Clear all stored events and reset state."""
        self._events.clear()
        self._fail_next_call = False
        self._fail_with_unavailable = False
        self._call_count = 0
        self._last_request = None

    def get_all_events(self) -> List[StoredEvent]:
        """Get all stored events (for test verification)."""
        return list(self._events.values())

    def get_events_for_program(self, program_id: UUID) -> List[StoredEvent]:
        """Get events for a specific program."""
        return [e for e in self._events.values() if e.program_id == program_id]

    def count(self) -> int:
        """Get count of stored events."""
        return len(self._events)

    def simulate_failure(self, unavailable: bool = False) -> None:
        """
        Configure the next call to fail.

        Args:
            unavailable: If True, raise CalendarAPIUnavailable; otherwise CalendarAPIError
        """
        self._fail_next_call = True
        self._fail_with_unavailable = unavailable

    # -------------------------------------------------------------------------
    # CalendarClient Interface Implementation
    # -------------------------------------------------------------------------

    async def bulk_create_program_events(
        self,
        program_id: UUID,
        events: List[ProgramEventData],
        auth_token: str,
    ) -> BulkCreateResult:
        """
        Create calendar events for a training program.

        Args:
            program_id: The training program UUID
            events: List of events to create
            auth_token: User's authorization token (unused in fake)

        Returns:
            BulkCreateResult with count and IDs of created events
        """
        self._call_count += 1
        self._last_request = {
            "method": "bulk_create",
            "program_id": program_id,
            "events": events,
            "auth_token": auth_token,
        }

        if self._fail_next_call:
            self._fail_next_call = False
            if self._fail_with_unavailable:
                raise CalendarAPIUnavailable("Simulated unavailable")
            raise CalendarAPIError("Simulated error", 500)

        created_ids = []
        for event in events:
            event_id = uuid4()
            stored = StoredEvent(
                id=event_id,
                user_id=self._user_id,
                program_id=program_id,
                program_workout_id=event.program_workout_id,
                program_week_number=event.program_week_number,
                title=event.title,
                date=event.date,
                type=event.type,
                primary_muscle=event.primary_muscle,
                intensity=event.intensity,
                json_payload=event.json_payload,
            )
            self._events[event_id] = stored
            created_ids.append(event_id)

        # Build explicit mapping: program_workout_id -> calendar_event_id
        event_mapping = {}
        for event, event_id in zip(events, created_ids):
            event_mapping[str(event.program_workout_id)] = str(event_id)

        return BulkCreateResult(
            program_id=program_id,
            events_created=len(created_ids),
            event_ids=created_ids,
            event_mapping=event_mapping,
        )

    async def get_program_events(
        self,
        program_id: UUID,
        auth_token: str,
    ) -> ProgramEventsResult:
        """
        Get all calendar events for a training program.

        Args:
            program_id: The training program UUID
            auth_token: User's authorization token (unused in fake)

        Returns:
            ProgramEventsResult with list of events
        """
        self._call_count += 1
        self._last_request = {
            "method": "get_events",
            "program_id": program_id,
            "auth_token": auth_token,
        }

        if self._fail_next_call:
            self._fail_next_call = False
            if self._fail_with_unavailable:
                raise CalendarAPIUnavailable("Simulated unavailable")
            raise CalendarAPIError("Simulated error", 500)

        program_events = [
            e.to_dict() for e in self._events.values()
            if e.program_id == program_id and e.user_id == self._user_id
        ]

        return ProgramEventsResult(
            program_id=program_id,
            events=program_events,
            total=len(program_events),
        )

    async def delete_program_events(
        self,
        program_id: UUID,
        auth_token: str,
    ) -> int:
        """
        Delete all calendar events for a training program.

        Args:
            program_id: The training program UUID
            auth_token: User's authorization token (unused in fake)

        Returns:
            Number of events deleted
        """
        self._call_count += 1
        self._last_request = {
            "method": "delete_events",
            "program_id": program_id,
            "auth_token": auth_token,
        }

        if self._fail_next_call:
            self._fail_next_call = False
            if self._fail_with_unavailable:
                raise CalendarAPIUnavailable("Simulated unavailable")
            raise CalendarAPIError("Simulated error", 500)

        to_delete = [
            event_id for event_id, event in self._events.items()
            if event.program_id == program_id and event.user_id == self._user_id
        ]

        for event_id in to_delete:
            del self._events[event_id]

        return len(to_delete)


class FailingCalendarClient(FakeCalendarClient):
    """
    A calendar client that always fails.

    Useful for testing error handling scenarios.
    """

    def __init__(self, unavailable: bool = True):
        """
        Initialize with failure mode.

        Args:
            unavailable: If True, raise CalendarAPIUnavailable; otherwise CalendarAPIError
        """
        super().__init__()
        self._always_fail = True
        self._fail_with_unavailable = unavailable

    async def bulk_create_program_events(self, *args, **kwargs) -> BulkCreateResult:
        """Always fails."""
        self._call_count += 1
        if self._fail_with_unavailable:
            raise CalendarAPIUnavailable("Calendar service unavailable")
        raise CalendarAPIError("Calendar service error", 500)

    async def get_program_events(self, *args, **kwargs) -> ProgramEventsResult:
        """Always fails."""
        self._call_count += 1
        if self._fail_with_unavailable:
            raise CalendarAPIUnavailable("Calendar service unavailable")
        raise CalendarAPIError("Calendar service error", 500)

    async def delete_program_events(self, *args, **kwargs) -> int:
        """Always fails."""
        self._call_count += 1
        if self._fail_with_unavailable:
            raise CalendarAPIUnavailable("Calendar service unavailable")
        raise CalendarAPIError("Calendar service error", 500)
