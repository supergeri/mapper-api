"""
Embedding Service Interface (Port).

Part of AMA-432: Semantic search endpoint for mapper-api

Defines the abstract interface for generating text embeddings.
Implementations may use OpenAI, local models, or other backends.
"""

from typing import Protocol


class EmbeddingService(Protocol):
    """Abstract interface for text embedding generation."""

    def generate_query_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Natural language query text

        Returns:
            List of floats representing the embedding vector

        Raises:
            Exception: If embedding generation fails
        """
        ...
