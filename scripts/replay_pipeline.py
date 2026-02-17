"""Pipeline replay script — runs workout data through transformation stages and diffs.

Passes workout JSON through the mapper-api transformation pipeline:
  ingest → CIR → Garmin YAML / WorkoutKit

At each hop, captures the output and compares against the input to find
where data is lost or corrupted.

Usage:
    python scripts/replay_pipeline.py                    # Run all built-in scenarios
    python scripts/replay_pipeline.py --scenario hyrox   # Run specific scenario
    python scripts/replay_pipeline.py --file input.json  # Run from file
"""

import json
import sys
import os
from pathlib import Path
from typing import Any

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.adapters.ingest_to_cir import to_cir
from backend.adapters.cir_to_garmin_yaml import to_garmin_yaml
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from backend.replay.core import Session, DiffEngine, IgnoreConfig
import yaml


# --- Built-in test scenarios ---

SCENARIOS = {
    "simple-strength": {
        "title": "Simple Strength",
        "exercises": [
            {"name": "Barbell Back Squat", "sets": 4, "reps": 8, "rest": 90, "equipment": ["barbell"]},
            {"name": "Bench Press", "sets": 4, "reps": 8, "rest": 90, "equipment": ["barbell", "bench"]},
            {"name": "Barbell Row", "sets": 3, "reps": 10, "rest": 60, "equipment": ["barbell"]},
        ],
    },
    "superset-workout": {
        "title": "Upper Body Supersets",
        "exercises": [
            {"name": "A1: Bench Press", "sets": 4, "reps": 8, "rest": 30, "equipment": ["barbell"]},
            {"name": "A2: Barbell Row", "sets": 4, "reps": 8, "rest": 90, "equipment": ["barbell"]},
            {"name": "B1: Overhead Press", "sets": 3, "reps": 10, "rest": 30, "equipment": ["barbell"]},
            {"name": "B2: Pull-ups", "sets": 3, "reps": 10, "rest": 90, "equipment": []},
            {"name": "Bicep Curls", "sets": 3, "reps": 12, "rest": 60, "equipment": ["dumbbell"]},
        ],
    },
    "circuit-training": {
        "title": "Full Body Circuit",
        "exercises": [
            {"name": "C1: Squats", "sets": 3, "reps": 15, "rest": 0, "equipment": []},
            {"name": "C1: Push-ups", "sets": 3, "reps": 15, "rest": 0, "equipment": []},
            {"name": "C1: Lunges", "sets": 3, "reps": 12, "rest": 0, "equipment": []},
            {"name": "C1: Burpees", "sets": 3, "reps": 10, "rest": 60, "equipment": []},
        ],
    },
    "hyrox": {
        "title": "Hyrox Full Simulation",
        "blocks": [
            {
                "structure": "circuit",
                "rounds": 1,
                "exercises": [
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "SkiErg", "reps": "1000m", "duration_seconds": 240},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Sled Push", "reps": "50m", "duration_seconds": 180},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Sled Pull", "reps": "50m", "duration_seconds": 180},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Burpee Broad Jumps", "reps": "80m", "duration_seconds": 240},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Rowing", "reps": "1000m", "duration_seconds": 240},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Farmers Carry", "reps": "200m", "duration_seconds": 180},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Sandbag Lunges", "reps": "100m", "duration_seconds": 300},
                    {"name": "1km Run", "duration_seconds": 300},
                    {"name": "Wall Balls", "reps": 100, "duration_seconds": 300},
                ],
            }
        ],
    },
    "structured-superset": {
        "title": "Structured Superset Input",
        "blocks": [
            {
                "structure": "superset",
                "rounds": 4,
                "exercises": [
                    {"name": "Bench Press", "sets": 4, "reps": 8, "rest": 30, "equipment": ["barbell"]},
                    {"name": "Barbell Row", "sets": 4, "reps": 8, "rest": 90, "equipment": ["barbell"]},
                ],
            },
            {
                "structure": "straight",
                "exercises": [
                    {"name": "Bicep Curls", "sets": 3, "reps": 12, "rest": 60, "equipment": ["dumbbell"]},
                ],
            },
        ],
    },
    "mixed-flat": {
        "title": "Mixed Flat with Circuit Label",
        "exercises": [
            {"name": "Barbell Back Squat", "sets": 4, "reps": 8, "rest": 90, "equipment": ["barbell"]},
            {"name": "A1: Bench Press", "sets": 3, "reps": 10, "rest": 30, "equipment": ["barbell"]},
            {"name": "A2: Dumbbell Rows", "sets": 3, "reps": 10, "rest": 60, "equipment": ["dumbbell"]},
            {"name": "C1: Burpees", "sets": 3, "reps": 10, "rest": 0, "circuit_label": "finisher"},
            {"name": "C1: Mountain Climbers", "sets": 3, "reps": 20, "rest": 0, "circuit_label": "finisher"},
            {"name": "C1: Jump Squats", "sets": 3, "reps": 15, "rest": 60, "circuit_label": "finisher"},
        ],
    },
}


class Colors:
    RESET = '\033[0m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    CYAN = '\033[96m'


def cir_to_dict(cir_obj) -> dict:
    """Convert CIR pydantic model to a plain dict for diffing."""
    return json.loads(cir_obj.model_dump_json())


def garmin_yaml_to_dict(yaml_str: str) -> dict:
    """Parse Garmin YAML export to dict."""
    return yaml.safe_load(yaml_str)


def run_scenario(name: str, ingest_json: dict) -> dict:
    """Run a scenario through the full pipeline, returning a report."""
    report = {
        "scenario": name,
        "input": ingest_json,
        "hops": [],
        "bugs_found": [],
    }

    # --- Hop 1: ingest → CIR ---
    try:
        cir = to_cir(ingest_json)
        cir_dict = cir_to_dict(cir)
        report["hops"].append({
            "name": "ingest → CIR",
            "success": True,
            "output": cir_dict,
        })
    except Exception as e:
        report["hops"].append({
            "name": "ingest → CIR",
            "success": False,
            "error": str(e),
        })
        report["bugs_found"].append({
            "hop": "ingest → CIR",
            "type": "crash",
            "error": str(e),
        })
        return report

    # --- Validate CIR against input ---
    input_exercise_count = _count_input_exercises(ingest_json)
    cir_exercise_count = sum(len(b["items"]) for b in cir_dict["workout"]["blocks"])

    if cir_exercise_count != input_exercise_count:
        report["bugs_found"].append({
            "hop": "ingest → CIR",
            "type": "exercise_count_mismatch",
            "expected": input_exercise_count,
            "actual": cir_exercise_count,
            "detail": f"Input had {input_exercise_count} exercises, CIR has {cir_exercise_count}",
        })

    # Check for lost data per exercise
    _check_exercise_data_preservation(ingest_json, cir_dict, report)

    # --- Hop 2: CIR → Garmin YAML ---
    try:
        garmin_yaml_str = to_garmin_yaml(cir)
        garmin_dict = garmin_yaml_to_dict(garmin_yaml_str)
        report["hops"].append({
            "name": "CIR → Garmin YAML",
            "success": True,
            "output": garmin_dict,
        })
    except Exception as e:
        report["hops"].append({
            "name": "CIR → Garmin YAML",
            "success": False,
            "error": str(e),
        })
        report["bugs_found"].append({
            "hop": "CIR → Garmin YAML",
            "type": "crash",
            "error": str(e),
        })

    # --- Hop 3: CIR → WorkoutKit ---
    # WorkoutKit expects blocks_json format (the raw blocks dict)
    try:
        # Build the blocks_json format that to_workoutkit expects
        blocks_json = _cir_to_blocks_json(cir_dict)
        wk_output = to_workoutkit(blocks_json)
        wk_dict = json.loads(wk_output.model_dump_json())
        report["hops"].append({
            "name": "CIR → WorkoutKit",
            "success": True,
            "output": wk_dict,
        })
    except Exception as e:
        report["hops"].append({
            "name": "CIR → WorkoutKit",
            "success": False,
            "error": str(e),
        })
        report["bugs_found"].append({
            "hop": "CIR → WorkoutKit",
            "type": "crash",
            "error": str(e),
        })

    return report


def _count_input_exercises(ingest_json: dict) -> int:
    """Count exercises in the input JSON."""
    if "blocks" in ingest_json and ingest_json["blocks"]:
        return sum(len(b.get("exercises", [])) for b in ingest_json["blocks"])
    return len(ingest_json.get("exercises", []))


def _check_exercise_data_preservation(ingest_json: dict, cir_dict: dict, report: dict):
    """Check that exercise data (sets, reps, rest, equipment) is preserved through CIR."""
    # Build flat list of input exercises
    input_exercises = []
    if "blocks" in ingest_json and ingest_json["blocks"]:
        for block in ingest_json["blocks"]:
            input_exercises.extend(block.get("exercises", []))
    else:
        input_exercises = ingest_json.get("exercises", [])

    # Build flat list of CIR exercises
    cir_exercises = []
    for block in cir_dict["workout"]["blocks"]:
        cir_exercises.extend(block["items"])

    # Compare by position (after accounting for possible reordering)
    for i, (inp, cir_ex) in enumerate(zip(input_exercises, cir_exercises)):
        # Check sets
        inp_sets = inp.get("sets")
        cir_sets = cir_ex.get("sets")
        if inp_sets is not None and cir_sets != inp_sets:
            report["bugs_found"].append({
                "hop": "ingest → CIR",
                "type": "field_changed",
                "exercise": inp["name"],
                "field": "sets",
                "expected": inp_sets,
                "actual": cir_sets,
            })

        # Check reps
        inp_reps = inp.get("reps")
        cir_reps = cir_ex.get("reps")
        if inp_reps is not None and cir_reps != inp_reps and str(cir_reps) != str(inp_reps):
            report["bugs_found"].append({
                "hop": "ingest → CIR",
                "type": "field_changed",
                "exercise": inp["name"],
                "field": "reps",
                "expected": inp_reps,
                "actual": cir_reps,
            })

        # Check rest
        inp_rest = inp.get("rest") or inp.get("rest_sec")
        cir_rest = cir_ex.get("rest_seconds")
        if inp_rest is not None and cir_rest != inp_rest:
            report["bugs_found"].append({
                "hop": "ingest → CIR",
                "type": "field_changed",
                "exercise": inp["name"],
                "field": "rest_seconds",
                "expected": inp_rest,
                "actual": cir_rest,
            })

        # Check equipment
        inp_equip = inp.get("equipment", [])
        cir_equip = cir_ex.get("equipment", [])
        if set(inp_equip) != set(cir_equip):
            report["bugs_found"].append({
                "hop": "ingest → CIR",
                "type": "field_changed",
                "exercise": inp["name"],
                "field": "equipment",
                "expected": inp_equip,
                "actual": cir_equip,
            })


def _cir_to_blocks_json(cir_dict: dict) -> dict:
    """Convert CIR dict to blocks_json format for WorkoutKit adapter.

    Maps CIR field names to the blocks_json field names that
    blocks_to_workoutkit.py expects:
      CIR 'type' → blocks_json 'structure' (checked by adapter)
      CIR 'rest_seconds' → blocks_json 'rest_sec'
      CIR 'duration_seconds' → blocks_json 'duration_sec'
      CIR 'rest_between_sets_seconds' → blocks_json 'rest_between_sec'
    """
    blocks = []
    for block in cir_dict["workout"]["blocks"]:
        block_dict = {
            "structure": block["type"],  # adapter checks "structure" or "type"
            "type": block["type"],       # fallback
            "rounds": block.get("rounds", 1),
            "rest_between_sec": block.get("rest_between_sets_seconds"),
            "exercises": [],
        }
        for ex in block["items"]:
            block_dict["exercises"].append({
                "name": ex["name"],
                "canonical_name": ex.get("canonical_name"),
                "sets": ex.get("sets"),
                "reps": ex.get("reps"),
                "duration_sec": ex.get("duration_seconds"),
                "rest_sec": ex.get("rest_seconds"),
                "equipment": ex.get("equipment", []),
            })
        blocks.append(block_dict)
    return {
        "title": cir_dict["workout"]["title"],
        "blocks": blocks,
    }


def print_report(report: dict):
    """Print a formatted report for a single scenario."""
    name = report["scenario"]
    bugs = report["bugs_found"]

    if bugs:
        status = f"{Colors.RED}BUGS FOUND ({len(bugs)}){Colors.RESET}"
    else:
        status = f"{Colors.GREEN}CLEAN{Colors.RESET}"

    print(f"\n{'='*70}")
    print(f"{Colors.BOLD}Scenario: {name}{Colors.RESET}  [{status}]")
    print(f"{'='*70}")

    for hop in report["hops"]:
        if hop["success"]:
            print(f"  {Colors.GREEN}✓{Colors.RESET} {hop['name']}")
        else:
            print(f"  {Colors.RED}✗{Colors.RESET} {hop['name']}: {hop.get('error', 'unknown')}")

    if bugs:
        print(f"\n  {Colors.BOLD}Bugs:{Colors.RESET}")
        for bug in bugs:
            hop = bug["hop"]
            bug_type = bug["type"]
            if bug_type == "crash":
                print(f"    {Colors.RED}[CRASH]{Colors.RESET} at {hop}: {bug['error']}")
            elif bug_type == "exercise_count_mismatch":
                print(f"    {Colors.YELLOW}[COUNT]{Colors.RESET} at {hop}: expected {bug['expected']} exercises, got {bug['actual']}")
            elif bug_type == "field_changed":
                print(f"    {Colors.YELLOW}[FIELD]{Colors.RESET} at {hop}: {bug['exercise']}.{bug['field']} = {bug['expected']} → {bug['actual']}")
            else:
                print(f"    {Colors.CYAN}[{bug_type.upper()}]{Colors.RESET} at {hop}: {bug}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Replay workout through transformation pipeline")
    parser.add_argument("--scenario", "-s", help="Run specific scenario")
    parser.add_argument("--file", "-f", type=Path, help="Load scenario from JSON file")
    parser.add_argument("--json-output", "-j", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    scenarios_to_run = {}

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
        scenarios_to_run[args.file.stem] = data
    elif args.scenario:
        if args.scenario not in SCENARIOS:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available: {', '.join(SCENARIOS.keys())}")
            sys.exit(1)
        scenarios_to_run[args.scenario] = SCENARIOS[args.scenario]
    else:
        scenarios_to_run = SCENARIOS

    all_reports = []
    total_bugs = 0

    for name, ingest_json in scenarios_to_run.items():
        report = run_scenario(name, ingest_json)
        all_reports.append(report)
        total_bugs += len(report["bugs_found"])
        if not args.json_output:
            print_report(report)

    if args.json_output:
        print(json.dumps(all_reports, indent=2, default=str))
    else:
        print(f"\n{'='*70}")
        print(f"{Colors.BOLD}Summary:{Colors.RESET} {len(all_reports)} scenarios, {total_bugs} bugs found")
        if total_bugs > 0:
            print(f"{Colors.RED}Pipeline has data integrity issues!{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}All scenarios clean.{Colors.RESET}")

    # Save reports to captures directory for replay engine
    captures_dir = ROOT / "captures" / "pipeline-replay"
    captures_dir.mkdir(parents=True, exist_ok=True)
    for report in all_reports:
        report_path = captures_dir / f"{report['scenario']}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))

    sys.exit(1 if total_bugs > 0 else 0)


if __name__ == "__main__":
    main()
