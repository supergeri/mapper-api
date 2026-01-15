"""
Block value object for workout structure.

Part of AMA-389: Define canonical Workout domain model
"""

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from domain.models.exercise import Exercise


class BlockType(str, Enum):
    """
    Types of workout blocks that define how exercises are performed.

    - STRAIGHT: Standard sets with rest between (A1, A2, A3...)
    - SUPERSET: Exercises performed back-to-back without rest (A1+A2, rest, repeat)
    - CIRCUIT: Multiple exercises in sequence, repeated as rounds
    - TIMED_ROUND: Exercises performed within a time limit (e.g., EMOM, AMRAP)
    """

    STRAIGHT = "straight"
    SUPERSET = "superset"
    CIRCUIT = "circuit"
    TIMED_ROUND = "timed_round"


class Block(BaseModel):
    """
    Value object representing a block of exercises within a workout.

    A block groups exercises that are performed together in a specific
    structure (straight sets, superset, circuit, etc.).

    Examples:
        >>> # Straight sets block
        >>> block = Block(
        ...     label="Main Lifts",
        ...     type=BlockType.STRAIGHT,
        ...     exercises=[
        ...         Exercise(name="Squat", sets=5, reps=5),
        ...         Exercise(name="Bench Press", sets=5, reps=5),
        ...     ]
        ... )

        >>> # Superset block
        >>> block = Block(
        ...     label="Accessory Superset",
        ...     type=BlockType.SUPERSET,
        ...     rounds=3,
        ...     exercises=[
        ...         Exercise(name="Bicep Curl", reps=12),
        ...         Exercise(name="Tricep Pushdown", reps=12),
        ...     ],
        ...     rest_between_seconds=60
        ... )

        >>> # Circuit block
        >>> block = Block(
        ...     label="Conditioning Circuit",
        ...     type=BlockType.CIRCUIT,
        ...     rounds=4,
        ...     exercises=[
        ...         Exercise(name="Burpees", reps=10),
        ...         Exercise(name="Mountain Climbers", duration_seconds=30),
        ...         Exercise(name="Jump Squats", reps=15),
        ...     ],
        ...     rest_between_seconds=90
        ... )
    """

    label: Optional[str] = Field(
        default=None, description="Block label (e.g., 'Warm-up', 'Main Lifts', 'Finisher')"
    )
    type: BlockType = Field(
        default=BlockType.STRAIGHT,
        description="Block structure type determining how exercises are performed",
    )
    rounds: int = Field(
        default=1,
        ge=1,
        description="Number of rounds/cycles through the exercises (for supersets, circuits)",
    )
    exercises: List[Exercise] = Field(
        ..., min_length=1, description="List of exercises in this block"
    )
    rest_between_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        description="Rest period between rounds/supersets in seconds",
    )

    @field_validator("exercises")
    @classmethod
    def validate_exercises(cls, v: List[Exercise]) -> List[Exercise]:
        """Ensure at least one exercise is present."""
        if not v:
            raise ValueError("Block must contain at least one exercise")
        return v

    @property
    def exercise_count(self) -> int:
        """
        Get the number of unique exercises in this block.

        Returns:
            Number of exercises in the block.
        """
        return len(self.exercises)

    @property
    def total_sets(self) -> int:
        """
        Calculate total sets across all exercises and rounds.

        For straight sets, sums individual exercise sets.
        For supersets/circuits, multiplies by rounds.

        Returns:
            Total number of sets in the block.
        """
        if self.type == BlockType.STRAIGHT:
            # Each exercise has its own sets
            return sum(ex.sets or 1 for ex in self.exercises)
        else:
            # Supersets/circuits: exercises done together, repeated for rounds
            return self.rounds * len(self.exercises)

    @property
    def exercise_names(self) -> List[str]:
        """
        Get list of exercise names in this block.

        Returns:
            List of exercise names in order.
        """
        return [ex.name for ex in self.exercises]

    @property
    def is_superset(self) -> bool:
        """Check if this block is a superset."""
        return self.type == BlockType.SUPERSET

    @property
    def is_circuit(self) -> bool:
        """Check if this block is a circuit."""
        return self.type == BlockType.CIRCUIT

    @property
    def is_timed(self) -> bool:
        """Check if this block is a timed round (EMOM, AMRAP, etc.)."""
        return self.type == BlockType.TIMED_ROUND

    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = []
        if self.label:
            parts.append(self.label)

        if self.type != BlockType.STRAIGHT:
            parts.append(f"({self.type.value})")

        if self.rounds > 1:
            parts.append(f"x{self.rounds} rounds")

        exercise_str = ", ".join(ex.name for ex in self.exercises[:3])
        if len(self.exercises) > 3:
            exercise_str += f" (+{len(self.exercises) - 3} more)"
        parts.append(f"[{exercise_str}]")

        return " ".join(parts)

    model_config = {
        "frozen": True,  # Make immutable (value object semantics)
        "json_schema_extra": {
            "examples": [
                {
                    "label": "Main Lifts",
                    "type": "straight",
                    "exercises": [
                        {"name": "Squat", "sets": 5, "reps": 5},
                        {"name": "Bench Press", "sets": 5, "reps": 5},
                    ],
                },
                {
                    "label": "Superset A",
                    "type": "superset",
                    "rounds": 3,
                    "exercises": [
                        {"name": "Bicep Curl", "reps": 12},
                        {"name": "Tricep Extension", "reps": 12},
                    ],
                    "rest_between_seconds": 60,
                },
            ]
        },
    }
