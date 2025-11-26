from typing import Iterable, Tuple, Optional, Dict, List
import re

from rapidfuzz import fuzz, process


def normalize_name(name: str) -> str:
    """
    Normalize exercise names for better fuzzy matching.

    - lowercase
    - strip whitespace
    - replace hyphens/underscores with spaces
    - remove non-alphanumeric characters (keep spaces)
    - collapse multiple spaces
    """
    if not name:
        return ""
    s = name.lower().strip()

    # common short aliases → expanded forms
    replacements = {
        "db ": "dumbbell ",
        "bb ": "barbell ",
        "wb ": "wall ball ",
        "kb ": "kettlebell ",
        "oh ": "overhead ",
        "ohp": "overhead press",
        "pu ": "push up ",
        "pressup": "push up",
    }
    for short, long in replacements.items():
        s = s.replace(short, long)

    s = s.replace("-", " ").replace("_", " ")

    # keep alnum and spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    # collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Optional hard-coded alias map for common weird names
ALIAS_MAP: Dict[str, str] = {
    "pushups": "push up",
    "push up": "push up",
    "push-ups": "push up",
    "bench press": "barbell bench press",
    "flat bench press": "barbell bench press",
    "incline bench": "incline barbell bench press",
    "hip thrusts": "hip thrust",
    "deadlifts": "deadlift",
    "rdl": "romanian deadlift",
    "alt db curl": "alternating dumbbell curl",
    "alt db curls": "alternating dumbbell curl",
}


def best_match(
    query: str, choices: Iterable[str]
) -> Tuple[Optional[str], float]:
    """
    Return (best_choice, confidence) for a given exercise name against a list
    of device exercise names.

    confidence is 0-1.
    """
    if not query:
        return None, 0.0

    normalized_query = normalize_name(query)
    if not normalized_query:
        return None, 0.0

    # alias: if normalized_query directly maps to a known alias within the
    # device's names, try that first
    alias_target = ALIAS_MAP.get(normalized_query)
    if alias_target and alias_target in choices:
        return alias_target, 1.0

    # Build a list of (original_name, normalized_name)
    norm_choices = [(c, normalize_name(c)) for c in choices]

    # Use rapidfuzz token_set_ratio on normalized tokens
    best_choice = None
    best_score = -1.0

    for original, norm in norm_choices:
        if not norm:
            continue
        score = fuzz.token_set_ratio(normalized_query, norm)
        if score > best_score:
            best_score = score
            best_choice = original

    if best_choice is None:
        return None, 0.0

    # map 0-100 → 0-1
    return best_choice, best_score / 100.0


def top_matches(
    query: str,
    choices: Iterable[str],
    limit: int = 5,
    score_cutoff: float = 0.3,
) -> List[Tuple[str, float]]:
    """
    Return a list of (choice, confidence) sorted by confidence desc.

    confidence is 0-1. Only include matches with confidence >= score_cutoff.
    """
    if not query:
        return []

    normalized_query = normalize_name(query)
    if not normalized_query:
        return []

    # Build list of (original, normalized)
    norm_choices = [(c, normalize_name(c)) for c in choices]

    scored: List[Tuple[str, float]] = []
    for original, norm in norm_choices:
        if not norm:
            continue
        score = fuzz.token_set_ratio(normalized_query, norm) / 100.0
        if score >= score_cutoff:
            scored.append((original, score))

    # sort by confidence desc
    scored.sort(key=lambda x: x[1], reverse=True)
    if limit is not None:
        scored = scored[:limit]
    return scored
