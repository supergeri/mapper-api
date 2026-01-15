"""
Golden tests for YAML export adapters.

Part of AMA-396: Add golden fixtures for YAML export
Phase 4 - Testing Overhaul

Tests YAML export output against saved fixtures to detect unintended changes.
Covers:
- cir_to_garmin_yaml: CIR -> Garmin YAML
- blocks_to_hyrox_yaml: blocks JSON -> Hyrox YAML
- blocks_to_hiit_garmin_yaml: blocks JSON -> HIIT YAML
"""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from tests.golden import assert_golden
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.adapters.blocks_to_hyrox_yaml import to_hyrox_yaml
from backend.adapters.blocks_to_hiit_garmin_yaml import to_hiit_garmin_yaml, is_hiit_workout
from shared.schemas.cir import CIR, Workout, Block, Exercise


# =============================================================================
# Test Data Factories
# =============================================================================


def create_simple_cir() -> CIR:
    """Create a simple CIR workout with basic exercises."""
    return CIR(
        workout=Workout(
            title="Simple Strength Workout",
            notes="Basic strength training session",
            tags=["strength", "beginner"],
            blocks=[
                Block(
                    type="straight",
                    rounds=1,
                    items=[
                        Exercise(
                            name="Barbell Squat",
                            canonical_name="squat",
                            sets=3,
                            reps=10,
                            rest_seconds=90,
                        ),
                        Exercise(
                            name="Bench Press",
                            canonical_name="bench_press",
                            sets=3,
                            reps=8,
                            rest_seconds=120,
                        ),
                    ],
                ),
            ],
        )
    )


def create_circuit_cir() -> CIR:
    """Create a CIR workout with circuit/superset structure."""
    return CIR(
        workout=Workout(
            title="Circuit Training",
            notes="Full body circuit",
            tags=["circuit", "conditioning"],
            blocks=[
                Block(
                    type="circuit",
                    rounds=3,
                    items=[
                        Exercise(
                            name="Pull-up",
                            canonical_name="pull_up",
                            sets=1,
                            reps=10,
                            rest_seconds=30,
                        ),
                        Exercise(
                            name="Push-up",
                            canonical_name="push_up",
                            sets=1,
                            reps=15,
                            rest_seconds=30,
                        ),
                        Exercise(
                            name="Air Squat",
                            canonical_name="air_squat",
                            sets=1,
                            reps=20,
                            rest_seconds=60,
                        ),
                    ],
                ),
            ],
        )
    )


def create_simple_blocks() -> dict:
    """Create simple blocks JSON for non-HIIT workout."""
    return {
        "title": "Week 1 Strength",
        "blocks": [
            {
                "label": "Block A",
                "structure": "3 rounds",
                "exercises": [
                    {
                        "name": "Goblet Squat",
                        "sets": 3,
                        "reps": 10,
                        "rest_type": "timed",
                        "rest_sec": 60,
                    },
                    {
                        "name": "Push Up",
                        "sets": 3,
                        "reps": 12,
                        "rest_type": "button",
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_superset_blocks() -> dict:
    """Create blocks JSON with supersets."""
    return {
        "title": "Superset Workout",
        "blocks": [
            {
                "label": "Superset A",
                "structure": "4 rounds",
                "exercises": [],
                "supersets": [
                    {
                        "exercises": [
                            {
                                "name": "A1: DB Incline Bench Press X8",
                                "reps": 8,
                                "rest_type": "timed",
                                "rest_sec": 30,
                            },
                            {
                                "name": "A2: TRX Rows X10",
                                "reps": 10,
                                "rest_type": "timed",
                                "rest_sec": 60,
                            },
                        ],
                    },
                ],
                "rest_between_sec": 90,
            },
        ],
    }


def create_hiit_blocks() -> dict:
    """Create blocks JSON for HIIT workout (for time)."""
    return {
        "title": "HIIT For Time",
        "blocks": [
            {
                "label": "Main",
                "structure": "for time (cap: 20 min)",
                "time_work_sec": 1200,
                "exercises": [
                    {
                        "name": "Run",
                        "distance_m": 400,
                    },
                    {
                        "name": "Burpees",
                        "reps": 10,
                    },
                    {
                        "name": "Wall Ball",
                        "reps": 20,
                    },
                ],
                "supersets": [],
            },
        ],
    }


def create_edge_case_blocks() -> dict:
    """Create blocks JSON with edge cases: special characters, complex names, etc."""
    return {
        "title": "Edge Case Workout & Test!",
        "blocks": [
            {
                "label": "Mixed",
                "structure": "2 rounds",
                "exercises": [
                    {
                        "name": "KB RDL into Goblet Squat X10",
                        "reps": 10,
                        "notes": "Keep back straight; don't rush",
                    },
                    {
                        "name": "200m Ski",
                        "distance_m": 200,
                    },
                    {
                        "name": "Band-Resisted Push-Ups (Heavy)",
                        "reps": 15,
                        "notes": "Full ROM; chest to floor",
                    },
                ],
                "supersets": [],
            },
        ],
    }


# =============================================================================
# Utility Functions
# =============================================================================


def normalize_yaml_date(yaml_output: str) -> str:
    """
    Normalize dynamic dates in YAML output for stable golden comparisons.

    The schedulePlan.start_from date is generated dynamically (today + 7 days),
    so we replace it with a fixed placeholder.
    """
    # Replace ISO date pattern in start_from: 'YYYY-MM-DD'
    return re.sub(
        r"start_from:\s*['\"]?\d{4}-\d{2}-\d{2}['\"]?",
        "start_from: 'NORMALIZED_DATE'",
        yaml_output,
    )


# =============================================================================
# CIR to Garmin YAML Tests
# =============================================================================


class TestCirToGarminYaml:
    """Golden tests for cir_to_garmin_yaml adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_simple_workout(self):
        """Simple straight-set workout exports correctly."""
        cir = create_simple_cir()
        output = to_garmin_yaml(cir)
        assert_golden(output, "yaml/cir_simple_workout.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_circuit_workout(self):
        """Circuit/superset workout exports with repeat structure."""
        cir = create_circuit_cir()
        output = to_garmin_yaml(cir)
        assert_golden(output, "yaml/cir_circuit_workout.yaml")


# =============================================================================
# Blocks to Hyrox YAML Tests
# =============================================================================


class TestBlocksToHyroxYaml:
    """Golden tests for blocks_to_hyrox_yaml adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_simple_strength_workout(self):
        """Simple strength workout exports correctly."""
        blocks = create_simple_blocks()
        output = to_hyrox_yaml(blocks)
        # Normalize date for stable comparison
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_simple_strength.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_superset_workout(self):
        """Superset workout exports with proper structure."""
        blocks = create_superset_blocks()
        output = to_hyrox_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_superset.yaml")

    @pytest.mark.golden
    @pytest.mark.unit
    def test_edge_cases(self):
        """Edge cases (special chars, empty names) handled correctly."""
        blocks = create_edge_case_blocks()
        output = to_hyrox_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hyrox_edge_cases.yaml")


# =============================================================================
# Blocks to HIIT YAML Tests
# =============================================================================


class TestBlocksToHiitYaml:
    """Golden tests for blocks_to_hiit_garmin_yaml adapter."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_hiit_detection(self):
        """HIIT workout is correctly detected."""
        hiit_blocks = create_hiit_blocks()
        non_hiit_blocks = create_simple_blocks()

        assert is_hiit_workout(hiit_blocks) is True
        assert is_hiit_workout(non_hiit_blocks) is False

    @pytest.mark.golden
    @pytest.mark.unit
    def test_hiit_for_time(self):
        """HIIT for-time workout exports with repeatUntilTime wrapper."""
        blocks = create_hiit_blocks()
        output = to_hiit_garmin_yaml(blocks)
        output = normalize_yaml_date(output)
        assert_golden(output, "yaml/hiit_for_time.yaml")


# =============================================================================
# Integration Tests
# =============================================================================


class TestYamlExportIntegration:
    """Integration tests for complete YAML export workflow."""

    @pytest.mark.golden
    @pytest.mark.unit
    def test_auto_map_selects_correct_adapter(self):
        """Auto-map endpoint logic selects correct adapter based on workout type."""
        from backend.adapters.blocks_to_hiit_garmin_yaml import is_hiit_workout

        hiit_blocks = create_hiit_blocks()
        strength_blocks = create_simple_blocks()

        # HIIT detection should work correctly
        assert is_hiit_workout(hiit_blocks) is True
        assert is_hiit_workout(strength_blocks) is False

        # Export using appropriate adapter
        hiit_output = to_hiit_garmin_yaml(hiit_blocks)
        strength_output = to_hyrox_yaml(strength_blocks)

        # HIIT output should have "sport: hiit"
        assert "sport: hiit" in hiit_output

        # Strength output should not have sport at top level (it's in workouts dict)
        # The Hyrox format doesn't explicitly specify sport

    @pytest.mark.golden
    @pytest.mark.unit
    def test_yaml_is_valid_format(self):
        """All YAML exports are valid YAML that can be parsed."""
        import yaml

        # Test CIR
        cir = create_simple_cir()
        cir_output = to_garmin_yaml(cir)
        parsed_cir = yaml.safe_load(cir_output)
        assert "workout" in parsed_cir

        # Test Hyrox
        hyrox_blocks = create_simple_blocks()
        hyrox_output = to_hyrox_yaml(hyrox_blocks)
        parsed_hyrox = yaml.safe_load(hyrox_output)
        assert "settings" in parsed_hyrox
        assert "workouts" in parsed_hyrox

        # Test HIIT
        hiit_blocks = create_hiit_blocks()
        hiit_output = to_hiit_garmin_yaml(hiit_blocks)
        parsed_hiit = yaml.safe_load(hiit_output)
        assert "settings" in parsed_hiit
        assert "workouts" in parsed_hiit
