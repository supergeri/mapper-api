"""Workouts router for workout CRUD and library management.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-381: Move workout CRUD endpoints from app.py
Updated in AMA-383: Move completion endpoints to routers/completions.py
Updated in AMA-388: Refactor to use dependency injection for repositories
Updated in AMA-394: Refactor to call SaveWorkoutUseCase
Updated in AMA-433: Add PATCH /workouts/{id} endpoint for JSON Patch operations

This router contains endpoints for:
- /workouts/save - Save workout to database
- /workouts - List user workouts
- /workouts/incoming - Get incoming (pending) workouts
- /workouts/{workout_id} - Get, delete, patch workout
- /workouts/{workout_id}/export-status - Update export status
- /workouts/{workout_id}/favorite - Toggle favorite
- /workouts/{workout_id}/used - Track usage
- /workouts/{workout_id}/tags - Update tags

Note: Completion endpoints (/workouts/complete, /workouts/completions) are in
api/routers/completions.py and must be registered BEFORE this router.
"""
from __future__ import annotations

import logging
import time
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Query, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import (
    get_current_user,
    get_save_workout_use_case,
    get_get_workout_use_case,
    get_patch_workout_use_case,
    get_search_repo,
    get_embedding_service,
    get_export_queue,
)
from application.ports import SearchRepository, EmbeddingService
from application.use_cases import SaveWorkoutUseCase, GetWorkoutUseCase
from application.use_cases.patch_workout import PatchWorkoutUseCase
from domain.models.patch_operation import PatchOperation
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from domain.converters.blocks_to_workout import blocks_to_workout
from domain.models import WorkoutMetadata, WorkoutSource
from backend.services.export_queue import ExportQueue
from backend.utils.intervals import calculate_intervals_duration, convert_exercise_to_interval

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Workouts"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class SaveWorkoutRequest(BaseModel):
    """Request for saving a workout."""
    profile_id: Optional[str] = None  # Deprecated: use auth instead
    workout_data: WorkoutData
    sources: List[str] = []
    device: str
    exports: Optional[dict] = None
    validation: Optional[dict] = None
    title: Optional[str] = None
    description: Optional[str] = None
    workout_id: Optional[str] = None  # Optional: for explicit updates to existing workouts


class WorkoutData(BaseModel):
    """Schema validation for workout_data structure.

    Provides type safety for workout data submitted via API.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    duration: Optional[int] = None
    duration_minutes: Optional[int] = None
    type: Optional[str] = None
    workout_type: Optional[str] = None
    blocks: Optional[List[dict]] = []
    intervals: Optional[List[dict]] = []
    metadata: Optional[dict] = None


class SearchResultItem(BaseModel):
    """A single search result item."""
    workout_id: str
    title: str | None = None
    description: str | None = None
    sources: list[str] = []
    similarity_score: float | None = None
    created_at: str | None = None


class SearchResponse(BaseModel):
    """Response model for workout search.

    Note: ``count`` is the number of results returned on this page after
    filters and pagination are applied. It is **not** the total number of
    matching workouts in the database.
    """
    success: bool = True
    results: list[SearchResultItem] = []
    count: int = 0
    query: str
    search_type: Literal["semantic", "keyword", "error"]
    query_embedding_time_ms: int | None = None
    search_time_ms: int | None = None


class UpdateWorkoutExportRequest(BaseModel):
    """Request for updating workout export status."""
    profile_id: str | None = None  # Deprecated: use auth instead
    is_exported: bool = True
    exported_to_device: str | None = None


class ToggleFavoriteRequest(BaseModel):
    """Request for toggling workout favorite status."""
    profile_id: str
    is_favorite: bool


class TrackUsageRequest(BaseModel):
    """Request for tracking workout usage."""
    profile_id: str


class GenerateWorkoutRequest(BaseModel):
    """Request body for the workout generation endpoint."""

    description: str = Field(..., min_length=1, max_length=5000)


class UpdateTagsRequest(BaseModel):
    """Request for updating workout tags."""
    profile_id: str
    tags: List[str]


class PatchWorkoutRequest(BaseModel):
    """Request for patching a workout with JSON Patch operations.

    Part of AMA-433: PATCH /workouts/{id} endpoint implementation.
    """
    operations: List[PatchOperation] = Field(
        ...,
        min_length=1,
        description="List of JSON Patch operations to apply",
        json_schema_extra={
            "example": [
                {"op": "replace", "path": "/title", "value": "Updated Title"},
                {"op": "add", "path": "/tags/-", "value": "strength"},
            ]
        },
    )


class ImportFromURLRequest(BaseModel):
    """Request body for the URL import endpoint."""

    url: str


class PatchWorkoutResponse(BaseModel):
    """Response for patch workout endpoint."""
    success: bool = True
    workout: dict | None = None
    changes_applied: int = 0
    embedding_regeneration: str = "none"


class PatchWorkoutErrorResponse(BaseModel):
    """Error response for patch workout endpoint."""
    detail: dict = Field(
        ...,
        json_schema_extra={
            "example": {
                "message": "Patch operation failed",
                "validation_errors": ["Invalid path: /exercises/99"],
            }
        },
    )


class SaveWorkoutResponse(BaseModel):
    """Response model for save workout endpoint."""
    success: bool = True
    workout_id: str | None = None
    message: str
    is_update: bool = False


class WorkoutListResponse(BaseModel):
    """Response model for list workouts endpoint."""
    success: bool = True
    workouts: list[dict]
    count: int


class WorkoutResponse(BaseModel):
    """Response model for single workout endpoint."""
    success: bool = True
    workout: dict | None = None


class WorkoutOperationResponse(BaseModel):
    """Response model for workout delete/operation endpoints."""
    success: bool = True
    message: str
    workout: dict | None = None


# =============================================================================
# Helper Functions
# =============================================================================


# =============================================================================
# Workout CRUD Endpoints
# =============================================================================


@router.post("/workouts/save")
def save_workout_endpoint(
    request: SaveWorkoutRequest,
    user_id: str = Depends(get_current_user),
    save_workout_use_case: SaveWorkoutUseCase = Depends(get_save_workout_use_case),
    export_queue: ExportQueue = Depends(get_export_queue),
):
    """Save a workout to database before syncing to device.

    With deduplication: if a workout with the same profile_id, title, and device
    already exists, it will be updated instead of creating a duplicate.

    Delegates business logic to SaveWorkoutUseCase and queues for export.
    """
    try:
        # Step 1: Convert HTTP request to domain model
        workout_data = request.workout_data.copy()

        # Apply title/description overrides if provided
        if request.title:
            workout_data["title"] = request.title
        if request.description:
            workout_data["description"] = request.description

        # Parse sources to WorkoutSource enum
        sources = []
        for src in request.sources:
            try:
                sources.append(WorkoutSource(src))
            except ValueError:
                pass

        # Add metadata to workout_data for converter
        workout_data["metadata"] = workout_data.get("metadata", {})
        workout_data["metadata"]["sources"] = [s.value for s in sources]

        # Convert to domain Workout
        workout = blocks_to_workout(workout_data)

        # Set workout ID if updating existing workout
        if request.workout_id:
            workout = workout.model_copy(update={"id": request.workout_id})

        # Step 2: Execute use case
        result = save_workout_use_case.execute(
            workout=workout,
            user_id=user_id,
            device=request.device,
        )

        # Step 3: Queue workout for export if save was successful
        if result.success and result.workout_id:
            export_queue.enqueue(
                workout_id=result.workout_id,
                user_id=user_id,
                device=request.device,
                export_formats=request.exports or {},
            )

        # Step 4: Convert use case result to HTTP response
        if result.success:
            return {
                "success": True,
                "workout_id": result.workout_id,
                "message": "Workout saved successfully",
                "is_update": result.is_update,
            }
        else:
            return {
                "success": False,
                "message": result.error or "Failed to save workout",
                "validation_errors": result.validation_errors,
            }

    except ValueError as e:
        # Conversion error (e.g., invalid workout_data)
        logger.warning(f"Failed to convert workout data: {e}")
        return {
            "success": False,
            "message": f"Invalid workout data: {str(e)}"
        }
    except TimeoutError as e:
        logger.error(f"Timeout saving workout: {e}")
        return {
            "success": False,
            "message": "Service temporarily unavailable. Please try again."
        }
    except Exception as e:
        logger.exception(f"Unexpected error saving workout: {e}")
        return {
            "success": False,
            "message": "Failed to save workout. Check server logs."
        }


@router.get("/workouts", response_model=WorkoutListResponse)
def get_workouts_endpoint(
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
    device: str = Query(None, description="Filter by device"),
    is_exported: bool = Query(None, description="Filter by export status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
):
    """Get workouts for the authenticated user, optionally filtered by device and export status."""
    result = get_workout_use_case.list_workouts(
        user_id=user_id,
        device=device,
        is_exported=is_exported,
        limit=limit,
    )

    return {
        "success": True,
        "workouts": result.workouts,
        "count": result.count
    }


@router.get("/workouts/search", response_model=SearchResponse)
def search_workouts_endpoint(
    q: str = Query(..., min_length=1, description="Natural language search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Result offset for pagination"),
    workout_type: Optional[str] = Query(None, description="Filter by workout type"),
    min_duration: Optional[int] = Query(None, ge=0, description="Minimum duration in minutes"),
    max_duration: Optional[int] = Query(None, ge=0, description="Maximum duration in minutes"),
    user_id: str = Depends(get_current_user),
    search_repo: SearchRepository = Depends(get_search_repo),
    embedding_service: Optional[EmbeddingService] = Depends(get_embedding_service),
):
    """
    Search workouts using semantic similarity or keyword fallback.

    Generates an embedding for the query via OpenAI and performs cosine similarity
    search against workout embeddings. Falls back to keyword search (ILIKE) if
    OpenAI is unavailable or embedding generation fails.

    Part of AMA-432: Semantic Search Endpoint
    """
    try:
        search_type = "semantic"
        query_embedding_time_ms = None
        query_embedding = None

        # Try semantic search first
        if embedding_service is not None:
            try:
                t0 = time.perf_counter()
                query_embedding = embedding_service.generate_query_embedding(q)
                query_embedding_time_ms = int((time.perf_counter() - t0) * 1000)
            except Exception as e:
                logger.warning(f"Embedding generation failed, falling back to keyword search: {e}")
                query_embedding = None

        # Perform search
        t0 = time.perf_counter()

        if query_embedding is not None:
            raw_results = search_repo.semantic_search(
                profile_id=user_id,
                query_embedding=query_embedding,
                limit=limit + offset,  # fetch enough to handle offset
                threshold=0.5,
            )
            search_type = "semantic"
        else:
            raw_results = search_repo.keyword_search(
                profile_id=user_id,
                query=q,
                limit=limit + offset,
            )
            search_type = "keyword"

        search_time_ms = int((time.perf_counter() - t0) * 1000)

        # Apply offset
        raw_results = raw_results[offset:]

        # Apply application-level filters
        if workout_type:
            raw_results = [
                r for r in raw_results
                if _matches_workout_type(r, workout_type)
            ]
        if min_duration is not None or max_duration is not None:
            raw_results = [
                r for r in raw_results
                if _matches_duration(r, min_duration, max_duration)
            ]

        # Build response items
        results = []
        for row in raw_results[:limit]:
            results.append(SearchResultItem(
                workout_id=str(row.get("id", "")),
                title=row.get("title"),
                description=row.get("description"),
                sources=row.get("sources") or [],
                similarity_score=row.get("similarity"),
                created_at=str(row["created_at"]) if row.get("created_at") else None,
            ))

        return SearchResponse(
            success=True,
            results=results,
            count=len(results),
            query=q,
            search_type=search_type,
            query_embedding_time_ms=query_embedding_time_ms,
            search_time_ms=search_time_ms,
        )

    except Exception as e:
        logger.exception(f"Search failed: {e}")
        return SearchResponse(
            success=False,
            results=[],
            count=0,
            query=q,
            search_type="error",
        )


def _matches_workout_type(row: dict, workout_type: str) -> bool:
    """Check if a workout row matches the given workout type filter."""
    workout_data = row.get("workout_data") or {}
    wtype = workout_data.get("type") or workout_data.get("workout_type") or ""
    return wtype.lower() == workout_type.lower()


def _matches_duration(row: dict, min_duration: Optional[int], max_duration: Optional[int]) -> bool:
    """Check if a workout row matches duration filters (in minutes)."""
    workout_data = row.get("workout_data") or {}
    duration = workout_data.get("duration")
    if duration is None:
        duration = workout_data.get("duration_minutes")
    if duration is None:
        # If no duration info, include in results (don't filter out)
        return True
    if min_duration is not None and duration < min_duration:
        return False
    if max_duration is not None and duration > max_duration:
        return False
    return True


@router.get("/workouts/incoming")
def get_incoming_workouts_endpoint(
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
):
    """
    Get incoming workouts that haven't been completed yet (AMA-236).

    This endpoint returns workouts that have been pushed to iOS Companion App
    but have not yet been recorded as completed in workout_completions.

    Use this instead of /workouts to get a filtered list of workouts
    that still need to be done.

    Args:
        user_id: Authenticated user ID (from Clerk JWT)
        limit: Maximum number of workouts to return

    Returns:
        List of pending workouts in iOS Companion format
    """
    result = get_workout_use_case.get_incoming_workouts(user_id, limit=limit)

    # Transform each workout to iOS companion format (same as /ios-companion/pending)
    transformed = []
    for workout_record in result.workouts:
        workout_data = workout_record.get("workout_data", {})
        title = workout_record.get("title") or workout_data.get("title", "Workout")

        # Use to_workoutkit to properly transform intervals
        try:
            workoutkit_dto = to_workoutkit(workout_data)
            intervals = [interval.model_dump() for interval in workoutkit_dto.intervals]
            sport = workoutkit_dto.sportType
        except Exception as e:
            logger.warning(f"Failed to transform workout {workout_record.get('id')}: {e}")
            intervals = []
            sport = "strengthTraining"
            for block in workout_data.get("blocks", []):
                for exercise in block.get("exercises", []):
                    intervals.append(convert_exercise_to_interval(exercise))

        # Calculate total duration from intervals
        total_duration = calculate_intervals_duration(intervals)

        transformed.append({
            "id": workout_record.get("id"),
            "name": title,
            "sport": sport,
            "duration": total_duration,
            "source": "amakaflow",
            "sourceUrl": None,
            "intervals": intervals,
            "pushedAt": workout_record.get("ios_companion_synced_at"),
            "createdAt": workout_record.get("created_at"),
        })

    return {
        "success": True,
        "workouts": transformed,
        "count": len(transformed)
    }


# =============================================================================
# Workout CRUD Endpoints (Parameterized routes)
# =============================================================================


@router.get("/workouts/{workout_id}", response_model=WorkoutResponse)
def get_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
):
    """Get a single workout by ID."""
    result = get_workout_use_case.get_workout(workout_id, user_id)

    if result.success:
        return {
            "success": True,
            "workout": result.workout
        }
    else:
        raise HTTPException(
            status_code=404,
            detail={"message": result.error}
        )


@router.put("/workouts/{workout_id}/export-status")
def update_workout_export_endpoint(
    workout_id: str,
    request: UpdateWorkoutExportRequest,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
    export_queue: ExportQueue = Depends(get_export_queue),
):
    """Update workout export status after syncing to device."""
    success = get_workout_use_case.update_export_status(
        workout_id=workout_id,
        user_id=user_id,
        is_exported=request.is_exported,
        exported_to_device=request.exported_to_device,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workout not found or not owned by user"}
        )

    # Queue export job if marking as exported
    if request.is_exported:
        export_queue.enqueue(
            workout_id=workout_id,
            user_id=user_id,
            device=request.exported_to_device or "unknown",
        )

    return {
        "success": True,
        "message": "Export status updated successfully"
    }


@router.delete("/workouts/{workout_id}")
def delete_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
):
    """Delete a workout."""
    success = get_workout_use_case.delete_workout(workout_id, user_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workout not found or not owned by user"}
        )

    return {
        "success": True,
        "message": "Workout deleted successfully"
    }


@router.patch("/workouts/{workout_id}/favorite")
def toggle_workout_favorite_endpoint(
    workout_id: str,
    request: ToggleFavoriteRequest,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
):
    """Toggle favorite status for a workout."""
    result = get_workout_use_case.toggle_favorite(
        workout_id=workout_id,
        user_id=user_id,
        is_favorite=request.is_favorite,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workout not found or not owned by user"}
        )

    return {
        "success": True,
        "workout": result,
        "message": "Favorite status updated"
    }


@router.patch("/workouts/{workout_id}/used")
def track_workout_usage_endpoint(
    workout_id: str,
    request: TrackUsageRequest,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
):
    """Track that a workout was used (update last_used_at and increment times_completed)."""
    result = get_workout_use_case.track_usage(workout_id, user_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workout not found or not owned by user"}
        )

    return {
        "success": True,
        "workout": result,
        "message": "Usage tracked"
    }


@router.patch("/workouts/{workout_id}/tags")
def update_workout_tags_endpoint(
    workout_id: str,
    request: UpdateTagsRequest,
    user_id: str = Depends(get_current_user),
    get_workout_use_case: GetWorkoutUseCase = Depends(get_get_workout_use_case),
):
    """Update tags for a workout."""
    result = get_workout_use_case.update_tags(
        workout_id=workout_id,
        user_id=user_id,
        tags=request.tags,
    )

    if not result:
        raise HTTPException(
            status_code=404,
            detail={"message": "Workout not found or not owned by user"}
        )

    return {
        "success": True,
        "workout": result,
        "message": "Tags updated"
    }


# =============================================================================
# Patch Workout Endpoint (AMA-433)
# =============================================================================


@router.patch(
    "/workouts/{workout_id}",
    response_model=PatchWorkoutResponse,
    responses={
        404: {"description": "Workout not found"},
        422: {"model": PatchWorkoutErrorResponse, "description": "Validation error"},
    },
)
def patch_workout_endpoint(
    workout_id: str,
    request: PatchWorkoutRequest,
    user_id: str = Depends(get_current_user),
    patch_use_case: PatchWorkoutUseCase = Depends(get_patch_workout_use_case),
):
    """
    Apply JSON Patch operations to a workout.

    This endpoint supports a subset of RFC 6902 JSON Patch for workout editing.
    Operations are applied atomically - all succeed or all fail.

    **Supported operations:**
    - `replace`: Replace a value at a path
    - `add`: Add a value at a path (e.g., append to array with `/-`)
    - `remove`: Remove a value at a path

    **Supported paths:**
    - `/title` or `/name`: Workout title
    - `/description`: Workout description
    - `/tags`: Replace tags array
    - `/tags/-`: Add tag (add op)
    - `/exercises/-`: Add exercise to first block
    - `/exercises/{index}`: Replace or remove exercise
    - `/exercises/{index}/{field}`: Replace exercise field (sets, reps, etc.)
    - `/blocks/{index}/exercises/-`: Add exercise to specific block
    - `/blocks/{index}/exercises/{index}`: Modify exercise in block

    **Example request:**
    ```json
    {
      "operations": [
        {"op": "replace", "path": "/title", "value": "New Title"},
        {"op": "add", "path": "/tags/-", "value": "strength"},
        {"op": "replace", "path": "/exercises/0/sets", "value": 4}
      ]
    }
    ```

    Part of AMA-433: PATCH /workouts/{id} endpoint implementation.
    """
    result = patch_use_case.execute(
        workout_id=workout_id,
        user_id=user_id,
        operations=request.operations,
    )

    if not result.success:
        if result.error == "Workout not found or not owned by user":
            raise HTTPException(
                status_code=404,
                detail={"message": result.error},
            )
        raise HTTPException(
            status_code=422,
            detail={
                "message": result.error or "Patch operation failed",
                "validation_errors": result.validation_errors,
            },
        )

    return PatchWorkoutResponse(
        success=True,
        workout=result.workout,
        changes_applied=result.changes_applied,
        embedding_regeneration=result.embedding_regeneration,
    )
