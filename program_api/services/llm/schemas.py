"""
LLM response schemas for exercise selection.

Part of AMA-462: Implement ProgramGenerator Service

Pydantic models for structured LLM responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ExerciseSelection(BaseModel):
    """A single exercise selected by the LLM."""

    exercise_id: str = Field(description="The exercise ID/slug from the database")
    exercise_name: str = Field(description="Human-readable exercise name")
    sets: int = Field(ge=1, le=10, description="Number of sets")
    reps: str = Field(description="Rep range or scheme (e.g., '8-12', '5x5', 'AMRAP')")
    rest_seconds: int = Field(ge=30, le=300, description="Rest between sets in seconds")
    notes: Optional[str] = Field(None, description="Form cues or coaching notes")
    order: int = Field(ge=1, description="Order in the workout (1 = first)")
    superset_group: Optional[str] = Field(
        None, description="Superset grouping identifier if applicable"
    )


class ExerciseSelectionRequest(BaseModel):
    """Request for LLM exercise selection."""

    workout_type: str = Field(description="Type of workout (push, pull, legs, etc.)")
    muscle_groups: List[str] = Field(description="Target muscle groups")
    equipment: List[str] = Field(description="Available equipment")
    exercise_count: int = Field(ge=3, le=12, description="Number of exercises to select")
    intensity_percent: float = Field(
        ge=0.0, le=1.0, description="Target intensity as decimal (can be low for deload)"
    )
    volume_modifier: float = Field(
        ge=0.0, le=2.0, description="Volume adjustment multiplier (can be low for deload)"
    )
    available_exercises: List[dict] = Field(
        description="List of available exercises from database"
    )
    user_limitations: Optional[List[str]] = Field(
        None, description="User limitations or injuries to avoid"
    )
    experience_level: str = Field(description="User experience level")
    goal: str = Field(description="Training goal")
    is_deload: bool = Field(default=False, description="Whether this is a deload week")


class ExerciseSelectionResponse(BaseModel):
    """Response from LLM exercise selection."""

    exercises: List[ExerciseSelection] = Field(
        description="Selected exercises in order"
    )
    workout_notes: Optional[str] = Field(
        None, description="General notes about the workout"
    )
    estimated_duration_minutes: int = Field(
        ge=20, le=120, description="Estimated workout duration"
    )


class WorkoutPlanRequest(BaseModel):
    """Request for a complete workout plan."""

    week_number: int = Field(ge=1, description="Week number in program")
    day_of_week: int = Field(ge=0, le=6, description="Day of week (0=Sunday)")
    workout_name: str = Field(description="Name of the workout")
    workout_type: str = Field(description="Type of workout")
    target_muscle_groups: List[str] = Field(description="Target muscle groups")
    equipment_available: List[str] = Field(description="Available equipment")
    time_per_session_minutes: int = Field(
        ge=30, le=120, description="Target session duration"
    )
    intensity_percent: float = Field(description="Target intensity")
    volume_modifier: float = Field(description="Volume adjustment")
    experience_level: str = Field(description="User experience level")
    goal: str = Field(description="Training goal")
    is_deload: bool = Field(default=False, description="Deload week flag")
    limitations: Optional[List[str]] = Field(None, description="User limitations")
