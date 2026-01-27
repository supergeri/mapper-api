"""
Infrastructure layer package for program-api.

Part of AMA-461: Create program-api service scaffold

This package contains concrete implementations of the port interfaces.
"""

from infrastructure.db import SupabaseProgramRepository
from infrastructure.calendar_client import (
    CalendarClient,
    CalendarClientError,
    CalendarAPIUnavailable,
    CalendarAPIError,
    ProgramEventData,
    BulkCreateResult,
    ProgramEventsResult,
)

__all__ = [
    "SupabaseProgramRepository",
    "CalendarClient",
    "CalendarClientError",
    "CalendarAPIUnavailable",
    "CalendarAPIError",
    "ProgramEventData",
    "BulkCreateResult",
    "ProgramEventsResult",
]
