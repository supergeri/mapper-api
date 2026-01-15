"""
Golden tests for ZWO (Zwift) export adapter.

Part of AMA-397: Add golden fixtures for ZWO export
Phase 4 - Testing Overhaul

Tests ZWO XML export output against saved fixtures to detect unintended changes.
Covers:
- Running workouts
- Cycling workouts with FTP percentages
- Interval workouts
- Warmup/cooldown blocks
"""

import re
import xml.etree.ElementTree as ET

import pytest

from tests.golden import assert_golden
from backend.adapters.blocks_to_zwo import to_zwo


# =============================================================================
# Test Data Factories
# =============================================================================


def create_simple_run_workout() -> dict:
    """Create a simple running workout."""
    return {
        "title": "Easy 5K Run",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "Easy jog warmup",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Main",
                "structure": "1 round",
                "exercises": [
                    {
                        "name": "Tempo run",
                        "distance_m": 3000,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "Easy jog cooldown",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_cycling_ftp_workout() -> dict:
    """Create a cycling workout with FTP percentage targets."""
    return {
        "title": "FTP Intervals",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 600,
                "exercises": [
                    {
                        "name": "50% FTP easy spin",
                        "duration_sec": 600,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Main Set",
                "structure": "4 rounds",
                "time_work_sec": 300,
                "rest_between_sec": 180,
                "exercises": [
                    {
                        "name": "95-100% FTP threshold",
                        "duration_sec": 300,
                        "rest_sec": 180,
                        "sets": 4,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "50% FTP recovery spin",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_interval_run_workout() -> dict:
    """Create a running workout with intervals."""
    return {
        "title": "Track Intervals",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 600,
                "exercises": [
                    {
                        "name": "Easy jog",
                        "duration_sec": 600,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Intervals",
                "structure": "6 rounds",
                "exercises": [
                    {
                        "name": "400m repeats",
                        "distance_m": 400,
                        "rest_sec": 90,
                        "sets": 6,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "Easy jog",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_cycling_edge_cases() -> dict:
    """Create a cycling workout with edge cases: watt targets, mixed intensities."""
    return {
        "title": "Mixed Power Workout",
        "blocks": [
            {
                "label": "Warmup",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "60% FTP spin",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Over-Unders",
                "structure": "3 rounds",
                "exercises": [
                    {
                        "name": "105% FTP over",
                        "duration_sec": 120,
                    },
                    {
                        "name": "85% FTP under",
                        "duration_sec": 120,
                    },
                ],
                "supersets": [],
            },
            {
                "label": "Cooldown",
                "time_work_sec": 300,
                "exercises": [
                    {
                        "name": "Easy spin recovery",
                        "duration_sec": 300,
                    },
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_zwo_xml(xml_str: str) -> str:
    """
    Normalize ZWO XML for stable golden comparisons.

    - Formats XML with consistent indentation
    - Sorts attributes for deterministic ordering
    """
    # Parse and re-serialize with consistent formatting
    # Remove XML declaration for comparison (we'll add it back)
    xml_content = re.sub(r'<\?xml[^?]*\?>\s*', '', xml_str)

    try:
        root = ET.fromstring(xml_content)
        # Re-serialize with sorted attributes
        return _element_to_normalized_string(root)
    except ET.ParseError:
        # If parsing fails, return as-is
        return xml_str


def _element_to_normalized_string(elem: ET.Element, indent: int = 0) -> str:
    """Convert element to normalized XML string with consistent formatting."""
    indent_str = "  " * indent
    tag = elem.tag

    # Sort attributes for deterministic output
    attrs = " ".join(f'{k}="{v}"' for k, v in sorted(elem.attrib.items()))
    if attrs:
        open_tag = f"{indent_str}<{tag} {attrs}>"
    else:
        open_tag = f"{indent_str}<{tag}>"

    if elem.text and elem.text.strip():
        # Element with text content
        return f"{open_tag}{elem.text.strip()}</{tag}>\n"

    children = list(elem)
    if children:
        # Element with child elements
        result = f"{open_tag}\n"
        for child in children:
            result += _element_to_normalized_string(child, indent + 1)
        result += f"{indent_str}</{tag}>\n"
        return result
    else:
        # Empty element with attributes (self-closing)
        if attrs:
            return f"{indent_str}<{tag} {attrs}/>\n"
        else:
            return f"{open_tag}</{tag}>\n"


# =============================================================================
# Running Workout Tests
# =============================================================================


class TestRunningZwoExport:
    """Golden tests for running ZWO export."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_simple_run_workout(self):
        """Simple running workout exports correctly."""
        blocks = create_simple_run_workout()
        output = to_zwo(blocks, sport="run")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/simple_run.xml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_interval_run_workout(self):
        """Running intervals export with repeats."""
        blocks = create_interval_run_workout()
        output = to_zwo(blocks, sport="run")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/interval_run.xml")


# =============================================================================
# Cycling Workout Tests
# =============================================================================


class TestCyclingZwoExport:
    """Golden tests for cycling ZWO export."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_ftp_cycling_workout(self):
        """Cycling workout with FTP percentages exports correctly."""
        blocks = create_cycling_ftp_workout()
        output = to_zwo(blocks, sport="ride")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/cycling_ftp.xml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_cycling_edge_cases(self):
        """Cycling workout with mixed power targets."""
        blocks = create_cycling_edge_cases()
        output = to_zwo(blocks, sport="ride")
        normalized = normalize_zwo_xml(output)
        assert_golden(normalized, "zwo/cycling_edge_cases.xml")


# =============================================================================
# Integration Tests
# =============================================================================


class TestZwoExportIntegration:
    """Integration tests for ZWO export."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_sport_auto_detection(self):
        """Sport type is auto-detected from exercise names."""
        run_blocks = create_simple_run_workout()
        cycle_blocks = create_cycling_ftp_workout()

        run_output = to_zwo(run_blocks)  # Should auto-detect "run"
        cycle_output = to_zwo(cycle_blocks)  # Should auto-detect "ride" (FTP keyword)

        assert "<sportType>run</sportType>" in run_output
        assert "<sportType>bike</sportType>" in cycle_output

    @pytest.mark.golden
    @pytest.mark.unit
    def test_zwo_is_valid_xml(self):
        """All ZWO exports are valid XML that can be parsed."""
        run_blocks = create_simple_run_workout()
        cycle_blocks = create_cycling_ftp_workout()

        run_output = to_zwo(run_blocks, sport="run")
        cycle_output = to_zwo(cycle_blocks, sport="ride")

        # Remove XML declaration for parsing
        run_content = re.sub(r'<\?xml[^?]*\?>\s*', '', run_output)
        cycle_content = re.sub(r'<\?xml[^?]*\?>\s*', '', cycle_output)

        # Parse should succeed
        run_root = ET.fromstring(run_content)
        cycle_root = ET.fromstring(cycle_content)

        # Check structure
        assert run_root.tag == "workout_file"
        assert cycle_root.tag == "workout_file"
        assert run_root.find("workout") is not None
        assert cycle_root.find("workout") is not None

    @pytest.mark.golden
    @pytest.mark.unit
    def test_ftp_percentage_extraction(self):
        """FTP percentages are correctly extracted from exercise names."""
        from backend.adapters.blocks_to_zwo import extract_power_target

        # Single percentage
        target = extract_power_target("50% FTP warmup")
        assert target is not None
        assert target.type == "power"
        assert target.min == 0.50
        assert target.max == 0.50

        # High single percentage
        target = extract_power_target("105% FTP over")
        assert target is not None
        assert target.type == "power"
        assert target.min == 1.05
        assert target.max == 1.05

        # No percentage
        target = extract_power_target("easy jog")
        assert target is None
