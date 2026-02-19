"""
Exports router for workout format conversion endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-380: Move export endpoints from mapping.py
Updated in AMA-394: Add export endpoint using ExportWorkoutUseCase
Updated in AMA-357: Move /map/* endpoints to mapping.py
Updated in AMA-358: Move /map/to-workoutkit, /map/to-zwo, /map/to-fit,
                   /map/fit-metadata, /map/preview-steps endpoints here

This router contains endpoints for:
- /export/{workout_id} - Export saved workout from database
- /map/to-workoutkit - Convert blocks JSON to Apple WorkoutKit format
- /map/to-zwo - Convert blocks JSON to Zwift ZWO XML format
- /map/to-fit - Convert blocks JSON to Garmin FIT file
- /map/fit-metadata - Get FIT export metadata
- /map/preview-steps - Get preview steps for FIT export
"""

import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from api.deps import get_current_user, get_export_workout_use_case, get_export_service
from application.use_cases import ExportWorkoutUseCase
from backend.services.export_service import ExportService

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Exports"],
)


# =============================================================================
# Request Models
# =============================================================================


class BlocksPayload(BaseModel):
    """Payload for blocks format used by workflow endpoints."""
    blocks_json: Dict[str, Any]


# =============================================================================
# Database Export Endpoints (via Use Case)
# =============================================================================


@router.get("/export/{workout_id}")
def export_saved_workout(
    workout_id: str,
    export_format: str = Query(
        "yaml",
        description="Export format: yaml, hiit, zwo, workoutkit, fit_metadata"
    ),
    update_status: bool = Query(
        False,
        description="Mark workout as exported after successful export"
    ),
    user_id: str = Depends(get_current_user),
    export_use_case: ExportWorkoutUseCase = Depends(get_export_workout_use_case),
):
    """Export a saved workout from the database to various formats.

    This endpoint retrieves a workout by ID and exports it to the requested format.
    Unlike /map/* endpoints which convert raw JSON, this exports persisted workouts.

    Supported formats:
    - yaml: Garmin-compatible YAML (auto-detects HIIT)
    - hiit: Garmin HIIT YAML format
    - zwo: Zwift ZWO XML format
    - workoutkit: Apple WorkoutKit DTO format
    - fit_metadata: FIT file metadata (for analysis)

    Args:
        workout_id: ID of the workout to export
        export_format: Target export format
        update_status: Whether to mark workout as exported

    Returns:
        Export data in requested format with metadata
    """
    result = export_use_case.execute(
        workout_id=workout_id,
        profile_id=user_id,
        export_format=export_format,
        update_export_status=update_status,
    )

    if result.success:
        return {
            "success": True,
            "export_format": result.export_format,
            "export_data": result.export_data,
            "workout_id": result.workout_id,
            "workout_title": result.workout_title,
            "warnings": result.warnings,
        }
    else:
        return {
            "success": False,
            "error": result.error,
            "workout_id": result.workout_id,
        }


# =============================================================================
# Blocks JSON Export Endpoints (direct conversion)
# =============================================================================


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
    sport: Optional[Literal["run", "ride"]] = Query(None, description="Sport type: 'run' or 'ride'. Auto-detected if not provided."),
    format: Literal["zwo", "xml"] = Query("zwo", description="File format: 'zwo' for Zwift, 'xml' for generic XML"),
    export_service: ExportService = Depends(get_export_service),
):
    """Convert blocks JSON to Zwift ZWO XML format for running or cycling workout.

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
    sport_type: Optional[Literal["strength", "cardio", "running"]] = Query(
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
