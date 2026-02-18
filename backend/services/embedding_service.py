"""
Embedding Service for generating query embeddings via OpenAI.

Part of AMA-432: Semantic search endpoint for mapper-api
Part of AMA-423: Add AIRequestContext to All AI Call Sites for Full Observability
AMA-422: Migrated to AIClientFactory with Helicone support

Calls OpenAI's text-embedding-3-small model to convert natural language
queries into 1536-dimension embedding vectors for cosine similarity search.
"""

import logging
from typing import Optional

from backend.ai import AIClientFactory, AIRequestContext

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates text embeddings using OpenAI's embedding API."""

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        user_id: Optional[str] = None,
    ):
        """
 service.

        Note        Initialize the embedding: The api_key is obtained from settings via AIClientFactory.
        This parameter is deprecated and will be removed in a future version.

        Args:
            model: Embedding model to use (default: text-embedding-3-small)
            user_id: Optional user ID for tracking/observability
        """
        # Create context for Helicone tracking
        context = AIRequestContext(
            user_id=user_id,
            feature_name="embedding_generate",
            custom_properties={"model": model},
        )
        self._client = AIClientFactory.create_openai_client(context=context)
        self._model = model

    def generate_query_embedding(
        self,
        text: str,
        context: Optional[AIRequestContext] = None,
    ) -> list[float]:
        """
        Generate an embedding vector for the given text.

        Args:
            text: Natural language query text
            context: AI request context for observability (AMA-423)

        Returns:
            List of floats representing the embedding vector (1536 dimensions)

        Raises:
            Exception: If OpenAI API call fails
        """
        # Build extra headers from context for observability
        extra_body = {}
        if context:
            helicone_headers = context.to_helicone_headers()
            if helicone_headers:
                # Helicone uses 'properties' in extra body
                extra_body["properties"] = helicone_headers

        response = self._client.embeddings.create(
            input=text,
            model=self._model,
            extra_body=extra_body if extra_body else None,
        )
        return response.data[0].embedding
