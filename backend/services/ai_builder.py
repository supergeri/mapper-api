"""
AI Builder Service for generating structured workouts from partial input.

Part of AMA-446: AI Builder API Endpoint

Accepts partial workout data (workout type, exercises, structure) and uses
LLM to fill in defaults (rest periods, typical reps, canonical exercise names).
Returns a complete workout matching the unified schema with Garmin compatibility
warnings and exercise suggestions.

LLM Integration:
- Primary: GPT-4o-mini for fast parsing
- Fallback: Claude 3 Haiku
- Timeout: 5 seconds with graceful degradation
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from domain.models import Block, BlockType, Exercise, Load, Workout, WorkoutMetadata, WorkoutSource
from backend.core.garmin_matcher import find_garmin_exercise, get_garmin_suggestions

logger = logging.getLogger(__name__)

# Default rest periods by workout type (seconds)
DEFAULT_REST_PERIODS: Dict[str, int] = {
    "strength": 120,
    "hypertrophy": 90,
    "endurance": 45,
    "hiit": 30,
    "circuit": 15,
    "crossfit": 60,
    "cardio": 30,
    "stretching": 15,
    "yoga": 10,
    "default": 60,
}

# Default reps by workout type
DEFAULT_REPS: Dict[str, int] = {
    "strength": 5,
    "hypertrophy": 10,
    "endurance": 15,
    "hiit": 12,
    "circuit": 12,
    "crossfit": 10,
    "default": 10,
}

# Default sets by workout type
DEFAULT_SETS: Dict[str, int] = {
    "strength": 5,
    "hypertrophy": 4,
    "endurance": 3,
    "hiit": 3,
    "circuit": 3,
    "crossfit": 3,
    "default": 3,
}

# LLM prompt for AI workout building
AI_BUILD_SYSTEM_PROMPT = """You are a workout programming assistant. Given partial workout data,
fill in sensible defaults to create a complete structured workout.

Rules:
- Use canonical exercise names (e.g., "Barbell Back Squat" not just "Squat")
- Assign rest periods appropriate to the workout type
- Fill in missing reps/sets based on workout type conventions
- If exercises are missing detail, add sensible defaults
- Return valid JSON matching the schema

Workout type conventions:
- strength: 3-5 reps, 3-5 sets, 120-180s rest
- hypertrophy: 8-12 reps, 3-4 sets, 60-90s rest
- endurance: 15-20 reps, 2-3 sets, 30-45s rest
- hiit: work/rest intervals, 20-45s work, 10-30s rest
- circuit: 10-15 reps, 2-4 rounds, minimal rest between exercises

Respond with ONLY valid JSON, no markdown formatting."""

AI_BUILD_USER_PROMPT_TEMPLATE = """Build a complete workout from this partial input:

Workout Type: {workout_type}
Format: {format}
Rounds: {rounds}

Exercises:
{exercises_text}

User Preferences:
{preferences_text}

Return JSON with this structure:
{{
  "title": "suggested workout title",
  "description": "brief description",
  "workout_type": "{workout_type}",
  "blocks": [
    {{
      "label": "block label",
      "type": "straight|superset|circuit",
      "rounds": number_or_null,
      "exercises": [
        {{
          "name": "canonical exercise name",
          "sets": number,
          "reps": number_or_string,
          "rest_seconds": number,
          "duration_seconds": number_or_null,
          "load_value": number_or_null,
          "load_unit": "lb|kg|null",
          "notes": "any notes"
        }}
      ]
    }}
  ]
}}"""


@dataclass
class ExerciseSuggestion:
    """A suggestion for an exercise field."""
    exercise_name: str
    field: str
    suggested_value: Any
    reason: str


@dataclass
class GarminCompatibility:
    """Garmin device compatibility information."""
    is_compatible: bool
    warnings: List[str] = field(default_factory=list)
    unsupported_exercises: List[str] = field(default_factory=list)
    mapped_exercises: Dict[str, str] = field(default_factory=dict)


@dataclass
class AIBuildResult:
    """Result of AI workout building."""
    workout: Optional[Workout] = None
    suggestions: List[ExerciseSuggestion] = field(default_factory=list)
    garmin_compatibility: Optional[GarminCompatibility] = None
    build_time_ms: int = 0
    llm_used: Optional[str] = None
    error: Optional[str] = None


class AIBuilderService:
    """
    Service for building structured workouts from partial input using AI.

    Uses a multi-stage approach:
    1. Parse and validate input
    2. Try LLM for intelligent defaults (with timeout + fallback)
    3. Fall back to rule-based defaults if LLM fails
    4. Map exercise names to canonical names
    5. Validate Garmin compatibility
    """

    LLM_TIMEOUT = 5.0  # seconds

    def __init__(
        self,
        openai_client: Optional[Any] = None,
        anthropic_client: Optional[Any] = None,
    ):
        self._openai_client = openai_client
        self._anthropic_client = anthropic_client

    def build(
        self,
        workout_type: Optional[str] = None,
        format: Optional[str] = None,
        rounds: Optional[int] = None,
        exercises: Optional[List[Dict[str, Any]]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
        source_url: Optional[str] = None,
    ) -> AIBuildResult:
        """
        Build a complete workout from partial input.

        Args:
            workout_type: Type of workout (strength, hypertrophy, hiit, etc.)
            format: Workout format (straight_sets, circuit, superset, etc.)
            rounds: Number of rounds/circuits
            exercises: List of partial exercise dicts
            user_preferences: User preferences for defaults
            source_url: Source URL for the workout

        Returns:
            AIBuildResult with complete workout, suggestions, and compatibility info
        """
        t0 = time.perf_counter()
        workout_type = (workout_type or "default").lower()
        exercises = exercises or []
        user_preferences = user_preferences or {}
        suggestions: List[ExerciseSuggestion] = []

        # Step 1: Try LLM-based building
        llm_result = None
        llm_used = None
        if exercises:
            llm_result, llm_used = self._try_llm_build(
                workout_type=workout_type,
                format=format,
                rounds=rounds,
                exercises=exercises,
                user_preferences=user_preferences,
            )

        # Step 2: Build workout (from LLM result or rule-based)
        if llm_result:
            workout, suggestions = self._build_from_llm_result(
                llm_result, workout_type, source_url
            )
        else:
            workout, suggestions = self._build_rule_based(
                workout_type=workout_type,
                format=format,
                rounds=rounds,
                exercises=exercises,
                user_preferences=user_preferences,
                source_url=source_url,
            )

        # Step 3: Map exercise names and check Garmin compatibility
        garmin_compat = self._check_garmin_compatibility(workout)

        build_time_ms = int((time.perf_counter() - t0) * 1000)

        return AIBuildResult(
            workout=workout,
            suggestions=suggestions,
            garmin_compatibility=garmin_compat,
            build_time_ms=build_time_ms,
            llm_used=llm_used,
        )

    def _try_llm_build(
        self,
        workout_type: str,
        format: Optional[str],
        rounds: Optional[int],
        exercises: List[Dict[str, Any]],
        user_preferences: Dict[str, Any],
    ) -> tuple[Optional[Dict], Optional[str]]:
        """Try building with LLM (GPT-4o-mini primary, Claude Haiku fallback)."""

        exercises_text = "\n".join(
            f"- {e.get('name', 'Unknown')}: "
            + ", ".join(f"{k}={v}" for k, v in e.items() if k != "name" and v is not None)
            for e in exercises
        )
        preferences_text = json.dumps(user_preferences) if user_preferences else "None"

        prompt = AI_BUILD_USER_PROMPT_TEMPLATE.format(
            workout_type=workout_type,
            format=format or "straight_sets",
            rounds=rounds or "auto",
            exercises_text=exercises_text or "None specified",
            preferences_text=preferences_text,
        )

        # Try GPT-4o-mini first
        if self._openai_client:
            try:
                result = self._call_openai(prompt)
                if result:
                    return result, "gpt-4o-mini"
            except Exception as e:
                logger.warning(f"OpenAI call failed: {e}")

        # Fallback to Claude Haiku
        if self._anthropic_client:
            try:
                result = self._call_anthropic(prompt)
                if result:
                    return result, "claude-3-haiku"
            except Exception as e:
                logger.warning(f"Anthropic call failed: {e}")

        return None, None

    def _call_openai(self, prompt: str) -> Optional[Dict]:
        """Call OpenAI GPT-4o-mini with timeout."""
        try:
            response = self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": AI_BUILD_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=2000,
                timeout=self.LLM_TIMEOUT,
            )
            content = response.choices[0].message.content
            # Strip markdown code blocks if present
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse OpenAI response as JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"OpenAI call error: {e}")
            return None

    def _call_anthropic(self, prompt: str) -> Optional[Dict]:
        """Call Anthropic Claude 3 Haiku with timeout."""
        try:
            response = self._anthropic_client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=2000,
                system=AI_BUILD_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
                timeout=self.LLM_TIMEOUT,
            )
            content = response.content[0].text
            content = content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content.rsplit("```", 1)[0]
            content = content.strip()
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Anthropic response as JSON: {e}")
            return None
        except Exception as e:
            logger.warning(f"Anthropic call error: {e}")
            return None

    def _build_from_llm_result(
        self,
        llm_result: Dict,
        workout_type: str,
        source_url: Optional[str],
    ) -> tuple[Workout, List[ExerciseSuggestion]]:
        """Convert LLM JSON result to domain Workout model."""
        suggestions: List[ExerciseSuggestion] = []
        blocks = []

        for block_data in llm_result.get("blocks", []):
            exercises = []
            for ex_data in block_data.get("exercises", []):
                name = ex_data.get("name", "Unknown Exercise")
                canonical_name = self._resolve_canonical_name(name)

                if canonical_name and canonical_name != name:
                    suggestions.append(ExerciseSuggestion(
                        exercise_name=name,
                        field="canonical_name",
                        suggested_value=canonical_name,
                        reason=f"Mapped '{name}' to canonical name '{canonical_name}'",
                    ))

                load = None
                if ex_data.get("load_value"):
                    load = Load(
                        value=ex_data["load_value"],
                        unit=ex_data.get("load_unit", "lb"),
                    )

                exercises.append(Exercise(
                    name=name,
                    canonical_name=canonical_name,
                    sets=ex_data.get("sets"),
                    reps=ex_data.get("reps"),
                    rest_seconds=ex_data.get("rest_seconds"),
                    duration_seconds=ex_data.get("duration_seconds"),
                    load=load,
                    notes=ex_data.get("notes"),
                ))

            block_type_str = block_data.get("type", "straight")
            try:
                block_type = BlockType(block_type_str)
            except ValueError:
                block_type = BlockType.STRAIGHT

            blocks.append(Block(
                label=block_data.get("label", "Main"),
                type=block_type,
                rounds=block_data.get("rounds") or 1,
                exercises=exercises,
            ))

        if not blocks:
            blocks = [Block(label="Main", exercises=[
                Exercise(name="Rest", sets=1, reps=1)
            ])]

        sources = [WorkoutSource.AI]
        if source_url:
            sources.append(WorkoutSource.IMPORT)

        workout = Workout(
            title=llm_result.get("title", "AI-Built Workout"),
            description=llm_result.get("description"),
            blocks=blocks,
            metadata=WorkoutMetadata(
                sources=sources,
                source_url=source_url,
            ),
            tags=[workout_type],
        )

        return workout, suggestions

    def _build_rule_based(
        self,
        workout_type: str,
        format: Optional[str],
        rounds: Optional[int],
        exercises: List[Dict[str, Any]],
        user_preferences: Dict[str, Any],
        source_url: Optional[str],
    ) -> tuple[Workout, List[ExerciseSuggestion]]:
        """Build workout using rule-based defaults (fallback when LLM unavailable)."""
        suggestions: List[ExerciseSuggestion] = []
        default_rest = DEFAULT_REST_PERIODS.get(workout_type, DEFAULT_REST_PERIODS["default"])
        default_reps = DEFAULT_REPS.get(workout_type, DEFAULT_REPS["default"])
        default_sets = DEFAULT_SETS.get(workout_type, DEFAULT_SETS["default"])

        # Apply user preference overrides
        if user_preferences.get("rest_seconds"):
            default_rest = user_preferences["rest_seconds"]
        if user_preferences.get("default_reps"):
            default_reps = user_preferences["default_reps"]
        if user_preferences.get("default_sets"):
            default_sets = user_preferences["default_sets"]

        built_exercises = []
        for ex_data in exercises:
            name = ex_data.get("name", "Unknown Exercise")
            canonical_name = self._resolve_canonical_name(name)

            if canonical_name and canonical_name != name:
                suggestions.append(ExerciseSuggestion(
                    exercise_name=name,
                    field="canonical_name",
                    suggested_value=canonical_name,
                    reason=f"Mapped '{name}' to canonical name '{canonical_name}'",
                ))

            sets = ex_data.get("sets") or default_sets
            reps = ex_data.get("reps") or default_reps
            rest_seconds = ex_data.get("rest_seconds")

            if rest_seconds is None:
                rest_seconds = default_rest
                suggestions.append(ExerciseSuggestion(
                    exercise_name=name,
                    field="rest_seconds",
                    suggested_value=rest_seconds,
                    reason=f"Default rest period for {workout_type} workout type",
                ))

            if ex_data.get("sets") is None:
                suggestions.append(ExerciseSuggestion(
                    exercise_name=name,
                    field="sets",
                    suggested_value=sets,
                    reason=f"Default sets for {workout_type} workout type",
                ))

            if ex_data.get("reps") is None and ex_data.get("duration_seconds") is None:
                suggestions.append(ExerciseSuggestion(
                    exercise_name=name,
                    field="reps",
                    suggested_value=reps,
                    reason=f"Default reps for {workout_type} workout type",
                ))

            load = None
            if ex_data.get("load_value"):
                load = Load(
                    value=ex_data["load_value"],
                    unit=ex_data.get("load_unit", "lb"),
                )

            built_exercises.append(Exercise(
                name=name,
                canonical_name=canonical_name,
                sets=sets,
                reps=ex_data.get("reps") or reps if not ex_data.get("duration_seconds") else ex_data.get("reps"),
                rest_seconds=rest_seconds,
                duration_seconds=ex_data.get("duration_seconds"),
                load=load,
                notes=ex_data.get("notes"),
                equipment=ex_data.get("equipment", []),
            ))

        if not built_exercises:
            built_exercises = [Exercise(name="Rest", sets=1, reps=1)]

        # Determine block type from format
        block_type = BlockType.STRAIGHT
        if format:
            format_lower = format.lower()
            if "circuit" in format_lower:
                block_type = BlockType.CIRCUIT
            elif "superset" in format_lower:
                block_type = BlockType.SUPERSET

        blocks = [Block(
            label="Main",
            type=block_type,
            rounds=rounds or 1,
            exercises=built_exercises,
        )]

        # Generate a title
        exercise_names = [e.name for e in built_exercises[:3]]
        title_parts = exercise_names[:3]
        title = f"{workout_type.title()} - {', '.join(title_parts)}"
        if len(built_exercises) > 3:
            title += f" +{len(built_exercises) - 3} more"

        sources = [WorkoutSource.AI]
        if source_url:
            sources.append(WorkoutSource.IMPORT)

        workout = Workout(
            title=title,
            description=f"AI-generated {workout_type} workout with {len(built_exercises)} exercises",
            blocks=blocks,
            metadata=WorkoutMetadata(
                sources=sources,
                source_url=source_url,
            ),
            tags=[workout_type],
        )

        return workout, suggestions

    def _resolve_canonical_name(self, name: str) -> Optional[str]:
        """Resolve an exercise name to its canonical Garmin name."""
        garmin_name, confidence = find_garmin_exercise(name)
        if garmin_name and confidence >= 0.7:
            return garmin_name
        return None

    def _check_garmin_compatibility(self, workout: Workout) -> GarminCompatibility:
        """Check Garmin device compatibility for the workout."""
        warnings: List[str] = []
        unsupported: List[str] = []
        mapped: Dict[str, str] = {}

        for block in workout.blocks:
            for exercise in block.exercises:
                garmin_name, confidence = find_garmin_exercise(exercise.name)

                if garmin_name and confidence >= 0.7:
                    mapped[exercise.name] = garmin_name
                elif garmin_name and confidence >= 0.5:
                    suggestions = get_garmin_suggestions(exercise.name, limit=3)
                    suggestion_names = [s[0] for s in suggestions]
                    warnings.append(
                        f"Exercise '{exercise.name}' has low confidence Garmin match. "
                        f"Suggestions: {', '.join(suggestion_names)}"
                    )
                    mapped[exercise.name] = garmin_name
                else:
                    unsupported.append(exercise.name)
                    suggestions = get_garmin_suggestions(exercise.name, limit=3)
                    if suggestions:
                        suggestion_names = [s[0] for s in suggestions]
                        warnings.append(
                            f"Exercise '{exercise.name}' not found in Garmin catalog. "
                            f"Closest matches: {', '.join(suggestion_names)}"
                        )
                    else:
                        warnings.append(
                            f"Exercise '{exercise.name}' not found in Garmin exercise catalog"
                        )

                # Check for Garmin-specific limitations
                if exercise.duration_seconds and exercise.duration_seconds > 3600:
                    warnings.append(
                        f"Exercise '{exercise.name}' duration ({exercise.duration_seconds}s) "
                        f"exceeds Garmin's 60-minute interval limit"
                    )

                if exercise.sets and exercise.sets > 99:
                    warnings.append(
                        f"Exercise '{exercise.name}' has {exercise.sets} sets, "
                        f"Garmin supports max 99 sets per exercise"
                    )

        is_compatible = len(unsupported) == 0 and len(warnings) == 0

        return GarminCompatibility(
            is_compatible=is_compatible,
            warnings=warnings,
            unsupported_exercises=unsupported,
            mapped_exercises=mapped,
        )
