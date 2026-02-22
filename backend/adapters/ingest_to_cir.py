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


def _extract_reps_from_name(name: str) -> Optional[int]:
    """Extract reps from exercise name prefix (e.g., '100 wall balls' -> 100)."""
    match = re.match(r'^(\d+)\s+(.+)$', name)
    if match:
        return int(match.group(1))
    return None


def _extract_distance_from_name(name: str) -> Optional[Tuple[float, str]]:
    """Extract distance from exercise name (e.g., '1000m Ski' -> (1000, 'm'))."""
    match = re.match(r'^(\d+(?:\.\d+)?)\s*(m|km|miles?|yards?)\s+(.+)$', name, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        unit = match.group(2).lower()
        # Normalize unit
        if unit.startswith('m') and len(unit) == 1:
            unit = 'm'  # meters
        elif unit == 'mi':
            unit = 'miles'
        return (value, unit)
    return None


def _clean_name_of_numeric_prefix(name: str) -> str:
    """Remove numeric prefix from exercise name (e.g., '100 wall balls' -> 'wall balls')."""
    match = re.match(r'^\d+\s+(.+)$', name)
    if match:
        return match.group(1)
    return name


def _detect_timed_station_format(block_dict: dict) -> Optional[int]:
    """Detect if block is a timed-station format (e.g., Hyrox).
    
    Returns the time cap in seconds if detected, None otherwise.
    
    Timed-station format indicators:
    - structure contains "timed station" or "station" or "hyrox"
    - time_cap_sec or time_work_sec is present
    - exercises have time-based notes like "5 minute cap"
    - structure contains time windows like "0-5:", "5-10:"
    """
    structure = block_dict.get("structure", "") or ""
    structure_lower = structure.lower()
    
    # Check for explicit time cap
    time_cap = block_dict.get("time_cap_sec") or block_dict.get("time_work_sec")
    if time_cap:
        return time_cap
    
    # Check for timed-station keywords in structure
    if "timed station" in structure_lower or "station" in structure_lower:
        # Try to extract time from structure like "5 minute station" or "5 min cap"
        time_match = re.search(r'(\d+)\s*(minute|min|second|sec)', structure, re.IGNORECASE)
        if time_match:
            value = int(time_match.group(1))
            unit = time_match.group(2).lower()
            if unit.startswith('min'):
                return value * 60
            return value
    
    # Check for time window pattern in notes or structure (e.g., "0-5:", "5-10:")
    notes = block_dict.get("notes", "") or ""
    full_text = f"{structure} {notes}"
    if re.search(r'\d+-\d+:', full_text):
        # Time window pattern detected - extract time interval
        # Pattern "0-5:" means 5 minute windows
        time_match = re.search(r'(\d+)-(\d+):', full_text)
        if time_match:
            start = int(time_match.group(1))
            end = int(time_match.group(2))
            return (end - start) * 60
    
    return None


def _exercise_from_dict(e: dict, time_cap_note: Optional[str] = None) -> Exercise:
    """Convert an exercise dict to a CIR Exercise."""
    name = e.get("name", "")
    
    # Extract reps from name prefix if not provided in dict
    reps = e.get("reps")
    if reps is None and name:
        reps = _extract_reps_from_name(name)
    
    # Use provided distance if available, otherwise try to extract from name
    distance = e.get("distance")
    distance_unit = e.get("distance_unit")
    if distance is None and name:
        dist_result = _extract_distance_from_name(name)
        if dist_result:
            distance, distance_unit = dist_result
    
    # Clean name of numeric prefix (only if we extracted reps from it)
    clean_name = name
    if reps is not None and _extract_reps_from_name(name):
        clean_name = _clean_name_of_numeric_prefix(name)
    
    # Get notes - add time cap note if provided
    notes = e.get("notes")
    if time_cap_note and not notes:
        notes = time_cap_note
    elif time_cap_note and notes:
        notes = f"{time_cap_note}. {notes}"
    
    return Exercise(
        name=clean_name or e.get("name", "Exercise"),
        sets=e.get("sets"),
        reps=reps,
        duration_seconds=e.get("duration_seconds"),
        rest_seconds=e.get("rest") or e.get("rest_sec"),
        equipment=e.get("equipment", []),
        modifiers=e.get("modifiers", []),
        tempo=e.get("tempo"),
        distance=distance,
        distance_unit=distance_unit,
        notes=notes,
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


def _detect_circuit_label(e: dict) -> Optional[str]:
    """Extract a circuit group label from an exercise dict.

    Checks (in order):
    1. Explicit circuit_label/circuit_group field
    2. Parenthesized label like "(circuit A)" or "(rounds A)"
    3. Letter prefix with multiple exercises: "A1:", "A2:", "A3:" (3+ with same letter = circuit)
    """
    # Explicit field
    label = e.get("circuit_label") or e.get("circuit_group") or e.get("rounds_label")
    if label:
        return str(label).upper()

    name = e.get("name", "")

    # Parenthesized: "(circuit A)", "(rounds A)", "(circuit 1)"
    match = re.search(r'\(circuit\s+([A-Za-z0-9])\)', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    match = re.search(r'\(rounds\s+([A-Za-z0-9])\)', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Letter prefix: "A1:", "A2:", "A3:" (3+ exercises with same letter = circuit)
    match = re.match(r'^([A-Za-z])\d+\s*[:;]\s*', name)
    if match:
        return match.group(1).upper()

    return None


def _clean_circuit_label_from_name(name: str) -> str:
    """Remove parenthesized circuit/rounds labels from exercise name."""
    cleaned = re.sub(r'\s*\(circuit\s+[A-Za-z0-9]\)', '', name, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'\s*\(rounds\s+[A-Za-z0-9]\)', '', cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _count_exercises_with_label(tagged: List[Tuple[Optional[str], dict]], label: str) -> int:
    """Count how many exercises have a specific label."""
    return sum(1 for l, _ in tagged if l == label)


def detect_superset_groups(exercises: List[dict]) -> List[Block]:
    """Detect circuit and superset groupings in a flat exercise list and return CIR Blocks.

    Circuits (3+ exercises done in rounds) are detected FIRST, then supersets
    (exactly 2 exercises done back-to-back). Ungrouped exercises are collected into
    Block(type="straight") blocks.
    """
    if not exercises:
        return [Block(type="straight", rounds=1, items=[])]

    # Tag each exercise with both circuit and superset labels (or None)
    # We'll first collect all labels, then determine which are circuits vs supersets
    all_labels: List[Tuple[Optional[str], dict]] = []  # (any_label, exercise)
    for e in exercises:
        # Check both circuit and superset labels
        circuit_label = _detect_circuit_label(e)
        superset_label = _detect_superset_label(e)
        # Use whichever label is found (circuit takes priority only after we count)
        label = circuit_label or superset_label
        all_labels.append((label, e))

    # First pass: identify which labels are circuits (3+ exercises with same label)
    # Labels with 2 exercises become supersets
    circuit_labels: set = set()
    superset_candidate_labels: set = set()
    for label in {l for l, _ in all_labels if l}:
        count = _count_exercises_with_label(all_labels, label)
        if count >= 3:
            circuit_labels.add(label)
        elif count == 2:
            superset_candidate_labels.add(label)

    # Second pass: create final tagged list with resolved types
    blocks: List[Block] = []
    current_circuit_label: Optional[str] = None
    current_superset_label: Optional[str] = None
    current_circuit_group: List[dict] = []
    current_superset_group: List[dict] = []
    standalone_buffer: List[dict] = []

    def _flush_standalone():
        nonlocal standalone_buffer
        if standalone_buffer:
            items = [_exercise_from_dict(e) for e in standalone_buffer]
            blocks.append(Block(type="straight", rounds=1, items=items))
            standalone_buffer = []

    def _flush_circuit():
        nonlocal current_circuit_group, current_circuit_label
        if current_circuit_group and current_circuit_label is not None:
            # Determine rounds from first exercise's sets
            rounds = 1
            first_sets = current_circuit_group[0].get("sets")
            if first_sets and first_sets > 0:
                rounds = first_sets
            items = []
            for e in current_circuit_group:
                ex = _exercise_from_dict(e)
                # Clean circuit label from name if present
                cleaned_name = _clean_circuit_label_from_name(ex.name)
                if cleaned_name != ex.name:
                    ex = ex.model_copy(update={"name": cleaned_name})
                items.append(ex)
            blocks.append(Block(type="circuit", rounds=rounds, items=items))
            current_circuit_group = []
            current_circuit_label = None

    def _flush_superset():
        nonlocal current_superset_group, current_superset_label
        if current_superset_group and current_superset_label is not None:
            # Determine rounds from first exercise's sets
            rounds = 1
            first_sets = current_superset_group[0].get("sets")
            if first_sets and first_sets > 0:
                rounds = first_sets
            items = []
            for e in current_superset_group:
                ex = _exercise_from_dict(e)
                # Clean superset label from name if present
                cleaned_name = _clean_superset_label_from_name(ex.name)
                if cleaned_name != ex.name:
                    ex = ex.model_copy(update={"name": cleaned_name})
                items.append(ex)
            blocks.append(Block(type="superset", rounds=rounds, items=items))
            current_superset_group = []
            current_superset_label = None

    for label, e in all_labels:
        # Resolve which type this label belongs to
        circuit_label = label if label in circuit_labels else None
        superset_label = label if label in superset_candidate_labels else None

        # Handle circuit labels (3+ exercises)
        if circuit_label and circuit_label in circuit_labels:
            # Flush any pending superset first
            _flush_superset()
            if circuit_label == current_circuit_label:
                current_circuit_group.append(e)
            else:
                # New circuit label — flush previous if any
                _flush_circuit()
                _flush_standalone()
                current_circuit_label = circuit_label
                current_circuit_group = [e]
        # Handle superset labels (exactly 2 exercises)
        elif superset_label:
            # Flush any pending circuit first
            _flush_circuit()
            if superset_label == current_superset_label:
                current_superset_group.append(e)
            else:
                # New superset label — flush previous if any
                _flush_superset()
                _flush_standalone()
                current_superset_label = superset_label
                current_superset_group = [e]
        # No label — standalone exercise
        else:
            _flush_circuit()
            _flush_superset()
            standalone_buffer.append(e)

    # Flush remaining
    _flush_circuit()
    _flush_superset()
    _flush_standalone()

    return blocks if blocks else [Block(type="straight", rounds=1, items=[])]


def _blocks_from_structured_input(ingest_json: dict) -> List[Block]:
    """Convert structured blocks[] input to CIR Blocks."""
    blocks = []
    for block_dict in ingest_json.get("blocks", []):
        # Detect timed-station format and get time cap
        time_cap_sec = _detect_timed_station_format(block_dict)
        
        # For timed-station format, rounds should always be 1
        # (you're doing one pass through all stations, each with a time cap)
        structure = block_dict.get("structure", "") or ""
        structure_lower = structure.lower()
        is_timed_station = time_cap_sec is not None or "timed station" in structure_lower or "station" in structure_lower
        
        # Build time cap note for exercises if we have a time cap
        time_cap_note = None
        if time_cap_sec:
            minutes = time_cap_sec // 60
            if minutes >= 1:
                time_cap_note = f"{minutes} minute cap"
            else:
                time_cap_note = f"{time_cap_sec} second cap"
        
        # Convert exercises with time cap info
        exercises = block_dict.get("exercises", [])
        items = [_exercise_from_dict(e, time_cap_note) for e in exercises]

        block_type = STRUCTURE_TO_BLOCK_TYPE.get(structure, "straight")
        
        # For timed-station format, force rounds to 1
        if is_timed_station:
            rounds = 1
        else:
            rounds = _resolve_rounds(block_dict)

        blocks.append(Block(type=block_type, rounds=rounds, time_cap_sec=time_cap_sec, items=items))
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
