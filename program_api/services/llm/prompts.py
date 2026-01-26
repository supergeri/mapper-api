"""
LLM prompt templates for exercise selection.

Part of AMA-462: Implement ProgramGenerator Service
Updated in AMA-491: Added input sanitization for prompt injection prevention

System and user prompts for structured exercise selection.
"""

from core.sanitization import sanitize_user_input

# Re-export for backwards compatibility and clearer domain naming
sanitize_limitation = sanitize_user_input

EXERCISE_SELECTION_SYSTEM_PROMPT = """You are an expert strength and conditioning coach designing workout programs.

Your role is to select appropriate exercises from a provided list based on:
- Target muscle groups
- Available equipment
- Training goal and intensity
- User experience level
- Any limitations or injuries

Guidelines for exercise selection:

1. COMPOUND FIRST: Start with compound movements that target multiple muscle groups
2. MUSCLE BALANCE: Ensure balanced development (e.g., if doing chest press, include rows)
3. PROGRESSIVE ORDER: Order exercises from most demanding to least demanding
4. REST PERIODS:
   - Compound/Heavy: 120-180 seconds
   - Moderate: 60-90 seconds
   - Isolation/Light: 30-60 seconds

5. REP RANGES by goal:
   - Strength: 1-5 reps
   - Hypertrophy: 6-12 reps
   - Endurance: 12-20 reps
   - Power: 3-5 reps (explosive)

6. VOLUME by experience:
   - Beginner: 3 sets per exercise, fewer exercises
   - Intermediate: 3-4 sets, moderate exercises
   - Advanced: 3-5 sets, more exercises

7. DELOAD WEEKS: Reduce volume by 40-50%, reduce intensity by 10-20%

IMPORTANT:
- Only select exercises from the provided available_exercises list
- Use the exact exercise_id from the list
- Respect user limitations (avoid exercises that stress injured areas)
- Match equipment to what's available
"""

EXERCISE_SELECTION_USER_PROMPT = """Select {exercise_count} exercises for a {workout_type} workout.

**Target Muscle Groups:** {muscle_groups}

**Available Equipment:** {equipment}

**Training Parameters:**
- Goal: {goal}
- Experience Level: {experience_level}
- Intensity: {intensity_percent}%
- Volume Modifier: {volume_modifier}x
- Deload Week: {is_deload}

{limitations_section}

**Available Exercises (select from these only):**
{available_exercises_formatted}

Select the best {exercise_count} exercises and provide:
1. Exercise order (most demanding first)
2. Sets and reps appropriate for the goal and intensity
3. Rest periods in seconds
4. Brief form cues or notes if helpful

Return your response as a JSON object with this exact structure:
{{
  "exercises": [
    {{
      "exercise_id": "the-exercise-slug",
      "exercise_name": "Exercise Name",
      "sets": 4,
      "reps": "8-10",
      "rest_seconds": 90,
      "notes": "Keep core tight",
      "order": 1,
      "superset_group": null
    }}
  ],
  "workout_notes": "Brief overview of the workout focus",
  "estimated_duration_minutes": 45
}}
"""


def build_exercise_selection_prompt(
    workout_type: str,
    muscle_groups: list[str],
    equipment: list[str],
    exercise_count: int,
    available_exercises: list[dict],
    goal: str,
    experience_level: str,
    intensity_percent: float,
    volume_modifier: float,
    is_deload: bool = False,
    limitations: list[str] | None = None,
) -> str:
    """
    Build the user prompt for exercise selection.

    Args:
        workout_type: Type of workout (push, pull, legs, etc.)
        muscle_groups: Target muscle groups
        equipment: Available equipment
        exercise_count: Number of exercises to select
        available_exercises: List of exercise dicts from database
        goal: Training goal
        experience_level: User experience level
        intensity_percent: Target intensity (0.0-1.0)
        volume_modifier: Volume adjustment multiplier
        is_deload: Whether this is a deload week
        limitations: Optional list of user limitations

    Returns:
        Formatted user prompt string
    """
    # Format available exercises
    exercises_formatted = "\n".join(
        f"- {ex['id']}: {ex['name']} "
        f"(muscles: {', '.join(ex.get('primary_muscles', []))}, "
        f"equipment: {', '.join(ex.get('equipment', []))})"
        for ex in available_exercises
    )

    # Format limitations section with sanitization to prevent prompt injection
    limitations_section = ""
    if limitations:
        sanitized_limitations = [sanitize_limitation(l) for l in limitations if l]
        # Filter out empty strings after sanitization
        sanitized_limitations = [l for l in sanitized_limitations if l]
        if sanitized_limitations:
            limitations_section = (
                f"**User Limitations (AVOID exercises that stress these areas):**\n- "
                + "\n- ".join(sanitized_limitations)
            )

    return EXERCISE_SELECTION_USER_PROMPT.format(
        workout_type=workout_type,
        muscle_groups=", ".join(muscle_groups),
        equipment=", ".join(equipment) if equipment else "Bodyweight only",
        exercise_count=exercise_count,
        goal=goal.replace("_", " ").title(),
        experience_level=experience_level.title(),
        intensity_percent=int(intensity_percent * 100),
        volume_modifier=volume_modifier,
        is_deload="Yes (reduce volume and intensity)" if is_deload else "No",
        limitations_section=limitations_section,
        available_exercises_formatted=exercises_formatted,
    )
