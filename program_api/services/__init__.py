"""
Services package for program-api.

Part of AMA-461: Create program-api service scaffold
Updated in AMA-462: Added template selector, program validator, LLM integration
Updated in AMA-463: Added TrainingFocus enum and rep range calculations
Updated in AMA-472: Added ExerciseSelector for intelligent exercise selection

Contains business logic services for:
- Program generation (AI-powered hybrid template + LLM approach)
- Periodization planning (5 periodization models)
- Template selection and matching
- Program validation (safety and quality)
- Progression tracking
- Exercise selection (intelligent fallback)
"""

from services.exercise_selector import (
    EQUIPMENT_MAPPING,
    ExerciseCandidate,
    ExerciseSelector,
    SlotRequirements,
)
from services.periodization import (
    BlockPhase,
    EffortType,
    PeriodizationModel,
    PeriodizationService,
    TrainingFocus,
    WeekParameters,
)
from services.program_generator import ProgramGenerationError, ProgramGenerator
from services.program_validator import (
    ProgramValidator,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from services.progression_engine import ProgressionEngine
from services.template_selector import TemplateMatch, TemplateSelector

__all__ = [
    # Exercise Selection
    "EQUIPMENT_MAPPING",
    "ExerciseCandidate",
    "ExerciseSelector",
    "SlotRequirements",
    # Periodization
    "BlockPhase",
    "EffortType",
    "PeriodizationModel",
    "PeriodizationService",
    "TrainingFocus",
    "WeekParameters",
    # Program Generation
    "ProgramGenerationError",
    "ProgramGenerator",
    # Validation
    "ProgramValidator",
    "ValidationIssue",
    "ValidationResult",
    "ValidationSeverity",
    # Progression
    "ProgressionEngine",
    # Templates
    "TemplateMatch",
    "TemplateSelector",
]
