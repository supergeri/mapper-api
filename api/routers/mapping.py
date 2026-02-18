"""
Mapping router for exercise mapping and transformation endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-379: Move mapping endpoints from app.py
Updated in AMA-380: Move export endpoints to exports.py
Updated in AMA-388: Refactor to use dependency injection for repositories
Updated in AMA-394: Add map-parsed endpoint using MapWorkoutUseCase
Updated in AMA-357: Move /map/* endpoints from exports.py

This router contains endpoints for:
- /map/* - Workout format conversion (Garmin YAML, FIT, WorkoutKit, ZWO)
- /workflow/* - Workout validation and processing
- /map-parsed - Map parsed workout using MapWorkoutUseCase
- /exercise/* - Exercise suggestions and matching
- /exercises/* - Exercise matching API
- /mappings/* - User mapping management
"""

import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.deps import get_exercise_match_repo, get_global_mapping_repo, get_map_workout_use_case, get_current_user, get_export_service
from application.ports import ExerciseMatchRepository, GlobalMappingRepository
from application.use_cases import MapWorkoutUseCase
from backend.parsers.models import ParsedWorkout
from backend.services.export_service import ExportService

# Import workflow processing (higher-level orchestration, not pure repository calls)
from backend.core.workflow import validate_workout_mapping, process_workout_with_validation

# Import user mappings (session-scoped, not per-user authenticated)
# TODO: Consider adding auth and migrating to UserMappingRepository in future
from backend.core.user_mappings import (
    add_user_mapping,
    remove_user_mapping,
    get_user_mapping,
    get_all_user_mappings,
    clear_all_user_mappings,
)
from backend.core.global_mappings import record_mapping_choice

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


class IngestPayload(BaseModel):
    """Payload for old ingest format conversion."""
    ingest_json: dict


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
# Map Parsed Workout Endpoint (via Use Case)
# =============================================================================


@router.post("/map-parsed")
def map_parsed_workout(
    parsed_workout: ParsedWorkout,
    device: str = Query("garmin", description="Target device: garmin, apple, ios_companion"),
    save: bool = Query(True, description="Whether to save the workout to database"),
    user_id: str = Depends(get_current_user),
    map_use_case: MapWorkoutUseCase = Depends(get_map_workout_use_case),
):
    """Map a parsed workout to canonical format and optionally save.

    This endpoint takes a ParsedWorkout (output from file parsing) and:
    1. Converts it to canonical Workout domain model
    2. Maps exercise names to Garmin canonical names
    3. Optionally saves to the database

    User mappings take priority over fuzzy matching.

    Args:
        parsed_workout: Parsed workout from file parsing (Excel, CSV, etc.)
        device: Target device for workout export
        save: Whether to save the workout to database
        user_id: Current authenticated user

    Returns:
        Mapped workout with exercise mapping statistics
    """
    result = map_use_case.execute(
        parsed_workout=parsed_workout,
        user_id=user_id,
        device=device,
        save=save,
    )

    if result.success:
        # Convert workout to dict for JSON response
        workout_data = result.workout.model_dump() if result.workout else None
        return {
            "success": True,
            "workout": workout_data,
            "workout_id": result.workout_id,
            "exercises_mapped": result.exercises_mapped,
            "exercises_unmapped": result.exercises_unmapped,
        }
    else:
        return {
            "success": False,
            "error": result.error,
        }


# =============================================================================
# Exercise Suggestion Endpoints
# =============================================================================


@router.post("/exercise/suggest")
def suggest_exercise(
    p: ExerciseSuggestionRequest,
    exercise_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
):
    """Get exercise suggestions and alternatives from Garmin database."""
    # Get best match
    matched_name, confidence = exercise_repo.find_match(p.exercise_name)

    # Get suggestions
    suggestions = exercise_repo.get_suggestions(p.exercise_name, limit=5)

    # Get similar by type if requested
    similar_by_type = []
    if p.include_similar_types:
        similar_by_type = exercise_repo.find_by_type(p.exercise_name, limit=10)

    return {
        "exercise_name": p.exercise_name,
        "best_match": matched_name,
        "confidence": confidence,
        "suggestions": [{"name": name, "confidence": conf} for name, conf in suggestions],
        "similar_by_type": similar_by_type,
    }


@router.get("/exercise/similar/{exercise_name}")
def get_similar_exercises_endpoint(
    exercise_name: str,
    limit: int = 10,
    exercise_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
):
    """Get similar exercises to the given name."""
    return {
        "exercise_name": exercise_name,
        "similar": exercise_repo.find_similar(exercise_name, limit=limit)
    }


@router.get("/exercise/by-type/{exercise_name}")
def get_exercises_by_type_endpoint(
    exercise_name: str,
    limit: int = 20,
    exercise_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
):
    """Get all exercises of the same type (e.g., all squats)."""
    category = exercise_repo.categorize(exercise_name)
    exercises = exercise_repo.find_by_type(exercise_name, limit=limit)
    return {
        "exercise_name": exercise_name,
        "category": category,
        "exercises": exercises
    }


# =============================================================================
# Exercise Match Endpoints
# =============================================================================


@router.post("/exercises/match", response_model=ExerciseMatchResult)
async def match_exercise_single(
    request: ExerciseMatchRequest,
    exercise_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
):
    """Match a single exercise name to Garmin exercise database.

    Returns the best match with confidence score and suggestions.

    Confidence thresholds:
    - 90%+ = "matched" (high confidence)
    - 50-90% = "needs_review" (medium confidence)
    - <50% = "unmapped" (low confidence)
    """
    name = request.name.strip()
    if not name:
        return ExerciseMatchResult(original_name=name, status="unmapped")

    matched_name, confidence = exercise_repo.find_match(name, threshold=0.3)
    suggestions_list = exercise_repo.get_suggestions(name, limit=request.limit, score_cutoff=0.3)
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
async def match_exercises_batch(
    request: ExerciseMatchBatchRequest,
    exercise_repo: ExerciseMatchRepository = Depends(get_exercise_match_repo),
):
    """Match multiple exercise names to Garmin exercise database.

    Deduplicates names for efficiency and returns results for each unique name.
    """
    unique_names = list(set(name.strip() for name in request.names if name.strip()))

    results = []
    for name in unique_names:
        matched_name, confidence = exercise_repo.find_match(name, threshold=0.3)
        suggestions_list = exercise_repo.get_suggestions(name, limit=request.limit, score_cutoff=0.3)
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
def get_popularity_stats_endpoint(
    global_mapping_repo: GlobalMappingRepository = Depends(get_global_mapping_repo),
):
    """Get statistics about global mapping popularity (crowd-sourced choices)."""
    stats = global_mapping_repo.get_stats()
    return stats


@router.get("/mappings/popularity/{exercise_name}")
def get_exercise_popularity(
    exercise_name: str,
    global_mapping_repo: GlobalMappingRepository = Depends(get_global_mapping_repo),
):
    """Get popular mappings for a specific exercise."""
    popular = global_mapping_repo.get_popular(exercise_name, limit=10)
    return {
        "exercise_name": exercise_name,
        "popular_mappings": [{"garmin_name": garmin, "count": count} for garmin, count in popular]
    }


@router.post("/mappings/popularity/record")
def record_mapping_choice_endpoint(
    p: UserMappingRequest,
    global_mapping_repo: GlobalMappingRepository = Depends(get_global_mapping_repo),
):
    """Record a mapping choice for global popularity (without saving as personal mapping)."""
    global_mapping_repo.record_choice(p.exercise_name, p.garmin_name)
    return {
        "message": "Mapping choice recorded for global popularity",
        "exercise_name": p.exercise_name,
        "garmin_name": p.garmin_name
    }


# =============================================================================
# Map Conversion Endpoints (moved from exports.py in AMA-357)
# =============================================================================


@router.post("/map/final")
def map_final(
    p: IngestPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """Convert old format (with exercises array) to Garmin YAML via CIR."""
    return export_service.map_final(p.ingest_json)


@router.post("/map/auto-map")
def auto_map_workout(
    p: BlocksPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """Automatically convert blocks JSON to Garmin YAML.

    Picks best exercise matches automatically - no user interaction needed.
    Automatically detects HIIT workouts and uses appropriate format.
    """
    return export_service.auto_map_workout(p.blocks_json)


@router.post("/map/to-hiit")
def map_to_hiit(
    p: BlocksPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """Convert blocks JSON to Garmin HIIT workout YAML format.

    Use this endpoint specifically for HIIT workouts (for time, AMRAP, EMOM, etc.).
    """
    return export_service.map_to_hiit(p.blocks_json)


@router.post("/map/to-workoutkit")
def map_to_workoutkit(
    p: BlocksPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """Convert blocks JSON to Apple WorkoutKit DTO format for creating workouts on Apple Watch."""
    return export_service.map_to_workoutkit(p.blocks_json)


@router.post("/map/to-zwo")
def map_to_zwo(
    p: BlocksPayload,
    sport: str = Query(None, description="Sport type: 'run' or 'ride'. Auto-detected if not provided."),
    format: str = Query("zwo", description="File format: 'zwo' for Zwift, 'xml' for generic XML"),
    export_service: ExportService = Depends(get_export_service),
):
    """Convert blocks JSON to Zwift ZWO XML format for running or cycling workouts.

    Args:
        p: Blocks JSON payload
        sport: Optional sport type ("run" or "ride"). If not provided, will auto-detect.
        format: File extension - 'zwo' for Zwift, 'xml' for generic XML

    Returns:
        ZWO XML file download that can be imported into Zwift or TrainingPeaks
    """
    return export_service.map_to_zwo(p.blocks_json, sport=sport, format=format)


@router.post("/map/to-fit")
def map_to_fit(
    p: BlocksPayload,
    sport_type: str = Query(
        None,
        description="Force sport type: 'strength', 'cardio', or 'running'. Auto-detected if not provided."
    ),
    use_lap_button: bool = Query(
        False,
        description="Use lap button press instead of reps/distance."
    ),
    export_service: ExportService = Depends(get_export_service),
):
    """Convert blocks JSON directly to Garmin FIT file for USB transfer to watch.

    The sport type affects how Garmin displays the workout:
    - strength: Best for pure strength/weight training
    - cardio: Best for mixed workouts with running, rowing, ski erg
    - running: Best for pure running workouts

    Lap Button Mode:
    - When enabled, all exercises use "press lap when done" instead of counting reps/distance

    Returns:
        Binary .fit file download ready for Garmin watch
    """
    return export_service.map_to_fit(p.blocks_json, sport_type=sport_type, use_lap_button=use_lap_button)


@router.post("/map/fit-metadata")
def map_fit_metadata(
    p: BlocksPayload,
    use_lap_button: bool = Query(False, description="Check metadata with lap button mode enabled"),
    export_service: ExportService = Depends(get_export_service),
):
    """Analyze workout and return metadata about FIT export.

    Returns:
        - detected_sport: Auto-detected sport type
        - warnings: Any warnings about mixed exercise types
        - exercise_count: Number of exercises in workout
        - use_lap_button: Whether lap button mode is enabled
    """
    return export_service.get_fit_metadata(p.blocks_json, use_lap_button=use_lap_button)


@router.post("/map/preview-steps")
def map_preview_steps(
    p: BlocksPayload,
    use_lap_button: bool = Query(False, description="Show preview with lap button mode"),
    export_service: ExportService = Depends(get_export_service),
):
    """Get preview steps that exactly match what will be exported to FIT.

    This is the single source of truth for exercise preview.
    The UI should call this endpoint instead of doing local mapping.
    """
    return export_service.get_preview_steps(p.blocks_json, use_lap_button=use_lap_button)


# =============================================================================
# Deprecated Endpoints (moved from exports.py in AMA-357)
# =============================================================================


@router.post("/map/workout")
def map_workout(
    p: BlocksPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """[Deprecated] Use /map/auto-map instead."""
    return export_service.auto_map_workout(p.blocks_json)


@router.post("/map/blocks-to-hyrox")
def map_blocks_to_hyrox(
    p: BlocksPayload,
    export_service: ExportService = Depends(get_export_service),
):
    """[Deprecated] Use /map/auto-map instead."""
    return export_service.auto_map_workout(p.blocks_json)
