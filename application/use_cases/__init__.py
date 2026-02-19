"""
Application Use Cases for AmakaFlow Mapper API.

Part of AMA-391: Create MapWorkout use case
Part of AMA-392: Create ExportWorkout use case
Part of AMA-393: Create SaveWorkout use case
Part of AMA-433: Create PatchWorkout use case
Phase 3 - Canonical Model + Use Cases

This package contains application-level use cases that orchestrate domain logic
and coordinate between ports/adapters. Use cases are the entry points for
business operations and contain the application's workflow logic.

Architecture follows Clean Architecture / Hexagonal pattern:
- Use cases orchestrate domain objects and repository ports
- Dependencies are injected via constructors for testability
- Use cases return domain models, not API responses

Usage:
    from application.use_cases import (
        MapWorkoutUseCase,
        MapWorkoutResult,
        ExportWorkoutUseCase,
        ExportWorkoutResult,
        SaveWorkoutUseCase,
        SaveWorkoutResult,
        PatchWorkoutUseCase,
        PatchWorkoutResult,
    )

    # Map a parsed workout
    map_use_case = MapWorkoutUseCase(
        exercise_match_repo=exercise_match_repo,
        user_mapping_repo=user_mapping_repo,
        workout_repo=workout_repo,
    )
    result = map_use_case.execute(
        parsed_workout=parsed,
        user_id="user-123",
        device="garmin",
    )

    # Export a workout
    export_use_case = ExportWorkoutUseCase(workout_repo=workout_repo)
    result = export_use_case.execute(
        workout_id="w-123",
        profile_id="user-123",
        export_format="yaml",
    )

    # Save a workout
    save_use_case = SaveWorkoutUseCase(workout_repo=workout_repo)
    result = save_use_case.execute(
        workout=workout,
        user_id="user-123",
        device="garmin",
    )

    # Patch a workout
    patch_use_case = PatchWorkoutUseCase(supabase_client=client)
    result = patch_use_case.execute(
        workout_id="w-123",
        user_id="user-123",
        operations=[...],
    )
"""

from application.use_cases.export_workout import (
    ExportFormat,
    ExportWorkoutResult,
    ExportWorkoutUseCase,
)
from application.use_cases.get_workout import (
    GetWorkoutUseCase,
    GetWorkoutResult,
    ListWorkoutsResult,
    GetIncomingWorkoutsResult,
)
from application.use_cases.map_workout import MapWorkoutResult, MapWorkoutUseCase
from application.use_cases.save_workout import (
    SaveWorkoutResult,
    SaveWorkoutUseCase,
    WorkoutValidationError,
)
from application.use_cases.patch_workout import (
    PatchWorkoutResult,
    PatchWorkoutUseCase,
    PatchValidationError,
)

__all__ = [
    # MapWorkout
    "MapWorkoutUseCase",
    "MapWorkoutResult",
    # ExportWorkout
    "ExportWorkoutUseCase",
    "ExportWorkoutResult",
    "ExportFormat",
    # GetWorkout
    "GetWorkoutUseCase",
    "GetWorkoutResult",
    "ListWorkoutsResult",
    "GetIncomingWorkoutsResult",
    # SaveWorkout
    "SaveWorkoutUseCase",
    "SaveWorkoutResult",
    "WorkoutValidationError",
    # PatchWorkout
    "PatchWorkoutUseCase",
    "PatchWorkoutResult",
    "PatchValidationError",
]
