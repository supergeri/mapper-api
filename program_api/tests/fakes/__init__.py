"""
Fake implementations for testing.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Added template, exercise, and LLM fakes

This package provides in-memory fake implementations of repository
interfaces for fast, isolated testing without database dependencies.
"""

from tests.fakes.exercise_repository import FakeExerciseRepository
from tests.fakes.llm_client import FailingExerciseSelector, FakeExerciseSelector
from tests.fakes.program_repository import FakeProgramRepository
from tests.fakes.template_repository import FakeTemplateRepository

__all__ = [
    "FakeExerciseRepository",
    "FakeExerciseSelector",
    "FailingExerciseSelector",
    "FakeProgramRepository",
    "FakeTemplateRepository",
]
