"""
Programs router for workout program management.

Part of AMA-593: Extract programs endpoints from app.py to routers

This router contains endpoints for:
- POST /programs - Create a new program
- GET /programs - List user programs
- GET /programs/{program_id} - Get single program details
- PATCH /programs/{program_id} - Update program
- DELETE /programs/{program_id} - Delete program
- POST /programs/{program_id}/members - Add workout/follow-along to program
- DELETE /programs/{program_id}/members/{member_id} - Remove from program
"""

import logging
from typing import Optional, Any

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel

from api.deps import (
    get_current_user,
    create_program,
    get_programs,
    get_program,
    update_program,
    delete_program,
    add_workout_to_program,
    remove_workout_from_program,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Programs"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateProgramRequest(BaseModel):
    """Request for creating a program."""
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class UpdateProgramRequest(BaseModel):
    """Request for updating a program."""
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    current_day_index: Optional[int] = None


class AddToProgramRequest(BaseModel):
    """Request for adding a workout or follow-along to a program."""
    workout_id: Optional[str] = None
    follow_along_id: Optional[str] = None
    day_order: Optional[int] = None


# =============================================================================
# Response Models
# =============================================================================


class CreateProgramResponse(BaseModel):
    """Response for creating a program."""
    success: bool
    program: Optional[dict] = None
    message: str


class GetProgramsResponse(BaseModel):
    """Response for getting all programs."""
    success: bool
    programs: list[dict] = []
    count: int


class GetProgramResponse(BaseModel):
    """Response for getting a single program."""
    success: bool
    program: Optional[dict] = None
    message: Optional[str] = None


class UpdateProgramResponse(BaseModel):
    """Response for updating a program."""
    success: bool
    program: Optional[dict] = None
    message: str


class DeleteProgramResponse(BaseModel):
    """Response for deleting a program."""
    success: bool
    message: str


class AddToProgramResponse(BaseModel):
    """Response for adding to a program."""
    success: bool
    member: Optional[dict] = None
    message: str


class RemoveFromProgramResponse(BaseModel):
    """Response for removing from a program."""
    success: bool
    message: str


# =============================================================================
# Programs Endpoints (AMA-593)
# =============================================================================


@router.post("/programs", response_model=CreateProgramResponse)
async def create_program_endpoint(
    request: CreateProgramRequest,
    current_user: str = Depends(get_current_user),
):
    """Create a new workout program."""

    result = create_program(
        profile_id=current_user,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon
    )

    if result:
        return {
            "success": True,
            "program": result,
            "message": "Program created"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to create program"
        )


@router.get("/programs", response_model=GetProgramsResponse)
async def get_programs_endpoint(
    include_inactive: bool = Query(False, description="Include inactive programs"),
    current_user: str = Depends(get_current_user),
):
    """Get all programs for a user."""

    programs = get_programs(
        profile_id=current_user,
        include_inactive=include_inactive
    )

    return {
        "success": True,
        "programs": programs,
        "count": len(programs)
    }


@router.get("/programs/{program_id}", response_model=GetProgramResponse)
async def get_program_endpoint(
    program_id: str,
    current_user: str = Depends(get_current_user),
):
    """Get a single program with its members."""

    program = get_program(program_id, current_user)

    if program:
        return {
            "success": True,
            "program": program
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="Program not found"
        )


@router.patch("/programs/{program_id}", response_model=UpdateProgramResponse)
async def update_program_endpoint(
    program_id: str,
    request: UpdateProgramRequest,
    current_user: str = Depends(get_current_user),
):
    """Update a program."""

    result = update_program(
        program_id=program_id,
        profile_id=current_user,
        name=request.name,
        description=request.description,
        color=request.color,
        icon=request.icon,
        is_active=request.is_active,
        current_day_index=request.current_day_index
    )

    if result:
        return {
            "success": True,
            "program": result,
            "message": "Program updated"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to update program"
        )


@router.delete("/programs/{program_id}", response_model=DeleteProgramResponse)
async def delete_program_endpoint(
    program_id: str,
    current_user: str = Depends(get_current_user),
):
    """Delete a program."""

    success = delete_program(program_id, current_user)

    if success:
        return {
            "success": True,
            "message": "Program deleted"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to delete program"
        )


@router.post("/programs/{program_id}/members", response_model=AddToProgramResponse)
async def add_to_program_endpoint(
    program_id: str,
    request: AddToProgramRequest,
    current_user: str = Depends(get_current_user),
):
    """Add a workout or follow-along to a program."""

    result = add_workout_to_program(
        program_id=program_id,
        profile_id=current_user,
        workout_id=request.workout_id,
        follow_along_id=request.follow_along_id,
        day_order=request.day_order
    )

    if result:
        return {
            "success": True,
            "member": result,
            "message": "Added to program"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to add to program"
        )


@router.delete("/programs/{program_id}/members/{member_id}", response_model=RemoveFromProgramResponse)
async def remove_from_program_endpoint(
    program_id: str,
    member_id: str,
    current_user: str = Depends(get_current_user),
):
    """Remove a workout from a program."""

    success = remove_workout_from_program(member_id, current_user)

    if success:
        return {
            "success": True,
            "message": "Removed from program"
        }
    else:
        raise HTTPException(
            status_code=400,
            detail="Failed to remove from program"
        )
