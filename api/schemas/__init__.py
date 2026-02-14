"""
Pydantic schemas for API requests and responses.

Organized by feature/domain:
- bulk_import: Bulk import workflow models
"""

from api.schemas.bulk_import import (
    BulkDetectRequest,
    BulkDetectResponse,
    BulkMapRequest,
    BulkMapResponse,
    BulkMatchRequest,
    BulkMatchResponse,
    BulkPreviewRequest,
    BulkPreviewResponse,
    BulkExecuteRequest,
    BulkExecuteResponse,
    BulkStatusResponse,
    ColumnMapping,
    DetectedItem,
    DetectedPattern,
    ExerciseMatch,
    ValidationIssue,
    PreviewWorkout,
    ImportStats,
    ImportResult,
)

__all__ = [
    "BulkDetectRequest",
    "BulkDetectResponse",
    "BulkMapRequest",
    "BulkMapResponse",
    "BulkMatchRequest",
    "BulkMatchResponse",
    "BulkPreviewRequest",
    "BulkPreviewResponse",
    "BulkExecuteRequest",
    "BulkExecuteResponse",
    "BulkStatusResponse",
    "ColumnMapping",
    "DetectedItem",
    "DetectedPattern",
    "ExerciseMatch",
    "ValidationIssue",
    "PreviewWorkout",
    "ImportStats",
    "ImportResult",
]
