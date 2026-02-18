"""
Fake SearchRepository Implementation for Testing.

Part of AMA-366: Add in-memory fake repositories for tests

This module provides an in-memory fake implementation of SearchRepository
for testing search functionality without a Supabase database.
"""

from typing import Any, List, Optional

from application.ports.search_repository import SearchRepository


class FakeSearchRepository:
    """
    In-memory fake implementation of SearchRepository.
    
    Supports both semantic search (by embedding) and keyword search
    for testing without a real database.
    
    Attributes:
        semantic_search_calls: Log of semantic_search calls for assertion
        keyword_search_calls: Log of keyword_search calls for assertion
    """
    
    def __init__(
        self,
        semantic_results: Optional[List[dict[str, Any]]] = None,
        keyword_results: Optional[List[dict[str, Any]]] = None,
    ):
        """
        Initialize FakeSearchRepository.
        
        Args:
            semantic_results: Results to return from semantic_search
            keyword_results: Results to return from keyword_search
        """
        self._semantic_results = semantic_results or []
        self._keyword_results = keyword_results or []
        self.semantic_search_calls: List[dict[str, Any]] = []
        self.keyword_search_calls: List[dict[str, Any]] = []
    
    def semantic_search(
        self,
        profile_id: str,
        query_embedding: list[float],
        limit: int = 10,
        threshold: float = 0.5,
    ) -> list[dict[str, Any]]:
        """
        Return predefined semantic search results.
        
        Args:
            profile_id: User profile ID (logged but not validated)
            query_embedding: Query embedding vector (logged but not used)
            limit: Maximum results to return
            threshold: Minimum similarity threshold (not applied in fake)
            
        Returns:
            List of workout dicts
        """
        self.semantic_search_calls.append({
            "profile_id": profile_id,
            "query_embedding": query_embedding,
            "limit": limit,
            "threshold": threshold,
        })
        return self._semantic_results[:limit]
    
    def keyword_search(
        self,
        profile_id: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return predefined keyword search results.
        
        Args:
            profile_id: User profile ID (logged but not validated)
            query: Search query string (logged but not used)
            limit: Maximum results to return
            
        Returns:
            List of workout dicts
        """
        self.keyword_search_calls.append({
            "profile_id": profile_id,
            "query": query,
            "limit": limit,
        })
        return self._keyword_results[:limit]
    
    def set_semantic_results(
        self,
        results: List[dict[str, Any]],
    ) -> None:
        """
        Set results for subsequent semantic_search calls.
        
        Args:
            results: List of workout dicts to return
        """
        self._semantic_results = results
    
    def set_keyword_results(
        self,
        results: List[dict[str, Any]],
    ) -> None:
        """
        Set results for subsequent keyword_search calls.
        
        Args:
            results: List of workout dicts to return
        """
        self._keyword_results = results
    
    def reset_calls(self) -> None:
        """Clear call history."""
        self.semantic_search_calls.clear()
        self.keyword_search_calls.clear()
    
    def reset_all(self) -> None:
        """Clear results and call history."""
        self._semantic_results.clear()
        self._keyword_results.clear()
        self.reset_calls()


# =============================================================================
# Protocol Compliance Verification
# =============================================================================

# This import verifies FakeSearchRepository implements SearchRepository
def _verify_protocol() -> SearchRepository:
    """Verify FakeSearchRepository conforms to SearchRepository protocol."""
    return FakeSearchRepository()


__all__ = ["FakeSearchRepository"]
