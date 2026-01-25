"""
Progression tracking router.

Part of AMA-461: Create program-api service scaffold

This router provides endpoints for tracking exercise progression:
- Get exercise history
- Record exercise performance

Note: These are stubs that will be implemented in future tickets.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import get_current_user

router = APIRouter(
    prefix="/progression",
    tags=["Progression"],
)


class ExerciseHistoryEntry(BaseModel):
    """A single exercise performance record."""

    exercise_id: UUID
    weight: float
    reps: int
    sets: int
    recorded_at: str


class RecordPerformanceRequest(BaseModel):
    """Request to record exercise performance."""

    exercise_id: UUID
    weight: float
    reps: int
    sets: int


@router.get("/history/{exercise_id}", response_model=List[ExerciseHistoryEntry])
async def get_exercise_history(
    exercise_id: UUID,
    user_id: str = Depends(get_current_user),
):
    """
    Get the performance history for a specific exercise.

    Args:
        exercise_id: The exercise UUID

    Returns:
        List of performance records for the exercise
    """
    # Stub: Will be implemented in future tickets
    return []


@router.post("/history", response_model=ExerciseHistoryEntry, status_code=201)
async def record_performance(
    request: RecordPerformanceRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Record a new exercise performance.

    Args:
        request: The performance data

    Returns:
        The created performance record
    """
    # Stub: Will be implemented in future tickets
    raise HTTPException(status_code=501, detail="Not implemented")
