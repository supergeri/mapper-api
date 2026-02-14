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
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Programs"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class CreateProgramRequest(BaseModel):
    """Request for creating a program."""
    profile_id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None


class UpdateProgramRequest(BaseModel):
    """Request for updating a program."""
    profile_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    is_active: Optional[bool] = None
    current_day_index: Optional[int] = None


class AddToProgramRequest(BaseModel):
    """Request for adding a workout or follow-along to a program."""
    profile_id: str
    workout_id: Optional[str] = None
    follow_along_id: Optional[str] = None
    day_order: Optional[int] = None


# =============================================================================
# Programs Endpoints (AMA-593)
# =============================================================================


@router.post("/programs")
def create_program_endpoint(request: CreateProgramRequest):
    """Create a new workout program."""
    from backend.database import create_program
    
    result = create_program(
        profile_id=request.profile_id,
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
        return {
            "success": False,
            "message": "Failed to create program"
        }


@router.get("/programs")
def get_programs_endpoint(
    profile_id: str = Query(..., description="User profile ID"),
    include_inactive: bool = Query(False, description="Include inactive programs")
):
    """Get all programs for a user."""
    from backend.database import get_programs
    
    programs = get_programs(
        profile_id=profile_id,
        include_inactive=include_inactive
    )

    return {
        "success": True,
        "programs": programs,
        "count": len(programs)
    }


@router.get("/programs/{program_id}")
def get_program_endpoint(
    program_id: str,
    profile_id: str = Query(..., description="User profile ID")
):
    """Get a single program with its members."""
    from backend.database import get_program
    
    program = get_program(program_id, profile_id)

    if program:
        return {
            "success": True,
            "program": program
        }
    else:
        return {
            "success": False,
            "message": "Program not found"
        }


@router.patch("/programs/{program_id}")
def update_program_endpoint(program_id: str, request: UpdateProgramRequest):
    """Update a program."""
    from backend.database import update_program
    
    result = update_program(
        program_id=program_id,
        profile_id=request.profile_id,
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
        return {
            "success": False,
            "message": "Failed to update program"
        }


@router.delete("/programs/{program_id}")
def delete_program_endpoint(
    program_id: str,
    profile_id: str = Query(..., description="User profile ID")
):
    """Delete a program."""
    from backend.database import delete_program
    
    success = delete_program(program_id, profile_id)

    if success:
        return {
            "success": True,
            "message": "Program deleted"
        }
    else:
        return {
            "success": False,
            "message": "Failed to delete program"
        }


@router.post("/programs/{program_id}/members")
def add_to_program_endpoint(program_id: str, request: AddToProgramRequest):
    """Add a workout or follow-along to a program."""
    from backend.database import add_workout_to_program
    
    result = add_workout_to_program(
        program_id=program_id,
        profile_id=request.profile_id,
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
        return {
            "success": False,
            "message": "Failed to add to program"
        }


@router.delete("/programs/{program_id}/members/{member_id}")
def remove_from_program_endpoint(
    program_id: str,
    member_id: str,
    profile_id: str = Query(..., description="User profile ID")
):
    """Remove a workout from a program."""
    from backend.database import remove_workout_from_program
    
    success = remove_workout_from_program(member_id, profile_id)

    if success:
        return {
            "success": True,
            "message": "Removed from program"
        }
    else:
        return {
            "success": False,
            "message": "Failed to remove from program"
        }
