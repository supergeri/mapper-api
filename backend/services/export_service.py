"""Export service for centralizing workout format conversions."""

import logging
from typing import Any, Dict, Optional

from backend.settings import Settings

logger = logging.getLogger(__name__)


class ExportService:
    """Centralizes all workout format conversion logic."""

    def __init__(self, settings: Settings):
        self._mapper_url = settings.mapper_api_url

    def is_hiit_workout(self, workout: Dict[str, Any]) -> bool:
        """Check if a workout qualifies as HIIT based on its structure."""
        # TODO: implement - move logic from exports router
        raise NotImplementedError

    def to_workoutkit(self, workout: Dict[str, Any]) -> Dict[str, Any]:
        """Convert workout to Apple WorkoutKit format."""
        # TODO: implement - move logic from exports router
        raise NotImplementedError

    def get_fit_metadata(self, workout: Dict[str, Any]) -> Dict[str, Any]:
        """Get FIT file metadata for a workout."""
        # TODO: implement - move logic from exports router
        raise NotImplementedError
