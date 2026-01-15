"""
MapWorkout Use Case.

Part of AMA-391: Create MapWorkout use case
Phase 3 - Canonical Model + Use Cases

Orchestrates the complete workflow for mapping workout content from a transcript
to a canonical Workout domain model with exercise matching.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from application.ports import (
    ExerciseMatchRepository,
    UserMappingRepository,
    WorkoutRepository,
)
from backend.parsers.models import ParsedWorkout
from domain.converters.ingest_to_workout import ingest_to_workout
from domain.models import Block, Exercise, Workout

logger = logging.getLogger(__name__)


@dataclass
class MapWorkoutResult:
    """Result of the MapWorkout use case execution."""

    success: bool
    workout: Optional[Workout] = None
    workout_id: Optional[str] = None
    error: Optional[str] = None
    exercises_mapped: int = 0
    exercises_unmapped: int = 0


class MapWorkoutUseCase:
    """
    Use case for mapping workout content to canonical format.

    Orchestrates the following workflow:
    1. Convert ParsedWorkout to canonical Workout domain model
    2. Map exercise names to canonical (Garmin) names
    3. Save the workout to persistent storage
    4. Return the canonical Workout

    Dependencies are injected via constructor for testability.

    Usage:
        >>> use_case = MapWorkoutUseCase(
        ...     exercise_match_repo=exercise_match_repo,
        ...     user_mapping_repo=user_mapping_repo,
        ...     workout_repo=workout_repo,
        ... )
        >>> result = use_case.execute(
        ...     parsed_workout=parsed,
        ...     user_id="user-123",
        ...     device="garmin",
        ... )
        >>> if result.success:
        ...     print(f"Saved workout: {result.workout_id}")
    """

    def __init__(
        self,
        exercise_match_repo: ExerciseMatchRepository,
        user_mapping_repo: UserMappingRepository,
        workout_repo: WorkoutRepository,
    ) -> None:
        """
        Initialize the use case with required dependencies.

        Args:
            exercise_match_repo: Repository for fuzzy matching exercise names
            user_mapping_repo: Repository for user-defined exercise mappings
            workout_repo: Repository for persisting workouts
        """
        self._exercise_match_repo = exercise_match_repo
        self._user_mapping_repo = user_mapping_repo
        self._workout_repo = workout_repo

    def execute(
        self,
        parsed_workout: ParsedWorkout,
        user_id: str,
        device: str,
        *,
        save: bool = True,
    ) -> MapWorkoutResult:
        """
        Execute the workout mapping workflow.

        Args:
            parsed_workout: Parsed workout from text/file parsing
            user_id: User profile ID for authorization and mappings
            device: Target device type (garmin, apple, ios_companion)
            save: Whether to save to repository (default True)

        Returns:
            MapWorkoutResult with success status, workout, and stats
        """
        try:
            # Step 1: Convert ParsedWorkout to domain Workout
            logger.info(f"Converting parsed workout: {parsed_workout.name}")
            workout = ingest_to_workout(parsed_workout)

            # Step 2: Map exercises to canonical names
            logger.debug(f"Mapping exercises for workout: {workout.title}")
            mapped_workout, mapped_count, unmapped_count = self._map_exercises(workout)

            logger.info(
                f"Exercise mapping complete: {mapped_count} mapped, "
                f"{unmapped_count} unmapped"
            )

            # Step 3: Save to repository if requested
            workout_id = None
            if save:
                logger.debug(f"Saving workout to repository for user: {user_id}")
                saved = self._workout_repo.save(
                    profile_id=user_id,
                    workout_data=mapped_workout.model_dump(),
                    sources=[s.value for s in mapped_workout.metadata.sources],
                    device=device,
                    title=mapped_workout.title,
                    description=mapped_workout.description,
                )

                if saved:
                    workout_id = saved.get("id")
                    logger.info(f"Workout saved with ID: {workout_id}")
                else:
                    logger.warning("Workout save returned None")

            return MapWorkoutResult(
                success=True,
                workout=mapped_workout,
                workout_id=workout_id,
                exercises_mapped=mapped_count,
                exercises_unmapped=unmapped_count,
            )

        except Exception as e:
            logger.exception(f"MapWorkout use case failed: {e}")
            return MapWorkoutResult(
                success=False,
                error=str(e),
            )

    def _map_exercises(self, workout: Workout) -> tuple[Workout, int, int]:
        """
        Map all exercises in the workout to canonical names.

        First checks user-defined mappings, then falls back to fuzzy matching.

        Args:
            workout: Workout with exercises to map

        Returns:
            Tuple of (updated_workout, mapped_count, unmapped_count)
        """
        mapped_count = 0
        unmapped_count = 0

        # Build new blocks with mapped exercises
        mapped_blocks: list[Block] = []

        for block in workout.blocks:
            mapped_exercises: list[Exercise] = []

            for exercise in block.exercises:
                canonical_name = self._resolve_exercise_name(exercise.name)

                if canonical_name:
                    # Create new exercise with canonical_name set
                    mapped_exercise = Exercise(
                        name=exercise.name,
                        canonical_name=canonical_name,
                        sets=exercise.sets,
                        reps=exercise.reps,
                        duration_seconds=exercise.duration_seconds,
                        load=exercise.load,
                        rest_seconds=exercise.rest_seconds,
                        equipment=exercise.equipment,
                        modifiers=exercise.modifiers,
                        tempo=exercise.tempo,
                        side=exercise.side,
                        notes=exercise.notes,
                    )
                    mapped_exercises.append(mapped_exercise)
                    mapped_count += 1
                    logger.debug(f"Mapped '{exercise.name}' -> '{canonical_name}'")
                else:
                    # Keep exercise without canonical_name
                    mapped_exercises.append(exercise)
                    unmapped_count += 1
                    logger.debug(f"No mapping found for '{exercise.name}'")

            # Create new block with mapped exercises
            mapped_block = Block(
                label=block.label,
                type=block.type,
                rounds=block.rounds,
                exercises=mapped_exercises,
            )
            mapped_blocks.append(mapped_block)

        # Create new workout with mapped blocks
        return (
            Workout(
                id=workout.id,
                title=workout.title,
                description=workout.description,
                blocks=mapped_blocks,
                notes=workout.notes,
                tags=workout.tags,
                metadata=workout.metadata,
            ),
            mapped_count,
            unmapped_count,
        )

    def _resolve_exercise_name(self, exercise_name: str) -> Optional[str]:
        """
        Resolve an exercise name to its canonical (Garmin) name.

        Priority:
        1. User-defined mapping (exact match)
        2. Fuzzy matching against Garmin exercise database

        Args:
            exercise_name: Original exercise name to resolve

        Returns:
            Canonical name if found, None otherwise
        """
        # First, check user-defined mappings
        user_mapping = self._user_mapping_repo.get(exercise_name)
        if user_mapping:
            logger.debug(f"Found user mapping for '{exercise_name}'")
            return user_mapping

        # Fall back to fuzzy matching
        matched_name, confidence = self._exercise_match_repo.find_match(
            exercise_name, threshold=0.5
        )

        if matched_name:
            logger.debug(
                f"Fuzzy matched '{exercise_name}' -> '{matched_name}' "
                f"(confidence: {confidence:.2f})"
            )
            return matched_name

        return None
