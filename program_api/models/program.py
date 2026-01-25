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

    name: str
    description: Optional[str] = None
    goal: ProgramGoal
    experience_level: ExperienceLevel
    duration_weeks: int = Field(ge=1, le=52)
    sessions_per_week: int = Field(ge=1, le=7)
    equipment_available: List[str] = []


class TrainingProgramUpdate(BaseModel):
    """Request model for updating a training program."""

    name: Optional[str] = None
    description: Optional[str] = None
    goal: Optional[ProgramGoal] = None
    experience_level: Optional[ExperienceLevel] = None
    duration_weeks: Optional[int] = Field(None, ge=1, le=52)
    sessions_per_week: Optional[int] = Field(None, ge=1, le=7)
    status: Optional[ProgramStatus] = None
    equipment_available: Optional[List[str]] = None
