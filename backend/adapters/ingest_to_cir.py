import re
from collections import OrderedDict
from typing import List, Optional, Tuple

from shared.schemas.cir import CIR, Workout, Block, Exercise


# Extensible mapping from ingestor structure names to CIR BlockType values.
# Add new structure types here — no logic changes needed.
STRUCTURE_TO_BLOCK_TYPE = {
    "superset": "superset",
    "circuit": "circuit",
    "tabata": "timed_round",
    "emom": "timed_round",
    "amrap": "timed_round",
    "for-time": "timed_round",
}


def _exercise_from_dict(e: dict) -> Exercise:
    """Convert an exercise dict to a CIR Exercise."""
    return Exercise(
        name=e["name"],
        sets=e.get("sets"),
        reps=e.get("reps"),
        duration_seconds=e.get("duration_seconds"),
        rest_seconds=e.get("rest") or e.get("rest_sec"),
        equipment=e.get("equipment", []),
        modifiers=e.get("modifiers", []),
        tempo=e.get("tempo"),
    )


def _resolve_rounds(block_dict: dict) -> int:
    """Resolve the rounds/sets count for a block, with fallbacks."""
    # 1. Block-level rounds or sets
    rounds = block_dict.get("rounds") or block_dict.get("sets")
    if rounds and rounds > 0:
        return rounds
    # 2. First exercise's sets as fallback (common for supersets)
    exercises = block_dict.get("exercises", [])
    if exercises:
        first_sets = exercises[0].get("sets")
        if first_sets and first_sets > 0:
            return first_sets
    # 3. Default
    return 1


def _detect_superset_label(e: dict) -> Optional[str]:
    """Extract a superset group label from an exercise dict.

    Checks (in order):
    1. Explicit superset_label/group field
    2. Parenthesized label like "(superset A)"
    3. Letter-number prefix like "A1:", "B2:"
    """
    # Explicit field
    label = e.get("superset_label") or e.get("group")
    if label:
        return str(label).upper()

    name = e.get("name", "")

    # Parenthesized: "(superset A)", "(superset B)"
    match = re.search(r'\(superset\s+([A-Za-z])\)', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Letter prefix: "A1:", "A2:", "B1;" (requires colon or semicolon delimiter)
    match = re.match(r'^([A-Za-z])\d+\s*[:;]\s*', name)
    if match:
        return match.group(1).upper()

    return None


def _clean_superset_label_from_name(name: str) -> str:
    """Remove parenthesized superset labels like '(superset A)' from exercise name."""
    cleaned = re.sub(r'\s*\(superset\s+[A-Za-z]\)', '', name, flags=re.IGNORECASE).strip()
    return cleaned


def detect_superset_groups(exercises: List[dict]) -> List[Block]:
    """Detect superset groupings in a flat exercise list and return CIR Blocks.

    Groups consecutive exercises that share a superset label into
    Block(type="superset"). Ungrouped exercises are collected into
    Block(type="straight") blocks.
    """
    if not exercises:
        return [Block(type="straight", rounds=1, items=[])]

    # Tag each exercise with its detected label (or None)
    tagged: List[Tuple[Optional[str], dict]] = []
    for e in exercises:
        label = _detect_superset_label(e)
        tagged.append((label, e))

    # Group into blocks, preserving order
    blocks: List[Block] = []
    # Collect consecutive exercises by label
    # When label changes or is None, flush the current group
    current_label: Optional[str] = None
    current_group: List[dict] = []
    standalone_buffer: List[dict] = []

    def _flush_standalone():
        nonlocal standalone_buffer
        if standalone_buffer:
            items = [_exercise_from_dict(e) for e in standalone_buffer]
            blocks.append(Block(type="straight", rounds=1, items=items))
            standalone_buffer = []

    def _flush_superset():
        nonlocal current_group, current_label
        if current_group and current_label is not None:
            # Determine rounds from first exercise's sets
            rounds = 1
            first_sets = current_group[0].get("sets")
            if first_sets and first_sets > 0:
                rounds = first_sets
            items = []
            for e in current_group:
                ex = _exercise_from_dict(e)
                # Clean superset label from name if present
                cleaned_name = _clean_superset_label_from_name(ex.name)
                if cleaned_name != ex.name:
                    ex = ex.model_copy(update={"name": cleaned_name})
                items.append(ex)
            blocks.append(Block(type="superset", rounds=rounds, items=items))
            current_group = []
            current_label = None

    for label, e in tagged:
        if label is None:
            # Flush any pending superset group first
            _flush_superset()
            standalone_buffer.append(e)
        else:
            if label == current_label:
                # Continue current superset group
                current_group.append(e)
            else:
                # New label — flush previous superset if any
                _flush_superset()
                # Flush standalone buffer before starting new superset
                _flush_standalone()
                current_label = label
                current_group = [e]

    # Flush remaining
    _flush_superset()
    _flush_standalone()

    return blocks if blocks else [Block(type="straight", rounds=1, items=[])]


def _blocks_from_structured_input(ingest_json: dict) -> List[Block]:
    """Convert structured blocks[] input to CIR Blocks."""
    blocks = []
    for block_dict in ingest_json.get("blocks", []):
        exercises = block_dict.get("exercises", [])
        items = [_exercise_from_dict(e) for e in exercises]

        structure = block_dict.get("structure", "")
        block_type = STRUCTURE_TO_BLOCK_TYPE.get(structure, "straight")
        rounds = _resolve_rounds(block_dict)

        blocks.append(Block(type=block_type, rounds=rounds, items=items))
    return blocks


def to_cir(ingest_json: dict) -> CIR:
    """Convert ingest JSON to CIR format.

    Handles two input shapes:
    1. Structured: {"blocks": [{"structure": "superset", "exercises": [...]}]}
    2. Flat: {"exercises": [...]} — applies superset detection heuristic
    """
    # Path 1: Structured blocks input
    if "blocks" in ingest_json and ingest_json["blocks"]:
        blocks = _blocks_from_structured_input(ingest_json)
    # Path 2: Flat exercises list with heuristic detection
    elif "exercises" in ingest_json:
        exercises = ingest_json.get("exercises", [])
        blocks = detect_superset_groups(exercises)
    else:
        blocks = [Block(type="straight", rounds=1, items=[])]

    return CIR(workout=Workout(
        title=ingest_json.get("title", "Imported Workout"),
        notes=ingest_json.get("notes"),
        tags=ingest_json.get("tags", []),
        blocks=blocks,
    ))
