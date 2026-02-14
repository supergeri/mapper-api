"""
Pydantic models for bulk import API.

Request and response models for the 5-step bulk import workflow:
1. Detect - Parse sources and detect workout items
2. Map - Apply column mappings (for files)
3. Match - Match exercises to Garmin database
4. Preview - Generate preview of workouts
5. Execute - Execute the import

Part of AMA-591: Extract bulk import router from app.py
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class DetectedItem(BaseModel):
    """Detected item from file/URL/image parsing"""
    id: str
    source_index: int
    source_type: str
    source_ref: str
    raw_data: Dict[str, Any]
    parsed_title: Optional[str] = None
    parsed_exercise_count: Optional[int] = None
    parsed_block_count: Optional[int] = None
    confidence: float = 0
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class ColumnMapping(BaseModel):
    """Column mapping for file imports"""
    source_column: str
    source_column_index: int
    target_field: str
    confidence: float = 0
    user_override: bool = False
    sample_values: List[str] = []


class DetectedPattern(BaseModel):
    """Detected pattern in the data"""
    pattern_type: str
    regex: Optional[str] = None
    confidence: float = 0
    examples: List[str] = []
    count: int = 0


class ExerciseMatch(BaseModel):
    """Exercise matching result"""
    id: str
    original_name: str
    matched_garmin_name: Optional[str] = None
    confidence: float = 0
    suggestions: List[Dict[str, Any]] = []
    status: Literal["matched", "needs_review", "unmapped", "new"] = "unmapped"
    user_selection: Optional[str] = None
    source_workout_ids: List[str] = []
    occurrence_count: int = 1


class ValidationIssue(BaseModel):
    """Validation issue found during preview"""
    id: str
    severity: Literal["error", "warning", "info"]
    field: str
    message: str
    workout_id: Optional[str] = None
    exercise_name: Optional[str] = None
    suggestion: Optional[str] = None
    auto_fixable: bool = False


class PreviewWorkout(BaseModel):
    """Preview workout before import"""
    id: str
    detected_item_id: str
    title: str
    description: Optional[str] = None
    exercise_count: int = 0
    block_count: int = 0
    estimated_duration: Optional[int] = None
    validation_issues: List[ValidationIssue] = []
    workout: Dict[str, Any] = {}
    selected: bool = True
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None


class ImportStats(BaseModel):
    """Import statistics for preview"""
    total_detected: int = 0
    total_selected: int = 0
    total_skipped: int = 0
    exercises_matched: int = 0
    exercises_needing_review: int = 0
    exercises_unmapped: int = 0
    new_exercises_to_create: int = 0
    estimated_duration: int = 0
    duplicates_found: int = 0
    validation_errors: int = 0
    validation_warnings: int = 0


class ImportResult(BaseModel):
    """Import result for a single workout"""
    workout_id: str
    title: str
    status: Literal["success", "failed", "skipped"]
    error: Optional[str] = None
    saved_workout_id: Optional[str] = None
    export_formats: Optional[List[str]] = None


# ============================================================================
# API Request Models
# ============================================================================


class BulkDetectRequest(BaseModel):
    """Request to detect workout items from sources"""
    profile_id: str
    source_type: Literal["file", "urls", "images"]
    sources: List[str]  # URLs, file content (base64), or image data


class BulkMapRequest(BaseModel):
    """Request to apply column mappings"""
    job_id: str
    profile_id: str
    column_mappings: List[ColumnMapping]


class BulkMatchRequest(BaseModel):
    """Request to match exercises"""
    job_id: str
    profile_id: str
    user_mappings: Optional[Dict[str, str]] = None  # original_name -> selected_garmin_name


class BulkPreviewRequest(BaseModel):
    """Request to generate preview"""
    job_id: str
    profile_id: str
    selected_ids: List[str]


class BulkExecuteRequest(BaseModel):
    """Request to execute import"""
    job_id: str
    profile_id: str
    workout_ids: List[str]
    device: str
    async_mode: bool = True


# ============================================================================
# API Response Models
# ============================================================================


class BulkDetectResponse(BaseModel):
    """Response from detect endpoint"""
    success: bool
    job_id: str
    items: List[DetectedItem]
    metadata: Dict[str, Any] = {}
    total: int
    success_count: int
    error_count: int


class BulkMapResponse(BaseModel):
    """Response from map endpoint"""
    success: bool
    job_id: str
    mapped_count: int
    patterns: List[DetectedPattern] = []


class BulkMatchResponse(BaseModel):
    """Response from match endpoint"""
    success: bool
    job_id: str
    exercises: List[ExerciseMatch]
    total_exercises: int
    matched: int
    needs_review: int
    unmapped: int


class BulkPreviewResponse(BaseModel):
    """Response from preview endpoint"""
    success: bool
    job_id: str
    workouts: List[PreviewWorkout]
    stats: ImportStats


class BulkExecuteResponse(BaseModel):
    """Response from execute endpoint"""
    success: bool
    job_id: str
    status: str
    message: str


class BulkStatusResponse(BaseModel):
    """Response from status endpoint"""
    success: bool
    job_id: str
    status: str
    progress: int
    current_item: Optional[str] = None
    results: List[ImportResult] = []
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class BulkCancelResponse(BaseModel):
    """Response from cancel endpoint"""
    success: bool
    message: str
