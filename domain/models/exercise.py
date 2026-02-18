"""
Exercise value object for workout exercises.

Part of AMA-389: Define canonical Workout domain model
"""

from typing import List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

from domain.models.load import Load


class Exercise(BaseModel):
    """
    Value object representing an exercise within a workout.

    An exercise can be prescribed by:
    - Reps (e.g., "10 reps", "3+1 reps", "AMRAP")
    - Duration (e.g., "60 seconds")
    - Both (rare, but possible for timed rep targets)

    The `reps` field is a Union[int, str] to preserve complex rep schemes
    like "3+1" (3 regular + 1 pause rep), "AMRAP" (as many reps as possible),
    or "8-12" (rep range).

    Examples:
        >>> exercise = Exercise(name="Bench Press", sets=4, reps=8)
        >>> exercise.is_rep_based
        True

        >>> exercise = Exercise(name="Plank", duration_seconds=60)
        >>> exercise.is_timed
        True

        >>> exercise = Exercise(
        ...     name="Squat",
        ...     sets=5,
        ...     reps=5,
        ...     load=Load(value=225, unit="lb")
        ... )
    """

    # Identity
    name: str = Field(..., min_length=1, description="Exercise name (display/raw)")
    canonical_name: Optional[str] = Field(
        default=None, description="Mapped Garmin exercise name"
    )

    # Equipment and modifiers
    equipment: List[str] = Field(
        default_factory=list,
        description="Equipment used (e.g., 'barbell', 'dumbbell', 'cable')",
    )
    modifiers: List[str] = Field(
        default_factory=list,
        description="Exercise modifiers (e.g., 'incline', 'pause', 'tempo')",
    )

    # Movement details
    tempo: Optional[str] = Field(
        default=None,
        description="Tempo notation (e.g., '3010' = 3s eccentric, 0s pause, 1s concentric, 0s top)",
    )
    side: Optional[Literal["left", "right", "bilateral"]] = Field(
        default=None, description="Side specification for unilateral exercises"
    )

    # Work prescription
    sets: Optional[int] = Field(default=None, ge=1, description="Number of sets")
    reps: Optional[Union[int, str]] = Field(
        default=None,
        description="Reps per set (int or string for complex schemes like '3+1', 'AMRAP')",
    )
    duration_seconds: Optional[int] = Field(
        default=None, ge=1, description="Duration in seconds for timed exercises"
    )

    # Load and rest
    load: Optional[Load] = Field(default=None, description="Weight/resistance")
    rest_seconds: Optional[int] = Field(
        default=None, ge=0, description="Rest period after exercise in seconds"
    )

    # Distance (for cardio exercises)
    distance: Optional[float] = Field(
        default=None, ge=0, description="Distance value (e.g., 5.0 for 5 miles/km)"
    )
    distance_unit: Optional[Literal["miles", "km", "meters", "yards", "feet"]] = Field(
        default=None,
        description="Distance unit (e.g., 'miles', 'km', 'meters', 'yards')",
    )

    # Notes
    notes: Optional[str] = Field(
        default=None, description="Additional instructions or notes"
    )

    @model_validator(mode="after")
    def validate_prescription(self) -> "Exercise":
        """Ensure at least reps or duration is specified for meaningful exercises."""
        # Allow exercises with just a name (for planning purposes)
        # Validation only warns if exercise has sets but no prescription
        if self.sets is not None and self.reps is None and self.duration_seconds is None:
            # This is valid but unusual - exercise with sets but no rep/duration target
            pass
        return self

    @property
    def is_timed(self) -> bool:
        """
        Check if this is a time-based exercise.

        Returns:
            True if duration_seconds is set, False otherwise.
        """
        return self.duration_seconds is not None

    @property
    def is_rep_based(self) -> bool:
        """
        Check if this is a rep-based exercise.

        Returns:
            True if reps is set, False otherwise.
        """
        return self.reps is not None

    @property
    def has_load(self) -> bool:
        """
        Check if this exercise has a load prescribed.

        Returns:
            True if load is set, False otherwise.
        """
        return self.load is not None

    @property
    def has_distance(self) -> bool:
        """
        Check if this exercise has a distance prescribed.

        Returns:
            True if distance is set, False otherwise.
        """
        return self.distance is not None

    @property
    def total_reps(self) -> Optional[int]:
        """
        Calculate total reps across all sets.

        Returns:
            Total reps if both sets and reps are integers, None otherwise.
            Returns None for complex rep schemes like "3+1" or "AMRAP".
        """
        if self.sets is None or self.reps is None:
            return None
        if isinstance(self.reps, int):
            return self.sets * self.reps
        return None  # Complex rep scheme

    @property
    def total_duration_seconds(self) -> Optional[int]:
        """
        Calculate total duration across all sets.

        Returns:
            Total duration in seconds if both sets and duration are set,
            None otherwise.
        """
        if self.sets is None or self.duration_seconds is None:
            return None
        return self.sets * self.duration_seconds

    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [self.name]

        if self.sets and self.reps:
            parts.append(f"{self.sets}x{self.reps}")
        elif self.sets and self.duration_seconds:
            parts.append(f"{self.sets}x{self.duration_seconds}s")
        elif self.reps:
            parts.append(f"{self.reps} reps")
        elif self.duration_seconds:
            parts.append(f"{self.duration_seconds}s")

        if self.load:
            parts.append(f"@ {self.load}")

        return " ".join(parts)

    model_config = {
        "frozen": True,  # Make immutable (value object semantics)
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Bench Press",
                    "sets": 4,
                    "reps": 8,
                    "load": {"value": 135, "unit": "lb"},
                    "rest_seconds": 90,
                },
                {
                    "name": "Plank",
                    "sets": 3,
                    "duration_seconds": 60,
                    "rest_seconds": 30,
                },
                {
                    "name": "Pause Squat",
                    "sets": 5,
                    "reps": "3+1",
                    "load": {"value": 100, "unit": "kg"},
                    "tempo": "3110",
                },
            ]
        },
    }
