"""
Application Use Cases for AmakaFlow Mapper API.

Part of AMA-391: Create MapWorkout use case
Phase 3 - Canonical Model + Use Cases

This package contains application-level use cases that orchestrate domain logic
and coordinate between ports/adapters. Use cases are the entry points for
business operations and contain the application's workflow logic.

Architecture follows Clean Architecture / Hexagonal pattern:
- Use cases orchestrate domain objects and repository ports
- Dependencies are injected via constructors for testability
- Use cases return domain models, not API responses

Usage:
    from application.use_cases import MapWorkoutUseCase, MapWorkoutResult

    # Create use case with injected dependencies
    use_case = MapWorkoutUseCase(
        exercise_match_repo=exercise_match_repo,
        user_mapping_repo=user_mapping_repo,
        workout_repo=workout_repo,
    )

    # Execute the use case
    result = use_case.execute(
        parsed_workout=parsed,
        user_id="user-123",
        device="garmin",
    )

    if result.success:
        workout = result.workout
        print(f"Mapped {result.exercises_mapped} exercises")
"""

from application.use_cases.map_workout import MapWorkoutResult, MapWorkoutUseCase

__all__ = [
    "MapWorkoutUseCase",
    "MapWorkoutResult",
]
