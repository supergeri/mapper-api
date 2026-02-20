"""
Chat Service for SSE Streaming Chat API.

AMA-439: Core SSE Streaming Endpoint Implementation

Handles:
- Claude Sonnet 4.5 AI interactions via Helicone
- Session management (create/resume)
- Message persistence
- Rate limiting
- Tool execution
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, AsyncGenerator, Callable
from backend.services.tool_executor import ToolExecutor
from backend.services.tool_schemas import get_all_tool_schemas

logger = logging.getLogger(__name__)


# System prompt for fitness coach persona
FITNESS_COACH_SYSTEM_PROMPT = """You are FitCoach, a knowledgeable and encouraging fitness coach assistant. 

Your role is to help users with:
- Finding and recommending workouts from their library
- Explaining exercise techniques and proper form
- Creating personalized workout recommendations
- Answering fitness-related questions
- Motivating and supporting users on their fitness journey

You have access to the user's workout library and can search for workouts that match their goals and preferences.

Guidelines:
- Be encouraging and positive
- Provide specific, actionable recommendations
- Keep responses concise but informative
- If you don't know something, admit it and offer to help find the answer
- Always prioritize user safety - remind them to consult professionals for medical advice

When searching for workouts, use the search_workouts tool to find relevant workouts from the user's library."""


class ChatService:
    """Service for handling chat interactions with Claude AI."""

    def __init__(
        self,
        tool_executor: Optional[ToolExecutor] = None,
    ):
        """
        Initialize the chat service.

        Args:
            tool_executor: Optional tool executor for function calling
        """
        self.tool_executor = tool_executor

    def create_anthropic_client(
        self,
        user_id: str,
        session_id: Optional[str] = None,
    ) -> Any:
        """
        Create an Anthropic client for Claude interactions.

        Args:
            user_id: User ID for tracking
            session_id: Optional session ID for conversation continuity

        Returns:
            Configured Anthropic client
        """
        context = AIRequestContext(
            user_id=user_id,
            session_id=session_id,
            feature_name="chat_stream",
            custom_properties={"model": "claude-sonnet-4-5-20250514"},
        )
        return AIClientFactory.create_anthropic_client(context=context)

    async def stream_chat(
        self,
        user_id: str,
        session_id: Optional[str],
        message: str,
        context: Optional[Dict[str, Any]],
    ) -> AsyncGenerator[tuple[str, Dict[str, Any]], None]:
        """
        Stream a chat response from Claude with SSE events.

        Args:
            user_id: User ID
            session_id: Existing session ID or None for new session
            message: User's message
            context: Context information (current_page, selected_workout_id)

        Yields:
            Tuple of (event_type, event_data) for SSE events
        """
        # Generate IDs
        message_id = str(uuid.uuid4())
        
        # Create or use session ID
        if session_id is None:
            session_id = str(uuid.uuid4())
            logger.info(f"Created new chat session: {session_id} for user: {user_id}")
        else:
            logger.info(f"Resuming chat session: {session_id} for user: {user_id}")

        # Send message_start event
        yield "message_start", {
            "session_id": session_id,
            "message_id": message_id,
        }

        # Get conversation history for context
        conversation_history = self._get_conversation_history(session_id)

        # Build messages for Claude
        messages = self._build_messages(conversation_history, message, context)

        try:
            # Create Anthropic client
            client = self.create_anthropic_client(user_id, session_id)

            # Tool schemas for function calling
            tool_schemas = get_all_tool_schemas()

            # Stream the response
            content_buffer = ""
            
            with client.messages.stream(
                model="claude-sonnet-4-5-20250514",
                max_tokens=4096,
                system=FITNESS_COACH_SYSTEM_PROMPT,
                messages=messages,
                tools=tool_schemas if tool_schemas else [],
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            text = event.delta.text
                            content_buffer += text
                            yield "content_delta", {
                                "content": text,
                                "message_id": message_id,
                            }
                    
                    elif event.type == "tool_use":
                        # Claude wants to use a tool
                        tool_name = event.name
                        tool_input = event.input
                        
                        yield "function_call", {
                            "function_name": tool_name,
                            "parameters": tool_input,
                            "message_id": message_id,
                        }
                        
                        # Execute the tool
                        if self.tool_executor:
                            try:
                                result = self.tool_executor.execute_tool(
                                    tool_name=tool_name,
                                    parameters=tool_input,
                                    profile_id=user_id,
                                )
                            except Exception as e:
                                logger.error(f"Tool execution failed: {e}")
                                result = {"success": False, "error": "Tool execution failed"}
                        else:
                            result = {"success": False, "error": "Tool executor not configured"}
                        
                        yield "function_result", {
                            "function_name": tool_name,
                            "result": result,
                            "message_id": message_id,
                        }
                    
                    elif event.type == "message_stop":
                        break

        except Exception as e:
            logger.error(f"Error in chat streaming: {e}")
            error_type = "function_failed"
            retry_after = None
            
            # Check for rate limiting
            error_str = str(e).lower()
            if "rate limit" in error_str or "429" in error_str:
                error_type = "rate_limit_exceeded"
                retry_after = 60  # Default retry after 60 seconds
            
            # Sanitize error message to avoid leaking sensitive details
            error_message = "An error occurred while processing your request. Please try again."
            if error_type == "rate_limit_exceeded":
                error_message = "Rate limit exceeded. Please try again later."
            
            yield "error", {
                "error_type": error_type,
                "message": error_message,
                "retry_after": retry_after,
            }

        # Send message_end event
        yield "message_end", {
            "message_id": message_id,
        }

        # Persist the conversation
        self._persist_message(session_id, user_id, message, content_buffer)

    def _get_conversation_history(self, session_id: str) -> list:
        """Get conversation history for a session.
        
        In a full implementation, this would load from the database.
        For now, returns empty list for new sessions.
        """
        # TODO: Load from chat_messages table
        return []

    def _build_messages(
        self,
        conversation_history: list,
        current_message: str,
        context: Optional[Dict[str, Any]],
    ) -> list:
        """Build the messages array for Claude."""
        messages = []
        
        # Add conversation history
        for msg in conversation_history:
            messages.append(msg)
        
        # Add current message with context
        user_message = {
            "role": "user",
            "content": current_message,
        }
        
        # Add context if available
        if context:
            context_str = ""
            if context.get("current_page"):
                context_str += f"User is currently on the: {context['current_page']} page. "
            if context.get("selected_workout_id"):
                context_str += f"User has selected workout ID: {context['selected_workout_id']}. "
            
            if context_str:
                user_message["content"] = f"{context_str}\n\n{current_message}"
        
        messages.append(user_message)
        
        return messages

    def _persist_message(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        """Persist chat messages to database.
        
        In a full implementation, this would store to chat_messages table.
        """
        # TODO: Implement database persistence
        logger.info(f"Would persist message to session {session_id}: user='{user_message[:50]}...', assistant='{assistant_message[:50]}...'")


class RateLimiter:
    """Rate limiter for AI requests using ai_request_limits table."""
    
    def __init__(self):
        """Initialize the rate limiter."""
        pass

    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[int]]:
        """
        Check if user has exceeded rate limit.

        Args:
            user_id: User ID to check

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        # TODO: Implement actual rate limiting with ai_request_limits table
        # For now, allow all requests
        return True, None

    def increment_rate_limit(self, user_id: str) -> None:
        """Increment the rate limit counter for a user."""
        # TODO: Implement actual rate limit increment
        pass


def create_chat_service(tool_executor: Optional[ToolExecutor] = None) -> ChatService:
    """Create a ChatService instance."""
    return ChatService(tool_executor=tool_executor)
