"""
Embedding Service for generating query embeddings via OpenAI.

Part of AMA-432: Semantic search endpoint for mapper-api

Calls OpenAI's text-embedding-3-small model to convert natural language
queries into 1536-dimension embedding vectors for cosine similarity search.
"""

import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates text embeddings using OpenAI's embedding API."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def generate_query_embedding(self, text: str) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Natural language query text

        Returns:
            List of floats representing the embedding vector (1536 dimensions)

        Raises:
            Exception: If OpenAI API call fails
        """
        response = self._client.embeddings.create(
            input=text,
            model=self._model,
        )
        return response.data[0].embedding
