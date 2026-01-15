"""
Supabase Mapping Repository Implementation.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This module implements the mapping repository protocols using Supabase as the backend.
Extracted from backend/core/user_mappings.py, global_mappings.py, and exercise_suggestions.py.
"""
import pathlib
from typing import Optional, Dict, Any, List, Tuple
from supabase import Client
import logging

from application.ports.mapping_repository import (
    UserMappingRepository,
    GlobalMappingRepository,
    ExerciseMatchRepository,
)

logger = logging.getLogger(__name__)

# Root path for loading garmin exercises file
ROOT = pathlib.Path(__file__).resolve().parents[2]

# Cache for loaded exercises
_GARMIN_EXERCISES = None


def _normalize(text: str) -> str:
    """Normalize exercise name for matching."""
    import re
    # Convert to lowercase, remove special chars, collapse whitespace
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _load_garmin_exercises() -> List[str]:
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


# ============================================================================
# Repository Implementations
# ============================================================================

class SupabaseUserMappingRepository:
    """
    Supabase implementation of UserMappingRepository.

    Handles per-user exercise name mappings stored in the database.
    Replaces the file-based user_mappings.yaml approach.
    """

    def __init__(self, client: Client, user_id: str):
        """
        Initialize with Supabase client and user ID.

        Args:
            client: Supabase client instance (injected)
            user_id: User ID for scoping mappings
        """
        self._client = client
        self._user_id = user_id

    def add(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> Dict[str, Any]:
        """Add or update a user-defined mapping."""
        try:
            normalized = _normalize(exercise_name)

            # Upsert the mapping
            result = self._client.table("user_mappings").upsert({
                "user_id": self._user_id,
                "exercise_name": normalized,
                "garmin_name": garmin_name,
            }, on_conflict="user_id,exercise_name").execute()

            if result.data and len(result.data) > 0:
                return {
                    "normalized": normalized,
                    "garmin_name": garmin_name,
                    "original": exercise_name,
                }

            return {"error": "Failed to save mapping"}

        except Exception as e:
            logger.error(f"Error adding user mapping: {e}")
            return {"error": str(e)}

    def remove(
        self,
        exercise_name: str,
    ) -> bool:
        """Remove a user-defined mapping."""
        try:
            normalized = _normalize(exercise_name)

            result = self._client.table("user_mappings") \
                .delete() \
                .eq("user_id", self._user_id) \
                .eq("exercise_name", normalized) \
                .execute()

            return len(result.data) > 0 if result.data else False

        except Exception as e:
            logger.error(f"Error removing user mapping: {e}")
            return False

    def get(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """Get the mapped Garmin name for an exercise."""
        try:
            normalized = _normalize(exercise_name)

            result = self._client.table("user_mappings") \
                .select("garmin_name") \
                .eq("user_id", self._user_id) \
                .eq("exercise_name", normalized) \
                .single() \
                .execute()

            if result.data:
                return result.data.get("garmin_name")

            return None

        except Exception as e:
            logger.error(f"Error getting user mapping: {e}")
            return None

    def get_all(self) -> Dict[str, str]:
        """Get all user-defined mappings."""
        try:
            result = self._client.table("user_mappings") \
                .select("exercise_name, garmin_name") \
                .eq("user_id", self._user_id) \
                .execute()

            if result.data:
                return {r["exercise_name"]: r["garmin_name"] for r in result.data}

            return {}

        except Exception as e:
            logger.error(f"Error getting all user mappings: {e}")
            return {}

    def clear_all(self) -> None:
        """Clear all user-defined mappings."""
        try:
            self._client.table("user_mappings") \
                .delete() \
                .eq("user_id", self._user_id) \
                .execute()

        except Exception as e:
            logger.error(f"Error clearing user mappings: {e}")


class SupabaseGlobalMappingRepository:
    """
    Supabase implementation of GlobalMappingRepository.

    Tracks crowd-sourced mapping popularity across all users.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected)
        """
        self._client = client

    def record_choice(
        self,
        exercise_name: str,
        garmin_name: str,
    ) -> None:
        """Record a user's mapping choice for global popularity tracking."""
        try:
            normalized = _normalize(exercise_name)

            # Try to increment existing count
            result = self._client.table("global_exercise_mappings") \
                .select("id, count") \
                .eq("exercise_name", normalized) \
                .eq("garmin_name", garmin_name) \
                .execute()

            if result.data and len(result.data) > 0:
                # Update existing record
                current_count = result.data[0].get("count", 0)
                self._client.table("global_exercise_mappings") \
                    .update({"count": current_count + 1}) \
                    .eq("id", result.data[0]["id"]) \
                    .execute()
            else:
                # Insert new record
                self._client.table("global_exercise_mappings").insert({
                    "exercise_name": normalized,
                    "garmin_name": garmin_name,
                    "count": 1,
                }).execute()

        except Exception as e:
            logger.error(f"Error recording mapping choice: {e}")

    def get_popular(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Tuple[str, int]]:
        """Get popular Garmin mappings for an exercise name."""
        try:
            normalized = _normalize(exercise_name)

            result = self._client.table("global_exercise_mappings") \
                .select("garmin_name, count") \
                .eq("exercise_name", normalized) \
                .order("count", desc=True) \
                .limit(limit) \
                .execute()

            if result.data:
                return [(r["garmin_name"], r["count"]) for r in result.data]

            return []

        except Exception as e:
            logger.error(f"Error getting popular mappings: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get global popularity statistics."""
        try:
            # Get total counts
            result = self._client.table("global_exercise_mappings") \
                .select("exercise_name, garmin_name, count") \
                .execute()

            if not result.data:
                return {
                    "total_choices": 0,
                    "unique_exercises": 0,
                    "unique_mappings": 0,
                    "most_popular": []
                }

            data = result.data
            total_choices = sum(r["count"] for r in data)
            unique_exercises = len(set(r["exercise_name"] for r in data))
            unique_mappings = len(data)

            # Sort by count and get top 10
            sorted_data = sorted(data, key=lambda x: x["count"], reverse=True)[:10]

            return {
                "total_choices": total_choices,
                "unique_exercises": unique_exercises,
                "unique_mappings": unique_mappings,
                "most_popular": [
                    {"exercise": r["exercise_name"], "garmin_name": r["garmin_name"], "count": r["count"]}
                    for r in sorted_data
                ]
            }

        except Exception as e:
            logger.error(f"Error getting global stats: {e}")
            return {
                "total_choices": 0,
                "unique_exercises": 0,
                "unique_mappings": 0,
                "most_popular": [],
                "error": str(e)
            }


class InMemoryExerciseMatchRepository:
    """
    In-memory implementation of ExerciseMatchRepository.

    Uses the Garmin exercise database file for fuzzy matching.
    This doesn't require Supabase since it uses the static exercise list.
    """

    def __init__(self, global_mapping_repo: Optional[GlobalMappingRepository] = None):
        """
        Initialize with optional global mapping repository for popularity boost.

        Args:
            global_mapping_repo: Optional repository for popularity data
        """
        self._global_repo = global_mapping_repo
        self._exercises = _load_garmin_exercises()

    def find_match(
        self,
        exercise_name: str,
        *,
        threshold: float = 0.3,
    ) -> Tuple[Optional[str], float]:
        """Find the best matching Garmin exercise for a name."""
        if not self._exercises:
            return None, 0.0

        try:
            from backend.mapping.exercise_name_matcher import best_match
            mapped_name, confidence = best_match(exercise_name, self._exercises)

            if mapped_name and confidence >= threshold:
                return mapped_name, confidence

            return None, 0.0

        except ImportError:
            # Fallback to basic matching
            from rapidfuzz import fuzz, process

            normalized_input = _normalize(exercise_name)
            results = process.extractOne(
                normalized_input,
                [_normalize(ex) for ex in self._exercises],
                scorer=fuzz.token_set_ratio
            )

            if results and results[1] / 100.0 >= threshold:
                # Find original name
                for ex in self._exercises:
                    if _normalize(ex) == results[0]:
                        return ex, results[1] / 100.0

            return None, 0.0

    def get_suggestions(
        self,
        exercise_name: str,
        *,
        limit: int = 5,
        score_cutoff: float = 0.3,
    ) -> List[Tuple[str, float]]:
        """Get suggested Garmin exercises for a name."""
        if not self._exercises:
            return []

        try:
            from backend.mapping.exercise_name_matcher import top_matches
            return top_matches(exercise_name, self._exercises, limit=limit, score_cutoff=score_cutoff)

        except ImportError:
            # Fallback to basic matching
            from rapidfuzz import fuzz, process

            normalized_input = _normalize(exercise_name)
            results = process.extract(
                normalized_input,
                [_normalize(ex) for ex in self._exercises],
                scorer=fuzz.token_set_ratio,
                limit=limit
            )

            suggestions = []
            for matched_normalized, score, _ in results:
                confidence = score / 100.0
                if confidence >= score_cutoff:
                    for ex in self._exercises:
                        if _normalize(ex) == matched_normalized:
                            suggestions.append((ex, confidence))
                            break

            return suggestions

    def find_similar(
        self,
        exercise_name: str,
        *,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Find similar exercises to the given name."""
        if not self._exercises:
            return []

        try:
            from rapidfuzz import fuzz, process

            normalized_input = _normalize(exercise_name)

            results = process.extract(
                normalized_input,
                [_normalize(ex) for ex in self._exercises],
                scorer=fuzz.token_set_ratio,
                limit=limit * 2
            )

            suggestions = []
            seen_names = set()

            for matched_normalized, score, _ in results:
                if score < 50:
                    continue

                for ex in self._exercises:
                    if _normalize(ex) == matched_normalized and ex not in seen_names:
                        suggestions.append({
                            "name": ex,
                            "score": score / 100.0,
                            "normalized": matched_normalized,
                        })
                        seen_names.add(ex)
                        if len(suggestions) >= limit:
                            break
                        break

            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Error finding similar exercises: {e}")
            return []

    def find_by_type(
        self,
        exercise_name: str,
        *,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Find exercises of the same type (e.g., all squats)."""
        if not self._exercises:
            return []

        try:
            from rapidfuzz import fuzz

            normalized_input = _normalize(exercise_name)

            # Movement keywords
            movement_keywords = [
                "squat", "press", "push", "pull", "row", "curl", "flye", "extension",
                "deadlift", "lunge", "plank", "crunch", "situp", "burpee", "jump",
                "swing", "carry", "drag", "pullup", "chinup", "dip", "raise", "shrug"
            ]

            matched_keywords = [kw for kw in movement_keywords if kw in normalized_input]

            if not matched_keywords:
                matched_keywords = [normalized_input]

            suggestions = []
            seen_names = set()

            for ex in self._exercises:
                ex_normalized = _normalize(ex)

                for keyword in matched_keywords:
                    if keyword in ex_normalized:
                        if ex not in seen_names:
                            score = fuzz.token_set_ratio(normalized_input, ex_normalized) / 100.0
                            suggestions.append({
                                "name": ex,
                                "score": score,
                                "normalized": ex_normalized,
                                "keyword": keyword,
                            })
                            seen_names.add(ex)
                            break

                if len(suggestions) >= limit:
                    break

            suggestions.sort(key=lambda x: -x["score"])
            return suggestions[:limit]

        except Exception as e:
            logger.error(f"Error finding exercises by type: {e}")
            return []

    def categorize(
        self,
        exercise_name: str,
    ) -> Optional[str]:
        """Get the category/type of an exercise."""
        original_lower = exercise_name.lower()
        normalized = _normalize(exercise_name).lower()
        combined = f"{original_lower} {normalized}"

        categories = [
            ("push_up", ["push up", "pushup", "push-up", "hand release push"]),
            ("squat", ["squat"]),
            ("lunge", ["lunge", "split"]),
            ("deadlift", ["deadlift", "rdl", "romanian deadlift"]),
            ("swing", ["swing"]),
            ("burpee", ["burpee"]),
            ("plank", ["plank"]),
            ("carry", ["carry", "farmers", "walk"]),
            ("drag", ["drag"]),
            ("press", ["press", "shoulder press", "bench press", "push press"]),
            ("pull", ["pull", "pullup", "chinup", "chin up", "pull down"]),
            ("row", ["row", "inverted row"]),
            ("curl", ["curl", "biceps curl"]),
            ("extension", ["extension", "triceps extension", "back extension"]),
            ("flye", ["flye", "fly"]),
            ("crunch", ["crunch", "situp", "sit up", "ab", "abdominal"]),
            ("raise", ["raise", "lateral raise"]),
        ]

        for category, keywords in categories:
            if any(kw in combined for kw in keywords):
                return category

        return None
