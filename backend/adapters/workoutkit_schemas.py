"""Pydantic models for Apple WorkoutKit DTO format."""
from typing import Literal, Optional, List, Union
from pydantic import BaseModel


class HRZoneTarget(BaseModel):
    hrZone: int


class PaceTarget(BaseModel):
    pace: float  # meters per second


class WorkoutTarget(BaseModel):
    hrZone: Optional[int] = None
    pace: Optional[float] = None


class TimeStep(BaseModel):
    kind: Literal["time"]
    seconds: int
    target: Optional[str] = None  # Exercise name for display (AMA-243)


class DistanceStep(BaseModel):
    kind: Literal["distance"]
    meters: int
    target: Optional[str] = None  # Exercise name for display (AMA-243)


class Load(BaseModel):
    value: float
    unit: Literal["kg", "lb"]


class RepsStep(BaseModel):
    kind: Literal["reps"]
    reps: int
    name: Optional[str] = None
    load: Optional[Load] = None
    restSec: Optional[int] = None


class RestStep(BaseModel):
    """Rest period between exercises.

    - seconds > 0: Timed rest with countdown
    - seconds = None: Manual rest ("tap when ready")
    """
    kind: Literal["rest"]
    seconds: Optional[int] = None  # None = manual rest


WKStepDTO = Union[TimeStep, DistanceStep, RepsStep, RestStep]


class WarmupInterval(BaseModel):
    kind: Literal["warmup"]
    seconds: int
    target: Optional[WorkoutTarget] = None


class CooldownInterval(BaseModel):
    kind: Literal["cooldown"]
    seconds: int
    target: Optional[WorkoutTarget] = None


class RepeatInterval(BaseModel):
    kind: Literal["repeat"]
    reps: int
    intervals: List[WKStepDTO]


WKIntervalDTO = Union[WarmupInterval, CooldownInterval, RepeatInterval, WKStepDTO]


class Schedule(BaseModel):
    startLocal: Optional[str] = None


class WKPlanDTO(BaseModel):
    title: str
    sportType: Literal["running", "cycling", "strengthTraining"]
    intervals: List[WKIntervalDTO]
    schedule: Optional[Schedule] = None

