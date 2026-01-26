"""
Request/response models for program generation.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-491: Added input validation for limitations

These models define the API contract for AI-powered program generation.
"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator

from core.constants import MAX_LIMITATIONS_COUNT
from core.sanitization import sanitize_user_input
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

    @field_validator("limitations", mode="before")
    @classmethod
    def validate_limitations(cls, v: Any) -> List[str]:
        """
        Validate and sanitize limitations to prevent prompt injection.

        - Limits the number of limitations
        - Removes control characters from each limitation
        - Truncates each limitation to max length
        - Filters out empty strings
        """
        if not v:
            return []

        if not isinstance(v, list):
            return []

        if len(v) > MAX_LIMITATIONS_COUNT:
            raise ValueError(
                f"Too many limitations. Maximum allowed: {MAX_LIMITATIONS_COUNT}"
            )

        sanitized = []
        for limitation in v:
            if not isinstance(limitation, str):
                continue
            clean = sanitize_user_input(limitation)
            if clean:
                sanitized.append(clean)

        return sanitized


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
