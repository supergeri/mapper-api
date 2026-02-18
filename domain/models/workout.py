"""
Workout aggregate root - the main domain entity.

Part of AMA-389: Define canonical Workout domain model
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from domain.models.block import Block
from domain.models.metadata import WorkoutMetadata


class WorkoutSettings(BaseModel):
    """
    Settings/options for a workout.

    Contains configuration options that affect how the workout
    should be performed or displayed.
    """

    rest_timer_enabled: bool = Field(
        default=True,
        description="Whether rest timer prompts are enabled",
    )
    auto_start_next_exercise: bool = Field(
        default=False,
        description="Whether to auto-start next exercise after rest period",
    )
    countdown_seconds: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Countdown seconds before starting each exercise (0-10)",
    )
    show_weights: bool = Field(
        default=True,
        description="Whether to show weight/load values during workout",
    )
    hide_rest_days: bool = Field(
        default=False,
        description="Whether to hide rest days in the workout",
    )


class Workout(BaseModel):
    """
    Aggregate root representing a complete workout.

    A Workout is the primary domain entity and contains:
    - Identity (id, title)
    - Structure (blocks containing exercises)
    - Metadata (source, platform, timestamps)
    - Usage tracking (favorites, completion count)

    Unlike value objects (Load, Exercise, Block), Workout has identity
    and can be mutated through domain methods.

    Examples:
        >>> from domain.models import Workout, Block, Exercise, WorkoutMetadata

        >>> workout = Workout(
        ...     title="Full Body Strength",
        ...     blocks=[
        ...         Block(
        ...             label="Main Lifts",
        ...             exercises=[
        ...                 Exercise(name="Squat", sets=5, reps=5),
        ...                 Exercise(name="Bench Press", sets=5, reps=5),
        ...                 Exercise(name="Deadlift", sets=3, reps=5),
        ...             ]
        ...         )
        ...     ],
        ...     tags=["strength", "full-body"]
        ... )

        >>> # Serialize to JSON
        >>> json_str = workout.model_dump_json()

        >>> # Deserialize from JSON
        >>> workout = Workout.model_validate_json(json_str)
    """

    # Identity
    id: Optional[str] = Field(
        default=None,
        description="Unique identifier (UUID). None for new, unsaved workouts.",
    )
    title: str = Field(
        ..., min_length=1, max_length=200, description="Workout title/name"
    )

    # Description and notes
    description: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Detailed description of the workout",
    )
    notes: Optional[str] = Field(
        default=None, max_length=2000, description="Additional notes or instructions"
    )

    # Organization
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorization and filtering"
    )

    # Structure
    blocks: List[Block] = Field(
        ..., min_length=1, description="Workout blocks containing exercises"
    )

    # Metadata
    metadata: WorkoutMetadata = Field(
        default_factory=WorkoutMetadata,
        description="Provenance, platform, and tracking metadata",
    )

    # Settings
    settings: WorkoutSettings = Field(
        default_factory=WorkoutSettings,
        description="Workout settings and preferences",
    )

    # Usage tracking
    is_favorite: bool = Field(default=False, description="Whether workout is favorited")
    times_completed: int = Field(
        default=0, ge=0, description="Number of times this workout was completed"
    )
    last_used_at: Optional[datetime] = Field(
        default=None, description="When the workout was last used/completed"
    )

    @field_validator("blocks")
    @classmethod
    def validate_blocks(cls, v: List[Block]) -> List[Block]:
        """Ensure at least one block is present."""
        if not v:
            raise ValueError("Workout must contain at least one block")
        return v

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Normalize and deduplicate tags."""
        # Lowercase and strip whitespace
        normalized = [tag.lower().strip() for tag in v if tag.strip()]
        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for tag in normalized:
            if tag not in seen:
                seen.add(tag)
                unique.append(tag)
        return unique

    # -------------------------------------------------------------------------
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def total_exercises(self) -> int:
        """
        Get total number of exercises across all blocks.

        Returns:
            Total exercise count.
        """
        return sum(block.exercise_count for block in self.blocks)

    @property
    def total_sets(self) -> int:
        """
        Get total number of sets across all blocks.

        Returns:
            Total set count.
        """
        return sum(block.total_sets for block in self.blocks)

    @property
    def exercise_names(self) -> List[str]:
        """
        Get flat list of all exercise names in order.

        Returns:
            List of exercise names.
        """
        names = []
        for block in self.blocks:
            names.extend(block.exercise_names)
        return names

    @property
    def unique_exercise_names(self) -> List[str]:
        """
        Get deduplicated list of exercise names.

        Returns:
            Unique exercise names in order of first appearance.
        """
        seen = set()
        unique = []
        for name in self.exercise_names:
            if name not in seen:
                seen.add(name)
                unique.append(name)
        return unique

    @property
    def block_count(self) -> int:
        """Get number of blocks in the workout."""
        return len(self.blocks)

    @property
    def is_new(self) -> bool:
        """Check if this workout has not been saved yet."""
        return self.id is None

    @property
    def has_been_used(self) -> bool:
        """Check if this workout has been completed at least once."""
        return self.times_completed > 0

    # -------------------------------------------------------------------------
    # Domain Methods (return new instances for immutability)
    # -------------------------------------------------------------------------

    def with_id(self, workout_id: str) -> "Workout":
        """
        Return a new Workout with the given ID set.

        Args:
            workout_id: The ID to assign.

        Returns:
            New Workout instance with the ID set.
        """
        return self.model_copy(update={"id": workout_id})

    def mark_exported(self, device: str) -> "Workout":
        """
        Return a new Workout marked as exported.

        Args:
            device: Device identifier exported to.

        Returns:
            New Workout with updated metadata.
        """
        new_metadata = self.metadata.model_copy(
            update={
                "is_exported": True,
                "exported_at": datetime.utcnow(),
                "exported_to_device": device,
            }
        )
        return self.model_copy(update={"metadata": new_metadata})

    def toggle_favorite(self) -> "Workout":
        """
        Return a new Workout with favorite status toggled.

        Returns:
            New Workout with is_favorite flipped.
        """
        return self.model_copy(update={"is_favorite": not self.is_favorite})

    def record_completion(self) -> "Workout":
        """
        Return a new Workout with completion recorded.

        Increments times_completed and updates last_used_at.

        Returns:
            New Workout with updated usage stats.
        """
        return self.model_copy(
            update={
                "times_completed": self.times_completed + 1,
                "last_used_at": datetime.utcnow(),
            }
        )

    def with_tags(self, tags: List[str]) -> "Workout":
        """
        Return a new Workout with updated tags.

        Args:
            tags: New list of tags.

        Returns:
            New Workout with updated tags.
        """
        return self.model_copy(update={"tags": tags})

    def add_tag(self, tag: str) -> "Workout":
        """
        Return a new Workout with an additional tag.

        Args:
            tag: Tag to add.

        Returns:
            New Workout with tag added (if not already present).
        """
        normalized = tag.lower().strip()
        if normalized and normalized not in self.tags:
            return self.model_copy(update={"tags": [*self.tags, normalized]})
        return self

    def remove_tag(self, tag: str) -> "Workout":
        """
        Return a new Workout with tag removed.

        Args:
            tag: Tag to remove.

        Returns:
            New Workout with tag removed.
        """
        normalized = tag.lower().strip()
        new_tags = [t for t in self.tags if t != normalized]
        return self.model_copy(update={"tags": new_tags})

    def __str__(self) -> str:
        """Human-readable string representation."""
        parts = [f'"{self.title}"']
        parts.append(f"{self.total_exercises} exercises")
        parts.append(f"{self.total_sets} sets")

        if self.is_favorite:
            parts.append("[favorite]")

        if self.times_completed > 0:
            parts.append(f"(completed {self.times_completed}x)")

        return f"Workout({', '.join(parts)})"

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "title": "Full Body Strength",
                    "description": "A complete full body workout",
                    "tags": ["strength", "full-body"],
                    "blocks": [
                        {
                            "label": "Main Lifts",
                            "type": "straight",
                            "exercises": [
                                {"name": "Squat", "sets": 5, "reps": 5},
                                {"name": "Bench Press", "sets": 5, "reps": 5},
                                {"name": "Deadlift", "sets": 3, "reps": 5},
                            ],
                        }
                    ],
                    "metadata": {
                        "sources": ["ai"],
                        "platform": "ios_companion",
                    },
                    "is_favorite": True,
                    "times_completed": 5,
                }
            ]
        },
    }
