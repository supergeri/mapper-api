"""
Match workout use case for detection endpoint.

Part of AMA-688: Auto-detection endpoint for matching detected exercises
against user's scheduled AmakaFlow workouts.
"""

from datetime import datetime, timedelta
from typing import Optional

from backend.schemas.detection import DetectionRequest, DetectionMatch


class MatchWorkoutUseCase:
    """
    Use case for matching detected exercises from wearable devices
    against user's scheduled AmakaFlow workouts.
    """

    def __init__(self, workout_repository):
        """
        Initialize the use case with a workout repository.

        Args:
            workout_repository: Repository for accessing workout data
        """
        self.workout_repository = workout_repository

    async def execute(self, request: DetectionRequest) -> DetectionMatch:
        """
        Match detected exercises against user's workouts.

        Args:
            request: Detection request with detected exercises and metadata

        Returns:
            DetectionMatch with match result and confidence score
        """
        # Query user's workouts for ±2h window around the timestamp
        workouts = self._get_workouts_in_time_window(
            user_id=request.user_id,
            timestamp=request.timestamp,
            window_hours=2
        )

        if not workouts:
            return DetectionMatch(
                matched=False,
                reason="no_scheduled_workout"
            )

        # Score each workout
        best_match = None
        best_score = 0.0

        for workout in workouts:
            score = self._score_workout(
                workout=workout,
                detected_exercises=request.detected_exercises,
                sport=request.sport,
                timestamp=request.timestamp
            )

            if score > best_score:
                best_score = score
                best_match = workout

        # Check if we have a match
        if best_match is None:
            return DetectionMatch(
                matched=False,
                reason="no_scheduled_workout"
            )

        # Check sport match
        workout_sport = self._get_workout_sport(best_match)
        sport_match = 1.0 if workout_sport == request.sport else 0.0

        if sport_match == 0.0:
            return DetectionMatch(
                matched=False,
                reason="sport_mismatch"
            )

        # Check if score exceeds threshold
        if best_score <= 0.85:
            return DetectionMatch(
                matched=False,
                reason="low_confidence"
            )

        # Return successful match
        return DetectionMatch(
            matched=True,
            workout_id=best_match.get("id"),
            workout_name=best_match.get("title"),
            confidence=best_score,
            match_reason=f"Matched {len(set(request.detected_exercises) & set(self._get_workout_exercises(best_match)))} exercises with {best_score:.2f} confidence"
        )

    def _get_workouts_in_time_window(
        self,
        user_id: str,
        timestamp: datetime,
        window_hours: int
    ) -> list:
        """
        Get workouts within a time window around the given timestamp.

        Args:
            user_id: User ID
            timestamp: Center of the time window
            window_hours: Window size in hours (±)

        Returns:
            List of workout records
        """
        # Get all workouts for the user
        workouts = self.workout_repository.get_list(
            profile_id=user_id,
            limit=100  # Get enough workouts to score
        )
        return workouts

    def _score_workout(
        self,
        workout: dict,
        detected_exercises: list[str],
        sport: str,
        timestamp: datetime
    ) -> float:
        """
        Score a workout based on schedule proximity, exercise overlap, and sport match.

        Score formula:
        schedule_proximity * 0.35 + exercise_overlap * 0.45 + sport_match * 0.20

        Args:
            workout: Workout record
            detected_exercises: List of detected exercise names
            sport: Detected sport
            timestamp: Detection timestamp

        Returns:
            Score between 0.0 and 1.0
        """
        # Calculate schedule proximity
        created_at = workout.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        schedule_proximity = self._calculate_schedule_proximity(timestamp, created_at)

        # Calculate exercise overlap (Jaccard similarity)
        workout_exercises = self._get_workout_exercises(workout)
        exercise_overlap = self._calculate_exercise_overlap(
            detected_exercises,
            workout_exercises
        )

        # Calculate sport match
        workout_sport = self._get_workout_sport(workout)
        sport_match = 1.0 if workout_sport == sport else 0.0

        # Calculate weighted score
        score = (
            schedule_proximity * 0.35 +
            exercise_overlap * 0.45 +
            sport_match * 0.20
        )

        return score

    def _calculate_schedule_proximity(
        self,
        detection_time: datetime,
        workout_time: datetime
    ) -> float:
        """
        Calculate schedule proximity score.

        - 1.0 if within 1 hour
        - Linear decay to 0.0 at 3 hours

        Args:
            detection_time: When the workout was detected
            workout_time: When the workout was scheduled/created

        Returns:
            Score between 0.0 and 1.0
        """
        # Convert to naive datetime for comparison if needed
        if detection_time.tzinfo is not None:
            detection_time = detection_time.replace(tzinfo=None)
        if workout_time.tzinfo is not None:
            workout_time = workout_time.replace(tzinfo=None)

        time_diff = abs((detection_time - workout_time).total_seconds() / 3600)  # hours

        if time_diff <= 1.0:
            return 1.0
        elif time_diff >= 3.0:
            return 0.0
        else:
            # Linear decay from 1.0 at 1h to 0.0 at 3h
            return 1.0 - (time_diff - 1.0) / 2.0

    def _calculate_exercise_overlap(
        self,
        detected: list[str],
        workout: list[str]
    ) -> float:
        """
        Calculate Jaccard similarity between detected and workout exercises.

        Jaccard = len(intersection) / len(union)

        Args:
            detected: List of detected exercise names
            workout: List of workout exercise names

        Returns:
            Jaccard similarity score between 0.0 and 1.0
        """
        if not detected or not workout:
            return 0.0

        # Normalize to lowercase for comparison
        detected_set = set(e.lower() for e in detected)
        workout_set = set(e.lower() for e in workout)

        intersection = len(detected_set & workout_set)
        union = len(detected_set | workout_set)

        if union == 0:
            return 0.0

        return intersection / union

    def _get_workout_exercises(self, workout: dict) -> list[str]:
        """
        Extract exercise names from a workout record.

        Args:
            workout: Workout record

        Returns:
            List of exercise names
        """
        exercises = []

        # Try to get from workout_data
        workout_data = workout.get("workout_data", {})
        blocks = workout_data.get("blocks", [])

        for block in blocks:
            block_exercises = block.get("exercises", [])
            for exercise in block_exercises:
                if isinstance(exercise, dict):
                    name = exercise.get("name")
                    if name:
                        exercises.append(name)
                elif isinstance(exercise, str):
                    exercises.append(exercise)

        # Also check for intervals
        intervals = workout_data.get("intervals", [])
        for interval in intervals:
            if isinstance(interval, dict):
                name = interval.get("name") or interval.get("exercise")
                if name:
                    exercises.append(name)

        return exercises

    def _get_workout_sport(self, workout: dict) -> str:
        """
        Get the sport type from a workout record.

        Args:
            workout: Workout record

        Returns:
            Sport type string (lowercase)
        """
        # Try workout_data first
        workout_data = workout.get("workout_data", {})
        sport = workout_data.get("type") or workout_data.get("sport") or ""

        # If not found, try title-based heuristics
        if not sport:
            title = workout.get("title", "").lower()
            if "run" in title:
                sport = "running"
            elif "cycle" in title:
                sport = "cycling"
            elif "cardio" in title:
                sport = "cardio"
            elif "strength" in title or "workout" in title:
                sport = "strength"

        return sport.lower()
