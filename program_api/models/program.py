"""
Domain models for training programs.

Part of AMA-461: Create program-api service scaffold

These models correspond to the database schema defined in AMA-460.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ProgramGoal(str, Enum):
    """Training program goals."""

    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"
    ENDURANCE = "endurance"
    WEIGHT_LOSS = "weight_loss"
    GENERAL_FITNESS = "general_fitness"
    SPORT_SPECIFIC = "sport_specific"


class ExperienceLevel(str, Enum):
    """User experience levels."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    ELITE = "elite"


class ProgramStatus(str, Enum):
    """Training program status."""

    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProgramWorkout(BaseModel):
    """A single workout within a program week."""

    id: UUID
    program_week_id: UUID
    day_of_week: int = Field(ge=1, le=7, description="1=Monday, 7=Sunday")
    name: str
    description: Optional[str] = None
    workout_id: Optional[UUID] = Field(
        None, description="Reference to saved workout template"
    )
    order_index: int = Field(ge=0)
    created_at: datetime
    updated_at: datetime


class ProgramWeek(BaseModel):
    """A week within a training program."""

    id: UUID
    program_id: UUID
    week_number: int = Field(ge=1)
    name: str
    description: Optional[str] = None
    deload: bool = False
    workouts: List[ProgramWorkout] = []
    created_at: datetime
    updated_at: datetime


class TrainingProgram(BaseModel):
    """A complete training program."""

    id: UUID
    user_id: str
    name: str
    description: Optional[str] = None
    goal: ProgramGoal
    experience_level: ExperienceLevel
    duration_weeks: int = Field(ge=1, le=52)
    sessions_per_week: int = Field(ge=1, le=7)
    status: ProgramStatus = ProgramStatus.DRAFT
    equipment_available: List[str] = []
    weeks: List[ProgramWeek] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingProgramCreate(BaseModel):
    """Request model for creating a training program."""

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    goal: ProgramGoal
    experience_level: ExperienceLevel
    duration_weeks: int = Field(ge=1, le=52)
    sessions_per_week: int = Field(ge=1, le=7)
    equipment_available: List[str] = []


class TrainingProgramUpdate(BaseModel):
    """Request model for updating a training program."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    goal: Optional[ProgramGoal] = None
    experience_level: Optional[ExperienceLevel] = None
    duration_weeks: Optional[int] = Field(None, ge=1, le=52)
    sessions_per_week: Optional[int] = Field(None, ge=1, le=7)
    status: Optional[ProgramStatus] = None
    equipment_available: Optional[List[str]] = None


class ProgramUpdateRequest(BaseModel):
    """
    Request model for PATCH updates to a program.

    Part of AMA-464: Program API endpoints.
    Supports partial updates to status, name, and current week tracking.
    """

    status: Optional[ProgramStatus] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    current_week: Optional[int] = Field(None, ge=1)


class ActivationRequest(BaseModel):
    """Request model for activating a program."""

    start_date: Optional[datetime] = Field(
        None, description="When to start the program. Defaults to today."
    )


class ActivationResponse(BaseModel):
    """Response model for program activation."""

    program_id: UUID
    status: ProgramStatus
    start_date: datetime
    scheduled_workouts: int = Field(
        description="Number of workouts scheduled on calendar"
    )
    message: str


class ProgramListResponse(BaseModel):
    """Response model for paginated program listing."""

    programs: List[TrainingProgram]
    total: int
    limit: int
    offset: int
    has_more: bool
