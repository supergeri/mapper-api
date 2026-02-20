"""
AI Build router for generating workouts from partial input using AI.

Part of AMA-446: AI Builder API Endpoint

Endpoint: POST /api/v1/workouts/ai-build
Accepts partial workout data and returns a structured workout with
AI-filled defaults, exercise suggestions, and Garmin compatibility info.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.deps import get_current_user, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["AI Build"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class AIBuildExerciseInput(BaseModel):
    """Input for a single exercise in the AI build request."""
    name: str = Field(..., min_length=1, description="Exercise name")
    sets: Optional[int] = Field(default=None, ge=1, description="Number of sets")
    reps: Optional[int] = Field(default=None, ge=1, description="Reps per set")
    duration_seconds: Optional[int] = Field(default=None, ge=1, description="Duration in seconds")
    rest_seconds: Optional[int] = Field(default=None, ge=0, description="Rest period in seconds")
    load_value: Optional[float] = Field(default=None, ge=0, description="Load/weight value")
    load_unit: Optional[str] = Field(default=None, description="Load unit (lb, kg)")
    equipment: Optional[List[str]] = Field(default_factory=list, description="Equipment needed")
    notes: Optional[str] = Field(default=None, description="Additional notes")


class AIBuildRequest(BaseModel):
    """Request body for the AI workout builder endpoint."""
    source_url: Optional[str] = Field(default=None, description="Source URL for the workout")
    workout_type: Optional[str] = Field(
        default="strength",
        description="Workout type (strength, hypertrophy, hiit, circuit, endurance, crossfit)",
    )
    format: Optional[str] = Field(
        default=None,
        description="Workout format (straight_sets, circuit, superset)",
    )
    rounds: Optional[int] = Field(default=None, ge=1, description="Number of rounds")
    exercises: List[AIBuildExerciseInput] = Field(
        default_factory=list,
        description="Partial exercise list to build from",
    )
    user_preferences: Optional[Dict[str, Any]] = Field(
        default=None,
        description="User preferences (rest_seconds, default_reps, default_sets, unit_system)",
    )


class ExerciseSuggestionResponse(BaseModel):
    """A suggestion for an exercise field."""
    exercise_name: str
    field: str
    suggested_value: Any
    reason: str


class GarminCompatibilityResponse(BaseModel):
    """Garmin compatibility information."""
    is_compatible: bool
    warnings: List[str] = []
    unsupported_exercises: List[str] = []
    mapped_exercises: Dict[str, str] = {}


class AIBuildResponse(BaseModel):
    """Response from the AI workout builder endpoint."""
    success: bool = True
    workout: Optional[Dict[str, Any]] = None
    suggestions: List[ExerciseSuggestionResponse] = []
    garmin_compatibility: Optional[GarminCompatibilityResponse] = None
    build_time_ms: int = 0
    llm_used: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Dependency Provider
# =============================================================================


def get_ai_builder_service():
    """Get AIBuilderService with available LLM clients."""
    from backend.services.ai_builder import AIBuilderService
    from backend.settings import get_settings as _get_settings

    settings = _get_settings()
    openai_client = None
    anthropic_client = None

    # Try to create OpenAI client
    if settings.openai_api_key:
        try:
            from backend.ai.client_factory import AIClientFactory, AIRequestContext
            context = AIRequestContext(feature_name="ai-build")
            openai_client = AIClientFactory.create_openai_client(
                context=context, timeout=5.0
            )
        except Exception as e:
            logger.warning(f"Failed to create OpenAI client for AI build: {e}")

    # Try to create Anthropic client
    try:
        from backend.ai.client_factory import AIClientFactory, AIRequestContext
        context = AIRequestContext(feature_name="ai-build")
        anthropic_client = AIClientFactory.create_anthropic_client(
            context=context, timeout=5.0
        )
    except Exception as e:
        logger.debug(f"Anthropic client not available for AI build: {e}")

    return AIBuilderService(
        openai_client=openai_client,
        anthropic_client=anthropic_client,
    )


# =============================================================================
# Endpoint
# =============================================================================


@router.post(
    "/api/v1/workouts/ai-build",
    response_model=AIBuildResponse,
    summary="Build workout from partial input using AI",
    description=(
        "Accepts partial workout data (workout type, exercises, structure) "
        "and returns a structured workout using AI assistance. "
        "Fills in defaults for rest periods, reps, sets, and canonical exercise names. "
        "Includes Garmin compatibility warnings."
    ),
)
def ai_build_workout(
    request: AIBuildRequest,
    user_id: str = Depends(get_current_user),
):
    """
    Build a structured workout from partial input using AI.

    Part of AMA-446: AI Builder API Endpoint

    Accepts partial workout data and uses LLM (GPT-4o-mini primary,
    Claude 3 Haiku fallback) to fill in sensible defaults. Falls back
    to rule-based defaults if LLM is unavailable.

    Returns:
    - Complete workout matching unified schema
    - Suggestions array with field suggestions and reasons
    - Garmin compatibility object with warnings
    """
    from backend.services.ai_builder import AIBuilderService

    try:
        service = get_ai_builder_service()

        result = service.build(
            workout_type=request.workout_type,
            format=request.format,
            rounds=request.rounds,
            exercises=[ex.model_dump() for ex in request.exercises],
            user_preferences=request.user_preferences,
            source_url=request.source_url,
        )

        if result.error:
            return AIBuildResponse(
                success=False,
                error=result.error,
                build_time_ms=result.build_time_ms,
            )

        # Convert workout to dict for response
        workout_dict = result.workout.model_dump() if result.workout else None

        # Convert suggestions
        suggestions = [
            ExerciseSuggestionResponse(
                exercise_name=s.exercise_name,
                field=s.field,
                suggested_value=s.suggested_value,
                reason=s.reason,
            )
            for s in result.suggestions
        ]

        # Convert Garmin compatibility
        garmin_compat = None
        if result.garmin_compatibility:
            garmin_compat = GarminCompatibilityResponse(
                is_compatible=result.garmin_compatibility.is_compatible,
                warnings=result.garmin_compatibility.warnings,
                unsupported_exercises=result.garmin_compatibility.unsupported_exercises,
                mapped_exercises=result.garmin_compatibility.mapped_exercises,
            )

        return AIBuildResponse(
            success=True,
            workout=workout_dict,
            suggestions=suggestions,
            garmin_compatibility=garmin_compat,
            build_time_ms=result.build_time_ms,
            llm_used=result.llm_used,
        )

    except Exception as e:
        logger.exception(f"AI build failed: {e}")
        return AIBuildResponse(
            success=False,
            error=f"Failed to build workout: {str(e)}",
        )
