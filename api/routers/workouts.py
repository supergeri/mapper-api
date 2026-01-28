"""
Workouts router for workout CRUD and library management.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-381: Move workout CRUD endpoints from app.py
Updated in AMA-383: Move completion endpoints to routers/completions.py
Updated in AMA-388: Refactor to use dependency injection for repositories
Updated in AMA-394: Refactor to call SaveWorkoutUseCase

This router contains endpoints for:
- /workouts/save - Save workout to database
- /workouts - List user workouts
- /workouts/incoming - Get incoming (pending) workouts
- /workouts/{workout_id} - Get, delete workout
- /workouts/{workout_id}/export-status - Update export status
- /workouts/{workout_id}/favorite - Toggle favorite
- /workouts/{workout_id}/used - Track usage
- /workouts/{workout_id}/tags - Update tags

Note: Completion endpoints (/workouts/complete, /workouts/completions) are in
api/routers/completions.py and must be registered BEFORE this router.
"""

import logging
import time
from typing import List, Literal, Optional

from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel

from api.deps import (
    get_current_user,
    get_workout_repo,
    get_save_workout_use_case,
    get_search_repo,
    get_embedding_service,
)
from application.ports import WorkoutRepository, SearchRepository, EmbeddingService
from application.use_cases import SaveWorkoutUseCase
from backend.adapters.blocks_to_workoutkit import to_workoutkit
from domain.converters.blocks_to_workout import blocks_to_workout
from domain.models import WorkoutMetadata, WorkoutSource

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Workouts"],
)


# =============================================================================
# Request/Response Models
# =============================================================================


class SaveWorkoutRequest(BaseModel):
    """Request for saving a workout."""
    profile_id: str | None = None  # Deprecated: use auth instead
    workout_data: dict
    sources: list[str] = []
    device: str
    exports: dict | None = None
    validation: dict | None = None
    title: str | None = None
    description: str | None = None
    workout_id: str | None = None  # Optional: for explicit updates to existing workouts


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


class UpdateTagsRequest(BaseModel):
    """Request for updating workout tags."""
    profile_id: str
    tags: List[str]


# =============================================================================
# Helper Functions
# =============================================================================


def calculate_intervals_duration(intervals: list) -> int:
    """Calculate total duration in seconds from intervals list."""
    total = 0
    for interval in intervals:
        kind = interval.get("kind")
        if kind == "time" or kind == "warmup" or kind == "cooldown":
            total += interval.get("seconds", 0)
        elif kind == "reps":
            # Estimate ~3 seconds per rep for rep-based exercises
            total += interval.get("reps", 0) * 3
            total += interval.get("restSec", 0) or 0
        elif kind == "repeat":
            # Recursive calculation for repeat intervals
            reps = interval.get("reps", 1)
            inner_duration = calculate_intervals_duration(interval.get("intervals", []))
            total += inner_duration * reps
        elif kind == "distance":
            # Estimate ~6 min/km for distance-based
            meters = interval.get("meters", 0)
            total += int(meters * 0.36)  # 6 min/km = 360s/1000m
    return total


def convert_exercise_to_interval(exercise: dict) -> dict:
    """
    Convert a workout exercise to iOS companion interval format.
    """
    name = exercise.get("name", "Exercise")
    reps = exercise.get("reps")
    sets = exercise.get("sets", 1) or 1
    duration_sec = exercise.get("duration_sec")
    rest_sec = exercise.get("rest_sec", 60)
    follow_along_url = exercise.get("followAlongUrl")

    # Determine load string
    load_parts = []
    if exercise.get("load"):
        load_parts.append(exercise.get("load"))
    if sets and sets > 1:
        load_parts.append(f"{sets} sets")
    load = ", ".join(load_parts) if load_parts else None

    if reps:
        # Rep-based exercise
        return {
            "kind": "reps",
            "reps": reps * (sets or 1),  # Total reps if multiple sets
            "name": name,
            "load": load,
            "restSec": rest_sec,
            "followAlongUrl": follow_along_url,
            "carouselPosition": None
        }
    elif duration_sec:
        # Time-based exercise
        return {
            "kind": "time",
            "seconds": duration_sec,
            "target": name
        }
    else:
        # Default to time-based with 60 seconds
        return {
            "kind": "time",
            "seconds": 60,
            "target": name
        }


# =============================================================================
# Workout CRUD Endpoints
# =============================================================================


@router.post("/workouts/save")
def save_workout_endpoint(
    request: SaveWorkoutRequest,
    user_id: str = Depends(get_current_user),
    save_workout_use_case: SaveWorkoutUseCase = Depends(get_save_workout_use_case),
):
    """Save a workout to database before syncing to device.

    With deduplication: if a workout with the same profile_id, title, and device
    already exists, it will be updated instead of creating a duplicate.

    Delegates business logic to SaveWorkoutUseCase.
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

        # Step 3: Convert use case result to HTTP response
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
    except Exception as e:
        logger.exception(f"Unexpected error saving workout: {e}")
        return {
            "success": False,
            "message": "Failed to save workout. Check server logs."
        }


@router.get("/workouts")
def get_workouts_endpoint(
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
    device: str = Query(None, description="Filter by device"),
    is_exported: bool = Query(None, description="Filter by export status"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of workouts"),
):
    """Get workouts for the authenticated user, optionally filtered by device and export status."""
    workouts = workout_repo.get_list(
        profile_id=user_id,
        device=device,
        is_exported=is_exported,
        limit=limit,
    )

    # Include sync status for each workout (AMA-307)
    for workout in workouts:
        workout_id = workout.get("id")
        if workout_id:
            workout["sync_status"] = workout_repo.get_sync_status(workout_id, user_id)

    return {
        "success": True,
        "workouts": workouts,
        "count": len(workouts)
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
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
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
    workouts = workout_repo.get_incoming(user_id, limit=limit)

    # Transform each workout to iOS companion format (same as /ios-companion/pending)
    transformed = []
    for workout_record in workouts:
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


@router.get("/workouts/{workout_id}")
def get_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Get a single workout by ID."""
    workout = workout_repo.get(workout_id, user_id)

    if workout:
        # Include sync status in response (AMA-307)
        sync_status = workout_repo.get_sync_status(workout_id, user_id)
        workout["sync_status"] = sync_status
        return {
            "success": True,
            "workout": workout
        }
    else:
        return {
            "success": False,
            "message": "Workout not found"
        }


@router.put("/workouts/{workout_id}/export-status")
def update_workout_export_endpoint(
    workout_id: str,
    request: UpdateWorkoutExportRequest,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Update workout export status after syncing to device."""
    success = workout_repo.update_export_status(
        workout_id=workout_id,
        profile_id=user_id,
        is_exported=request.is_exported,
        exported_to_device=request.exported_to_device
    )

    if success:
        return {
            "success": True,
            "message": "Export status updated successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update export status"
        }


@router.delete("/workouts/{workout_id}")
def delete_workout_endpoint(
    workout_id: str,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Delete a workout."""
    success = workout_repo.delete(workout_id, user_id)

    if success:
        return {
            "success": True,
            "message": "Workout deleted successfully"
        }
    else:
        return {
            "success": False,
            "message": "Failed to delete workout"
        }


@router.patch("/workouts/{workout_id}/favorite")
def toggle_workout_favorite_endpoint(
    workout_id: str,
    request: ToggleFavoriteRequest,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Toggle favorite status for a workout."""
    result = workout_repo.toggle_favorite(
        workout_id=workout_id,
        profile_id=user_id,
        is_favorite=request.is_favorite
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Favorite status updated"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update favorite status"
        }


@router.patch("/workouts/{workout_id}/used")
def track_workout_usage_endpoint(
    workout_id: str,
    request: TrackUsageRequest,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Track that a workout was used (update last_used_at and increment times_completed)."""
    result = workout_repo.track_usage(
        workout_id=workout_id,
        profile_id=user_id
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Usage tracked"
        }
    else:
        return {
            "success": False,
            "message": "Failed to track usage"
        }


@router.patch("/workouts/{workout_id}/tags")
def update_workout_tags_endpoint(
    workout_id: str,
    request: UpdateTagsRequest,
    user_id: str = Depends(get_current_user),
    workout_repo: WorkoutRepository = Depends(get_workout_repo),
):
    """Update tags for a workout."""
    result = workout_repo.update_tags(
        workout_id=workout_id,
        profile_id=user_id,
        tags=request.tags
    )

    if result:
        return {
            "success": True,
            "workout": result,
            "message": "Tags updated"
        }
    else:
        return {
            "success": False,
            "message": "Failed to update tags"
        }
