"""
ExportWorkout Use Case.

Part of AMA-392: Create ExportWorkout use case
Phase 3 - Canonical Model + Use Cases

Orchestrates the complete workflow for exporting workouts to various formats
(YAML, ZWO, WorkoutKit, FIT metadata).
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from application.ports import WorkoutRepository
from domain.converters.db_converters import db_row_to_workout, _workout_to_blocks_format
from domain.models import Workout

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""

    YAML = "yaml"
    HIIT = "hiit"
    ZWO = "zwo"
    WORKOUTKIT = "workoutkit"
    FIT_METADATA = "fit_metadata"


@dataclass
class ExportWorkoutResult:
    """Result of the ExportWorkout use case execution."""

    success: bool
    export_format: Optional[str] = None
    export_data: Optional[Union[str, bytes, Dict[str, Any]]] = None
    workout_id: Optional[str] = None
    workout_title: Optional[str] = None
    error: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class ExportWorkoutUseCase:
    """
    Use case for exporting workouts to various formats.

    Orchestrates the following workflow:
    1. Retrieve workout from repository
    2. Convert to domain Workout model
    3. Convert to blocks format for exporters
    4. Delegate to format-specific exporter (adapter)
    5. Optionally update export status
    6. Return export data

    Dependencies are injected via constructor for testability.
    Format-specific export logic remains in adapters.

    Usage:
        >>> use_case = ExportWorkoutUseCase(workout_repo=workout_repo)
        >>> result = use_case.execute(
        ...     workout_id="123",
        ...     profile_id="user-456",
        ...     export_format="yaml",
        ... )
        >>> if result.success:
        ...     print(result.export_data)
    """

    def __init__(
        self,
        workout_repo: WorkoutRepository,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            workout_repo: Repository for retrieving workouts
        """
        self._workout_repo = workout_repo

    def execute(
        self,
        workout_id: str,
        profile_id: str,
        export_format: str,
        *,
        update_export_status: bool = False,
        **format_options: Any,
    ) -> ExportWorkoutResult:
        """
        Execute the workout export workflow.

        Args:
            workout_id: ID of the workout to export
            profile_id: User profile ID for authorization
            export_format: Target format (yaml, hiit, zwo, workoutkit, fit_metadata)
            update_export_status: Whether to mark workout as exported
            **format_options: Format-specific options (e.g., sport for ZWO)

        Returns:
            ExportWorkoutResult with success status and export data
        """
        try:
            # Validate format
            try:
                fmt = ExportFormat(export_format.lower())
            except ValueError:
                valid_formats = [f.value for f in ExportFormat]
                return ExportWorkoutResult(
                    success=False,
                    error=f"Unknown export format: {export_format}. "
                    f"Valid formats: {', '.join(valid_formats)}",
                )

            # Step 1: Retrieve workout from repository
            logger.info(f"Retrieving workout {workout_id} for export")
            workout_row = self._workout_repo.get(workout_id, profile_id)

            if not workout_row:
                logger.warning(f"Workout not found: {workout_id}")
                return ExportWorkoutResult(
                    success=False,
                    workout_id=workout_id,
                    error="Workout not found",
                )

            # Step 2: Convert DB row to domain Workout
            logger.debug("Converting DB row to domain Workout")
            workout = db_row_to_workout(workout_row)

            # Step 3: Convert Workout to blocks format for exporters
            blocks_json = _workout_to_blocks_format(workout)

            # Step 4: Delegate to format-specific exporter
            logger.info(f"Exporting workout to format: {fmt.value}")
            export_data, warnings = self._export_to_format(
                blocks_json, fmt, **format_options
            )

            # Step 5: Optionally update export status
            if update_export_status:
                logger.debug("Updating export status")
                self._workout_repo.update_export_status(
                    workout_id,
                    profile_id,
                    is_exported=True,
                    exported_to_device=fmt.value,
                )

            logger.info(f"Export complete for workout: {workout.title}")
            return ExportWorkoutResult(
                success=True,
                export_format=fmt.value,
                export_data=export_data,
                workout_id=workout_id,
                workout_title=workout.title,
                warnings=warnings,
            )

        except Exception as e:
            logger.exception(f"ExportWorkout use case failed: {e}")
            return ExportWorkoutResult(
                success=False,
                workout_id=workout_id,
                error=str(e),
            )

    def _export_to_format(
        self,
        blocks_json: Dict[str, Any],
        export_format: ExportFormat,
        **options: Any,
    ) -> tuple[Union[str, bytes, Dict[str, Any]], List[str]]:
        """
        Delegate to format-specific exporter.

        Args:
            blocks_json: Workout in blocks format
            export_format: Target export format
            **options: Format-specific options

        Returns:
            Tuple of (export_data, warnings)
        """
        warnings: List[str] = []

        if export_format == ExportFormat.YAML:
            from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
            from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout

            # Auto-detect HIIT and use appropriate format
            if is_hiit_workout(blocks_json):
                from backend.adapters.blocks_to_hiit_garmin_yaml import (
                    to_hiit_garmin_yaml,
                )

                warnings.append("Detected HIIT workout, using HIIT format")
                return to_hiit_garmin_yaml(blocks_json), warnings

            return to_hyrox_yaml(blocks_json), warnings

        elif export_format == ExportFormat.HIIT:
            from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml

            return to_hiit_garmin_yaml(blocks_json), warnings

        elif export_format == ExportFormat.ZWO:
            from backend.adapters.blocks_to_zwo import to_zwo

            sport = options.get("sport")
            return to_zwo(blocks_json, sport=sport), warnings

        elif export_format == ExportFormat.WORKOUTKIT:
            from backend.adapters.blocks_to_workoutkit import to_workoutkit

            dto = to_workoutkit(blocks_json)
            return dto.model_dump(), warnings

        elif export_format == ExportFormat.FIT_METADATA:
            from backend.adapters.blocks_to_fit import get_fit_metadata

            metadata = get_fit_metadata(blocks_json)
            return metadata, warnings

        else:
            raise ValueError(f"Unhandled export format: {export_format}")

    def execute_from_workout(
        self,
        workout: Workout,
        export_format: str,
        **format_options: Any,
    ) -> ExportWorkoutResult:
        """
        Export a workout directly from domain model (without DB lookup).

        Useful for exporting unsaved workouts or in-memory workouts.

        Args:
            workout: Domain Workout model to export
            export_format: Target format
            **format_options: Format-specific options

        Returns:
            ExportWorkoutResult with success status and export data
        """
        try:
            # Validate format
            try:
                fmt = ExportFormat(export_format.lower())
            except ValueError:
                valid_formats = [f.value for f in ExportFormat]
                return ExportWorkoutResult(
                    success=False,
                    error=f"Unknown export format: {export_format}. "
                    f"Valid formats: {', '.join(valid_formats)}",
                )

            # Convert Workout to blocks format for exporters
            blocks_json = _workout_to_blocks_format(workout)

            # Delegate to format-specific exporter
            logger.info(f"Exporting workout to format: {fmt.value}")
            export_data, warnings = self._export_to_format(
                blocks_json, fmt, **format_options
            )

            return ExportWorkoutResult(
                success=True,
                export_format=fmt.value,
                export_data=export_data,
                workout_id=workout.id,
                workout_title=workout.title,
                warnings=warnings,
            )

        except Exception as e:
            logger.exception(f"ExportWorkout use case failed: {e}")
            return ExportWorkoutResult(
                success=False,
                workout_id=workout.id,
                error=str(e),
            )
