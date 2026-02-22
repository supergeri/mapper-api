from pydantic import BaseModel

from typing import List, Optional, Literal, Union



BlockType = Literal["straight", "superset", "circuit", "timed_round"]



class Load(BaseModel):

    value: float

    unit: Literal["lb","kg"]

    per_side: bool = False



class Exercise(BaseModel):

    kind: Literal["exercise"] = "exercise"

    name: str

    canonical_name: Optional[str] = None

    equipment: List[str] = []

    modifiers: List[str] = []

    tempo: Optional[str] = None

    side: Optional[Literal["left","right","bilateral"]] = None

    sets: Optional[int] = None

    reps: Optional[Union[int,str]] = None

    duration_seconds: Optional[int] = None

    load: Optional[Load] = None

    rest_seconds: Optional[int] = None

    distance: Optional[float] = None

    distance_unit: Optional[Literal["miles", "km", "m", "yards", "feet"]] = None

    notes: Optional[str] = None



class Block(BaseModel):

    type: BlockType = "straight"

    rounds: int = 1

    time_cap_sec: Optional[int] = None

    items: List[Exercise]



class Workout(BaseModel):

    title: str

    notes: Optional[str] = None

    tags: List[str] = []

    blocks: List[Block]



class CIR(BaseModel):

    workout: Workout
