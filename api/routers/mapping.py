"""
Mapping router for exercise mapping and transformation endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-379: Move mapping endpoints from app.py
Updated in AMA-380: Move export endpoints to exports.py

This router contains endpoints for:
- /workflow/* - Workout validation and processing
- /exercise/* - Exercise suggestions and matching
- /exercises/* - Exercise matching API
- /mappings/* - User mapping management
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter
from pydantic import BaseModel

# Import exercise matching
from backend.core.exercise_suggestions import (
    suggest_alternatives,
    find_similar_exercises,
    find_exercises_by_type,
    categorize_exercise,
)

# Import workflow processing
from backend.core.workflow import validate_workout_mapping, process_workout_with_validation

# Import user mappings
from backend.core.user_mappings import (
    add_user_mapping,
    remove_user_mapping,
    get_user_mapping,
    get_all_user_mappings,
    clear_all_user_mappings,
)
from backend.core.global_mappings import (
    record_mapping_choice,
    get_popular_mappings,
    get_popularity_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Mapping"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class BlocksPayload(BaseModel):
    """Payload for blocks format used by workflow endpoints."""
    blocks_json: dict


class ExerciseSuggestionRequest(BaseModel):
    """Request for exercise suggestions."""
    exercise_name: str
    include_similar_types: bool = True


class UserMappingRequest(BaseModel):
    """Request for user mapping operations."""
    exercise_name: str
    garmin_name: str


class ExerciseMatchRequest(BaseModel):
    """Request for single exercise matching."""
    name: str
    limit: int = 5


class ExerciseMatchBatchRequest(BaseModel):
    """Request for batch exercise matching."""
    names: List[str]
    limit: int = 5


class ExerciseMatchResult(BaseModel):
    """Result of exercise matching."""
    original_name: str
    matched_name: Optional[str] = None
    confidence: float = 0
    status: str = "unmapped"  # matched, needs_review, unmapped
    suggestions: List[Dict[str, Any]] = []


class ExerciseMatchBatchResponse(BaseModel):
    """Response for batch exercise matching."""
    results: List[ExerciseMatchResult]
    total: int
    matched: int
    needs_review: int
    unmapped: int


# =============================================================================
# Workflow Endpoints
# =============================================================================


@router.post("/workflow/validate")
def validate_workout(p: BlocksPayload):
    """Validate workout mapping and identify exercises needing review."""
    validation = validate_workout_mapping(p.blocks_json)

    unmapped = validation.get("unmapped_exercises", [])
    if unmapped:
        logger.warning(
            f"Validation found {len(unmapped)} unmapped exercises out of "
            f"{validation.get('total_exercises', 0)} total"
        )
        for ex in unmapped:
            suggestions = ex.get("suggestions", [])
            top_suggestion = suggestions[0] if suggestions else None
            logger.debug(
                f"Unmapped: '{ex.get('original_name')}' "
                f"(confidence: {ex.get('confidence', 0):.2f}, "
                f"top suggestion: {top_suggestion['name'] if top_suggestion else 'none'})"
            )

    return validation


@router.post("/workflow/process")
def process_workout(p: BlocksPayload, auto_proceed: bool = True):
    """Complete workflow: validate exercises and generate YAML.

    Defaults to auto-proceed with best matches.
    """
    result = process_workout_with_validation(p.blocks_json, auto_proceed=auto_proceed)
    return result


@router.post("/workflow/process-with-review")
def process_workout_with_review(p: BlocksPayload):
    """Process workout but require review of unmapped exercises (stricter validation)."""
    result = process_workout_with_validation(p.blocks_json, auto_proceed=False)
    return result


# =============================================================================
# Exercise Suggestion Endpoints
# =============================================================================


@router.post("/exercise/suggest")
def suggest_exercise(p: ExerciseSuggestionRequest):
    """Get exercise suggestions and alternatives from Garmin database."""
    suggestions = suggest_alternatives(
        p.exercise_name,
        include_similar_types=p.include_similar_types
    )
    return suggestions


@router.get("/exercise/similar/{exercise_name}")
def get_similar_exercises_endpoint(exercise_name: str, limit: int = 10):
    """Get similar exercises to the given name."""
    return {
        "exercise_name": exercise_name,
        "similar": find_similar_exercises(exercise_name, limit=limit)
    }


@router.get("/exercise/by-type/{exercise_name}")
def get_exercises_by_type_endpoint(exercise_name: str, limit: int = 20):
    """Get all exercises of the same type (e.g., all squats)."""
    category = categorize_exercise(exercise_name)
    exercises = find_exercises_by_type(exercise_name, limit=limit)
    return {
        "exercise_name": exercise_name,
        "category": category,
        "exercises": exercises
    }


# =============================================================================
# Exercise Match Endpoints
# =============================================================================


@router.post("/exercises/match", response_model=ExerciseMatchResult)
async def match_exercise_single(request: ExerciseMatchRequest):
    """Match a single exercise name to Garmin exercise database.

    Returns the best match with confidence score and suggestions.

    Confidence thresholds:
    - 90%+ = "matched" (high confidence)
    - 50-90% = "needs_review" (medium confidence)
    - <50% = "unmapped" (low confidence)
    """
    from backend.core.garmin_matcher import find_garmin_exercise, get_garmin_suggestions

    name = request.name.strip()
    if not name:
        return ExerciseMatchResult(original_name=name, status="unmapped")

    matched_name, confidence = find_garmin_exercise(name, threshold=30)
    suggestions_list = get_garmin_suggestions(name, limit=request.limit, score_cutoff=0.3)
    suggestions = [
        {"name": sugg_name, "confidence": round(sugg_conf, 2)}
        for sugg_name, sugg_conf in suggestions_list
    ]

    if matched_name and confidence >= 0.90:
        status = "matched"
    elif matched_name and confidence >= 0.50:
        status = "needs_review"
    else:
        status = "unmapped"
        if suggestions and not matched_name:
            matched_name = suggestions[0]["name"]
            confidence = suggestions[0]["confidence"]

    return ExerciseMatchResult(
        original_name=name,
        matched_name=matched_name,
        confidence=round(confidence, 2) if confidence else 0,
        status=status,
        suggestions=suggestions,
    )


@router.post("/exercises/match/batch", response_model=ExerciseMatchBatchResponse)
async def match_exercises_batch(request: ExerciseMatchBatchRequest):
    """Match multiple exercise names to Garmin exercise database.

    Deduplicates names for efficiency and returns results for each unique name.
    """
    from backend.core.garmin_matcher import find_garmin_exercise, get_garmin_suggestions

    unique_names = list(set(name.strip() for name in request.names if name.strip()))

    results = []
    for name in unique_names:
        matched_name, confidence = find_garmin_exercise(name, threshold=30)
        suggestions_list = get_garmin_suggestions(name, limit=request.limit, score_cutoff=0.3)
        suggestions = [
            {"name": sugg_name, "confidence": round(sugg_conf, 2)}
            for sugg_name, sugg_conf in suggestions_list
        ]

        if matched_name and confidence >= 0.90:
            status = "matched"
        elif matched_name and confidence >= 0.50:
            status = "needs_review"
        else:
            status = "unmapped"
            if suggestions and not matched_name:
                matched_name = suggestions[0]["name"]
                confidence = suggestions[0]["confidence"]

        results.append(ExerciseMatchResult(
            original_name=name,
            matched_name=matched_name,
            confidence=round(confidence, 2) if confidence else 0,
            status=status,
            suggestions=suggestions,
        ))

    matched_count = len([r for r in results if r.status == "matched"])
    review_count = len([r for r in results if r.status == "needs_review"])
    unmapped_count = len([r for r in results if r.status == "unmapped"])

    return ExerciseMatchBatchResponse(
        results=results,
        total=len(results),
        matched=matched_count,
        needs_review=review_count,
        unmapped=unmapped_count,
    )


# =============================================================================
# User Mapping Endpoints
# =============================================================================


@router.post("/mappings/add")
def save_mapping(p: UserMappingRequest):
    """Save a user-defined mapping: exercise_name -> garmin_name.

    Also records global popularity.
    """
    result = add_user_mapping(p.exercise_name, p.garmin_name)
    record_mapping_choice(p.exercise_name, p.garmin_name)
    return {
        "message": "Mapping saved successfully (also recorded for global popularity)",
        "mapping": result
    }


@router.delete("/mappings/remove/{exercise_name}")
def delete_mapping(exercise_name: str):
    """Remove a user-defined mapping."""
    removed = remove_user_mapping(exercise_name)
    if removed:
        return {"message": f"Mapping for '{exercise_name}' removed successfully"}
    else:
        return {"message": f"No mapping found for '{exercise_name}'"}


@router.get("/mappings")
def list_mappings():
    """Get all user-defined mappings."""
    mappings = get_all_user_mappings()
    return {"total": len(mappings), "mappings": mappings}


@router.get("/mappings/lookup/{exercise_name}")
def lookup_mapping(exercise_name: str):
    """Check if a user mapping exists for an exercise."""
    garmin_name = get_user_mapping(exercise_name)
    if garmin_name:
        return {
            "exercise_name": exercise_name,
            "mapped_to": garmin_name,
            "exists": True
        }
    else:
        return {
            "exercise_name": exercise_name,
            "mapped_to": None,
            "exists": False
        }


@router.delete("/mappings/clear")
def clear_mappings():
    """Clear all user mappings."""
    clear_all_user_mappings()
    return {"message": "All user mappings cleared successfully"}


@router.get("/mappings/popularity/stats")
def get_popularity_stats_endpoint():
    """Get statistics about global mapping popularity (crowd-sourced choices)."""
    stats = get_popularity_stats()
    return stats


@router.get("/mappings/popularity/{exercise_name}")
def get_exercise_popularity(exercise_name: str):
    """Get popular mappings for a specific exercise."""
    popular = get_popular_mappings(exercise_name, limit=10)
    return {
        "exercise_name": exercise_name,
        "popular_mappings": [{"garmin_name": garmin, "count": count} for garmin, count in popular]
    }


@router.post("/mappings/popularity/record")
def record_mapping_choice_endpoint(p: UserMappingRequest):
    """Record a mapping choice for global popularity (without saving as personal mapping)."""
    record_mapping_choice(p.exercise_name, p.garmin_name)
    return {
        "message": "Mapping choice recorded for global popularity",
        "exercise_name": p.exercise_name,
        "garmin_name": p.garmin_name
    }
