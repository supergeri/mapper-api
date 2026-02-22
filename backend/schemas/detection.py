"""
Detection schemas for wearable device workout detection.

Part of AMA-688: Auto-detection endpoint for matching detected exercises
against user's scheduled AmakaFlow workouts.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DetectionRequest(BaseModel):
    """Request body for workout detection endpoint."""

    user_id: str
    device: str  # "apple_watch" | "garmin" | "wear_os"
    timestamp: datetime
    sport: str  # "strength" | "running" | "cycling" | "cardio" | "unknown"
    detected_exercises: list[str]  # e.g. ["squat", "deadlift"]
    hr_bpm: Optional[float] = None
    motion_variance: Optional[float] = None
    classifier_confidence: Optional[float] = None


class DetectionMatch(BaseModel):
    """Response for workout detection endpoint."""

    matched: bool
    workout_id: Optional[str] = None
    workout_name: Optional[str] = None
    confidence: Optional[float] = None
    match_reason: Optional[str] = None
    reason: Optional[str] = None  # "no_scheduled_workout" | "low_confidence" | "sport_mismatch"
