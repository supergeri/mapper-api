"""
Program generation router.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Implemented generation endpoint

This router provides endpoints for AI-powered program generation:
- Generate new training programs based on user preferences
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import (
    get_current_user,
    get_exercise_repo,
    get_program_repo,
    get_settings,
    get_template_repo,
)
from application.ports import ExerciseRepository, ProgramRepository, TemplateRepository
from backend.settings import Settings
from models.generation import GenerateProgramRequest, GenerateProgramResponse
from services.program_generator import ProgramGenerationError, ProgramGenerator

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/generate",
    tags=["Generation"],
)


def get_program_generator(
    settings: Settings = Depends(get_settings),
    program_repo: ProgramRepository = Depends(get_program_repo),
    template_repo: TemplateRepository = Depends(get_template_repo),
    exercise_repo: ExerciseRepository = Depends(get_exercise_repo),
) -> ProgramGenerator:
    """
    Create and return a ProgramGenerator instance.

    Args:
        settings: Application settings
        program_repo: Program repository
        template_repo: Template repository
        exercise_repo: Exercise repository

    Returns:
        Configured ProgramGenerator instance
    """
    return ProgramGenerator(
        program_repo=program_repo,
        template_repo=template_repo,
        exercise_repo=exercise_repo,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
    )


@router.post("", response_model=GenerateProgramResponse)
async def generate_program(
    request: GenerateProgramRequest,
    user_id: str = Depends(get_current_user),
    generator: ProgramGenerator = Depends(get_program_generator),
):
    """
    Generate a new training program using AI.

    This endpoint takes user preferences and generates a personalized
    training program using a hybrid template-guided LLM approach:

    1. **Template Selection**: Finds the best matching template based on
       goal, experience level, and session frequency.

    2. **Periodization**: Applies appropriate periodization model
       (linear, undulating, block, conjugate, or reverse linear).

    3. **Exercise Selection**: Uses LLM to select exercises matching
       muscle groups, equipment, and user constraints.

    4. **Validation**: Ensures program meets safety and balance requirements.

    5. **Persistence**: Saves the program to the database.

    Args:
        request: Generation parameters including:
            - goal: Primary training goal
            - duration_weeks: Program length (1-52)
            - sessions_per_week: Training frequency (1-7)
            - experience_level: User's training experience
            - equipment_available: Available equipment
            - limitations: Any injuries or constraints

    Returns:
        Generated training program with metadata and suggestions

    Raises:
        HTTPException 400: If generation request is invalid
        HTTPException 500: If generation fails
    """
    logger.info(
        f"Generate program request: goal={request.goal}, "
        f"duration={request.duration_weeks}w, sessions={request.sessions_per_week}/w"
    )

    try:
        response = await generator.generate(request, user_id)
        return response

    except ProgramGenerationError as e:
        logger.error(f"Program generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Program generation failed: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Unexpected error during program generation: {e}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred during program generation",
        )
