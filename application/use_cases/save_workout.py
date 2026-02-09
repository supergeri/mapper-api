"""
SaveWorkout Use Case.

Part of AMA-393: Create SaveWorkout use case
Phase 3 - Canonical Model + Use Cases

Orchestrates workout persistence with validation, handling both
create (new workout) and update (existing workout) operations.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from application.ports import WorkoutRepository
from domain.converters.db_converters import _workout_to_blocks_format
from domain.models import Workout

logger = logging.getLogger(__name__)


class WorkoutValidationError(Exception):
    """Raised when workout validation fails."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


@dataclass
class SaveWorkoutResult:
    """Result of the SaveWorkout use case execution."""

    success: bool
    workout: Optional[Workout] = None
    workout_id: Optional[str] = None
    is_update: bool = False
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)


class SaveWorkoutUseCase:
    """
    Use case for saving workouts with validation.

    Orchestrates the following workflow:
    1. Validate workout completeness
    2. Determine create vs update based on workout ID
    3. Convert domain model to repository format
    4. Persist via repository
    5. Return saved workout with generated ID

    Dependencies are injected via constructor for testability.

    Usage:
        >>> use_case = SaveWorkoutUseCase(workout_repo=workout_repo)
        >>> result = use_case.execute(
        ...     workout=workout,
        ...     user_id="user-123",
        ...     device="garmin",
        ... )
        >>> if result.success:
        ...     print(f"Saved workout: {result.workout_id}")
    """

    def __init__(
        self,
        workout_repo: WorkoutRepository,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            workout_repo: Repository for persisting workouts
        """
        self._workout_repo = workout_repo

    def execute(
        self,
        workout: Workout,
        user_id: str,
        device: str,
        *,
        validate: bool = True,
    ) -> SaveWorkoutResult:
        """
        Execute the save workout workflow.

        Args:
            workout: Domain Workout model to save
            user_id: User profile ID for authorization
            device: Target device type (garmin, apple, ios_companion)
            validate: Whether to perform business validation (default True)

        Returns:
            SaveWorkoutResult with success status and saved workout
        """
        try:
            # Defense-in-depth: always reject workouts with 0 exercises,
            # even when validate=False (AMA-561)
            if workout.total_exercises == 0:
                logger.warning(
                    "Rejecting empty workout '%s': 0 exercises across %d blocks",
                    workout.title,
                    len(workout.blocks),
                )
                return SaveWorkoutResult(
                    success=False,
                    error="Workout must contain at least one exercise",
                    validation_errors=["Workout has 0 exercises"],
                )

            # Step 1: Validate workout if requested
            if validate:
                validation_errors = self._validate_workout(workout)
                if validation_errors:
                    logger.warning(f"Workout validation failed: {validation_errors}")
                    return SaveWorkoutResult(
                        success=False,
                        error="Workout validation failed",
                        validation_errors=validation_errors,
                    )

            # Step 2: Determine create vs update
            is_update = workout.id is not None
            operation = "update" if is_update else "create"
            logger.info(f"Saving workout ({operation}): {workout.title}")

            # Step 3: Convert domain model to repository format
            workout_data = _workout_to_blocks_format(workout)
            sources = [src.value for src in workout.metadata.sources]

            # Step 4: Persist via repository
            saved = self._workout_repo.save(
                profile_id=user_id,
                workout_data=workout_data,
                sources=sources,
                device=device,
                title=workout.title,
                description=workout.description,
                workout_id=workout.id,
            )

            if not saved:
                logger.error("Repository save returned None")
                return SaveWorkoutResult(
                    success=False,
                    error="Failed to save workout",
                    is_update=is_update,
                )

            # Step 5: Build result with updated workout
            saved_id = saved.get("id")
            saved_workout = workout.with_id(saved_id) if not workout.id else workout

            logger.info(f"Workout saved successfully: {saved_id}")
            return SaveWorkoutResult(
                success=True,
                workout=saved_workout,
                workout_id=saved_id,
                is_update=is_update,
            )

        except WorkoutValidationError as e:
            logger.warning(f"Workout validation error: {e}")
            return SaveWorkoutResult(
                success=False,
                error=e.message,
                validation_errors=e.errors,
            )

        except Exception as e:
            logger.exception(f"SaveWorkout use case failed: {e}")
            return SaveWorkoutResult(
                success=False,
                error=str(e),
            )

    def _validate_workout(self, workout: Workout) -> List[str]:
        """
        Validate workout business rules.

        Pydantic handles structural validation (types, required fields).
        This method handles business validation rules.

        Args:
            workout: Workout to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors: List[str] = []

        # Title validation
        if not workout.title or not workout.title.strip():
            errors.append("Workout title is required")

        # Blocks validation
        if not workout.blocks:
            errors.append("Workout must have at least one block")

        # Check for empty blocks
        for i, block in enumerate(workout.blocks):
            if not block.exercises:
                errors.append(f"Block {i + 1} has no exercises")

        # Check for exercises without names
        for block in workout.blocks:
            for ex in block.exercises:
                if not ex.name or not ex.name.strip():
                    errors.append("All exercises must have a name")
                    break

        # Total exercises check
        if workout.total_exercises == 0:
            errors.append("Workout must contain at least one exercise")

        return errors

    def execute_create(
        self,
        workout: Workout,
        user_id: str,
        device: str,
    ) -> SaveWorkoutResult:
        """
        Convenience method for creating a new workout.

        Ensures the workout is treated as new (clears any existing ID).

        Args:
            workout: Workout to create (ID will be ignored)
            user_id: User profile ID
            device: Target device type

        Returns:
            SaveWorkoutResult with new workout ID
        """
        # Ensure no ID for create operation
        new_workout = workout.model_copy(update={"id": None})
        return self.execute(new_workout, user_id, device)

    def execute_update(
        self,
        workout: Workout,
        user_id: str,
        device: str,
    ) -> SaveWorkoutResult:
        """
        Convenience method for updating an existing workout.

        Ensures the workout has an ID.

        Args:
            workout: Workout to update (must have ID)
            user_id: User profile ID
            device: Target device type

        Returns:
            SaveWorkoutResult with updated workout

        Raises:
            ValueError: If workout has no ID
        """
        if not workout.id:
            return SaveWorkoutResult(
                success=False,
                error="Cannot update workout without ID",
            )
        return self.execute(workout, user_id, device)
