"""
Database infrastructure package.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Added template and exercise repositories
"""

from infrastructure.db.exercise_repository import SupabaseExerciseRepository
from infrastructure.db.program_repository import SupabaseProgramRepository
from infrastructure.db.template_repository import SupabaseTemplateRepository

__all__ = [
    "SupabaseExerciseRepository",
    "SupabaseProgramRepository",
    "SupabaseTemplateRepository",
]
