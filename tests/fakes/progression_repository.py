"""
Fake Progression Repository for Testing.

Part of AMA-299: Exercise Progression Tracking
Phase 3 - Progression Features

In-memory implementation of ProgressionRepository for fast, isolated testing.
"""
from typing import Optional, List, Dict, Any
from datetime import date, timedelta
from collections import defaultdict


class FakeProgressionRepository:
    """
    In-memory fake implementation of ProgressionRepository.

    Stores completion data in memory for testing progression features.
    """

    def __init__(self):
        """Initialize with empty storage."""
        # Map: user_id -> List[session_data]
        self._sessions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # Map: exercise_id -> exercise_metadata
        self._exercise_metadata: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        """Clear all stored data."""
        self._sessions.clear()
        self._exercise_metadata.clear()

    def seed_sessions(
        self,
        user_id: str,
        sessions: List[Dict[str, Any]],
    ) -> None:
        """
        Seed the repository with session data.

        Args:
            user_id: User ID
            sessions: List of session dicts, each with:
                - completion_id: str
                - workout_date: str (ISO format)
                - workout_name: Optional[str]
                - exercise_id: str (canonical exercise ID)
                - exercise_name: str
                - sets: List of set dicts with weight, reps, etc.
        """
        self._sessions[user_id].extend(sessions)
        # Sort by date descending
        self._sessions[user_id].sort(
            key=lambda s: s.get("workout_date", ""),
            reverse=True,
        )

    def seed_exercise_metadata(
        self,
        exercise_id: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Seed exercise metadata (name, muscle groups, etc.).

        Args:
            exercise_id: Canonical exercise ID
            metadata: Exercise metadata dict
        """
        self._exercise_metadata[exercise_id] = metadata

    def get_exercise_history(
        self,
        user_id: str,
        exercise_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Get the history of a specific exercise for a user."""
        all_sessions = self._sessions.get(user_id, [])

        # Filter to the specific exercise
        exercise_sessions = [
            s for s in all_sessions
            if s.get("exercise_id") == exercise_id
        ]

        total = len(exercise_sessions)
        paginated = exercise_sessions[offset:offset + limit]

        exercise = self._exercise_metadata.get(exercise_id, {})

        return {
            "sessions": paginated,
            "total": total,
            "exercise": exercise,
        }

    def get_all_exercise_sessions(
        self,
        user_id: str,
        exercise_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all sessions for an exercise (no pagination)."""
        all_sessions = self._sessions.get(user_id, [])
        return [
            s for s in all_sessions
            if s.get("exercise_id") == exercise_id
        ]

    def get_last_weight_used(
        self,
        user_id: str,
        exercise_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the last weight used for an exercise."""
        sessions = self.get_all_exercise_sessions(user_id, exercise_id)

        # Find the most recent set with a weight
        for session in sessions:  # Already sorted by date desc
            for set_data in session.get("sets", []):
                if set_data.get("weight") is not None and set_data.get("status") == "completed":
                    return {
                        "exercise_id": exercise_id,
                        "weight": set_data["weight"],
                        "weight_unit": set_data.get("weight_unit", "lbs"),
                        "reps_completed": set_data.get("reps_completed", 0),
                        "workout_date": session.get("workout_date", ""),
                        "completion_id": session.get("completion_id", ""),
                    }

        return None

    def get_volume_by_muscle_group(
        self,
        user_id: str,
        *,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: str = "daily",
        muscle_groups: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get training volume aggregated by muscle group."""
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        all_sessions = self._sessions.get(user_id, [])

        # Filter by date range
        filtered_sessions = []
        for session in all_sessions:
            workout_date_str = session.get("workout_date", "")
            if workout_date_str:
                try:
                    workout_date = date.fromisoformat(workout_date_str[:10])
                    if start_date <= workout_date <= end_date:
                        filtered_sessions.append(session)
                except ValueError:
                    pass

        # Aggregate volume by muscle group and period
        volume_data: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        summary: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "total_volume": 0.0,
            "total_sets": 0,
            "total_reps": 0,
        })

        for session in filtered_sessions:
            exercise_id = session.get("exercise_id", "")
            exercise_meta = self._exercise_metadata.get(exercise_id, {})
            primary_muscles = exercise_meta.get("primary_muscles", ["other"])

            # Filter by muscle groups if specified
            if muscle_groups:
                if not any(m in primary_muscles for m in muscle_groups):
                    continue

            workout_date_str = session.get("workout_date", "")[:10]

            # Determine period key based on granularity
            period_key = workout_date_str  # daily
            if granularity == "weekly":
                d = date.fromisoformat(workout_date_str)
                week_start = d - timedelta(days=d.weekday())
                period_key = week_start.isoformat()
            elif granularity == "monthly":
                period_key = workout_date_str[:7]  # YYYY-MM

            for set_data in session.get("sets", []):
                weight = set_data.get("weight", 0) or 0
                reps = set_data.get("reps_completed", 0) or 0

                if set_data.get("status") == "completed":
                    volume = weight * reps

                    for muscle in primary_muscles:
                        volume_data[muscle][period_key] += volume
                        summary[muscle]["total_volume"] += volume
                        summary[muscle]["total_sets"] += 1
                        summary[muscle]["total_reps"] += reps

        # Convert to list format
        data_list = []
        for muscle, periods in volume_data.items():
            for period, total_volume in sorted(periods.items()):
                data_list.append({
                    "period": period,
                    "muscle_group": muscle,
                    "total_volume": round(total_volume, 1),
                    "total_sets": 0,  # Simplified for fake
                    "total_reps": 0,
                })

        return {
            "data": data_list,
            "summary": dict(summary),
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        }

    def get_exercises_with_history(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get exercises that the user has history for."""
        all_sessions = self._sessions.get(user_id, [])

        # Count sessions per exercise
        exercise_counts: Dict[str, int] = defaultdict(int)
        exercise_names: Dict[str, str] = {}

        for session in all_sessions:
            exercise_id = session.get("exercise_id")
            if exercise_id:
                exercise_counts[exercise_id] += 1
                if exercise_id not in exercise_names:
                    exercise_names[exercise_id] = session.get("exercise_name", exercise_id)

        # Build result
        result = [
            {
                "exercise_id": ex_id,
                "exercise_name": exercise_names.get(ex_id, ex_id),
                "session_count": count,
            }
            for ex_id, count in exercise_counts.items()
        ]

        # Sort by session count descending
        result.sort(key=lambda x: x["session_count"], reverse=True)

        return result[:limit]


# =============================================================================
# Default Test Data
# =============================================================================


def create_test_sessions(
    user_id: str = "test_user",
    exercise_id: str = "barbell-bench-press",
    num_sessions: int = 5,
) -> List[Dict[str, Any]]:
    """
    Create sample session data for testing.

    Args:
        user_id: User ID
        exercise_id: Exercise to create sessions for
        num_sessions: Number of sessions to create

    Returns:
        List of session dicts
    """
    sessions = []
    base_date = date.today() - timedelta(days=num_sessions * 7)

    for i in range(num_sessions):
        session_date = base_date + timedelta(days=i * 7)
        base_weight = 135 + (i * 5)  # Progress weight over time

        sessions.append({
            "completion_id": f"completion_{i}",
            "workout_date": session_date.isoformat(),
            "workout_name": f"Push Day {i + 1}",
            "exercise_id": exercise_id,
            "exercise_name": "Barbell Bench Press",
            "sets": [
                {
                    "set_number": 1,
                    "weight": base_weight,
                    "weight_unit": "lbs",
                    "reps_completed": 8,
                    "reps_planned": 8,
                    "status": "completed",
                },
                {
                    "set_number": 2,
                    "weight": base_weight,
                    "weight_unit": "lbs",
                    "reps_completed": 7,
                    "reps_planned": 8,
                    "status": "completed",
                },
                {
                    "set_number": 3,
                    "weight": base_weight,
                    "weight_unit": "lbs",
                    "reps_completed": 6,
                    "reps_planned": 8,
                    "status": "completed",
                },
            ],
        })

    return sessions
