"""
Infrastructure layer package for program-api.

Part of AMA-461: Create program-api service scaffold

This package contains concrete implementations of the port interfaces.
"""

from infrastructure.db import SupabaseProgramRepository

__all__ = [
    "SupabaseProgramRepository",
]
