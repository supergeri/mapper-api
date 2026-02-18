"""
Tool Executor Service for AI Agent Tools.

Part of AMA-568: search_workouts tool ignores `query` parameter

Implements the execution logic for tools that AI agents (like Claude) can call.
The search_workouts tool now properly utilizes the query parameter for semantic
or keyword search, instead of ignoring it.

This fixes the issue where natural language queries like 'upper body dumbbells'
were being silently ignored.
"""

import logging
from typing import Any, Optional

from application.ports import SearchRepository, EmbeddingService

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    Executes AI agent tools with proper parameter handling.

    This service handles tool execution for AI agents like Claude,
    providing a bridge between the AI's natural language queries and
    the underlying search functionality.
    """

    def __init__(
        self,
        search_repository: SearchRepository,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        """
        Initialize the tool executor.

        Args:
            search_repository: Repository for workout search operations
            embedding_service: Optional service for generating query embeddings
                             (enables semantic search when available)
        """
        self.search_repo = search_repository
        self.embedding_service = embedding_service

    def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        profile_id: str = "",
    ) -> dict[str, Any]:
        """
        Execute a tool by name with the given parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            profile_id: User profile ID to scope results

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool_name is not recognized
        """
        if tool_name == "search_workouts":
            return self._search_workouts(parameters, profile_id=profile_id)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _search_workouts(self, params: dict[str, Any], profile_id: str = "") -> dict[str, Any]:
        """
        Search for workouts based on query and filters.

        This handler properly utilizes the query parameter for search,
        addressing AMA-568 where queries were previously ignored.

        Args:
            params: Search parameters including:
                - query: Natural language search query (REQUIRED)
                - limit: Max results (default: 10)
                - workout_type: Filter by workout type
                - min_duration: Minimum duration in minutes
                - max_duration: Maximum duration in minutes
            profile_id: User profile ID to scope results

        Returns:
            Search results with workout details

        Raises:
            ValueError: If required parameters are missing
        """
        # Extract parameters - query is required
        query = params.get("query")
        if not query:
            raise ValueError("search_workouts tool requires 'query' parameter")

        limit = params.get("limit", 10)
        workout_type = params.get("workout_type")
        min_duration = params.get("min_duration")
        max_duration = params.get("max_duration")

        logger.info(f"Executing search_workouts with query: '{query}'")

        # Try semantic search first if embedding service is available
        results = []
        search_type = "keyword"  # default

        if self.embedding_service is not None:
            try:
                # Generate embedding from the query string
                query_embedding = self.embedding_service.generate_query_embedding(query)

                # Perform semantic search using the query parameter
                # Fetch more results to account for filtering
                raw_results = self.search_repo.semantic_search(
                    profile_id=profile_id,
                    query_embedding=query_embedding,
                    limit=limit * 2,  # Fetch extra to handle filters
                    threshold=0.5,
                )
                search_type = "semantic"
                results = raw_results

            except Exception as e:
                logger.warning(f"Semantic search failed, falling back to keyword search: {e}")
                search_type = "keyword_fallback"

        # If no results from semantic search (or it failed), use keyword search
        if not results:
            results = self.search_repo.keyword_search(
                profile_id=profile_id,
                query=query,
                limit=limit * 2,  # Fetch extra to handle filters
            )

        # Apply filters BEFORE limiting to ensure consistent pagination
        if workout_type:
            results = [r for r in results if self._matches_workout_type(r, workout_type)]

        if min_duration is not None or max_duration is not None:
            results = [r for r in results if self._matches_duration(r, min_duration, max_duration)]

        # Apply limit AFTER filtering
        results = results[:limit]

        # Format results for AI agent consumption
        formatted_results = []
        for row in results:
            created_at = row.get("created_at")
            formatted_results.append({
                "workout_id": str(row.get("id", "")),
                "title": row.get("title"),
                "description": row.get("description"),
                "sources": row.get("sources") or [],
                "similarity_score": row.get("similarity"),
                "created_at": str(created_at) if created_at else None,
            })

        return {
            "success": True,
            "results": formatted_results,
            "count": len(formatted_results),
            "query": query,
            "search_type": search_type,
        }

    def _matches_workout_type(self, row: dict, workout_type: str) -> bool:
        """Check if a workout row matches the given workout type filter."""
        workout_data = row.get("workout_data") or {}
        wtype = workout_data.get("type") or workout_data.get("workout_type") or ""
        return wtype.lower() == workout_type.lower()

    def _matches_duration(
        self,
        row: dict,
        min_duration: Optional[int],
        max_duration: Optional[int]
    ) -> bool:
        """Check if a workout row matches duration filters (in minutes)."""
        workout_data = row.get("workout_data") or {}
        duration = workout_data.get("duration")
        if duration is None:
            duration = workout_data.get("duration_minutes")
        if duration is None:
            # If no duration info, include in results
            return True
        if min_duration is not None and duration < min_duration:
            return False
        if max_duration is not None and duration > max_duration:
            return False
        return True


# Factory function for creating executor (can be used with dependency injection)
def create_tool_executor(
    search_repo: SearchRepository,
    embedding_service: Optional[EmbeddingService] = None,
) -> ToolExecutor:
    """
    Create a ToolExecutor instance.

    This can be used with FastAPI dependency injection.

    Args:
        search_repo: Search repository instance
        embedding_service: Optional embedding service

    Returns:
        Configured ToolExecutor instance
    """
    return ToolExecutor(
        search_repository=search_repo,
        embedding_service=embedding_service,
    )
