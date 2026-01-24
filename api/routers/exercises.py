"""
Exercises router for exercise matching and lookup.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

This router provides endpoints for:
- Matching planned exercise names to canonical exercises
- Looking up exercises by ID, muscle group, or equipment
- Batch matching for multiple exercises
"""
import re
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from pydantic import BaseModel, Field

from api.deps import get_exercises_repo, get_exercise_matcher
from application.ports import ExercisesRepository
from backend.core.exercise_matcher import ExerciseMatchingService, ExerciseMatch, MatchMethod

router = APIRouter(
    prefix="/exercises",
    tags=["Exercises"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class MatchRequest(BaseModel):
    """Request model for matching a single exercise name."""
    planned_name: str = Field(..., description="Exercise name from workout plan")


class BatchMatchRequest(BaseModel):
    """Request model for matching multiple exercise names."""
    planned_names: List[str] = Field(
        ...,
        description="List of exercise names to match",
        min_length=1,
        max_length=100,
    )


class MatchResponse(BaseModel):
    """Response model for exercise match result."""
    exercise_id: Optional[str] = Field(None, description="Canonical exercise ID if matched")
    exercise_name: Optional[str] = Field(None, description="Canonical exercise name if matched")
    confidence: float = Field(..., description="Match confidence (0.0 to 1.0)")
    method: str = Field(..., description="How the match was determined")
    reasoning: Optional[str] = Field(None, description="Explanation of match")
    suggested_alias: Optional[str] = Field(None, description="Suggested alias to add")

    @classmethod
    def from_match(cls, match: ExerciseMatch) -> "MatchResponse":
        """Convert ExerciseMatch to response model."""
        return cls(
            exercise_id=match.exercise_id,
            exercise_name=match.exercise_name,
            confidence=match.confidence,
            method=match.method.value,
            reasoning=match.reasoning,
            suggested_alias=match.suggested_alias,
        )


class BatchMatchResponse(BaseModel):
    """Response model for batch exercise matching."""
    matches: List[MatchResponse] = Field(..., description="Match results in same order as input")


class ExerciseResponse(BaseModel):
    """Response model for a single exercise."""
    id: str
    name: str
    aliases: List[str] = Field(default_factory=list)
    primary_muscles: List[str] = Field(default_factory=list)
    secondary_muscles: List[str] = Field(default_factory=list)
    equipment: List[str] = Field(default_factory=list)
    default_weight_source: Optional[str] = None
    supports_1rm: bool = False
    one_rm_formula: Optional[str] = None
    category: Optional[str] = None
    movement_pattern: Optional[str] = None


class ExerciseListResponse(BaseModel):
    """Response model for list of exercises."""
    exercises: List[ExerciseResponse]
    count: int


# =============================================================================
# Matching Endpoints
# =============================================================================


@router.post("/canonical/match", response_model=MatchResponse)
def match_exercise_canonical(
    request: MatchRequest,
    matcher: ExerciseMatchingService = Depends(get_exercise_matcher),
) -> MatchResponse:
    """
    Match a planned exercise name to a canonical exercise.

    This matches to the canonical exercises database (used for progression tracking,
    1RM calculation, muscle group analytics). Different from /exercises/match which
    matches to Garmin exercises.

    Uses a multi-stage matching approach:
    1. Exact name match (confidence: 1.0)
    2. Alias match (confidence: 0.93-0.95)
    3. Fuzzy match with rapidfuzz (confidence: based on score)
    4. LLM fallback (if enabled, confidence: based on LLM)

    Returns the best match found, or no match if confidence is too low.
    """
    match = matcher.match(request.planned_name)
    return MatchResponse.from_match(match)


@router.post("/canonical/match/batch", response_model=BatchMatchResponse)
def match_exercises_canonical_batch(
    request: BatchMatchRequest,
    matcher: ExerciseMatchingService = Depends(get_exercise_matcher),
) -> BatchMatchResponse:
    """
    Match multiple planned exercise names to canonical exercises.

    Returns matches in the same order as the input names.
    More efficient than calling /canonical/match multiple times.
    """
    matches = matcher.match_batch(request.planned_names)
    return BatchMatchResponse(
        matches=[MatchResponse.from_match(m) for m in matches]
    )


@router.get("/canonical/suggest", response_model=List[MatchResponse])
def suggest_canonical_matches(
    planned_name: str = Query(..., description="Exercise name to get suggestions for"),
    limit: int = Query(5, ge=1, le=20, description="Maximum suggestions to return"),
    matcher: ExerciseMatchingService = Depends(get_exercise_matcher),
) -> List[MatchResponse]:
    """
    Get top matching suggestions from canonical exercises.

    Returns multiple candidates sorted by confidence.
    Useful for showing alternatives to the user.
    """
    suggestions = matcher.suggest_matches(planned_name, limit=limit)
    return [MatchResponse.from_match(s) for s in suggestions]


# =============================================================================
# Lookup Endpoints
# =============================================================================


# Valid exercise ID pattern: lowercase letters, numbers, and hyphens
EXERCISE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$|^[a-z0-9]$")


@router.get("/{exercise_id}", response_model=ExerciseResponse)
def get_exercise(
    exercise_id: str = Path(
        ...,
        description="Exercise slug (e.g., 'barbell-bench-press')",
        min_length=1,
        max_length=100,
    ),
    repo: ExercisesRepository = Depends(get_exercises_repo),
) -> ExerciseResponse:
    """
    Get a canonical exercise by ID.

    Args:
        exercise_id: The exercise slug (e.g., "barbell-bench-press")
    """
    # Validate exercise_id format
    if not EXERCISE_ID_PATTERN.match(exercise_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid exercise_id format. Use lowercase letters, numbers, and hyphens only."
        )

    exercise = repo.get_by_id(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail=f"Exercise '{exercise_id}' not found")
    return ExerciseResponse(**exercise)


@router.get("", response_model=ExerciseListResponse)
def list_exercises(
    muscle: Optional[str] = Query(None, description="Filter by primary muscle group"),
    equipment: Optional[str] = Query(None, description="Filter by equipment type"),
    category: Optional[str] = Query(
        None,
        description="Filter by category",
        enum=["compound", "isolation", "cardio"],
    ),
    supports_1rm: Optional[bool] = Query(None, description="Filter by 1RM support"),
    search: Optional[str] = Query(None, description="Search by name pattern"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    repo: ExercisesRepository = Depends(get_exercises_repo),
) -> ExerciseListResponse:
    """
    List canonical exercises with optional filters.

    Filters can be combined. All specified filters are applied together (AND logic).
    """
    # Start with base query based on primary filter
    if search:
        # Search by name pattern first
        exercises = repo.search_by_name_pattern(f"%{search}%", limit=500)
    elif muscle:
        exercises = repo.find_by_muscle_group(muscle, limit=500)
    elif equipment:
        exercises = repo.find_by_equipment(equipment, limit=500)
    elif supports_1rm is True and category is None:
        exercises = repo.find_exercises_supporting_1rm(limit=500)
    elif category == "compound" and supports_1rm is None:
        exercises = repo.find_compound_exercises(limit=500)
    else:
        # Get all exercises for combined filtering
        exercises = repo.get_all(limit=500)

    # Apply additional filters (combined AND logic)
    if muscle and not search:
        # Already filtered by muscle in primary query
        pass
    elif muscle:
        exercises = [e for e in exercises if muscle in e.get("primary_muscles", [])]

    if equipment and not (not search and not muscle):
        exercises = [e for e in exercises if equipment in e.get("equipment", [])]

    if category:
        exercises = [e for e in exercises if e.get("category") == category]

    if supports_1rm is not None:
        exercises = [e for e in exercises if e.get("supports_1rm") == supports_1rm]

    # Apply limit after all filters
    exercises = exercises[:limit]

    return ExerciseListResponse(
        exercises=[ExerciseResponse(**e) for e in exercises],
        count=len(exercises),
    )
