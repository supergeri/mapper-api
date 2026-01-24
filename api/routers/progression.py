"""
Progression router for exercise history and analytics.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

This router provides endpoints for:
- Exercise history with set details and 1RM calculations
- Personal records (1RM, max weight, max reps)
- "Use Last Weight" for companion apps
- Volume analytics by muscle group
"""
import re
from dataclasses import asdict
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from api.deps import get_current_user, get_progression_service
from backend.core.progression_service import (
    ProgressionService,
    ExerciseHistoryResponse,
    PersonalRecordResponse,
    LastWeightResponse,
    VolumeAnalyticsResponse,
)

router = APIRouter(
    prefix="/progression",
    tags=["Progression"],
)


# =============================================================================
# Response Models
# =============================================================================


class SetDetailResponse(BaseModel):
    """Response model for a single set."""
    set_number: int
    weight: Optional[float] = None
    weight_unit: str = "lbs"
    reps_completed: Optional[int] = None
    reps_planned: Optional[int] = None
    status: str = "completed"
    estimated_1rm: Optional[float] = None
    is_pr: bool = False


class SessionResponse(BaseModel):
    """Response model for an exercise session."""
    completion_id: str
    workout_date: str
    workout_name: Optional[str] = None
    exercise_name: str
    sets: List[SetDetailResponse] = Field(default_factory=list)
    session_best_1rm: Optional[float] = None
    session_max_weight: Optional[float] = None
    session_total_volume: Optional[float] = None


class ExerciseHistoryApiResponse(BaseModel):
    """Response model for exercise history endpoint."""
    exercise_id: str
    exercise_name: str
    supports_1rm: bool = False
    one_rm_formula: str = "brzycki"
    sessions: List[SessionResponse] = Field(default_factory=list)
    total_sessions: int
    all_time_best_1rm: Optional[float] = None
    all_time_max_weight: Optional[float] = None


class PersonalRecordItem(BaseModel):
    """A single personal record."""
    exercise_id: str
    exercise_name: str
    record_type: str  # "1rm", "max_weight", "max_reps"
    value: float
    unit: str  # "lbs", "kg", "reps"
    achieved_at: Optional[str] = None
    completion_id: Optional[str] = None
    details: Optional[dict] = None


class PersonalRecordsApiResponse(BaseModel):
    """Response model for personal records endpoint."""
    records: List[PersonalRecordItem]
    exercise_id: Optional[str] = None


class LastWeightApiResponse(BaseModel):
    """Response model for last weight endpoint."""
    exercise_id: str
    exercise_name: str
    weight: float
    weight_unit: str
    reps_completed: int
    workout_date: str
    completion_id: str


class VolumeDataPoint(BaseModel):
    """A single volume data point."""
    period: str
    muscle_group: str
    total_volume: float
    total_sets: int
    total_reps: int


class VolumeAnalyticsApiResponse(BaseModel):
    """Response model for volume analytics endpoint."""
    data: List[VolumeDataPoint]
    summary: dict
    period: dict
    granularity: str


class ExerciseWithHistory(BaseModel):
    """An exercise that the user has history for."""
    exercise_id: str
    exercise_name: str
    session_count: int


class ExercisesWithHistoryResponse(BaseModel):
    """Response model for exercises with history endpoint."""
    exercises: List[ExerciseWithHistory]
    total: int


# =============================================================================
# Endpoints
# =============================================================================


# Valid exercise ID pattern: lowercase letters, numbers, and hyphens
EXERCISE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


def _validate_exercise_id(exercise_id: str) -> None:
    """Validate exercise ID format."""
    if not EXERCISE_ID_PATTERN.match(exercise_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid exercise_id format. Use lowercase letters, numbers, and hyphens only."
        )


@router.get("/exercises", response_model=ExercisesWithHistoryResponse)
async def get_exercises_with_history(
    limit: int = Query(50, ge=1, le=200, description="Maximum exercises to return"),
    user_id: str = Depends(get_current_user),
    service: ProgressionService = Depends(get_progression_service),
) -> ExercisesWithHistoryResponse:
    """
    Get exercises that the user has performed.

    Returns a list of exercises where the user has at least one completed
    session with weight data, sorted by most frequently performed.
    """
    exercises = service.get_exercises_with_history(user_id, limit=limit)
    return ExercisesWithHistoryResponse(
        exercises=[ExerciseWithHistory(**e) for e in exercises],
        total=len(exercises),
    )


@router.get("/exercises/{exercise_id}/history", response_model=ExerciseHistoryApiResponse)
async def get_exercise_history(
    exercise_id: str = Path(..., description="Canonical exercise ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum sessions to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_id: str = Depends(get_current_user),
    service: ProgressionService = Depends(get_progression_service),
) -> ExerciseHistoryApiResponse:
    """
    Get the history of a specific exercise.

    Returns sessions where the exercise was performed, ordered by date descending.
    Each session includes all sets with weight, reps, and calculated estimated 1RM.
    """
    _validate_exercise_id(exercise_id)

    result = service.get_exercise_history(
        user_id,
        exercise_id,
        limit=limit,
        offset=offset,
    )

    if result is None:
        raise HTTPException(status_code=404, detail=f"Exercise '{exercise_id}' not found")

    # Convert dataclass to response model
    sessions = []
    for session in result.sessions:
        sets = [
            SetDetailResponse(
                set_number=s.set_number,
                weight=s.weight,
                weight_unit=s.weight_unit,
                reps_completed=s.reps_completed,
                reps_planned=s.reps_planned,
                status=s.status,
                estimated_1rm=s.estimated_1rm,
                is_pr=s.is_pr,
            )
            for s in session.sets
        ]
        sessions.append(SessionResponse(
            completion_id=session.completion_id,
            workout_date=session.workout_date,
            workout_name=session.workout_name,
            exercise_name=session.exercise_name,
            sets=sets,
            session_best_1rm=session.session_best_1rm,
            session_max_weight=session.session_max_weight,
            session_total_volume=session.session_total_volume,
        ))

    return ExerciseHistoryApiResponse(
        exercise_id=result.exercise_id,
        exercise_name=result.exercise_name,
        supports_1rm=result.supports_1rm,
        one_rm_formula=result.one_rm_formula,
        sessions=sessions,
        total_sessions=result.total_sessions,
        all_time_best_1rm=result.all_time_best_1rm,
        all_time_max_weight=result.all_time_max_weight,
    )


@router.get("/exercises/{exercise_id}/last-weight", response_model=LastWeightApiResponse)
async def get_last_weight(
    exercise_id: str = Path(..., description="Canonical exercise ID"),
    user_id: str = Depends(get_current_user),
    service: ProgressionService = Depends(get_progression_service),
) -> LastWeightApiResponse:
    """
    Get the last weight used for an exercise.

    Returns the most recent completed set with a weight value.
    Used for the "Use Last Weight" feature in companion apps.
    """
    _validate_exercise_id(exercise_id)

    result = service.get_last_weight(user_id, exercise_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No weight history found for exercise '{exercise_id}'"
        )

    return LastWeightApiResponse(
        exercise_id=result.exercise_id,
        exercise_name=result.exercise_name,
        weight=result.weight,
        weight_unit=result.weight_unit,
        reps_completed=result.reps_completed,
        workout_date=result.workout_date,
        completion_id=result.completion_id,
    )


@router.get("/records", response_model=PersonalRecordsApiResponse)
async def get_personal_records(
    record_type: Optional[str] = Query(
        None,
        description="Filter by record type",
        enum=["1rm", "max_weight", "max_reps"],
    ),
    exercise_id: Optional[str] = Query(None, description="Filter by exercise ID"),
    limit: int = Query(20, ge=1, le=100, description="Maximum records to return"),
    user_id: str = Depends(get_current_user),
    service: ProgressionService = Depends(get_progression_service),
) -> PersonalRecordsApiResponse:
    """
    Get personal records for the user.

    Calculates records from all exercise history:
    - 1rm: Best estimated 1RM (calculated from weight/reps)
    - max_weight: Heaviest weight lifted
    - max_reps: Most reps at any weight
    """
    if exercise_id:
        _validate_exercise_id(exercise_id)

    result = service.get_personal_records(
        user_id,
        record_type=record_type,
        exercise_id=exercise_id,
        limit=limit,
    )

    return PersonalRecordsApiResponse(
        records=[PersonalRecordItem(**r) for r in result.records],
        exercise_id=result.exercise_id,
    )


@router.get("/volume", response_model=VolumeAnalyticsApiResponse)
async def get_volume_analytics(
    start_date: Optional[date] = Query(None, description="Start of date range (default: 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End of date range (default: today)"),
    granularity: str = Query(
        "daily",
        description="Time granularity",
        enum=["daily", "weekly", "monthly"],
    ),
    muscle_groups: Optional[str] = Query(
        None,
        description="Comma-separated muscle groups to filter",
    ),
    user_id: str = Depends(get_current_user),
    service: ProgressionService = Depends(get_progression_service),
) -> VolumeAnalyticsApiResponse:
    """
    Get training volume analytics by muscle group.

    Returns total volume (weight * reps) for each muscle group
    over the specified time period, aggregated by the specified granularity.
    """
    # Parse muscle groups
    parsed_muscles = None
    if muscle_groups:
        parsed_muscles = [m.strip() for m in muscle_groups.split(",") if m.strip()]

    result = service.get_volume_analytics(
        user_id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        muscle_groups=parsed_muscles,
    )

    return VolumeAnalyticsApiResponse(
        data=[VolumeDataPoint(**d) for d in result.data],
        summary=result.summary,
        period=result.period,
        granularity=result.granularity,
    )
