"""
Golden tests for all export formats.

Part of AMA-372: Add golden fixtures for key export formats
Phase 4.2 - Testing Overhaul

Consolidated golden tests covering all major export adapters:
- Hyrox YAML export
- HIIT YAML export (EMOM, AMRAP)
- ZWO export (running, cycling)
- WorkoutKit export
- FIT metadata validation

This file provides a single entry point for golden regression testing
across all export adapters.
"""

import re
import json
import xml.etree.ElementTree as ET

import pytest

from tests.golden import assert_golden
from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from backend.adapters.blocks_to_zwo import to_zwo
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.adapters.blocks_to_fit import get_fit_metadata, blocks_to_steps
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from shared.schemas.cir import CIR, Workout, Block, Exercise


# =============================================================================
# Test Data Factories - Hyrox
# =============================================================================


def create_hyrox_interval_blocks() -> dict:
    """Create a Hyrox-style interval workout."""
    return {
        "title": "HYROX Interval Training",
        "blocks": [
            {
                "label": "Main",
                "structure": "8 rounds",
                "exercises": [
                    {"name": "Ski Erg", "distance_m": 500},
                    {"name": "Burpee", "reps": 10},
                    {"name": "Box Jump", "reps": 12},
                    {"name": "Rowing", "distance_m": 500},
                    {"name": "Wall Ball", "reps": 20},
                    {"name": "Kettlebell Swing", "reps": 24},
                    {"name": "Burpee", "reps": 10},
                    {"name": "Pull-Up", "reps": 10},
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Test Data Factories - HIIT
# =============================================================================


def create_emom_blocks() -> dict:
    """Create an EMOM (Every Minute on the Minute) workout."""
    return {
        "title": "EMOM 12 Minutes",
        "blocks": [
            {
                "label": "Main",
                "structure": "EMOM 12 min",
                "time_work_sec": 720,
                "exercises": [
                    {"name": "Kettlebell Swing", "reps": 15},
                    {"name": "Push-Up", "reps": 10},
                    {"name": "Air Squat", "reps": 15},
                    {"name": "Mountain Climber", "reps": 20},
                ],
                "supersets": [],
            },
        ],
    }


def create_amrap_blocks() -> dict:
    """Create an AMRAP (As Many Rounds As Possible) workout."""
    return {
        "title": "AMRAP 15 Minutes",
        "blocks": [
            {
                "label": "Main",
                "structure": "AMRAP 15 min",
                "time_work_sec": 900,
                "exercises": [
                    {"name": "Run", "distance_m": 200},
                    {"name": "Burpee", "reps": 10},
                    {"name": "Double Under", "reps": 15},
                    {"name": "Thruster", "reps": 10},
                    {"name": "Pull-Up", "reps": 8},
                ],
                "supersets": [],
            },
        ],
    }


def create_hiit_for_time_blocks() -> dict:
    """Create a HIIT for-time workout."""
    return {
        "title": "HIIT For Time",
        "blocks": [
            {
                "label": "Main",
                "structure": "for time (cap: 20 min)",
                "time_work_sec": 1200,
                "exercises": [
                    {"name": "Run", "distance_m": 400},
                    {"name": "Burpees", "reps": 10},
                    {"name": "Wall Ball", "reps": 20},
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Test Data Factories - ZWO
# =============================================================================


def create_zwo_running_blocks() -> dict:
    """Create a simple running workout for ZWO."""
    return {
        "title": "Easy 5K Run",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 300,
                "exercises": [{"name": "Easy jog warmup", "duration_sec": 300}],
                "supersets": [],
            },
            {
                "label": "Main",
                "structure": "1 round",
                "exercises": [{"name": "Tempo run", "distance_m": 3000}],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [{"name": "Easy jog cooldown", "duration_sec": 300}],
                "supersets": [],
            },
        ],
    }


def create_zwo_cycling_blocks() -> dict:
    """Create a cycling workout for ZWO."""
    return {
        "title": "FTP Intervals",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 600,
                "exercises": [{"name": "50% FTP easy spin", "duration_sec": 600}],
                "supersets": [],
            },
            {
                "label": "Main Set",
                "structure": "4 rounds",
                "time_work_sec": 300,
                "rest_between_sec": 180,
                "exercises": [
                    {"name": "95-100% FTP threshold", "duration_sec": 300, "rest_sec": 180, "sets": 4}
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [{"name": "50% FTP recovery spin", "duration_sec": 300}],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Test Data Factories - WorkoutKit
# =============================================================================


def create_workoutkit_strength_blocks() -> dict:
    """Create a simple strength workout for WorkoutKit."""
    return {
        "title": "Upper Body Basics",
        "blocks": [
            {"label": "Warmup", "time_work_sec": 300, "exercises": [], "supersets": []},
            {
                "label": "Main Set",
                "exercises": [
                    {"name": "Push-Ups", "reps": 15},
                    {"name": "Dumbbell Rows", "reps": 12},
                    {"name": "Shoulder Press", "reps": 10},
                ],
                "supersets": [],
            },
            {"label": "Cooldown", "time_work_sec": 180, "exercises": [], "supersets": []},
        ],
    }


# =============================================================================
# Test Data Factories - FIT
# =============================================================================


def create_fit_strength_blocks() -> dict:
    """Create a strength workout for FIT metadata."""
    return {
        "title": "Upper Body Strength",
        "blocks": [
            {
                "structure": "3 rounds",
                "rest_between_sec": 60,
                "exercises": [
                    {"name": "Bench Press", "reps": 8, "sets": 3, "rest_sec": 90},
                    {"name": "Barbell Row", "reps": 10, "sets": 3, "rest_sec": 60},
                ],
                "supersets": [],
            },
        ],
    }


def create_fit_cardio_blocks() -> dict:
    """Create a cardio workout for FIT metadata."""
    return {
        "title": "Cardio Conditioning",
        "blocks": [
            {
                "exercises": [
                    {"name": "Ski Erg", "distance_m": 500},
                    {"name": "Assault Bike", "duration_sec": 60},
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_yaml_date(yaml_output: str) -> str:
    """Normalize dynamic dates in YAML output for stable golden comparisons."""
    return re.sub(
        r"start_from:\s*['\"]?\d{4}-\d{2}-\d{2}['\"]?",
        "start_from: 'NORMALIZED_DATE'",
        yaml_output,
    )


def normalize_zwo_xml(xml_str: str) -> str:
    """Normalize ZWO XML for stable golden comparisons."""
    xml_content = re.sub(r"<\?xml[^?]*\?>\s*", "", xml_str)
    try:
        root = ET.fromstring(xml_content)
        return _element_to_normalized_string(root)
    except ET.ParseError:
        return xml_str


def _element_to_normalized_string(elem: ET.Element, indent: int = 0) -> str:
    """Convert element to normalized XML string."""
    indent_str = "  " * indent
    tag = elem.tag
    attrs = " ".join(f'{k}="{v}"' for k, v in sorted(elem.attrib.items()))
    if attrs:
        open_tag = f"{indent_str}<{tag} {attrs}>"
    else:
        open_tag = f"{indent_str}<{tag}>"

    if elem.text and elem.text.strip():
        return f"{open_tag}{elem.text.strip()}</{tag}>\n"

    children = list(elem)
    if children:
        result = f"{open_tag}\n"
        for child in children:
            result += _element_to_normalized_string(child, indent + 1)
        result += f"{indent_str}</{tag}>\n"
        return result
    else:
        if attrs:
            return f"{indent_str}<{tag} {attrs}/>\n"
        else:
            return f"{open_tag}</{tag}>\n"


def normalize_workoutkit_json(wk_dto) -> str:
    """Normalize WorkoutKit DTO for stable golden comparisons."""
    return json.dumps(wk_dto.model_dump(exclude_none=True), indent=2, sort_keys=True)


# =============================================================================
# Hyrox YAML Tests
# =============================================================================


class TestHyroxYamlExports:
    """Golden tests for Hyrox YAML export adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_simple_strength(self):
        """Simple strength workout exports correctly."""
        blocks = {
            "title": "Week 1 Strength",
            "blocks": [
                {
                    "label": "Block A",
                    "structure": "3 rounds",
                    "exercises": [
                        {"name": "Goblet Squat", "sets": 3, "reps": 10, "rest_type": "timed", "rest_sec": 60},
                        {"name": "Push Up", "sets": 3, "reps": 12, "rest_type": "button"},
                    ],
                    "supersets": [],
                },
            ],
        }
        output = to_hyrox_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_simple_strength.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_superset_workout(self):
        """Superset workout exports with proper structure."""
        blocks = {
            "title": "Superset Workout",
            "blocks": [
                {
                    "label": "Superset A",
                    "structure": "4 rounds",
                    "exercises": [],
                    "supersets": [
                        {
                            "exercises": [
                                {"name": "A1: DB Incline Bench Press X8", "reps": 8, "rest_type": "timed", "rest_sec": 30},
                                {"name": "A2: TRX Rows X10", "reps": 10, "rest_type": "timed", "rest_sec": 60},
                            ],
                        },
                    ],
                    "rest_between_sec": 90,
                },
            ],
        }
        output = to_hyrox_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_superset.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_interval_workout(self):
        """Hyrox interval workout exports correctly."""
        blocks = create_hyrox_interval_blocks()
        output = to_hyrox_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_interval_workout.yaml")


# =============================================================================
# HIIT YAML Tests
# =============================================================================


class TestHiitYamlExports:
    """Golden tests for HIIT YAML export adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_hiit_detection(self):
        """HIIT workout is correctly detected."""
        hiit_blocks = create_hiit_for_time_blocks()
        strength_blocks = create_workoutkit_strength_blocks()
        assert is_hiit_workout(hiit_blocks) is True
        assert is_hiit_workout(strength_blocks) is False

    @pytest.mark.golden
    @pytest.mark.unit
    def test_hiit_for_time(self):
        """HIIT for-time workout exports with repeatUntilTime wrapper."""
        blocks = create_hiit_for_time_blocks()
        output = to_hiit_garmin_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hiit_for_time.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_emom_workout(self):
        """EMOM workout exports correctly."""
        blocks = create_emom_blocks()
        output = to_hiit_garmin_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hiit_emom_workout.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_amrap_workout(self):
        """AMRAP workout exports correctly."""
        blocks = create_amrap_blocks()
        output = to_hiit_garmin_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hiit_amrap_workout.yaml")


# =============================================================================
# ZWO Tests
# =============================================================================


class TestZwoExports:
    """Golden tests for ZWO (Zwift) export adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_running_workout(self):
        """Running workout exports correctly."""
        blocks = create_zwo_running_blocks()
        output = to_zwo(blocks, sport="run")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/simple_run.xml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_cycling_workout(self):
        """Cycling workout exports correctly."""
        blocks = create_zwo_cycling_blocks()
        output = to_zwo(blocks, sport="ride")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/cycling_ftp.xml")


# =============================================================================
# WorkoutKit Tests
# =============================================================================


class TestWorkoutKitExports:
    """Golden tests for WorkoutKit (Apple Watch) export adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_strength_workout(self):
        """Strength workout exports correctly."""
        blocks = create_workoutkit_strength_blocks()
        output = to_workoutkit(blocks)
        normalized = normalize_workoutkit_json(output)
        assert_golden(normalized, "workoutkit/simple_strength.json")


# =============================================================================
# FIT Tests
# =============================================================================


class TestFitMetadataExports:
    """Golden tests for FIT metadata validation."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_strength_metadata(self):
        """Strength workout metadata exports correctly."""
        blocks = create_fit_strength_blocks()
        metadata = get_fit_metadata(blocks)
        output = json.dumps(metadata, indent=2, sort_keys=True)
        assert_golden(output, "fit/strength_metadata.json")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_cardio_metadata(self):
        """Cardio workout metadata exports correctly."""
        blocks = create_fit_cardio_blocks()
        metadata = get_fit_metadata(blocks)
        output = json.dumps(metadata, indent=2, sort_keys=True)
        assert_golden(output, "fit/cardio_metadata.json")


# =============================================================================
# Integration Tests
# =============================================================================


class TestExportIntegration:
    """Integration tests for export adapters."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_all_exports_produce_valid_output(self):
        """All exports produce valid, non-empty output."""
        # Hyrox
        hyrox_blocks = {"title": "Test", "blocks": [{"exercises": [{"name": "Squat", "reps": 10}], "supersets": []}]}
        hyrox_output = to_hyrox_yaml(hyrox_blocks)
        assert hyrox_output is not None
        assert len(hyrox_output) > 0

        # HIIT
        hiit_blocks = create_hiit_for_time_blocks()
        hiit_output = to_hiit_garmin_yaml(hiit_blocks)
        assert hiit_output is not None
        assert len(hiit_output) > 0

        # ZWO
        zwo_blocks = create_zwo_running_blocks()
        zwo_output = to_zwo(zwo_blocks, sport="run")
        assert zwo_output is not None
        assert len(zwo_output) > 0

        # WorkoutKit
        wk_blocks = create_workoutkit_strength_blocks()
        wk_output = to_workoutkit(wk_blocks)
        assert wk_output is not None
        assert len(wk_output.model_dump_json()) > 0

        # FIT
        fit_blocks = create_fit_strength_blocks()
        fit_metadata = get_fit_metadata(fit_blocks)
        assert fit_metadata is not None

    @pytest.mark.golden
    @pytest.mark.unit
    def test_yaml_is_valid_yaml(self):
        """All YAML exports are valid YAML that can be parsed."""
        import yaml

        # Hyrox
        hyrox_blocks = {"title": "Test", "blocks": [{"exercises": [{"name": "Squat", "reps": 10}], "supersets": []}]}
        hyrox_output = to_hyrox_yaml(hyrox_blocks)
        parsed_hyrox = yaml.safe_load(hyrox_output)
        assert "settings" in parsed_hyrox
        assert "workouts" in parsed_hyrox

        # HIIT
        hiit_blocks = create_hiit_for_time_blocks()
        hiit_output = to_hiit_garmin_yaml(hiit_blocks)
        parsed_hiit = yaml.safe_load(hiit_output)
        assert "settings" in parsed_hiit
        assert "workouts" in parsed_hiit
