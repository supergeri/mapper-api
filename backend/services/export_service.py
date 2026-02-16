"""
Export Service for Format Conversion.

Part of AMA-610: Wire ExportService into exports router

This module provides business logic for converting workout formats:
- Ingest format to Garmin YAML
- Blocks JSON to various formats (Garmin, Hyrox, HIIT, WorkoutKit, ZWO, FIT)
- Format detection and routing
"""

import re
import logging
from typing import Dict, Any, Optional

from fastapi import Response

from backend.adapters.ingest_to_cir import to_cir
from backend.core.canonicalize import canonicalize
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_zwo import to_zwo
from backend.adapters.blocks_to_fit import to_fit_response, get_fit_metadata

logger = logging.getLogger(__name__)


class ExportService:
    """Service for converting workout formats to various export formats."""

    def map_final(self, ingest_json: dict) -> Dict[str, str]:
        """
        Convert old format (with exercises array) to Garmin YAML via CIR.

        Args:
            ingest_json: Original ingest format JSON

        Returns:
            Dictionary with 'yaml' key containing the YAML output
        """
        cir = canonicalize(to_cir(ingest_json))
        return {"yaml": to_garmin_yaml(cir)}

    def auto_map_workout(self, blocks_json: dict) -> Dict[str, str]:
        """
        Automatically convert blocks JSON to Garmin YAML.

        Picks best exercise matches automatically - no user interaction needed.
        Automatically detects HIIT workouts and uses appropriate format.

        Args:
            blocks_json: Blocks format JSON

        Returns:
            Dictionary with 'yaml' key containing the YAML output
        """
        if is_hiit_workout(blocks_json):
            yaml_output = to_hiit_garmin_yaml(blocks_json)
        else:
            yaml_output = to_hyrox_yaml(blocks_json)
        return {"yaml": yaml_output}

    def map_to_hiit(self, blocks_json: dict) -> Dict[str, str]:
        """
        Convert blocks JSON to Garmin HIIT workout YAML format.

        Use this for HIIT workouts (for time, AMRAP, EMOM, etc.).

        Args:
            blocks_json: Blocks format JSON

        Returns:
            Dictionary with 'yaml' key containing the YAML output
        """
        yaml_output = to_hiit_garmin_yaml(blocks_json)
        return {"yaml": yaml_output}

    def map_to_workoutkit(self, blocks_json: dict) -> Dict[str, Any]:
        """
        Convert blocks JSON to Apple WorkoutKit DTO format.

        Args:
            blocks_json: Blocks format JSON

        Returns:
            WorkoutKit DTO as dictionary
        """
        workoutkit_dto = to_workoutkit(blocks_json)
        return workoutkit_dto.model_dump()

    def map_to_zwo(
        self,
        blocks_json: dict,
        sport: Optional[str] = None,
        format: str = "zwo",
    ) -> Response:
        """
        Convert blocks JSON to Zwift ZWO XML format.

        Args:
            blocks_json: Blocks format JSON
            sport: Optional sport type ("run" or "ride"). Auto-detected if not provided.
            format: File format - 'zwo' for Zwift, 'xml' for generic XML

        Returns:
            Response with ZWO XML file download
        """
        zwo_xml = to_zwo(blocks_json, sport=sport)

        # Extract workout name for filename
        workout_name = blocks_json.get("title", "workout")
        safe_name = re.sub(r'[^\w\s-]', '', workout_name).strip()
        safe_name = re.sub(r'[-\s]+', '-', safe_name)[:50]

        file_ext = format.lower() if format.lower() in ["zwo", "xml"] else "zwo"

        return Response(
            content=zwo_xml,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.{file_ext}"'},
        )

    def map_to_fit(
        self,
        blocks_json: dict,
        sport_type: Optional[str] = None,
        use_lap_button: bool = False,
    ) -> Response:
        """
        Convert blocks JSON directly to Garmin FIT file.

        Args:
            blocks_json: Blocks format JSON
            sport_type: Force sport type ('strength', 'cardio', or 'running'). Auto-detected if not provided.
            use_lap_button: Use lap button press instead of reps/distance

        Returns:
            Response with binary .fit file download
        """
        return to_fit_response(
            blocks_json,
            force_sport_type=sport_type,
            use_lap_button=use_lap_button,
        )

    def get_fit_metadata(
        self,
        blocks_json: dict,
        use_lap_button: bool = False,
    ) -> Dict[str, Any]:
        """
        Analyze workout and return metadata about FIT export.

        Args:
            blocks_json: Blocks format JSON
            use_lap_button: Whether lap button mode is enabled

        Returns:
            Dictionary with FIT metadata
        """
        return get_fit_metadata(blocks_json, use_lap_button=use_lap_button)

    def get_preview_steps(
        self,
        blocks_json: dict,
        use_lap_button: bool = False,
    ) -> Dict[str, Any]:
        """
        Get preview steps that match what will be exported to FIT.

        Args:
            blocks_json: Blocks format JSON
            use_lap_button: Show preview with lap button mode

        Returns:
            Dictionary with 'steps' key containing preview steps
        """
        try:
            from amakaflow_fitfiletool import get_preview_steps
            return {"steps": get_preview_steps(blocks_json, use_lap_button=use_lap_button)}
        except ImportError:
            from backend.adapters.blocks_to_fit import blocks_to_steps
            steps, _ = blocks_to_steps(blocks_json, use_lap_button=use_lap_button)
            return {"steps": steps}
