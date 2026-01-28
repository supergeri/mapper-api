"""
Search Repository Interface (Port).

Part of AMA-432: Semantic search endpoint for mapper-api

Defines the abstract interface for workout search operations including
semantic (embedding-based) and keyword (text-based) search.
"""

from typing import Protocol, Any


class SearchRepository(Protocol):
    """Abstract interface for workout search operations."""

    def semantic_search(
        self,
        profile_id: str,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Search workouts by embedding similarity.

        Args:
            profile_id: User profile ID to scope results
            query_embedding: Query embedding vector (1536 dimensions)
            limit: Maximum number of results
            threshold: Minimum cosine similarity threshold (0-1)

        Returns:
            List of workout dicts with similarity scores
        """
        ...

    def keyword_search(
        self,
        profile_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Fallback text search using ILIKE on title and description.

        Args:
            profile_id: User profile ID to scope results
            query: Search query string
            limit: Maximum number of results

        Returns:
            List of matching workout dicts
        """
        ...
