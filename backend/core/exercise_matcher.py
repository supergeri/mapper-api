"""
Exercise Matching Service for mapping planned exercise names to canonical exercises.

Part of AMA-299: Exercise Database for Progression Tracking
Phase 2 - Matching Service

This service provides a multi-stage matching approach:
1. Exact name match (case-insensitive)
2. Alias match (check aliases array)
3. Fuzzy match using rapidfuzz
4. LLM fallback for semantic matching (optional)
"""
import json
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING
from enum import Enum

from rapidfuzz import fuzz, process

from backend.core.normalize import normalize

if TYPE_CHECKING:
    from application.ports import ExercisesRepository

logger = logging.getLogger(__name__)


class MatchMethod(str, Enum):
    """How the match was determined."""
    EXACT = "exact"
    ALIAS = "alias"
    FUZZY = "fuzzy"
    LLM = "llm"
    NONE = "none"


@dataclass
class ExerciseMatch:
    """Result of an exercise matching attempt."""
    exercise_id: Optional[str]
    exercise_name: Optional[str]
    confidence: float  # 0.0 to 1.0
    method: MatchMethod
    reasoning: Optional[str] = None
    suggested_alias: Optional[str] = None  # If we should add this as an alias


class ExerciseMatchingService:
    """
    Service for matching free-text exercise names to canonical exercises.

    Uses a multi-stage approach:
    1. Exact name match (confidence: 1.0)
    2. Alias match (confidence: 0.95)
    3. Fuzzy match with rapidfuzz (confidence: based on score)
    4. LLM fallback (confidence: based on LLM response)
    """

    # Thresholds for fuzzy matching
    FUZZY_AUTO_ACCEPT = 0.90  # Auto-accept if fuzzy score >= 90%
    FUZZY_REVIEW = 0.70       # Needs review if between 70-90%
    FUZZY_REJECT = 0.50       # Reject if below 50%

    def __init__(
        self,
        exercises_repository: "ExercisesRepository",
        llm_client: Optional[Any] = None,
        enable_llm_fallback: bool = True
    ):
        """
        Initialize the matching service.

        Args:
            exercises_repository: Repository for querying exercises table
            llm_client: Optional LLM client for semantic matching fallback
            enable_llm_fallback: Whether to use LLM for low-confidence matches
        """
        self._repo = exercises_repository
        self._llm_client = llm_client
        self._enable_llm_fallback = enable_llm_fallback
        self._exercises_cache: Optional[List[Dict[str, Any]]] = None

    def _get_all_exercises(self) -> List[Dict[str, Any]]:
        """Get all exercises, using cache if available."""
        if self._exercises_cache is None:
            self._exercises_cache = self._repo.get_all(limit=500)
        return self._exercises_cache

    def clear_cache(self):
        """Clear the exercises cache."""
        self._exercises_cache = None

    def match(self, planned_name: str) -> ExerciseMatch:
        """
        Match a planned exercise name to a canonical exercise.

        Args:
            planned_name: The exercise name from the workout plan

        Returns:
            ExerciseMatch with the best match found
        """
        if not planned_name or not planned_name.strip():
            return ExerciseMatch(
                exercise_id=None,
                exercise_name=None,
                confidence=0.0,
                method=MatchMethod.NONE,
                reasoning="Empty input"
            )

        planned_name = planned_name.strip()

        # Stage 1: Exact name match
        match = self._try_exact_match(planned_name)
        if match:
            return match

        # Stage 2: Alias match
        match = self._try_alias_match(planned_name)
        if match:
            return match

        # Stage 3: Fuzzy match
        match = self._try_fuzzy_match(planned_name)
        if match and match.confidence >= self.FUZZY_AUTO_ACCEPT:
            return match

        # Stage 4: LLM fallback (if enabled and fuzzy match is weak)
        if self._enable_llm_fallback and self._llm_client:
            llm_match = self._try_llm_match(planned_name, match)
            if llm_match and llm_match.confidence > (match.confidence if match else 0):
                return llm_match

        # Return best fuzzy match if we have one
        if match:
            return match

        # No match found
        return ExerciseMatch(
            exercise_id=None,
            exercise_name=None,
            confidence=0.0,
            method=MatchMethod.NONE,
            reasoning=f"No match found for '{planned_name}'"
        )

    def _try_exact_match(self, planned_name: str) -> Optional[ExerciseMatch]:
        """Try exact name match (case-insensitive)."""
        exercise = self._repo.find_by_exact_name(planned_name)
        if exercise:
            logger.debug(f"Exact match: '{planned_name}' -> '{exercise['id']}'")
            return ExerciseMatch(
                exercise_id=exercise["id"],
                exercise_name=exercise["name"],
                confidence=1.0,
                method=MatchMethod.EXACT,
                reasoning="Exact name match"
            )
        return None

    def _try_alias_match(self, planned_name: str) -> Optional[ExerciseMatch]:
        """Try alias match."""
        exercise = self._repo.find_by_alias(planned_name)
        if exercise:
            logger.debug(f"Alias match: '{planned_name}' -> '{exercise['id']}'")
            return ExerciseMatch(
                exercise_id=exercise["id"],
                exercise_name=exercise["name"],
                confidence=0.95,
                method=MatchMethod.ALIAS,
                reasoning=f"Alias match: '{planned_name}' is an alias"
            )

        # Also try case-insensitive alias matching by normalizing
        normalized_input = normalize(planned_name)
        exercises = self._get_all_exercises()
        for ex in exercises:
            for alias in ex.get("aliases", []):
                if normalize(alias) == normalized_input:
                    logger.debug(f"Normalized alias match: '{planned_name}' -> '{ex['id']}'")
                    return ExerciseMatch(
                        exercise_id=ex["id"],
                        exercise_name=ex["name"],
                        confidence=0.93,
                        method=MatchMethod.ALIAS,
                        reasoning=f"Normalized alias match: '{alias}'"
                    )
        return None

    def _try_fuzzy_match(self, planned_name: str) -> Optional[ExerciseMatch]:
        """Try fuzzy matching using rapidfuzz."""
        exercises = self._get_all_exercises()
        if not exercises:
            return None

        normalized_input = normalize(planned_name)

        # Build list of (exercise, normalized_name) for matching
        candidates = []
        for ex in exercises:
            # Match against exercise name
            candidates.append((ex, normalize(ex["name"]), "name"))
            # Also match against aliases
            for alias in ex.get("aliases", []):
                candidates.append((ex, normalize(alias), "alias"))

        # Find best match using rapidfuzz
        best_match = None
        best_score = 0.0
        best_source = None

        for ex, candidate_name, source in candidates:
            # Use token_set_ratio for more flexible matching
            score = fuzz.token_set_ratio(normalized_input, candidate_name) / 100.0

            # Boost score if equipment keywords match
            if self._has_equipment_keyword_match(planned_name, ex):
                score = min(score + 0.05, 1.0)

            if score > best_score:
                best_score = score
                best_match = ex
                best_source = source

        if best_match and best_score >= self.FUZZY_REJECT:
            # Determine if we should suggest adding this as an alias
            suggested_alias = None
            if best_score >= self.FUZZY_AUTO_ACCEPT and best_source == "name":
                # High confidence match but not an existing alias - suggest adding it
                normalized_existing_aliases = [normalize(a) for a in best_match.get("aliases", [])]
                if normalized_input not in normalized_existing_aliases:
                    suggested_alias = planned_name

            return ExerciseMatch(
                exercise_id=best_match["id"],
                exercise_name=best_match["name"],
                confidence=best_score,
                method=MatchMethod.FUZZY,
                reasoning=f"Fuzzy match (score: {best_score:.2f})",
                suggested_alias=suggested_alias
            )

        return None

    def _has_equipment_keyword_match(self, planned_name: str, exercise: Dict[str, Any]) -> bool:
        """Check if equipment keywords in the input match the exercise equipment."""
        equipment = exercise.get("equipment", [])
        if not equipment:
            return False

        input_lower = planned_name.lower()
        equipment_keywords = {
            "barbell": ["barbell", "bb", "bar"],
            "dumbbell": ["dumbbell", "db", "dumbell"],
            "cable": ["cable"],
            "machine": ["machine"],
            "smith_machine": ["smith", "smith machine"],
            "kettlebell": ["kettlebell", "kb"],
            "bodyweight": ["bodyweight", "body weight", "bw"],
        }

        for eq in equipment:
            keywords = equipment_keywords.get(eq, [eq])
            if any(kw in input_lower for kw in keywords):
                return True
        return False

    def _try_llm_match(
        self,
        planned_name: str,
        fuzzy_match: Optional[ExerciseMatch]
    ) -> Optional[ExerciseMatch]:
        """
        Try LLM-based semantic matching as fallback.

        Only called when fuzzy matching confidence is low.
        """
        if not self._llm_client:
            return None

        try:
            # Get top fuzzy candidates to provide context to LLM
            exercises = self._get_all_exercises()
            normalized_input = normalize(planned_name)

            # Get top 5 fuzzy candidates
            candidates = []
            for ex in exercises:
                score = fuzz.token_set_ratio(normalized_input, normalize(ex["name"])) / 100.0
                candidates.append((ex, score))

            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = candidates[:5]

            # Build prompt for LLM
            candidate_list = "\n".join([
                f"- {ex['name']} (id: {ex['id']}, muscles: {ex.get('primary_muscles', [])})"
                for ex, _ in top_candidates
            ])

            prompt = f"""You are an exercise matching expert. Given an exercise name from a workout plan, identify which canonical exercise it refers to.

Input exercise name: "{planned_name}"

Candidate exercises from our database:
{candidate_list}

Respond with JSON:
{{
  "exercise_id": "the-canonical-id" or null if no match,
  "confidence": 0.0 to 1.0,
  "reasoning": "brief explanation"
}}

If the input doesn't clearly match any candidate, return null for exercise_id with low confidence."""

            # Call LLM (assuming OpenAI-compatible client)
            response = self._llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            if result.get("exercise_id"):
                # Find the exercise details
                matched_ex = next(
                    (ex for ex, _ in top_candidates if ex["id"] == result["exercise_id"]),
                    None
                )
                if matched_ex:
                    # Clamp confidence to valid range [0.0, 1.0]
                    raw_confidence = result.get("confidence", 0.7)
                    confidence = max(0.0, min(1.0, raw_confidence))
                    return ExerciseMatch(
                        exercise_id=result["exercise_id"],
                        exercise_name=matched_ex["name"],
                        confidence=confidence,
                        method=MatchMethod.LLM,
                        reasoning=result.get("reasoning", "LLM semantic match"),
                        suggested_alias=planned_name if confidence >= 0.85 else None
                    )

        except Exception as e:
            logger.warning(f"LLM matching failed for '{planned_name}': {e}")

        return None

    def match_batch(self, planned_names: List[str]) -> List[ExerciseMatch]:
        """
        Match multiple exercise names in batch.

        Args:
            planned_names: List of exercise names to match

        Returns:
            List of ExerciseMatch results in same order
        """
        return [self.match(name) for name in planned_names]

    def suggest_matches(self, planned_name: str, limit: int = 5) -> List[ExerciseMatch]:
        """
        Get top N suggested matches for an exercise name.

        Useful for showing alternatives to the user.

        Args:
            planned_name: The exercise name to match
            limit: Maximum number of suggestions

        Returns:
            List of top matches sorted by confidence
        """
        exercises = self._get_all_exercises()
        if not exercises:
            return []

        normalized_input = normalize(planned_name)
        matches = []

        for ex in exercises:
            # Calculate score against name
            name_score = fuzz.token_set_ratio(normalized_input, normalize(ex["name"])) / 100.0

            # Also check aliases and take best score
            alias_score = 0.0
            for alias in ex.get("aliases", []):
                alias_score = max(
                    alias_score,
                    fuzz.token_set_ratio(normalized_input, normalize(alias)) / 100.0
                )

            best_score = max(name_score, alias_score)

            # Equipment keyword bonus
            if self._has_equipment_keyword_match(planned_name, ex):
                best_score = min(best_score + 0.05, 1.0)

            if best_score >= 0.3:  # Minimum threshold for suggestions
                matches.append(ExerciseMatch(
                    exercise_id=ex["id"],
                    exercise_name=ex["name"],
                    confidence=best_score,
                    method=MatchMethod.FUZZY,
                    reasoning=f"Suggestion (score: {best_score:.2f})"
                ))

        # Sort by confidence and return top N
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:limit]
