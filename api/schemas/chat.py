"""
Chat Schemas for SSE Streaming Chat API.

AMA-439: Core SSE Streaming Endpoint Implementation

Schemas for:
- ChatStreamRequest: Request body for POST /chat/stream
- SSE Events: Different event types for Server-Sent Events
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field


class ChatContext(BaseModel):
    """Context information for the chat request."""
    current_page: Optional[str] = Field(
        default=None,
        description="Current page the user is on (e.g., 'workouts', 'programs', 'settings')"
    )
    selected_workout_id: Optional[str] = Field(
        default=None,
        description="ID of the currently selected workout, if any"
    )


class ChatStreamRequest(BaseModel):
    """Request body for POST /chat/stream."""
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session ID to resume. Null creates a new session.",
        min_length=1,
        max_length=64,
        pattern=r"^[a-zA-Z0-9\-_]+$",
    )
    message: str = Field(
        ...,
        description="User's message to the AI assistant",
        min_length=1,
        max_length=10000,
    )
    context: Optional[ChatContext] = Field(
        default=None,
        description="Context information about the user's current state"
    )


class SSEMessageStart(BaseModel):
    """SSE event: message_start"""
    session_id: str
    message_id: str


class SSEContentDelta(BaseModel):
    """SSE event: content_delta"""
    content: str
    message_id: str


class SSEFunctionCall(BaseModel):
    """SSE event: function_call"""
    function_name: str
    parameters: Dict[str, Any]
    message_id: str


class SSEFunctionResult(BaseModel):
    """SSE event: function_result"""
    function_name: str
    result: Dict[str, Any]
    message_id: str


class SSEMessageEnd(BaseModel):
    """SSE event: message_end"""
    message_id: str


class SSEError(BaseModel):
    """SSE event: error"""
    error_type: str
    message: str
    retry_after: Optional[int] = Field(
        default=None,
        description="Seconds to wait before retrying (for rate limit errors)"
    )


def format_sse_event(event_type: str, data: Dict[str, Any]) -> str:
    """Format a dictionary as an SSE event string.
    
    Args:
        event_type: The SSE event type (e.g., 'message_start', 'content_delta')
        data: The event data as a dictionary
        
    Returns:
        Properly formatted SSE string with event type and data
    """
    import json
    json_data = json.dumps(data)
    return f"event: {event_type}\ndata: {json_data}\n\n"
