"""
Programs router for periodization planning.

Part of AMA-567 Phase E: Program pipeline (batched generation)

This router provides:
- Periodization plan calculation for multi-week programs
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_current_user
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
    goal: ProgramGoal = Field(..., description="Training goal")
    experience_level: ExperienceLevel = Field(..., description="User experience level")
    periodization_model: Optional[PeriodizationModel] = Field(
        None,
        alias="model",
        description="Periodization model (linear, undulating, block, conjugate, reverse_linear). Auto-selected if omitted.",
    )

    model_config = {"populate_by_name": True}


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
    periodization_model: str = Field(..., alias="model", description="Periodization model used")
    weeks: List[WeekParametersResponse]

    model_config = {"populate_by_name": True}


# =============================================================================
# Dependencies
# =============================================================================


def get_periodization_service() -> PeriodizationService:
    """Dependency for PeriodizationService."""
    return PeriodizationService()


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/periodization-plan", response_model=PeriodizationPlanResponse)
def create_periodization_plan(
    request: PeriodizationPlanRequest,
    user_id: str = Depends(get_current_user),
    service: PeriodizationService = Depends(get_periodization_service),
) -> PeriodizationPlanResponse:
    """
    Calculate a periodization plan for a training program.

    Given duration, goal, and experience level, returns week-by-week
    training parameters (intensity, volume, deload weeks, focus).

    If no periodization model is specified, one is auto-selected
    based on goal, experience, and duration.
    """
    goal = request.goal
    experience = request.experience_level
    model = request.periodization_model

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
        periodization_model=model.value,
        weeks=[WeekParametersResponse.from_week_params(w) for w in weeks],
    )
