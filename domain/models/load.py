"""
Load value object for exercise weight/resistance.

Part of AMA-389: Define canonical Workout domain model
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


# Conversion constant
LB_TO_KG = 0.45359237
KG_TO_LB = 2.20462262


class Load(BaseModel):
    """
    Value object representing weight/resistance for an exercise.

    Supports both pounds (lb) and kilograms (kg) with conversion methods.
    The `per_side` flag indicates if the load is per arm/leg (e.g., dumbbell
    exercises) or total (e.g., barbell exercises).

    Examples:
        >>> load = Load(value=135, unit="lb")
        >>> load.to_kg()
        61.24

        >>> load = Load(value=20, unit="kg", per_side=True)
        >>> load.total_load_kg()
        40.0
    """

    value: float = Field(..., gt=0, description="Weight/resistance value")
    unit: Literal["lb", "kg"] = Field(..., description="Unit of measurement")
    per_side: bool = Field(
        default=False,
        description="True if load is per arm/leg (e.g., dumbbells), False for total load",
    )

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: float) -> float:
        """Ensure value is positive and reasonable."""
        if v <= 0:
            raise ValueError("Load value must be positive")
        if v > 2000:
            raise ValueError("Load value exceeds reasonable maximum (2000)")
        return round(v, 2)

    def to_kg(self) -> float:
        """
        Convert load to kilograms.

        Returns:
            Load value in kilograms, rounded to 2 decimal places.
        """
        if self.unit == "kg":
            return self.value
        return round(self.value * LB_TO_KG, 2)

    def to_lb(self) -> float:
        """
        Convert load to pounds.

        Returns:
            Load value in pounds, rounded to 2 decimal places.
        """
        if self.unit == "lb":
            return self.value
        return round(self.value * KG_TO_LB, 2)

    def total_load_kg(self) -> float:
        """
        Get total load in kg, accounting for per_side.

        For per_side loads (e.g., dumbbells), returns double the value.

        Returns:
            Total load in kilograms.
        """
        base = self.to_kg()
        return base * 2 if self.per_side else base

    def total_load_lb(self) -> float:
        """
        Get total load in lb, accounting for per_side.

        For per_side loads (e.g., dumbbells), returns double the value.

        Returns:
            Total load in pounds.
        """
        base = self.to_lb()
        return base * 2 if self.per_side else base

    def __str__(self) -> str:
        """Human-readable string representation."""
        side_note = " per side" if self.per_side else ""
        return f"{self.value} {self.unit}{side_note}"

    model_config = {
        "frozen": True,  # Make immutable (value object semantics)
        "json_schema_extra": {
            "examples": [
                {"value": 135, "unit": "lb", "per_side": False},
                {"value": 20, "unit": "kg", "per_side": True},
            ]
        },
    }
