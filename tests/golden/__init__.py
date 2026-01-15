"""
Golden test harness for export output validation.

Part of AMA-395: Create golden test harness for exporters
Phase 4 - Testing Overhaul

This package provides infrastructure for snapshot/golden testing of export outputs.
Golden tests compare actual output against saved "golden" fixtures to detect
unintended changes in export formats.

Usage:
    from tests.golden import assert_golden, update_golden

    @pytest.mark.golden
    def test_yaml_export(workout_data):
        output = to_garmin_yaml(workout_data)
        assert_golden(output, "exports/yaml/simple_workout.yaml")

To update fixtures when output changes intentionally:
    pytest --update-golden tests/golden/
"""

from tests.golden.conftest import (
    assert_golden,
    update_golden,
    GoldenTestError,
    FIXTURES_DIR,
)

__all__ = [
    "assert_golden",
    "update_golden",
    "GoldenTestError",
    "FIXTURES_DIR",
]
