"""
Detection router for workout auto-detection endpoint.

Part of AMA-688: Auto-detection endpoint for matching detected exercises
against user's scheduled AmakaFlow workouts.
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_user, get_workout_repo
from application.ports import WorkoutRepository
from backend.schemas.detection import DetectionRequest, DetectionMatch
from application.use_cases.match_workout import MatchWorkoutUseCase

router = APIRouter(
    prefix="/workouts",
    tags=["Detection"],
)


def get_match_workout_use_case(
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
) -> MatchWorkoutUseCase:
    """Get a MatchWorkoutUseCase instance."""
    return MatchWorkoutUseCase(workout_repository=workout_repo)


@router.post("/detect", response_model=DetectionMatch)
async def detect_workout(
    request: DetectionRequest,
    user_id: str = Depends(get_current_user),
    match_workout_use_case: MatchWorkoutUseCase = Depends(get_match_workout_use_case),
) -> DetectionMatch:
    """
    Detect and match a workout based on wearable device sensor data.

    When a wearable device detects exercise patterns on-device, it calls this
    endpoint to match the detected activity against the user's scheduled
    AmakaFlow workouts.

    Returns the best match if confidence exceeds 0.85, otherwise returns a
    no-match with a reason code:
    - "no_scheduled_workout": No workouts in ±2h window
    - "sport_mismatch": Workouts found but sport doesn't match
    - "low_confidence": Workouts found and sport matched, but score ≤ 0.85
    """
    return await match_workout_use_case.execute(request)
