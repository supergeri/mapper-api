"""
Exports router for workout format conversion endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-380: Move export endpoints from mapping.py
Updated in AMA-394: Add export endpoint using ExportWorkoutUseCase

This router contains endpoints for:
- /map/* - Workout format conversion (Garmin YAML, FIT, WorkoutKit, ZWO)
- /export/{workout_id} - Export saved workout from database
"""

import re
import logging
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel

from api.deps import get_current_user, get_export_workout_use_case
from application.use_cases import ExportWorkoutUseCase

# Import mapping/conversion adapters
from backend.adapters.ingest_to_cir import to_cir
from backend.core.canonicalize import canonicalize
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_zwo import to_zwo
from backend.adapters.blocks_to_fit import to_fit_response, get_fit_metadata

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Exports"],
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
# Deprecated Endpoints
# =============================================================================


@router.post("/map/workout")
def map_workout(p: BlocksPayload):
    """[Deprecated] Use /map/auto-map instead."""
    return auto_map_workout(p)


@router.post("/map/blocks-to-hyrox")
def map_blocks_to_hyrox(p: BlocksPayload):
    """[Deprecated] Use /map/auto-map instead."""
    return auto_map_workout(p)
