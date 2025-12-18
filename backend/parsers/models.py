"""
Parser Models

Pydantic models for the normalized workout schema that all parsers output to.
Based on AMA-101 requirements.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from enum import Enum


class ExerciseFlag(str, Enum):
    """Flags for special exercise types"""
    COMPLEX = "complex"       # Complex movements like "3+1", "4+4"
    DURATION = "duration"     # Duration-based like "60s", "30s"
    PERCENTAGE = "percentage" # Percentage weights like "70%", "@RPE8"
    WARMUP = "warmup"        # Warmup sets


class ParsedExercise(BaseModel):
    """Normalized exercise structure from any parser"""
    raw_name: str = Field(..., description="Original exercise name from source")
    order: str = Field(default="1", description="Order indicator: '1', '5a', '5b'")
    sets: int = Field(default=1, ge=1)
    reps: str = Field(default="1", description="Reps as string to preserve '3+1', '60s'")
    weight: Optional[str] = Field(default=None, description="Weight value")
    weight_unit: Optional[Literal["kg", "lbs"]] = None
    rpe: Optional[float] = Field(default=None, ge=1, le=10)
    notes: Optional[str] = None
    superset_group: Optional[str] = Field(default=None, description="Group ID for supersets")
    flags: List[ExerciseFlag] = Field(default_factory=list)

    # Additional metadata
    rest_seconds: Optional[int] = None
    tempo: Optional[str] = None  # e.g., "3010"

    class Config:
        use_enum_values = True


class ParsedWorkout(BaseModel):
    """Normalized workout structure from any parser"""
    name: str = Field(..., description="Workout name/title")
    date: Optional[str] = Field(default=None, description="ISO date string")
    week: Optional[str] = Field(default=None, description="Week identifier")
    day: Optional[str] = Field(default=None, description="Day identifier")
    description: Optional[str] = None
    exercises: List[ParsedExercise] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    # Source tracking
    source_sheet: Optional[str] = Field(default=None, description="Excel sheet name")
    source_row_start: Optional[int] = None
    source_row_end: Optional[int] = None


class DetectedPattern(BaseModel):
    """Pattern detected during parsing"""
    pattern_type: Literal[
        "superset_notation",
        "complex_movement",
        "duration_exercise",
        "percentage_weight",
        "warmup_sets",
        "header_row",
        "exercise_grouping"
    ]
    regex: Optional[str] = None
    confidence: float = Field(default=0, ge=0, le=100)
    examples: List[str] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class DetectedPatterns(BaseModel):
    """Collection of all detected patterns"""
    supersets: Optional[DetectedPattern] = None
    complex_movements: Optional[DetectedPattern] = None
    duration_exercises: Optional[DetectedPattern] = None
    percentage_weights: Optional[DetectedPattern] = None
    warmup_sets: Optional[DetectedPattern] = None


class ColumnInfo(BaseModel):
    """Information about a detected column"""
    index: int
    name: str
    sample_values: List[str] = Field(default_factory=list)
    detected_type: Optional[str] = None  # 'exercise', 'sets', 'reps', 'weight', etc.
    confidence: float = Field(default=0, ge=0, le=100)


class ParseResult(BaseModel):
    """Result from a parser"""
    success: bool = True
    workouts: List[ParsedWorkout] = Field(default_factory=list)
    patterns: DetectedPatterns = Field(default_factory=DetectedPatterns)
    columns: List[ColumnInfo] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)

    # Detection quality
    confidence: float = Field(default=0, ge=0, le=100)
    detected_format: Optional[str] = None  # 'strong_app', 'hevy', 'excel_multi_sheet', etc.

    # For multi-sheet Excel files
    sheet_names: List[str] = Field(default_factory=list)
    total_rows: int = 0
    header_row: Optional[int] = None

    # 1RM values if detected
    one_rep_maxes: Dict[str, float] = Field(default_factory=dict)


class FileInfo(BaseModel):
    """Information about the file being parsed"""
    filename: str
    extension: str
    size_bytes: int = 0
    content_type: Optional[str] = None
    encoding: Optional[str] = None
