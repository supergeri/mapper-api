"""
Mapping router for exercise mapping and transformation endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-379: Move mapping endpoints from app.py

This router contains endpoints for:
- /map/* - Workout format conversion (Garmin YAML, FIT, WorkoutKit, ZWO)
- /workflow/* - Workout validation and processing
- /exercise/* - Exercise suggestions and matching
- /exercises/* - Exercise matching API
- /mappings/* - User mapping management
"""

import re
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

# Import mapping/conversion adapters
from backend.adapters.ingest_to_cir import to_cir
from backend.core.canonicalize import canonicalize
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_zwo import to_zwo
from backend.adapters.blocks_to_fit import to_fit_response, get_fit_metadata

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


class IngestPayload(BaseModel):
    """Payload for old ingest format conversion."""
    ingest_json: dict


class BlocksPayload(BaseModel):
    """Payload for blocks format conversion."""
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
# Map Conversion Endpoints
# =============================================================================


@router.post("/map/final")
def map_final(p: IngestPayload):
    """Convert old format (with exercises array) to Garmin YAML via CIR."""
    cir = canonicalize(to_cir(p.ingest_json))
    return {"yaml": to_garmin_yaml(cir)}


@router.post("/map/auto-map")
def auto_map_workout(p: BlocksPayload):
    """Automatically convert blocks JSON to Garmin YAML.

    Picks best exercise matches automatically - no user interaction needed.
    Automatically detects HIIT workouts and uses appropriate format.
    """
    if is_hiit_workout(p.blocks_json):
        yaml_output = to_hiit_garmin_yaml(p.blocks_json)
    else:
        yaml_output = to_hyrox_yaml(p.blocks_json)
    return {"yaml": yaml_output}


@router.post("/map/to-hiit")
def map_to_hiit(p: BlocksPayload):
    """Convert blocks JSON to Garmin HIIT workout YAML format.

    Use this endpoint specifically for HIIT workouts (for time, AMRAP, EMOM, etc.).
    """
    yaml_output = to_hiit_garmin_yaml(p.blocks_json)
    return {"yaml": yaml_output}


@router.post("/map/to-workoutkit")
def map_to_workoutkit(p: BlocksPayload):
    """Convert blocks JSON to Apple WorkoutKit DTO format for creating workouts on Apple Watch."""
    workoutkit_dto = to_workoutkit(p.blocks_json)
    return workoutkit_dto.model_dump()


@router.post("/map/to-zwo")
def map_to_zwo(
    p: BlocksPayload,
    sport: str = Query(None, description="Sport type: 'run' or 'ride'. Auto-detected if not provided."),
    format: str = Query("zwo", description="File format: 'zwo' for Zwift, 'xml' for generic XML")
):
    """Convert blocks JSON to Zwift ZWO XML format for running or cycling workouts.

    Args:
        p: Blocks JSON payload
        sport: Optional sport type ("run" or "ride"). If not provided, will auto-detect.
        format: File extension - 'zwo' for Zwift, 'xml' for generic XML

    Returns:
        ZWO XML file download that can be imported into Zwift or TrainingPeaks
    """
    zwo_xml = to_zwo(p.blocks_json, sport=sport)

    # Extract workout name for filename
    workout_name = p.blocks_json.get("title", "workout")
    safe_name = re.sub(r'[^\w\s-]', '', workout_name).strip()
    safe_name = re.sub(r'[-\s]+', '-', safe_name)[:50]

    file_ext = format.lower() if format.lower() in ["zwo", "xml"] else "zwo"

    return Response(
        content=zwo_xml,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{file_ext}"'}
    )


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
    )
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
    return to_fit_response(p.blocks_json, force_sport_type=sport_type, use_lap_button=use_lap_button)


@router.post("/map/fit-metadata")
def map_fit_metadata(
    p: BlocksPayload,
    use_lap_button: bool = Query(False, description="Check metadata with lap button mode enabled")
):
    """Analyze workout and return metadata about FIT export.

    Returns:
        - detected_sport: Auto-detected sport type
        - warnings: Any warnings about mixed exercise types
        - exercise_count: Number of exercises in workout
        - use_lap_button: Whether lap button mode is enabled
    """
    return get_fit_metadata(p.blocks_json, use_lap_button=use_lap_button)


@router.post("/map/preview-steps")
def map_preview_steps(
    p: BlocksPayload,
    use_lap_button: bool = Query(False, description="Show preview with lap button mode")
):
    """Get preview steps that exactly match what will be exported to FIT.

    This is the single source of truth for exercise preview.
    The UI should call this endpoint instead of doing local mapping.
    """
    try:
        from amakaflow_fitfiletool import get_preview_steps
        return {"steps": get_preview_steps(p.blocks_json, use_lap_button=use_lap_button)}
    except ImportError:
        from backend.adapters.blocks_to_fit import blocks_to_steps
        steps, _ = blocks_to_steps(p.blocks_json, use_lap_button=use_lap_button)
        return {"steps": steps}


# Deprecated endpoints
@router.post("/map/workout")
def map_workout(p: BlocksPayload):
    """[Deprecated] Use /map/auto-map instead."""
    return auto_map_workout(p)


@router.post("/map/blocks-to-hyrox")
def map_blocks_to_hyrox(p: BlocksPayload):
    """[Deprecated] Use /map/auto-map instead."""
    return auto_map_workout(p)


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
