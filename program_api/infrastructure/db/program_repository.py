"""
Supabase implementation of ProgramRepository.

Part of AMA-461: Create program-api service scaffold

This implementation uses the Supabase Python client to interact with
the training_programs, program_weeks, and program_workouts tables
defined in AMA-460.
"""

import json
from typing import Dict, List, Optional

from supabase import Client

from application.exceptions import ProgramCreationError


class SupabaseProgramRepository:
    """
    Supabase-backed program repository implementation.

    Queries against:
    - training_programs: Main program metadata
    - program_weeks: Weekly structure within programs
    - program_workouts: Individual workouts within weeks
    """

    def __init__(self, client: Client):
        """
        Initialize repository with Supabase client.

        Args:
            client: Authenticated Supabase client
        """
        self._client = client

    def get_by_user(self, user_id: str) -> List[Dict]:
        """
        Get all programs for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of program dictionaries
        """
        response = (
            self._client.table("training_programs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        return response.data

    def get_by_id(self, program_id: str) -> Optional[Dict]:
        """
        Get a program by its ID.

        Args:
            program_id: The program's UUID as string

        Returns:
            Program dictionary if found, None otherwise
        """
        response = (
            self._client.table("training_programs")
            .select("*")
            .eq("id", program_id)
            .single()
            .execute()
        )
        return response.data if response.data else None

    def create(self, data: Dict) -> Dict:
        """
        Create a new program.

        Args:
            data: Program data dictionary

        Returns:
            Created program dictionary with generated ID
        """
        response = (
            self._client.table("training_programs")
            .insert(data)
            .execute()
        )
        return response.data[0]

    def update(self, program_id: str, data: Dict) -> Dict:
        """
        Update an existing program.

        Args:
            program_id: The program's UUID as string
            data: Updated program data

        Returns:
            Updated program dictionary
        """
        response = (
            self._client.table("training_programs")
            .update(data)
            .eq("id", program_id)
            .execute()
        )
        return response.data[0]

    def delete(self, program_id: str) -> bool:
        """
        Delete a program.

        Cascades to program_weeks and program_workouts via FK constraints.

        Args:
            program_id: The program's UUID as string

        Returns:
            True if deleted, False if not found
        """
        response = (
            self._client.table("training_programs")
            .delete()
            .eq("id", program_id)
            .execute()
        )
        return len(response.data) > 0

    def get_weeks(self, program_id: str) -> List[Dict]:
        """
        Get all weeks for a program with their workouts.

        Args:
            program_id: The program's UUID as string

        Returns:
            List of week dictionaries with nested workouts
        """
        # Get weeks
        weeks_response = (
            self._client.table("program_weeks")
            .select("*")
            .eq("program_id", program_id)
            .order("week_number")
            .execute()
        )
        weeks = weeks_response.data

        # Get workouts for each week
        for week in weeks:
            workouts_response = (
                self._client.table("program_workouts")
                .select("*")
                .eq("program_week_id", week["id"])
                .order("order_index")
                .execute()
            )
            week["workouts"] = workouts_response.data

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
        data["program_id"] = program_id
        response = (
            self._client.table("program_weeks")
            .insert(data)
            .execute()
        )
        return response.data[0]

    def create_workout(self, week_id: str, data: Dict) -> Dict:
        """
        Create a new workout in a week.

        Args:
            week_id: The week's UUID as string
            data: Workout data dictionary

        Returns:
            Created workout dictionary
        """
        data["program_week_id"] = week_id
        response = (
            self._client.table("program_workouts")
            .insert(data)
            .execute()
        )
        return response.data[0]

    def create_program_atomic(
        self,
        program_data: Dict,
        weeks_data: List[Dict],
    ) -> Dict:
        """
        Create a program with all weeks and workouts atomically.

        Uses a PostgreSQL stored procedure to ensure all inserts happen
        in a single transaction. If any insert fails, the entire operation
        is rolled back.

        Args:
            program_data: Program data dictionary
            weeks_data: List of week dictionaries, each containing a "workouts" key

        Returns:
            Dictionary with created IDs

        Raises:
            ProgramCreationError: If the RPC call fails
        """
        try:
            response = self._client.rpc(
                "create_program_with_weeks_workouts",
                {
                    "p_program": json.dumps(program_data),
                    "p_weeks": json.dumps(weeks_data),
                }
            ).execute()

            if response.data is None:
                raise ProgramCreationError("RPC returned no data")

            return response.data
        except Exception as e:
            if isinstance(e, ProgramCreationError):
                raise
            raise ProgramCreationError(f"Atomic program creation failed: {e}") from e
