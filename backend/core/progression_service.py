"""
Progression Service for Exercise Tracking.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

This module provides business logic for exercise progression tracking:
- 1RM calculations using Brzycki and Epley formulas
- Exercise history with calculated metrics
- Personal record tracking
- Volume analytics
"""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, timedelta
import logging

from application.ports.progression_repository import ProgressionRepository
from application.ports.exercises_repository import ExercisesRepository

logger = logging.getLogger(__name__)


# =============================================================================
# 1RM Calculation Formulas
# =============================================================================


def calculate_1rm_brzycki(weight: float, reps: int) -> float:
    """
    Calculate estimated 1RM using Brzycki formula.

    Formula: 1RM = weight * (36 / (37 - reps))

    Most accurate for rep ranges 1-10. Less reliable above 10 reps.

    Args:
        weight: Weight lifted
        reps: Number of reps completed

    Returns:
        Estimated 1RM
    """
    if reps <= 0:
        return 0.0
    if reps == 1:
        return float(weight)
    if reps >= 37:
        # Formula breaks down at 37+ reps
        return float(weight) * 2.5  # Reasonable cap

    return weight * (36.0 / (37.0 - reps))


def calculate_1rm_epley(weight: float, reps: int) -> float:
    """
    Calculate estimated 1RM using Epley formula.

    Formula: 1RM = weight * (1 + reps/30)

    Works well across all rep ranges but may overestimate at high reps.

    Args:
        weight: Weight lifted
        reps: Number of reps completed

    Returns:
        Estimated 1RM
    """
    if reps <= 0:
        return 0.0
    if reps == 1:
        return float(weight)

    return weight * (1.0 + reps / 30.0)


def calculate_1rm(
    weight: float,
    reps: int,
    formula: str = "brzycki",
) -> float:
    """
    Calculate estimated 1RM using the specified formula.

    Args:
        weight: Weight lifted
        reps: Number of reps completed
        formula: Formula to use ("brzycki" or "epley")

    Returns:
        Estimated 1RM, rounded to 1 decimal place
    """
    if formula == "epley":
        result = calculate_1rm_epley(weight, reps)
    else:
        # Default to Brzycki
        result = calculate_1rm_brzycki(weight, reps)

    return round(result, 1)


# =============================================================================
# Response DTOs
# =============================================================================


@dataclass
class SetWithEstimated1RM:
    """A set with calculated estimated 1RM."""
    set_number: int
    weight: Optional[float]
    weight_unit: str
    reps_completed: Optional[int]
    reps_planned: Optional[int]
    status: str
    estimated_1rm: Optional[float] = None
    is_pr: bool = False  # Is this set a personal record?


@dataclass
class SessionWith1RM:
    """An exercise session with 1RM calculations."""
    completion_id: str
    workout_date: str
    workout_name: Optional[str]
    exercise_name: str
    sets: List[SetWithEstimated1RM] = field(default_factory=list)
    session_best_1rm: Optional[float] = None
    session_max_weight: Optional[float] = None
    session_total_volume: Optional[float] = None


@dataclass
class ExerciseHistoryResponse:
    """Response for exercise history endpoint."""
    exercise_id: str
    exercise_name: str
    supports_1rm: bool
    one_rm_formula: str
    sessions: List[SessionWith1RM]
    total_sessions: int
    all_time_best_1rm: Optional[float] = None
    all_time_max_weight: Optional[float] = None


@dataclass
class PersonalRecordResponse:
    """Response for personal records endpoint."""
    records: List[Dict[str, Any]]
    exercise_id: Optional[str] = None


@dataclass
class LastWeightResponse:
    """Response for last weight endpoint."""
    exercise_id: str
    exercise_name: str
    weight: float
    weight_unit: str
    reps_completed: int
    workout_date: str
    completion_id: str


@dataclass
class VolumeAnalyticsResponse:
    """Response for volume analytics endpoint."""
    data: List[Dict[str, Any]]
    summary: Dict[str, Any]
    period: Dict[str, Any]
    granularity: str


# =============================================================================
# Progression Service
# =============================================================================


class ProgressionService:
    """
    Service for exercise progression tracking and analytics.

    Provides business logic on top of repository data access, including:
    - 1RM calculation and enrichment
    - Personal record detection
    - Volume aggregation
    """

    def __init__(
        self,
        progression_repo: ProgressionRepository,
        exercises_repo: ExercisesRepository,
    ):
        """
        Initialize the progression service.

        Args:
            progression_repo: Repository for progression data access
            exercises_repo: Repository for exercise metadata
        """
        self._progression_repo = progression_repo
        self._exercises_repo = exercises_repo

    def get_exercise_history(
        self,
        user_id: str,
        exercise_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Optional[ExerciseHistoryResponse]:
        """
        Get exercise history with 1RM calculations.

        Fetches session data and enriches each set with estimated 1RM.

        Args:
            user_id: User ID
            exercise_id: Canonical exercise ID
            limit: Maximum sessions to return
            offset: Pagination offset

        Returns:
            ExerciseHistoryResponse or None if exercise not found
        """
        # Get exercise metadata
        exercise = self._exercises_repo.get_by_id(exercise_id)
        if not exercise:
            logger.warning(f"Exercise not found: {exercise_id}")
            return None

        supports_1rm = exercise.get("supports_1rm", False)
        formula = exercise.get("one_rm_formula", "brzycki")

        # Get session history
        history = self._progression_repo.get_exercise_history(
            user_id,
            exercise_id,
            limit=limit,
            offset=offset,
        )

        sessions_data = history.get("sessions", [])
        total_sessions = history.get("total", len(sessions_data))

        # Track all-time bests
        all_time_best_1rm = 0.0
        all_time_max_weight = 0.0

        # Enrich sessions with 1RM calculations
        sessions: List[SessionWith1RM] = []
        for session_data in sessions_data:
            sets_raw = session_data.get("sets", [])
            session_best_1rm = 0.0
            session_max_weight = 0.0
            session_total_volume = 0.0

            enriched_sets: List[SetWithEstimated1RM] = []
            for set_data in sets_raw:
                weight = set_data.get("weight")
                reps = set_data.get("reps_completed")

                estimated_1rm = None
                if supports_1rm and weight is not None and reps is not None and reps > 0:
                    estimated_1rm = calculate_1rm(weight, reps, formula)
                    if estimated_1rm > session_best_1rm:
                        session_best_1rm = estimated_1rm
                    if estimated_1rm > all_time_best_1rm:
                        all_time_best_1rm = estimated_1rm

                if weight is not None:
                    if weight > session_max_weight:
                        session_max_weight = weight
                    if weight > all_time_max_weight:
                        all_time_max_weight = weight

                    if reps is not None and reps > 0:
                        session_total_volume += weight * reps

                enriched_sets.append(SetWithEstimated1RM(
                    set_number=set_data.get("set_number", 1),
                    weight=weight,
                    weight_unit=set_data.get("weight_unit", "lbs"),
                    reps_completed=reps,
                    reps_planned=set_data.get("reps_planned"),
                    status=set_data.get("status", "completed"),
                    estimated_1rm=estimated_1rm,
                ))

            session = SessionWith1RM(
                completion_id=session_data.get("completion_id", ""),
                workout_date=session_data.get("workout_date", ""),
                workout_name=session_data.get("workout_name"),
                exercise_name=session_data.get("exercise_name", exercise.get("name", "")),
                sets=enriched_sets,
                session_best_1rm=session_best_1rm if session_best_1rm > 0 else None,
                session_max_weight=session_max_weight if session_max_weight > 0 else None,
                session_total_volume=round(session_total_volume, 1) if session_total_volume > 0 else None,
            )
            sessions.append(session)

        return ExerciseHistoryResponse(
            exercise_id=exercise_id,
            exercise_name=exercise.get("name", exercise_id),
            supports_1rm=supports_1rm,
            one_rm_formula=formula,
            sessions=sessions,
            total_sessions=total_sessions,
            all_time_best_1rm=all_time_best_1rm if all_time_best_1rm > 0 else None,
            all_time_max_weight=all_time_max_weight if all_time_max_weight > 0 else None,
        )

    def get_personal_records(
        self,
        user_id: str,
        *,
        record_type: Optional[str] = None,  # "1rm", "max_weight", "max_reps"
        exercise_id: Optional[str] = None,
        limit: int = 20,
    ) -> PersonalRecordResponse:
        """
        Get personal records for a user.

        Calculates records from all exercise history:
        - 1RM: Best estimated 1RM
        - max_weight: Heaviest weight lifted
        - max_reps: Most reps at any weight

        Args:
            user_id: User ID
            record_type: Filter to specific record type
            exercise_id: Filter to specific exercise
            limit: Maximum records to return

        Returns:
            PersonalRecordResponse with records list
        """
        records: List[Dict[str, Any]] = []

        # Get exercises to calculate records for
        if exercise_id:
            exercises = [self._exercises_repo.get_by_id(exercise_id)]
            exercises = [e for e in exercises if e is not None]
        else:
            # Get exercises that the user has history for
            exercises_with_history = self._progression_repo.get_exercises_with_history(
                user_id,
                limit=limit,
            )
            exercise_ids = [e.get("exercise_id") for e in exercises_with_history]
            exercises = [
                self._exercises_repo.get_by_id(eid)
                for eid in exercise_ids
                if eid
            ]
            exercises = [e for e in exercises if e is not None]

        for exercise in exercises:
            ex_id = exercise.get("id", "")
            ex_name = exercise.get("name", "")
            supports_1rm = exercise.get("supports_1rm", False)
            formula = exercise.get("one_rm_formula", "brzycki")

            # Get all sessions for this exercise
            sessions = self._progression_repo.get_all_exercise_sessions(
                user_id,
                ex_id,
            )

            # Calculate records
            best_1rm = None
            best_1rm_details = None
            best_1rm_date = None
            best_1rm_completion = None

            max_weight = None
            max_weight_date = None
            max_weight_completion = None

            max_reps = None
            max_reps_weight = None
            max_reps_date = None
            max_reps_completion = None

            for session in sessions:
                session_date = session.get("workout_date", "")
                completion_id = session.get("completion_id", "")

                for set_data in session.get("sets", []):
                    weight = set_data.get("weight")
                    reps = set_data.get("reps_completed")

                    if weight is not None and reps is not None and reps > 0:
                        # Calculate 1RM
                        if supports_1rm:
                            est_1rm = calculate_1rm(weight, reps, formula)
                            if best_1rm is None or est_1rm > best_1rm:
                                best_1rm = est_1rm
                                best_1rm_details = {"weight": weight, "reps": reps}
                                best_1rm_date = session_date
                                best_1rm_completion = completion_id

                        # Track max weight
                        if max_weight is None or weight > max_weight:
                            max_weight = weight
                            max_weight_date = session_date
                            max_weight_completion = completion_id

                        # Track max reps (at any weight)
                        if max_reps is None or reps > max_reps:
                            max_reps = reps
                            max_reps_weight = weight
                            max_reps_date = session_date
                            max_reps_completion = completion_id

            # Add records based on filter
            if (record_type is None or record_type == "1rm") and best_1rm is not None:
                records.append({
                    "exercise_id": ex_id,
                    "exercise_name": ex_name,
                    "record_type": "1rm",
                    "value": best_1rm,
                    "unit": "lbs",  # TODO: get from set data
                    "achieved_at": best_1rm_date,
                    "completion_id": best_1rm_completion,
                    "details": best_1rm_details,
                })

            if (record_type is None or record_type == "max_weight") and max_weight is not None:
                records.append({
                    "exercise_id": ex_id,
                    "exercise_name": ex_name,
                    "record_type": "max_weight",
                    "value": max_weight,
                    "unit": "lbs",
                    "achieved_at": max_weight_date,
                    "completion_id": max_weight_completion,
                })

            if (record_type is None or record_type == "max_reps") and max_reps is not None:
                records.append({
                    "exercise_id": ex_id,
                    "exercise_name": ex_name,
                    "record_type": "max_reps",
                    "value": max_reps,
                    "unit": "reps",
                    "achieved_at": max_reps_date,
                    "completion_id": max_reps_completion,
                    "details": {"weight": max_reps_weight},
                })

        # Sort by value descending within each record type
        records.sort(key=lambda r: (r["record_type"], -r["value"]))

        return PersonalRecordResponse(
            records=records[:limit],
            exercise_id=exercise_id,
        )

    def get_last_weight(
        self,
        user_id: str,
        exercise_id: str,
    ) -> Optional[LastWeightResponse]:
        """
        Get the last weight used for an exercise.

        Used for "Use Last Weight" feature in companion apps.

        Args:
            user_id: User ID
            exercise_id: Canonical exercise ID

        Returns:
            LastWeightResponse or None if no history
        """
        # Verify exercise exists
        exercise = self._exercises_repo.get_by_id(exercise_id)
        if not exercise:
            return None

        result = self._progression_repo.get_last_weight_used(user_id, exercise_id)
        if not result:
            return None

        return LastWeightResponse(
            exercise_id=exercise_id,
            exercise_name=exercise.get("name", exercise_id),
            weight=result.get("weight", 0),
            weight_unit=result.get("weight_unit", "lbs"),
            reps_completed=result.get("reps_completed", 0),
            workout_date=result.get("workout_date", ""),
            completion_id=result.get("completion_id", ""),
        )

    def get_volume_analytics(
        self,
        user_id: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "daily",
        muscle_groups: Optional[List[str]] = None,
    ) -> VolumeAnalyticsResponse:
        """
        Get training volume analytics by muscle group.

        Args:
            user_id: User ID
            start_date: Start of date range (default: 30 days ago)
            end_date: End of date range (default: today)
            granularity: "daily", "weekly", or "monthly"
            muscle_groups: Filter to specific muscle groups

        Returns:
            VolumeAnalyticsResponse with data and summary
        """
        # Set default date range
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        result = self._progression_repo.get_volume_by_muscle_group(
            user_id,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            muscle_groups=muscle_groups,
        )

        return VolumeAnalyticsResponse(
            data=result.get("data", []),
            summary=result.get("summary", {}),
            period={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            granularity=granularity,
        )

    def get_exercises_with_history(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get exercises that the user has history for.

        Args:
            user_id: User ID
            limit: Maximum exercises to return

        Returns:
            List of exercises with session counts
        """
        return self._progression_repo.get_exercises_with_history(user_id, limit=limit)
