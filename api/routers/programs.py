"""
Programs router for periodization planning.

Part of AMA-567 Phase E: Program pipeline (batched generation)

This router provides:
- Periodization plan calculation for multi-week programs
"""

from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.core.periodization_service import (
    PeriodizationService,
    ProgramGoal,
    ExperienceLevel,
    PeriodizationModel,
    WeekParameters,
)

router = APIRouter(
    prefix="/programs",
    tags=["Programs"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class PeriodizationPlanRequest(BaseModel):
    """Request model for calculating a periodization plan."""
    duration_weeks: int = Field(..., ge=4, le=52, description="Program duration in weeks")
    goal: str = Field(..., description="Training goal (strength, hypertrophy, etc.)")
    experience_level: str = Field(..., description="beginner, intermediate, or advanced")
    model: Optional[str] = Field(
        None,
        description="Periodization model (linear, undulating, block, conjugate, reverse_linear). Auto-selected if omitted.",
    )


class WeekParametersResponse(BaseModel):
    """Response model for a single week's periodization parameters."""
    week_number: int
    intensity_percent: float = Field(..., description="Training intensity (0.0-1.0)")
    volume_modifier: float = Field(..., description="Volume multiplier")
    is_deload: bool
    phase: Optional[str] = Field(None, description="Block phase (accumulation/transmutation/realization)")
    effort_type: Optional[str] = Field(None, description="Conjugate effort type")
    focus: str = Field(..., description="Training focus (strength/power/hypertrophy/endurance/deload)")
    notes: Optional[str] = None

    @classmethod
    def from_week_params(cls, wp: WeekParameters) -> "WeekParametersResponse":
        return cls(
            week_number=wp.week_number,
            intensity_percent=wp.intensity_percent,
            volume_modifier=wp.volume_modifier,
            is_deload=wp.is_deload,
            phase=wp.phase.value if wp.phase else None,
            effort_type=wp.effort_type.value if wp.effort_type else None,
            focus=wp.focus.value,
            notes=wp.notes,
        )


class PeriodizationPlanResponse(BaseModel):
    """Response model for a full periodization plan."""
    model: str = Field(..., description="Periodization model used")
    weeks: List[WeekParametersResponse]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/periodization-plan", response_model=PeriodizationPlanResponse)
def create_periodization_plan(
    request: PeriodizationPlanRequest,
) -> PeriodizationPlanResponse:
    """
    Calculate a periodization plan for a training program.

    Given duration, goal, and experience level, returns week-by-week
    training parameters (intensity, volume, deload weeks, focus).

    If no periodization model is specified, one is auto-selected
    based on goal, experience, and duration.
    """
    service = PeriodizationService()

    # Map string values to enums
    goal = ProgramGoal(request.goal)
    experience = ExperienceLevel(request.experience_level)
    model = PeriodizationModel(request.model) if request.model else None

    # Auto-select model if not specified
    if model is None:
        model = service.select_periodization_model(goal, experience, request.duration_weeks)

    weeks = service.plan_progression(
        duration_weeks=request.duration_weeks,
        goal=goal,
        experience_level=experience,
        model=model,
    )

    return PeriodizationPlanResponse(
        model=model.value,
        weeks=[WeekParametersResponse.from_week_params(w) for w in weeks],
    )
