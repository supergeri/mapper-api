"""
Training programs CRUD router.

Part of AMA-461: Create program-api service scaffold

This router provides endpoints for managing training programs:
- List user's programs
- Get program details
- Create new programs
- Update programs
- Delete programs

Note: These are stubs that will be implemented in future tickets.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user
from models.program import TrainingProgram, TrainingProgramCreate, TrainingProgramUpdate

router = APIRouter(
    prefix="/programs",
    tags=["Programs"],
)


@router.get("", response_model=List[TrainingProgram])
async def list_programs(
    user_id: str = Depends(get_current_user),
):
    """
    List all training programs for the current user.

    Returns:
        List of training programs
    """
    # Stub: Will be implemented in AMA-462
    return []


@router.get("/{program_id}", response_model=TrainingProgram)
async def get_program(
    program_id: UUID,
    user_id: str = Depends(get_current_user),
):
    """
    Get a specific training program by ID.

    Args:
        program_id: The program UUID

    Returns:
        The training program details
    """
    # Stub: Will be implemented in AMA-462
    raise HTTPException(status_code=404, detail="Program not found")


@router.post("", response_model=TrainingProgram, status_code=201)
async def create_program(
    program: TrainingProgramCreate,
    user_id: str = Depends(get_current_user),
):
    """
    Create a new training program.

    Args:
        program: The program data

    Returns:
        The created training program
    """
    # Stub: Will be implemented in AMA-462
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/{program_id}", response_model=TrainingProgram)
async def update_program(
    program_id: UUID,
    program: TrainingProgramUpdate,
    user_id: str = Depends(get_current_user),
):
    """
    Update an existing training program.

    Args:
        program_id: The program UUID
        program: The updated program data

    Returns:
        The updated training program
    """
    # Stub: Will be implemented in AMA-462
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{program_id}", status_code=204)
async def delete_program(
    program_id: UUID,
    user_id: str = Depends(get_current_user),
):
    """
    Delete a training program.

    Args:
        program_id: The program UUID
    """
    # Stub: Will be implemented in AMA-462
    raise HTTPException(status_code=501, detail="Not implemented")
