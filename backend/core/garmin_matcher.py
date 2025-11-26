"""
Garmin exercise name matcher using official Garmin exercise database.
"""
import pathlib
from rapidfuzz import fuzz, process
from .normalize import normalize
from backend.mapping.exercise_name_matcher import best_match, top_matches

ROOT = pathlib.Path(__file__).resolve().parents[2]

# Cache for loaded exercises
_GARMIN_EXERCISES = None


def load_garmin_exercises():
    """Load Garmin exercise names from file."""
    global _GARMIN_EXERCISES
    if _GARMIN_EXERCISES is None:
        exercises_file = ROOT / "shared/dictionaries/garmin_exercise_names.txt"
        if exercises_file.exists():
            with open(exercises_file, 'r') as f:
                _GARMIN_EXERCISES = [line.strip() for line in f if line.strip()]
        else:
            _GARMIN_EXERCISES = []
    return _GARMIN_EXERCISES


def find_garmin_exercise(raw_name: str, threshold: int = 80) -> tuple[str, float]:
    """
    Find best matching Garmin exercise name.
    Returns (garmin_name, confidence) where confidence is 0-1.
    
    Uses the new exercise_name_matcher for robust fuzzy matching.
    """
    exercises = load_garmin_exercises()
    if not exercises:
        return None, 0.0
    
    # Use the new robust matcher
    mapped_name, confidence = best_match(raw_name, exercises)
    
    # Apply threshold (convert from 0-1 to 0-100 for comparison)
    if mapped_name and confidence * 100 >= threshold:
        return mapped_name, confidence
    
    return None, 0.0


def get_garmin_suggestions(raw_name: str, limit: int = 5, score_cutoff: float = 0.3) -> list[tuple[str, float]]:
    """
    Get top matching Garmin exercise suggestions.
    Returns list of (garmin_name, confidence) tuples sorted by confidence desc.
    """
    exercises = load_garmin_exercises()
    if not exercises:
        return []
    
    return top_matches(raw_name, exercises, limit=limit, score_cutoff=score_cutoff)


def fuzzy_match_garmin(raw_name: str) -> str:
    """
    Fuzzy match to Garmin exercise name with fallback.
    Returns best matching Garmin name or None.
    
    For very generic/short names, require higher match quality.
    """
    # If name is very short/generic, require better matches
    if len(raw_name.split()) <= 1 and len(raw_name) <= 5:
        threshold = 85  # Require better match for single words
    else:
        threshold = 70
    
    garmin_name, score = find_garmin_exercise(raw_name, threshold=threshold)
    
    # For single-word matches, ensure it's a valid exercise name
    if garmin_name and len(raw_name.split()) == 1:
        # Check if the match is reasonable (not too different in length)
        if abs(len(garmin_name) - len(raw_name)) > len(raw_name) * 2:
            # Match seems too different, try again with higher threshold
            garmin_name2, score2 = find_garmin_exercise(raw_name, threshold=90)
            if score2 > score:
                return garmin_name2
    
    return garmin_name

