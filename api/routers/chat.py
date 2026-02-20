"""
Chat Router for SSE Streaming Chat API.

AMA-439: Core SSE Streaming Endpoint Implementation

Endpoints:
- POST /chat/stream - SSE stream for chat with Claude

This endpoint provides real-time streaming responses from Claude Sonnet 4.5
with support for function calling and tool execution.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.deps import get_current_user
from api.schemas.chat import ChatStreamRequest, format_sse_event
from backend.services.chat_service import create_chat_service, RateLimiter
from backend.services.tool_executor import create_tool_executor

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Chat"],
)

# Initialize rate limiter
rate_limiter = RateLimiter()


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatStreamRequest,
    http_request: Request,
    user_id: str = Depends(get_current_user),
) -> StreamingResponse:
    """
    Stream chat responses from Claude AI with SSE.

    This endpoint provides real-time streaming responses from Claude Sonnet 4.5,
    including:
    - message_start: Sent when message processing begins
    - content_delta: Streaming text content as it arrives
    - function_call: When Claude wants to call a tool
    - function_result: Results from tool execution
    - message_end: When the response is complete
    - error: Error events (including rate_limit_exceeded)

    Request Body:
        - session_id: Existing session ID to resume, or null for new session
        - message: User's message to the AI assistant
        - context: Optional context (current_page, selected_workout_id)

    SSE Events:
        - message_start: {session_id, message_id}
        - content_delta: {content, message_id} (streaming text)
        - function_call: {function_name, parameters, message_id}
        - function_result: {function_name, result, message_id}
        - message_end: {message_id}
        - error: {error_type, message, retry_after?}

    Args:
        request: Chat request with session_id, message, and context
        http_request: FastAPI request object
        user_id: Authenticated user ID (from Clerk JWT)

    Returns:
        StreamingResponse with SSE format
    """
    # Check rate limit before processing
    is_allowed, retry_after = rate_limiter.check_rate_limit(user_id)
    if not is_allowed:
        # Return error event for rate limit exceeded
        async def rate_limit_error_stream():
            yield format_sse_event("error", {
                "error_type": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please try again later.",
                "retry_after": retry_after or 60,
            })
        
        return StreamingResponse(
            rate_limit_error_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    # Create chat service with tool executor
    # Note: In production, these would be injected via dependencies
    tool_executor = None
    search_repo = None
    embedding_service = None
    try:
        from api.deps import get_search_repo, get_embedding_service
        search_repo = get_search_repo()
        embedding_service = get_embedding_service()
        tool_executor = create_tool_executor(search_repo, embedding_service)
    except ImportError as e:
        logger.warning(f"Tool executor dependencies not available: {e}")
    except ConnectionError as e:
        logger.warning(f"Tool executor connection failed: {e}")
    except Exception as e:
        logger.error(f"Unexpected error initializing tool executor: {e}")

    chat_service = create_chat_service(tool_executor)

    # Context data from request
    context_data = None
    if request.context:
        context_data = {
            "current_page": request.context.current_page,
            "selected_workout_id": request.context.selected_workout_id,
        }

    async def event_stream():
        """Generate SSE events for the chat response."""
        
        # Process the chat and stream response
        try:
            async for event_type, event_data in chat_service.stream_chat(
                user_id=user_id,
                session_id=request.session_id,
                message=request.message,
                context=context_data,
            ):
                yield format_sse_event(event_type, event_data)
            
            # Increment rate limit on success
            rate_limiter.increment_rate_limit(user_id)
            
            logger.info(f"Chat stream completed for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error in chat stream: {e}")
            # Sanitize error message
            error_message = "An error occurred while processing your request. Please try again."
            yield format_sse_event("error", {
                "error_type": "function_failed",
                "message": error_message,
            })

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
