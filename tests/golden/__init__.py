"""
Golden test harness for export output validation.

Part of AMA-395: Create golden test harness for exporters
Phase 4 - Testing Overhaul
Extended in AMA-371: Additional helpers for workout fixture loading

This package provides infrastructure for snapshot/golden testing of export outputs.
Golden tests compare actual output against saved "golden" fixtures to detect
unintended changes in export formats.

Usage:
    from tests.golden import assert_golden, update_golden, load_fixture, compare_output

    @pytest.mark.golden
    def test_yaml_export(workout_data):
        # Load input fixture
        workout = load_fixture("workouts/simple.json")

        # Process and export
        output = to_garmin_yaml(workout)

        # Compare against expected output
        assert_golden(output, "exports/yaml/simple_workout.yaml")

    # Or use compare_output for more control
    @pytest.mark.golden
    def test_workout_export_comparison(workout_data):
        output = export_workout(workout_data)
        compare_output(output, "expected/workout_output.json", regenerate=False)

To update fixtures when output changes intentionally:
    pytest --update-golden tests/golden/
    pytest --regenerate-golden tests/golden/
"""

from tests.golden.conftest import (
    assert_golden,
    update_golden,
    load_fixture,
    compare_output,
    GoldenTestError,
    FIXTURES_DIR,
)

__all__ = [
    "assert_golden",
    "update_golden",
    "load_fixture",
    "compare_output",
    "GoldenTestError",
    "FIXTURES_DIR",
]
