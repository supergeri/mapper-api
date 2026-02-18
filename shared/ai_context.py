"""
AI Request Context for tracking metadata in AI API calls.

This module provides the AIRequestContext dataclass that should be passed
to all AI API calls for observability in tools like Helicone.

Usage:
    from shared.ai_context import AIRequestContext
    
    context = AIRequestContext(
        user_id="user_123",
        feature_name="workout_import",
        session_id="session_456",
        environment="production"
    )
    
    # Pass to services
    embedding_service.generate_query_embedding("query", context=context)
"""

from dataclasses import dataclass, field
from typing import Optional


VALID_ENVIRONMENTS = {"production", "staging", "dev", "development", "test"}


@dataclass
class AIRequestContext:
    """
    Context to attach to AI API calls for tracking and observability.
    
    This enables:
    - Per-user cost attribution (user_id)
    - Feature cost breakdown (feature_name)
    - Session grouping (session_id)
    - Environment tracking (environment)
    
    Args:
        user_id: The user making the request (for cost attribution)
        feature_name: The feature triggering the AI call (for cost breakdown)
        session_id: Optional session identifier (for grouping requests)
        environment: Deployment environment (production, staging, dev)
        extra: Additional metadata key-value pairs
    """
    user_id: Optional[str] = None
    feature_name: Optional[str] = None
    session_id: Optional[str] = None
    environment: str = "production"
    extra: dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate context after initialization."""
        # Validate environment
        if self.environment not in VALID_ENVIRONMENTS:
            raise ValueError(
                f"Invalid environment '{self.environment}'. "
                f"Must be one of: {', '.join(sorted(VALID_ENVIRONMENTS))}"
            )
        
        # Validate user_id is non-empty if provided
        if self.user_id is not None and not self.user_id:
            raise ValueError("user_id must be a non-empty string if provided")
        
        # Validate feature_name is non-empty if provided
        if self.feature_name is not None and not self.feature_name:
            raise ValueError("feature_name must be a non-empty string if provided")
    
    def to_dict(self) -> dict:
        """Convert context to dictionary for API headers."""
        result = {
            "environment": self.environment,
        }
        if self.user_id:
            result["user_id"] = self.user_id
        if self.feature_name:
            result["feature_name"] = self.feature_name
        if self.session_id:
            result["session_id"] = self.session_id
        if self.extra:
            result.update(self.extra)
        return result
    
    def to_helicone_headers(self) -> dict:
        """
        Convert to Helicone-compatible headers.
        
        Helicone supports these properties:
        https://docs.helicone.ai/getting-started/concepts#properties
        """
        properties = self.to_dict()
        
        # Map to Helicone's expected property names
        helicone_props = {}
        if "user_id" in properties:
            helicone_props["user_id"] = properties["user_id"]
        if "feature_name" in properties:
            helicone_props["feature_name"] = properties["feature_name"]
        if "session_id" in properties:
            helicone_props["session_id"] = properties["session_id"]
        if "environment" in properties:
            helicone_props["environment"] = properties["environment"]
            
        return helicone_props


# Default context for when no context is provided
DEFAULT_AI_CONTEXT = AIRequestContext(
    feature_name="unknown",
    environment="production"
)
