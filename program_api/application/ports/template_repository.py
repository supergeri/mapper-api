"""
Template repository port (interface).

Part of AMA-462: Implement ProgramGenerator Service

This Protocol defines the contract for program template persistence operations.
Infrastructure implementations (e.g., Supabase) must satisfy this interface.
"""

from typing import Dict, List, Optional, Protocol


class TemplateRepository(Protocol):
    """
    Repository interface for program template persistence.

    Templates provide reusable structures for the hybrid template-guided
    LLM approach to program generation.
    """

    def get_by_id(self, template_id: str) -> Optional[Dict]:
        """
        Get a template by its ID.

        Args:
            template_id: The template's UUID as string

        Returns:
            Template dictionary if found, None otherwise
        """
        ...

    def get_by_criteria(
        self,
        goal: str,
        experience_level: str,
        sessions_per_week: Optional[int] = None,
        duration_weeks: Optional[int] = None,
    ) -> List[Dict]:
        """
        Find templates matching specified criteria.

        Args:
            goal: Training goal (strength, hypertrophy, etc.)
            experience_level: User experience level
            sessions_per_week: Optional filter for session count
            duration_weeks: Optional filter for duration

        Returns:
            List of matching template dictionaries, ordered by relevance
        """
        ...

    def get_system_templates(self) -> List[Dict]:
        """
        Get all system-provided templates.

        Returns:
            List of system template dictionaries
        """
        ...

    def get_user_templates(self, user_id: str) -> List[Dict]:
        """
        Get all templates created by a specific user.

        Args:
            user_id: The user's ID

        Returns:
            List of user template dictionaries
        """
        ...

    def create(self, data: Dict) -> Dict:
        """
        Create a new template.

        Args:
            data: Template data dictionary

        Returns:
            Created template dictionary with generated ID
        """
        ...

    def increment_usage_count(self, template_id: str) -> bool:
        """
        Increment the usage count for a template.

        Args:
            template_id: The template's UUID as string

        Returns:
            True if updated, False if not found
        """
        ...
