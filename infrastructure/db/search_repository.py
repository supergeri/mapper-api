"""
Supabase Search Repository implementation.

Part of AMA-432: Semantic search endpoint for mapper-api

Implements semantic search via the match_workouts RPC function
and keyword fallback via ILIKE on title/description.
"""

import logging
from typing import Any

from supabase import Client

logger = logging.getLogger(__name__)


class SupabaseSearchRepository:
    """Supabase-backed implementation of SearchRepository."""

    def __init__(self, client: Client):
        self._client = client

    def semantic_search(
        self,
        profile_id: str,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """Search workouts by embedding similarity using match_workouts RPC."""
        result = self._client.rpc(
            "match_workouts",
            {
                "query_embedding": query_embedding,
                "match_threshold": threshold,
                "match_count": limit,
                "p_profile_id": profile_id,
            },
        ).execute()

        return result.data or []

    def keyword_search(
        self,
        profile_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Fallback text search using ILIKE on title and description."""
        sanitized = self._escape_ilike(query)
        pattern = f"%{sanitized}%"

        result = (
            self._client.table("workouts")
            .select("id, profile_id, title, description, workout_data, sources, created_at")
            .eq("profile_id", profile_id)
            .or_(f"title.ilike.{pattern},description.ilike.{pattern}")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return result.data or []

    @staticmethod
    def _escape_ilike(value: str) -> str:
        """Escape metacharacters in user input for safe use in PostgREST ILIKE filters.

        Backslash-escapes SQL ILIKE wildcards (``%``, ``_``, ``\\``) and strips
        PostgREST filter-syntax delimiters (``.`` and ``,``) to prevent filter
        injection via the ``.or_()`` method.
        """
        # Escape SQL ILIKE wildcards
        value = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        # Strip PostgREST filter delimiters that could inject additional clauses
        value = value.replace(",", " ").replace(".", " ")
        return value
