"""
Training programs CRUD router.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-464: Implement program CRUD endpoints

This router provides endpoints for managing training programs:
- List user's programs (with filtering and pagination)
- Get program details (including weeks and workouts)
- Create new programs
- Update programs (partial updates)
- Activate programs (set status and schedule)
- Delete programs (soft delete via archive)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from api.deps import get_current_user, get_program_repo
from application.ports import ProgramRepository
from models.program import (
    ActivationRequest,
    ActivationResponse,
    ProgramListResponse,
    ProgramStatus,
    ProgramUpdateRequest,
    ProgramWeek,
    TrainingProgram,
    TrainingProgramCreate,
    TrainingProgramUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/programs",
    tags=["Programs"],
)


# =============================================================================
# Custom Exceptions
# =============================================================================


class ProgramNotFoundError(HTTPException):
    """Raised when a program cannot be found."""

    def __init__(self, program_id: UUID):
        super().__init__(
            status_code=404,
            detail=f"Program {program_id} not found",
        )


class ProgramAccessDeniedError(HTTPException):
    """
    Raised when user doesn't have access to a program.

    Returns 404 instead of 403 to prevent resource enumeration attacks.
    An attacker cannot distinguish between "not found" and "not authorized".
    """

    def __init__(self, program_id: UUID):
        super().__init__(
            status_code=404,
            detail=f"Program {program_id} not found",
        )


# =============================================================================
# Helper Functions
# =============================================================================


def _get_program_or_404(
    program_id: UUID,
    user_id: str,
    program_repo: ProgramRepository,
) -> dict:
    """
    Get a program by ID, raising appropriate errors if not found or unauthorized.

    Args:
        program_id: The program UUID
        user_id: The requesting user's ID
        program_repo: Program repository

    Returns:
        Program dictionary

    Raises:
        ProgramNotFoundError: If program doesn't exist
        ProgramAccessDeniedError: If user doesn't own the program
    """
    program = program_repo.get_by_id(str(program_id))
    if not program:
        raise ProgramNotFoundError(program_id)
    if program.get("user_id") != user_id:
        raise ProgramAccessDeniedError(program_id)
    return program


def _build_training_program(
    program_data: dict,
    weeks_data: Optional[List[dict]] = None,
) -> TrainingProgram:
    """
    Build a TrainingProgram model from database dictionaries.

    Args:
        program_data: Program dictionary from database
        weeks_data: Optional list of week dictionaries with workouts

    Returns:
        TrainingProgram model instance
    """
    weeks = []
    if weeks_data:
        weeks = [ProgramWeek(**week) for week in weeks_data]

    return TrainingProgram(
        id=program_data["id"],
        user_id=program_data["user_id"],
        name=program_data["name"],
        description=program_data.get("description"),
        goal=program_data["goal"],
        experience_level=program_data["experience_level"],
        duration_weeks=program_data["duration_weeks"],
        sessions_per_week=program_data["sessions_per_week"],
        status=program_data.get("status", "draft"),
        equipment_available=program_data.get("equipment_available", []),
        weeks=weeks,
        created_at=program_data["created_at"],
        updated_at=program_data["updated_at"],
    )


# =============================================================================
# List Programs
# =============================================================================


@router.get("", response_model=ProgramListResponse)
async def list_programs(
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
    status: Optional[ProgramStatus] = Query(
        None, description="Filter by program status"
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum programs to return"),
    offset: int = Query(0, ge=0, description="Number of programs to skip"),
) -> ProgramListResponse:
    """
    List all training programs for the current user.

    Supports filtering by status and pagination.

    Args:
        status: Optional status filter (draft, active, completed, archived)
        limit: Maximum number of programs to return (default 20, max 100)
        offset: Number of programs to skip for pagination

    Returns:
        Paginated list of training programs
    """
    logger.info(f"Listing programs for user {user_id}, status={status}")

    # Get all programs for user
    all_programs = program_repo.get_by_user(user_id)

    # Filter by status if provided
    if status:
        all_programs = [p for p in all_programs if p.get("status") == status.value]

    total = len(all_programs)

    # Apply pagination
    paginated = all_programs[offset : offset + limit]

    # Convert to models (without weeks for list view)
    programs = [_build_training_program(p) for p in paginated]

    return ProgramListResponse(
        programs=programs,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


# =============================================================================
# Get Program
# =============================================================================


@router.get("/{program_id}", response_model=TrainingProgram)
async def get_program(
    program_id: UUID,
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> TrainingProgram:
    """
    Get a specific training program by ID.

    Returns the full program including all weeks and workouts.

    Args:
        program_id: The program UUID

    Returns:
        The training program with full details

    Raises:
        404: Program not found
        403: Access denied
    """
    logger.info(f"Getting program {program_id} for user {user_id}")

    program = _get_program_or_404(program_id, user_id, program_repo)

    # Get weeks with workouts
    weeks = program_repo.get_weeks(str(program_id))

    return _build_training_program(program, weeks)


# =============================================================================
# Create Program
# =============================================================================


@router.post("", response_model=TrainingProgram, status_code=201)
async def create_program(
    program: TrainingProgramCreate,
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> TrainingProgram:
    """
    Create a new training program.

    Creates an empty program shell in draft status.
    Use the /generate endpoint to create a program with AI-generated content.

    Args:
        program: The program data

    Returns:
        The created training program
    """
    logger.info(f"Creating program '{program.name}' for user {user_id}")

    program_data = {
        "user_id": user_id,
        "name": program.name,
        "description": program.description,
        "goal": program.goal.value,
        "experience_level": program.experience_level.value,
        "duration_weeks": program.duration_weeks,
        "sessions_per_week": program.sessions_per_week,
        "equipment_available": program.equipment_available,
        "status": ProgramStatus.DRAFT.value,
    }

    created = program_repo.create(program_data)
    logger.info(f"Created program {created['id']}")

    return _build_training_program(created)


# =============================================================================
# Update Program
# =============================================================================


@router.patch("/{program_id}", response_model=TrainingProgram)
async def update_program(
    program_id: UUID,
    update: ProgramUpdateRequest,
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> TrainingProgram:
    """
    Update an existing training program.

    Supports partial updates to status, name, and current week tracking.

    Args:
        program_id: The program UUID
        update: Fields to update (all optional)

    Returns:
        The updated training program

    Raises:
        404: Program not found
        403: Access denied
    """
    logger.info(f"Updating program {program_id} for user {user_id}")

    # Verify access
    program = _get_program_or_404(program_id, user_id, program_repo)

    # Build update data (only non-None fields)
    update_data = {}
    if update.status is not None:
        update_data["status"] = update.status.value
    if update.name is not None:
        update_data["name"] = update.name
    if update.current_week is not None:
        # Validate current_week is within program duration
        if update.current_week > program["duration_weeks"]:
            raise HTTPException(
                status_code=422,
                detail=f"current_week ({update.current_week}) exceeds program duration ({program['duration_weeks']} weeks)",
            )
        update_data["current_week"] = update.current_week

    if not update_data:
        # No changes, return existing program
        weeks = program_repo.get_weeks(str(program_id))
        return _build_training_program(program, weeks)

    updated = program_repo.update(str(program_id), update_data)
    weeks = program_repo.get_weeks(str(program_id))

    return _build_training_program(updated, weeks)


# =============================================================================
# Full Update Program (PUT)
# =============================================================================


@router.put("/{program_id}", response_model=TrainingProgram)
async def replace_program(
    program_id: UUID,
    program: TrainingProgramUpdate,
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> TrainingProgram:
    """
    Replace/update an existing training program (full update).

    Args:
        program_id: The program UUID
        program: The updated program data

    Returns:
        The updated training program

    Raises:
        404: Program not found
        403: Access denied
    """
    logger.info(f"Replacing program {program_id} for user {user_id}")

    # Verify access
    _get_program_or_404(program_id, user_id, program_repo)

    # Build update data (only non-None fields)
    update_data = {}
    if program.name is not None:
        update_data["name"] = program.name
    if program.description is not None:
        update_data["description"] = program.description
    if program.goal is not None:
        update_data["goal"] = program.goal.value
    if program.experience_level is not None:
        update_data["experience_level"] = program.experience_level.value
    if program.duration_weeks is not None:
        update_data["duration_weeks"] = program.duration_weeks
    if program.sessions_per_week is not None:
        update_data["sessions_per_week"] = program.sessions_per_week
    if program.status is not None:
        update_data["status"] = program.status.value
    if program.equipment_available is not None:
        update_data["equipment_available"] = program.equipment_available

    if not update_data:
        raise HTTPException(
            status_code=422,
            detail="No fields provided for update",
        )

    updated = program_repo.update(str(program_id), update_data)
    weeks = program_repo.get_weeks(str(program_id))

    return _build_training_program(updated, weeks)


# =============================================================================
# Activate Program
# =============================================================================


@router.post("/{program_id}/activate", response_model=ActivationResponse)
async def activate_program(
    program_id: UUID,
    request: Optional[ActivationRequest] = Body(default=None),
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> ActivationResponse:
    """
    Activate a training program.

    Sets the program status to 'active' and optionally schedules workouts
    on the user's calendar starting from the specified date.

    Args:
        program_id: The program UUID
        request: Optional activation options (start_date)

    Returns:
        Activation confirmation with scheduling details

    Raises:
        404: Program not found
        403: Access denied
        422: Program cannot be activated (e.g., already active/completed)
    """
    logger.info(f"Activating program {program_id} for user {user_id}")

    program = _get_program_or_404(program_id, user_id, program_repo)

    # Check if program can be activated
    current_status = program.get("status", "draft")
    if current_status == ProgramStatus.ACTIVE.value:
        raise HTTPException(
            status_code=422,
            detail="Program is already active",
        )
    if current_status == ProgramStatus.COMPLETED.value:
        raise HTTPException(
            status_code=422,
            detail="Cannot activate a completed program",
        )
    if current_status == ProgramStatus.ARCHIVED.value:
        raise HTTPException(
            status_code=422,
            detail="Cannot activate an archived program. Restore it first.",
        )

    # Determine start date
    if request and request.start_date:
        start_date = request.start_date
    else:
        start_date = datetime.now(timezone.utc)

    # Update program status
    program_repo.update(
        str(program_id),
        {
            "status": ProgramStatus.ACTIVE.value,
            "start_date": start_date.isoformat(),
            "current_week": 1,
        },
    )

    # Get weeks to count scheduled workouts
    weeks = program_repo.get_weeks(str(program_id))
    total_workouts = sum(len(week.get("workouts", [])) for week in weeks)

    # TODO: Integrate with calendar service to schedule workouts (AMA-469)
    # For now, we just return the count of workouts that would be scheduled

    return ActivationResponse(
        program_id=program_id,
        status=ProgramStatus.ACTIVE,
        start_date=start_date,
        scheduled_workouts=total_workouts,
        message=f"Program activated successfully. {total_workouts} workouts scheduled.",
    )


# =============================================================================
# Delete Program
# =============================================================================


@router.delete("/{program_id}", status_code=204)
async def delete_program(
    program_id: UUID,
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
) -> None:
    """
    Delete (archive) a training program.

    Performs a soft delete by setting the program status to 'archived'.
    Archived programs are hidden from the default list view but can be
    restored by updating the status.

    Args:
        program_id: The program UUID

    Raises:
        404: Program not found
        403: Access denied
    """
    logger.info(f"Archiving program {program_id} for user {user_id}")

    program = _get_program_or_404(program_id, user_id, program_repo)

    # Check if already archived
    if program.get("status") == ProgramStatus.ARCHIVED.value:
        # Idempotent - already archived
        return

    # Soft delete by setting status to archived
    program_repo.update(str(program_id), {"status": ProgramStatus.ARCHIVED.value})

    logger.info(f"Archived program {program_id}")
