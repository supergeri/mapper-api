"""
Fake Completion Repository for testing.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

This module provides an in-memory implementation of CompletionRepository
for fast, isolated testing without database dependencies.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import uuid
import copy

from application.ports import HealthMetricsDTO, CompletionSummary


def _format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration."""
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}:{secs:02d}"


def _calculate_duration_seconds(started_at: str, ended_at: str) -> int:
    """Calculate duration in seconds between two ISO timestamps."""
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    end = datetime.fromisoformat(ended_at.replace("Z", "+00:00"))
    return int((end - start).total_seconds())


class FakeCompletionRepository:
    """
    In-memory fake implementation of CompletionRepository for testing.

    Stores completions in a dict keyed by completion ID.

    Usage:
        repo = FakeCompletionRepository()
        repo.seed([{"id": "c1", "user_id": "user1", ...}])
        result = repo.save(user_id="user1", started_at="...", ...)
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._completions: Dict[str, Dict[str, Any]] = {}
        # Also track workouts created via save_voice_workout_with_completion
        self._voice_workouts: Dict[str, Dict[str, Any]] = {}

    def reset(self) -> None:
        """Clear all stored completions and voice workouts."""
        self._completions.clear()
        self._voice_workouts.clear()

    def seed(self, completions: List[Dict[str, Any]]) -> None:
        """
        Seed the repository with test data.

        Args:
            completions: List of completion dicts. Must include 'id' and 'user_id'.
        """
        for completion in completions:
            completion_id = completion.get("id") or str(uuid.uuid4())
            self._completions[completion_id] = {**completion, "id": completion_id}

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all stored completions (test helper)."""
        return list(self._completions.values())

    # =========================================================================
    # CompletionRepository Protocol Methods
    # =========================================================================

    def save(
        self,
        user_id: str,
        *,
        started_at: str,
        ended_at: str,
        health_metrics: HealthMetricsDTO,
        source: str = "apple_watch",
        workout_event_id: Optional[str] = None,
        follow_along_workout_id: Optional[str] = None,
        workout_id: Optional[str] = None,
        source_workout_id: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
        heart_rate_samples: Optional[List[Dict[str, Any]]] = None,
        workout_structure: Optional[List[Dict[str, Any]]] = None,
        set_logs: Optional[List[Dict[str, Any]]] = None,
        execution_log: Optional[Dict[str, Any]] = None,
        is_simulated: bool = False,
        simulation_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save a workout completion record."""
        completion_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        duration_seconds = _calculate_duration_seconds(started_at, ended_at)

        completion = {
            "id": completion_id,
            "user_id": user_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "source": source,
            "workout_event_id": workout_event_id,
            "follow_along_workout_id": follow_along_workout_id,
            "workout_id": workout_id,
            "source_workout_id": source_workout_id,
            "avg_heart_rate": health_metrics.avg_heart_rate,
            "max_heart_rate": health_metrics.max_heart_rate,
            "min_heart_rate": health_metrics.min_heart_rate,
            "active_calories": health_metrics.active_calories,
            "total_calories": health_metrics.total_calories,
            "distance_meters": health_metrics.distance_meters,
            "steps": health_metrics.steps,
            "device_info": device_info,
            "heart_rate_samples": heart_rate_samples or [],
            "workout_structure": workout_structure,
            "set_logs": set_logs,
            "execution_log": execution_log,
            "is_simulated": is_simulated,
            "simulation_config": simulation_config,
            "created_at": now,
        }

        self._completions[completion_id] = completion

        return {
            "success": True,
            "completion_id": completion_id,
            "summary": {
                "duration_formatted": _format_duration(duration_seconds),
                "avg_heart_rate": health_metrics.avg_heart_rate,
                "calories": health_metrics.active_calories or health_metrics.total_calories,
            },
        }

    def get_by_id(
        self,
        user_id: str,
        completion_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single completion with full details."""
        completion = self._completions.get(completion_id)
        if completion and completion.get("user_id") == user_id:
            return copy.deepcopy(completion)
        return None

    def get_user_completions(
        self,
        user_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        include_simulated: bool = True,
    ) -> Dict[str, Any]:
        """Get completion history for a user."""
        results = []
        for completion in self._completions.values():
            if completion.get("user_id") != user_id:
                continue
            if not include_simulated and completion.get("is_simulated"):
                continue
            # Return summary view (without HR samples for list view)
            summary = copy.deepcopy(completion)
            summary.pop("heart_rate_samples", None)
            results.append(summary)

        # Sort by created_at descending
        results.sort(key=lambda c: c.get("created_at", ""), reverse=True)

        total = len(results)
        paginated = results[offset : offset + limit]

        return {"completions": paginated, "total": total}

    def save_voice_workout_with_completion(
        self,
        user_id: str,
        workout_data: Dict[str, Any],
        completion_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Save a voice-created workout with its completion atomically."""
        workout_id = str(uuid.uuid4())
        completion_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Save the voice workout
        workout = {
            "id": workout_id,
            "user_id": user_id,
            "profile_id": user_id,
            "title": workout_data.get("name", "Voice Workout"),
            "sport": workout_data.get("sport", "strength_training"),
            "intervals": workout_data.get("intervals", []),
            "source": "voice",
            "created_at": now,
        }
        self._voice_workouts[workout_id] = workout

        # Save the completion
        started_at = completion_data.get("started_at", now)
        ended_at = completion_data.get("ended_at", now)
        duration_seconds = _calculate_duration_seconds(started_at, ended_at)

        completion = {
            "id": completion_id,
            "user_id": user_id,
            "workout_id": workout_id,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "source": completion_data.get("source", "voice"),
            "is_simulated": False,
            "created_at": now,
        }
        self._completions[completion_id] = completion

        return {
            "success": True,
            "workout_id": workout_id,
            "completion_id": completion_id,
            "summary": {
                "duration_formatted": _format_duration(duration_seconds),
                "title": workout.get("title"),
            },
        }

    def get_completed_workout_ids(
        self,
        user_id: str,
    ) -> set:
        """Get IDs of workouts that have been completed by the user."""
        completed_ids = set()
        for completion in self._completions.values():
            if completion.get("user_id") != user_id:
                continue
            # Collect all linked workout IDs
            for field in ["workout_id", "follow_along_workout_id", "workout_event_id"]:
                if completion.get(field):
                    completed_ids.add(completion[field])
        return completed_ids
