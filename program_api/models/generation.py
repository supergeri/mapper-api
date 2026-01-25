"""
Request/response models for program generation.

Part of AMA-461: Create program-api service scaffold

These models define the API contract for AI-powered program generation.
"""

from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from models.program import ProgramGoal, ExperienceLevel, TrainingProgram


class GenerateProgramRequest(BaseModel):
    """Request model for generating a training program."""

    goal: ProgramGoal = Field(description="Primary training goal")
    duration_weeks: int = Field(
        ge=1, le=52, description="Program duration in weeks"
    )
    sessions_per_week: int = Field(
        ge=1, le=7, description="Number of training sessions per week"
    )
    experience_level: ExperienceLevel = Field(
        description="User's training experience level"
    )
    equipment_available: List[str] = Field(
        default_factory=list,
        description="List of available equipment (e.g., 'barbell', 'dumbbells', 'cables')",
    )
    focus_areas: List[str] = Field(
        default_factory=list,
        description="Specific muscle groups or movement patterns to emphasize",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Any injuries or limitations to work around",
    )
    preferences: Optional[str] = Field(
        None,
        description="Additional preferences or notes for program generation",
    )


class GenerateProgramResponse(BaseModel):
    """Response model for generated training program."""

    program: TrainingProgram = Field(description="The generated training program")
    generation_metadata: dict = Field(
        default_factory=dict,
        description="Metadata about the generation process",
    )
    suggestions: List[str] = Field(
        default_factory=list,
        description="AI suggestions for optimizing the program",
    )
