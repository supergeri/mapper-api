"""
Workflow functions for processing blocks JSON with exercise validation.
"""
from typing import List, Dict, Optional
from backend.adapters.blocks_to_hyrox_yaml import map_exercise_to_garmin, to_hyrox_yaml
from backend.core.exercise_suggestions import suggest_alternatives
from backend.core.garmin_matcher import find_garmin_exercise, get_garmin_suggestions
import logging

logger = logging.getLogger(__name__)


def extract_all_exercises_from_blocks(blocks_json: dict) -> List[Dict]:
    """Extract all exercises from blocks JSON with their metadata."""
    exercises = []
    
    for block_idx, block in enumerate(blocks_json.get("blocks", [])):
        block_label = block.get("label", f"Block {block_idx + 1}")
        
        # From exercises array
        for ex_idx, ex in enumerate(block.get("exercises", [])):
            exercises.append({
                "name": ex.get("name", ""),
                "block": block_label,
                "location": f"exercises[{ex_idx}]",
                "sets": ex.get("sets"),
                "reps": ex.get("reps"),
                "distance_m": ex.get("distance_m"),
                "type": ex.get("type")
            })
        
        # From supersets
        for superset_idx, superset in enumerate(block.get("supersets", [])):
            for ex_idx, ex in enumerate(superset.get("exercises", [])):
                exercises.append({
                    "name": ex.get("name", ""),
                    "block": block_label,
                    "location": f"supersets[{superset_idx}].exercises[{ex_idx}]",
                    "sets": ex.get("sets"),
                    "reps": ex.get("reps"),
                    "distance_m": ex.get("distance_m"),
                    "type": ex.get("type")
                })
    
    return exercises


def validate_workout_mapping(blocks_json: dict, confidence_threshold: float = 0.85) -> Dict:
    """
    Validate workout mapping and identify exercises that need review.
    Returns validation results with suggestions.
    
    Uses new exercise_name_matcher for robust fuzzy matching.
    Applies thresholds:
    - confidence >= 0.88 -> status = "valid"
    - 0.40 <= confidence < 0.88 -> status = "needs_review"
    - mapped_name is None or confidence < 0.40 -> status = "unmapped"
    """
    exercises = extract_all_exercises_from_blocks(blocks_json)
    
    results = {
        "total_exercises": len(exercises),
        "validated_exercises": [],
        "needs_review": [],
        "unmapped_exercises": [],
        "can_proceed": True
    }
    
    for ex_info in exercises:
        ex_name = ex_info["name"]
        if not ex_name:
            continue
        
        # Use new robust matcher to get mapped_name and confidence
        mapped_name, confidence = find_garmin_exercise(ex_name, threshold=40)  # Low threshold to get suggestions
        
        # Get suggestions using the new matcher
        suggestions_list = get_garmin_suggestions(ex_name, limit=5, score_cutoff=0.3)
        suggestions = [{"name": name, "confidence": conf} for name, conf in suggestions_list]
        
        # Also get legacy suggestions for additional context
        legacy_suggestions = suggest_alternatives(ex_name, include_similar_types=True)
        
        # Determine status based on thresholds
        if mapped_name is None or confidence < 0.40:
            status = "unmapped"
        elif confidence >= 0.88:
            status = "valid"
        else:  # 0.40 <= confidence < 0.88
            status = "needs_review"
        
        # Get description from legacy mapper if available
        description = ""
        try:
            _, description, _ = map_exercise_to_garmin(
                ex_name,
                ex_reps=ex_info.get("reps"),
                ex_distance_m=ex_info.get("distance_m")
            )
        except Exception as e:
            logger.debug(f"Could not get description for {ex_name}: {e}")
        
        ex_result = {
            "original_name": ex_name,
            "mapped_name": mapped_name,  # Use mapped_name instead of mapped_to for consistency
            "mapped_to": mapped_name,  # Keep for backward compatibility
            "confidence": confidence,
            "description": description,
            "block": ex_info["block"],
            "location": ex_info["location"],
            "status": status,
            "suggestions": suggestions  # List of {name, confidence} tuples from new matcher
        }
        
        # Log mapping failures for debugging
        if status == "unmapped":
            logger.warning(
                f"Unmapped exercise: '{ex_name}' (confidence: {confidence:.2f}, "
                f"top suggestion: {suggestions[0]['name'] if suggestions else 'none'})"
            )
        elif status == "needs_review":
            logger.debug(
                f"Exercise needs review: '{ex_name}' -> '{mapped_name}' "
                f"(confidence: {confidence:.2f})"
            )
        
        # Categorize into results
        if status == "unmapped":
            results["unmapped_exercises"].append(ex_result)
            results["needs_review"].append(ex_result)  # Also add to needs_review
        elif status == "needs_review":
            results["needs_review"].append(ex_result)
        else:  # status == "valid"
            results["validated_exercises"].append(ex_result)
    
    # If there are unmapped exercises, can't proceed without user input
    if results["unmapped_exercises"]:
        results["can_proceed"] = False
    
    return results


def process_workout_with_validation(blocks_json: dict, auto_proceed: bool = False) -> Dict:
    """
    Complete workflow: validate exercises and optionally generate YAML.
    """
    validation = validate_workout_mapping(blocks_json)
    
    result = {
        "validation": validation,
        "yaml": None,
        "message": None
    }
    
    if validation["can_proceed"] or auto_proceed:
        try:
            yaml_output = to_hyrox_yaml(blocks_json)
            result["yaml"] = yaml_output
            result["message"] = "Workout converted successfully"
        except Exception as e:
            result["message"] = f"Error generating YAML: {str(e)}"
    else:
        result["message"] = f"Please review {len(validation['unmapped_exercises'])} unmapped exercises before proceeding"
    
    return result

