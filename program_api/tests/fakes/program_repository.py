"""
Fake program repository for testing.

Part of AMA-461: Create program-api service scaffold

This fake implementation stores data in memory and provides
helper methods for test setup and verification.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4


class FakeProgramRepository:
    """
    In-memory fake implementation of ProgramRepository.

    Provides the same interface as SupabaseProgramRepository
    but stores data in dictionaries for fast, isolated testing.
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._programs: Dict[str, Dict] = {}
        self._weeks: Dict[str, Dict] = {}
        self._workouts: Dict[str, Dict] = {}

    # -------------------------------------------------------------------------
    # Test Helpers
    # -------------------------------------------------------------------------

    def seed(self, programs: List[Dict]) -> None:
        """
        Seed the repository with test data.

        Args:
            programs: List of program dictionaries to add
        """
        for program in programs:
            program_id = program.get("id", str(uuid4()))
            self._programs[program_id] = {**program, "id": program_id}

    def seed_with_weeks(self, program: Dict, weeks: List[Dict]) -> None:
        """
        Seed a program with its weeks.

        Args:
            program: Program dictionary
            weeks: List of week dictionaries
        """
        program_id = program.get("id", str(uuid4()))
        self._programs[program_id] = {**program, "id": program_id}
        for week in weeks:
            week_id = week.get("id", str(uuid4()))
            self._weeks[week_id] = {**week, "id": week_id, "program_id": program_id}

    def reset(self) -> None:
        """Clear all stored data."""
        self._programs.clear()
        self._weeks.clear()
        self._workouts.clear()

    def get_all(self) -> List[Dict]:
        """Get all stored programs (for test verification)."""
        return list(self._programs.values())

    def count(self) -> int:
        """Get count of stored programs."""
        return len(self._programs)

    # -------------------------------------------------------------------------
    # Repository Interface Implementation
    # -------------------------------------------------------------------------

    def get_by_user(self, user_id: str) -> List[Dict]:
        """
        Get all programs for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of program dictionaries for this user
        """
        return [
            p for p in self._programs.values()
            if p.get("user_id") == user_id
        ]

    def get_by_id(self, program_id: str) -> Optional[Dict]:
        """
        Get a program by its ID.

        Args:
            program_id: The program's UUID as string

        Returns:
            Program dictionary if found, None otherwise
        """
        return self._programs.get(program_id)

    def create(self, data: Dict) -> Dict:
        """
        Create a new program.

        Args:
            data: Program data dictionary

        Returns:
            Created program dictionary with generated ID
        """
        program_id = data.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat() + "Z"
        program = {
            **data,
            "id": program_id,
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
            "status": data.get("status", "draft"),
        }
        self._programs[program_id] = program
        return program

    def update(self, program_id: str, data: Dict) -> Dict:
        """
        Update an existing program.

        Args:
            program_id: The program's UUID as string
            data: Updated program data

        Returns:
            Updated program dictionary

        Raises:
            KeyError: If program not found
        """
        if program_id not in self._programs:
            raise KeyError(f"Program {program_id} not found")

        program = self._programs[program_id]
        now = datetime.utcnow().isoformat() + "Z"
        updated = {
            **program,
            **data,
            "id": program_id,  # Preserve ID
            "updated_at": now,
        }
        self._programs[program_id] = updated
        return updated

    def delete(self, program_id: str) -> bool:
        """
        Delete a program.

        Args:
            program_id: The program's UUID as string

        Returns:
            True if deleted, False if not found
        """
        if program_id in self._programs:
            del self._programs[program_id]
            # Cascade delete weeks
            weeks_to_delete = [
                wid for wid, w in self._weeks.items()
                if w.get("program_id") == program_id
            ]
            for week_id in weeks_to_delete:
                del self._weeks[week_id]
            return True
        return False

    def get_weeks(self, program_id: str) -> List[Dict]:
        """
        Get all weeks for a program with their workouts.

        Args:
            program_id: The program's UUID as string

        Returns:
            List of week dictionaries with nested workouts
        """
        weeks = [
            w for w in self._weeks.values()
            if w.get("program_id") == program_id
        ]
        # Sort by week_number
        weeks.sort(key=lambda w: w.get("week_number", 0))

        # Add workouts to each week
        for week in weeks:
            week_id = week["id"]
            week["workouts"] = sorted(
                [wo for wo in self._workouts.values() if wo.get("program_week_id") == week_id],
                key=lambda wo: wo.get("order_index", 0)
            )

        return weeks

    def create_week(self, program_id: str, data: Dict) -> Dict:
        """
        Create a new week in a program.

        Args:
            program_id: The program's UUID as string
            data: Week data dictionary

        Returns:
            Created week dictionary
        """
        week_id = data.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat() + "Z"
        week = {
            **data,
            "id": week_id,
            "program_id": program_id,
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._weeks[week_id] = week
        return week

    def create_workout(self, week_id: str, data: Dict) -> Dict:
        """
        Create a new workout in a week.

        Args:
            week_id: The week's UUID as string
            data: Workout data dictionary

        Returns:
            Created workout dictionary
        """
        workout_id = data.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat() + "Z"
        workout = {
            **data,
            "id": workout_id,
            "program_week_id": week_id,
            "created_at": data.get("created_at", now),
            "updated_at": data.get("updated_at", now),
        }
        self._workouts[workout_id] = workout
        return workout
