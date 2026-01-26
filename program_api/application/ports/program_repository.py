"""
Program repository port (interface).

Part of AMA-461: Create program-api service scaffold

This Protocol defines the contract for program persistence operations.
Infrastructure implementations (e.g., Supabase) must satisfy this interface.
"""

from typing import Dict, List, Optional, Protocol


class ProgramRepository(Protocol):
    """
    Repository interface for training program persistence.

    All methods work with dictionaries for flexibility.
    The infrastructure layer handles serialization to/from domain models.
    """

    def get_by_user(self, user_id: str) -> List[Dict]:
        """
        Get all programs for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of program dictionaries
        """
        ...

    def get_by_id(self, program_id: str) -> Optional[Dict]:
        """
        Get a program by its ID.

        Args:
            program_id: The program's UUID as string

        Returns:
            Program dictionary if found, None otherwise
        """
        ...

    def create(self, data: Dict) -> Dict:
        """
        Create a new program.

        Args:
            data: Program data dictionary

        Returns:
            Created program dictionary with generated ID
        """
        ...

    def update(self, program_id: str, data: Dict) -> Dict:
        """
        Update an existing program.

        Args:
            program_id: The program's UUID as string
            data: Updated program data

        Returns:
            Updated program dictionary
        """
        ...

    def delete(self, program_id: str) -> bool:
        """
        Delete a program.

        Args:
            program_id: The program's UUID as string

        Returns:
            True if deleted, False if not found
        """
        ...

    def get_weeks(self, program_id: str) -> List[Dict]:
        """
        Get all weeks for a program.

        Args:
            program_id: The program's UUID as string

        Returns:
            List of week dictionaries with workouts
        """
        ...

    def create_week(self, program_id: str, data: Dict) -> Dict:
        """
        Create a new week in a program.

        Args:
            program_id: The program's UUID as string
            data: Week data dictionary

        Returns:
            Created week dictionary
        """
        ...

    def create_workout(self, week_id: str, data: Dict) -> Dict:
        """
        Create a new workout in a week.

        Args:
            week_id: The week's UUID as string
            data: Workout data dictionary

        Returns:
            Created workout dictionary
        """
        ...

    def create_program_atomic(
        self,
        program_data: Dict,
        weeks_data: List[Dict],
    ) -> Dict:
        """
        Create a program with all weeks and workouts atomically.

        This method creates the program, weeks, and workouts in a single
        database transaction. If any insert fails, the entire operation
        is rolled back, preventing orphaned records.

        Args:
            program_data: Program data dictionary
            weeks_data: List of week dictionaries, each containing a "workouts" key
                        with a list of workout dictionaries

        Returns:
            Dictionary with created IDs:
            {
                "program": {"id": <program_uuid>},
                "weeks": [<week_uuid>, ...],
                "workouts": [<workout_uuid>, ...]
            }

        Raises:
            ProgramCreationError: If the atomic creation fails
        """
        ...
