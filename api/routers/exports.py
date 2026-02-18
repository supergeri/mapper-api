"""
Exports router for workout format conversion endpoints.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-380: Move export endpoints from mapping.py
Updated in AMA-394: Add export endpoint using ExportWorkoutUseCase
Updated in AMA-357: Move /map/* endpoints to mapping.py

This router contains endpoints for:
- /export/{workout_id} - Export saved workout from database
"""

import logging
from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user, get_export_workout_use_case
from application.use_cases import ExportWorkoutUseCase

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Exports"],
)


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
