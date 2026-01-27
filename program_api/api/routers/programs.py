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
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query

from api.deps import get_calendar_client, get_current_user, get_program_repo, verify_service_token
from application.ports import ProgramRepository
from infrastructure.calendar_client import (
    CalendarAPIError,
    CalendarAPIUnavailable,
    CalendarClient,
    ProgramEventData,
)
from models.program import (
    ActivationRequest,
    ActivationResponse,
    CalendarEventMapping,
    ProgramListResponse,
    ProgramStatus,
    ProgramUpdateRequest,
    ProgramWeek,
    TrainingProgram,
    TrainingProgramCreate,
    TrainingProgramUpdate,
    WorkoutCompletedWebhook,
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


def _calculate_workout_date(
    start_date: date,
    week_number: int,
    day_of_week: int,
) -> date:
    """
    Calculate the actual date for a workout based on program start date.

    Args:
        start_date: The program start date
        week_number: Week number in the program (1-indexed)
        day_of_week: Day of week (0=Sunday through 6=Saturday in DB,
                     but we treat it as 0=Monday through 6=Sunday for calculation)

    Returns:
        The calculated date for the workout
    """
    # Calculate days from start:
    # - Week 1, Day 0 (Monday) = start_date + 0 days
    # - Week 1, Day 1 (Tuesday) = start_date + 1 day
    # - Week 2, Day 0 (Monday) = start_date + 7 days
    # etc.
    days_offset = (week_number - 1) * 7 + day_of_week
    return start_date + timedelta(days=days_offset)


@router.post("/{program_id}/activate", response_model=ActivationResponse)
async def activate_program(
    program_id: UUID,
    request: Optional[ActivationRequest] = Body(default=None),
    authorization: Optional[str] = Header(None),
    user_id: str = Depends(get_current_user),
    program_repo: ProgramRepository = Depends(get_program_repo),
    calendar_client: CalendarClient = Depends(get_calendar_client),
) -> ActivationResponse:
    """
    Activate a training program.

    Sets the program status to 'active' and schedules all workouts
    on the user's calendar starting from the specified date.

    The calendar integration (AMA-469) creates events for each workout
    in the program, calculating actual dates from the start date and
    the workout's day_of_week setting.

    Args:
        program_id: The program UUID
        request: Optional activation options (start_date)

    Returns:
        Activation confirmation with scheduling details

    Raises:
        404: Program not found
        403: Access denied
        422: Program cannot be activated (e.g., already active/completed)
        503: Calendar service unavailable
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

    # Convert to date for calendar calculations
    start_date_only = start_date.date() if hasattr(start_date, 'date') else start_date

    # Get weeks with workouts
    weeks = program_repo.get_weeks(str(program_id))

    # Build calendar events for all workouts
    calendar_events: List[ProgramEventData] = []
    for week in weeks:
        week_number = week.get("week_number", 1)
        for workout in week.get("workouts", []):
            workout_date = _calculate_workout_date(
                start_date_only,
                week_number,
                workout.get("day_of_week", 0),
            )

            # Determine workout type for calendar
            workout_type = workout.get("workout_type", "strength")
            # Map program workout types to calendar workout types
            type_mapping = {
                "upper": "strength",
                "lower": "strength",
                "full_body": "strength",
                "push": "strength",
                "pull": "strength",
                "legs": "strength",
                "strength": "strength",
                "cardio": "run",
                "hiit": "strength",
                "mobility": "mobility",
                "recovery": "recovery",
            }
            calendar_type = type_mapping.get(workout_type.lower(), "strength")

            # Determine primary muscle group
            muscle_mapping = {
                "upper": "upper",
                "lower": "lower",
                "full_body": "full_body",
                "push": "upper",
                "pull": "upper",
                "legs": "lower",
            }
            primary_muscle = muscle_mapping.get(workout_type.lower())

            event = ProgramEventData(
                title=workout.get("name", f"Week {week_number} Workout"),
                date=workout_date,
                program_workout_id=UUID(workout["id"]),
                program_week_number=week_number,
                type=calendar_type,
                primary_muscle=primary_muscle,
                intensity=2 if not week.get("is_deload") else 1,
                json_payload={
                    "program_name": program.get("name"),
                    "week_name": week.get("focus", f"Week {week_number}"),
                    "workout_description": workout.get("notes"),
                    "exercises": workout.get("exercises", []),
                    "target_duration_minutes": workout.get("target_duration_minutes"),
                },
            )
            calendar_events.append(event)

    total_workouts = len(calendar_events)
    scheduled_count = 0
    event_mapping: List[CalendarEventMapping] = []

    # Create calendar events if we have any workouts
    if calendar_events and authorization:
        auth_token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization

        try:
            result = await calendar_client.bulk_create_program_events(
                program_id=program_id,
                events=calendar_events,
                auth_token=auth_token,
            )
            scheduled_count = result.events_created

            # Use explicit mapping returned by Calendar-API
            # This ensures correct mapping regardless of processing order
            for workout_id_str, event_id_str in result.event_mapping.items():
                event_mapping.append(
                    CalendarEventMapping(
                        program_workout_id=UUID(workout_id_str),
                        calendar_event_id=UUID(event_id_str),
                    )
                )

            logger.info(
                f"Created {scheduled_count} calendar events for program {program_id}"
            )
        except CalendarAPIUnavailable as e:
            logger.warning(f"Calendar-API unavailable during activation: {e}")
            # Don't fail activation if calendar is unavailable
            # Program will be active but without calendar events
        except CalendarAPIError as e:
            logger.error(f"Calendar-API error during activation: {e}")
            if e.status_code >= 500:
                # Server error - don't fail activation
                pass
            else:
                # Client error - might be auth issue, log but continue
                logger.warning(
                    f"Calendar event creation failed with status {e.status_code}"
                )

    # Build calendar_event_mapping JSON for storage
    calendar_mapping_json = None
    if event_mapping:
        calendar_mapping_json = {
            str(m.program_workout_id): str(m.calendar_event_id)
            for m in event_mapping
        }

    # Update program status and store calendar event mapping
    program_repo.update(
        str(program_id),
        {
            "status": ProgramStatus.ACTIVE.value,
            "start_date": start_date.isoformat(),
            "current_week": 1,
            "calendar_event_mapping": calendar_mapping_json,
        },
    )

    message = f"Program activated successfully. {scheduled_count} workouts scheduled on calendar."
    if scheduled_count < total_workouts:
        message = f"Program activated. {scheduled_count}/{total_workouts} workouts scheduled (some calendar events may have failed)."

    return ActivationResponse(
        program_id=program_id,
        status=ProgramStatus.ACTIVE,
        start_date=start_date,
        scheduled_workouts=scheduled_count,
        calendar_event_mapping=event_mapping if event_mapping else None,
        message=message,
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


# =============================================================================
# Program Webhook Endpoints (AMA-469)
# =============================================================================


@router.post("/{program_id}/workout-completed")
async def workout_completed_webhook(
    program_id: UUID,
    payload: WorkoutCompletedWebhook,
    x_user_id: Optional[str] = Header(None, description="User ID from calling service"),
    authorization: Optional[str] = Header(None),
    service_authenticated: bool = Depends(verify_service_token),
    program_repo: ProgramRepository = Depends(get_program_repo),
):
    """
    Webhook endpoint called when a program workout is marked complete on calendar.

    Called by Calendar-API when a workout event with a program_id is marked
    as completed. Updates the program's progression tracking.

    Requires service-to-service authentication via X-Service-Token header.
    User context is provided via X-User-Id header from the calling service.

    Args:
        program_id: The training program UUID
        payload: Webhook payload with completion details
        x_user_id: User ID passed from Calendar-API
        authorization: Fallback Bearer token for user auth

    Returns:
        Acknowledgment of the completion

    Raises:
        401: Missing or invalid service token
        404: Program not found
    """
    # Extract user_id from X-User-Id header (set by Calendar-API) or Authorization
    user_id = x_user_id
    if not user_id and authorization:
        # Fallback to extracting from Bearer token
        if authorization.startswith("Bearer "):
            user_id = authorization[7:]

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Missing user identification (X-User-Id header or Authorization)",
        )

    logger.info(
        f"Workout completed webhook for program {program_id}, "
        f"workout {payload.program_workout_id}, week {payload.program_week_number}, "
        f"user {user_id}"
    )

    # Verify program exists and user has access
    program = _get_program_or_404(program_id, user_id, program_repo)

    # Check if this completion advances the current week
    current_week = program.get("current_week", 1)
    if payload.program_week_number > current_week:
        # User completed a workout from a future week - update current_week
        program_repo.update(
            str(program_id),
            {"current_week": payload.program_week_number},
        )
        logger.info(
            f"Advanced program {program_id} to week {payload.program_week_number}"
        )

    # TODO: Track individual workout completions in a separate table
    # For now, we just log the completion and update current_week
    # Future enhancement: add workout_completions tracking table

    return {
        "success": True,
        "program_id": str(program_id),
        "workout_id": str(payload.program_workout_id),
        "week_number": payload.program_week_number,
        "message": "Workout completion recorded",
    }
