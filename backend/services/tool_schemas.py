"""
Tool Schemas for AI Agent Tools.

Part of AMA-568: search_workouts tool ignores `query` parameter

Defines the schemas for tools that AI agents (like Claude) can call,
including the search_workouts tool which now properly utilizes the query parameter.
"""

from typing import Any, Dict, List, Optional


# Tool schema for search_workouts - defines what parameters the tool accepts
SEARCH_WORKOUTS_SCHEMA = {
    "name": "search_workouts",
    "description": "Search for workouts in the user's library. Supports semantic (AI-powered) and keyword search. Use natural language queries like 'upper body dumbbells' or '30 minute cardio'.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query (e.g., 'upper body dumbbells', 'HIIT cardio', 'leg day'). This query is used for semantic similarity search against workout titles and descriptions."
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 10
            },
            "workout_type": {
                "type": "string",
                "description": "Filter by workout type (e.g., 'strength', 'cardio', 'hiit')"
            },
            "min_duration": {
                "type": "integer",
                "description": "Minimum workout duration in minutes"
            },
            "max_duration": {
                "type": "integer",
                "description": "Maximum workout duration in minutes"
            }
        },
        "required": ["query"]
    }
}


# Registry of all available tools
TOOL_SCHEMAS = [
    SEARCH_WORKOUTS_SCHEMA,
]


def get_tool_schema(tool_name: str) -> Optional[Dict[str, Any]]:
    """Get the schema for a specific tool by name."""
    for schema in TOOL_SCHEMAS:
        if schema["name"] == tool_name:
            return schema
    return None


def get_all_tool_schemas() -> List[Dict[str, Any]]:
    """Get all available tool schemas."""
    return TOOL_SCHEMAS
