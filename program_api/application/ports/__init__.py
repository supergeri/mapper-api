"""
Port interfaces (Protocols) for program-api.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Added template and exercise repositories

This package defines the interface contracts that the infrastructure
layer must implement. Using Protocols enables:
- Clean separation of concerns
- Easy testing with mock implementations
- Dependency inversion (depend on abstractions, not concretions)
"""

from application.ports.exercise_repository import ExerciseRepository
from application.ports.program_repository import ProgramRepository
from application.ports.template_repository import TemplateRepository

__all__ = [
    "ExerciseRepository",
    "ProgramRepository",
    "TemplateRepository",
]
