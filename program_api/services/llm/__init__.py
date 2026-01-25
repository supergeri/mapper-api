"""
LLM integration module for program-api.

Part of AMA-462: Implement ProgramGenerator Service

This module provides LLM-powered exercise selection for the hybrid
template-guided program generation approach.
"""

from services.llm.client import OpenAIExerciseSelector
from services.llm.schemas import (
    ExerciseSelection,
    ExerciseSelectionRequest,
    ExerciseSelectionResponse,
)

__all__ = [
    "OpenAIExerciseSelector",
    "ExerciseSelection",
    "ExerciseSelectionRequest",
    "ExerciseSelectionResponse",
]
