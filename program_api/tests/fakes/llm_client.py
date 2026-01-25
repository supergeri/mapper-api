"""
Fake LLM client for testing.

Part of AMA-462: Implement ProgramGenerator Service

This fake implementation provides deterministic responses
without calling the actual OpenAI API.
"""

from typing import List, Optional

from services.llm.schemas import (
    ExerciseSelection,
    ExerciseSelectionRequest,
    ExerciseSelectionResponse,
)


class FakeExerciseSelector:
    """
    Deterministic fake for OpenAIExerciseSelector.

    Returns predictable exercise selections based on the request,
    allowing tests to verify the integration without LLM costs.
    """

    def __init__(self, predefined_response: Optional[ExerciseSelectionResponse] = None):
        """
        Initialize the fake selector.

        Args:
            predefined_response: Optional fixed response to return
        """
        self._predefined_response = predefined_response
        self._call_count = 0
        self._last_request: Optional[ExerciseSelectionRequest] = None

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    @property
    def call_count(self) -> int:
        """Get number of times select_exercises was called."""
        return self._call_count

    @property
    def last_request(self) -> Optional[ExerciseSelectionRequest]:
        """Get the last request received."""
        return self._last_request

    def set_response(self, response: ExerciseSelectionResponse) -> None:
        """Set a predefined response to return."""
        self._predefined_response = response

    def reset(self) -> None:
        """Reset call tracking."""
        self._call_count = 0
        self._last_request = None

    # -------------------------------------------------------------------------
    # OpenAIExerciseSelector Interface
    # -------------------------------------------------------------------------

    async def select_exercises(
        self,
        request: ExerciseSelectionRequest,
        use_cache: bool = True,
    ) -> ExerciseSelectionResponse:
        """
        Select exercises deterministically.

        If a predefined response is set, returns that.
        Otherwise, generates a response based on available exercises.

        Args:
            request: Exercise selection request
            use_cache: Ignored in fake

        Returns:
            ExerciseSelectionResponse with selected exercises
        """
        self._call_count += 1
        self._last_request = request

        if self._predefined_response:
            return self._predefined_response

        # Generate deterministic response
        return self._generate_response(request)

    def _generate_response(
        self,
        request: ExerciseSelectionRequest,
    ) -> ExerciseSelectionResponse:
        """Generate a deterministic response based on request."""
        exercises: List[ExerciseSelection] = []

        # Sort available exercises for deterministic order
        sorted_exercises = sorted(
            request.available_exercises,
            key=lambda x: (
                0 if x.get("category") == "compound" else 1,
                x.get("name", ""),
            ),
        )

        # Select up to requested count
        selected = sorted_exercises[: request.exercise_count]

        # Determine rep scheme based on goal
        rep_schemes = {
            "strength": ("3-5", 4, 150),
            "hypertrophy": ("8-12", 4, 90),
            "endurance": ("15-20", 3, 60),
            "weight_loss": ("12-15", 3, 45),
            "general_fitness": ("10-15", 3, 60),
        }

        reps, base_sets, rest = rep_schemes.get(
            request.goal, ("8-12", 3, 90)
        )

        # Apply deload modifier
        sets = base_sets if not request.is_deload else max(2, base_sets - 1)

        for i, ex in enumerate(selected, 1):
            exercises.append(
                ExerciseSelection(
                    exercise_id=ex.get("id", f"exercise-{i}"),
                    exercise_name=ex.get("name", f"Exercise {i}"),
                    sets=sets,
                    reps=reps,
                    rest_seconds=rest,
                    notes=f"Fake selection for {request.workout_type}",
                    order=i,
                    superset_group=None,
                )
            )

        return ExerciseSelectionResponse(
            exercises=exercises,
            workout_notes=f"Deterministic selection for {request.workout_type} workout",
            estimated_duration_minutes=len(exercises) * 8 + 10,
        )

    def clear_cache(self) -> None:
        """No-op for fake."""
        pass


class FailingExerciseSelector:
    """
    Fake selector that always fails.

    Useful for testing fallback behavior.
    """

    def __init__(self, error_message: str = "LLM unavailable"):
        """
        Initialize with error message.

        Args:
            error_message: Error message to raise
        """
        self._error_message = error_message
        self._call_count = 0

    @property
    def call_count(self) -> int:
        """Get number of times select_exercises was called."""
        return self._call_count

    async def select_exercises(
        self,
        request: ExerciseSelectionRequest,
        use_cache: bool = True,
    ) -> ExerciseSelectionResponse:
        """Always raises an exception."""
        self._call_count += 1
        raise RuntimeError(self._error_message)

    def clear_cache(self) -> None:
        """No-op for fake."""
        pass
