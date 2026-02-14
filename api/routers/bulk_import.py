"""
Bulk import router for the 5-step import workflow.

Handles import of workouts from multiple sources:
- Files (Excel, CSV, JSON, Text)
- URLs (YouTube, Instagram, TikTok, Vimeo)
- Images (JPG, PNG, WebP, etc.)

Endpoints:
- POST /import/detect — Detect workout items from sources
- POST /import/detect/file — Detect from uploaded file
- POST /import/detect/urls — Detect from URLs
- POST /import/detect/images — Detect from images (OCR)
- POST /import/map — Apply column mappings (files only)
- POST /import/match — Match exercises to Garmin database
- POST /import/preview — Generate preview before import
- POST /import/execute — Execute the bulk import
- GET /import/status/{job_id} — Get import job status
- POST /import/cancel/{job_id} — Cancel a running import

Part of AMA-591: Extract bulk import router from monolithic app.py
"""

import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, UploadFile
from fastapi import File as FastAPIFile

from api.deps import get_current_user
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
    BulkCancelResponse,
    ColumnMapping,
)
from backend.bulk_import import bulk_import_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/import",
    tags=["bulk-import"],
)


# ============================================================================
# Step 1: Detect - Parse sources and detect workout items
# ============================================================================


@router.post(
    "/detect",
    response_model=BulkDetectResponse,
    summary="Detect workout items from sources",
    description="Step 1 of bulk import: Parse and detect workout items from files, URLs, or images",
)
async def bulk_import_detect(
    request: BulkDetectRequest,
    current_user=Depends(get_current_user),
):
    """
    Detect and parse workout items from sources.

    Step 1 of the bulk import workflow.

    Accepts:
    - file: Base64-encoded file content (Excel, CSV, JSON, Text)
    - urls: List of URLs (YouTube, Instagram, TikTok)
    - images: Base64-encoded image data for OCR

    Returns detected items with confidence scores and any parsing errors.
    """
    return await bulk_import_service.detect_items(
        profile_id=request.profile_id,
        source_type=request.source_type,
        sources=request.sources,
    )


@router.post(
    "/detect/file",
    response_model=BulkDetectResponse,
    summary="Detect from uploaded file",
    description="Step 1 variant: Upload Excel, CSV, JSON, or text file for workout detection",
)
async def bulk_import_detect_file(
    file: UploadFile = FastAPIFile(...),
    profile_id: str = Form(..., description="User profile ID"),
    current_user=Depends(get_current_user),
):
    """
    Detect and parse workout items from an uploaded file.

    Step 1 of the bulk import workflow (file upload variant).

    Accepts file uploads via multipart/form-data:
    - Excel (.xlsx, .xls)
    - CSV (.csv)
    - JSON (.json)
    - Text (.txt)

    Returns detected items with confidence scores and any parsing errors.
    """
    # Read file content
    content = await file.read()
    filename = file.filename or "upload.txt"

    # Encode as base64 with filename prefix for the parser
    base64_content = f"{filename}:{base64.b64encode(content).decode('utf-8')}"

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="file",
        sources=[base64_content],
    )


@router.post(
    "/detect/urls",
    response_model=BulkDetectResponse,
    summary="Detect from URLs",
    description="Step 1 variant: Detect workouts from video URLs (YouTube, Instagram, TikTok)",
)
async def bulk_import_detect_urls(
    profile_id: str = Form(..., description="User profile ID"),
    urls: str = Form(..., description="Newline or comma-separated URLs"),
    current_user=Depends(get_current_user),
):
    """
    Detect and parse workout items from URLs.

    Step 1 of the bulk import workflow (URL variant).

    Accepts URLs via form data (newline or comma-separated):
    - YouTube (youtube.com, youtu.be)
    - Instagram (instagram.com/p/, /reel/, /tv/)
    - TikTok (tiktok.com, vm.tiktok.com)

    Fetches metadata using oEmbed APIs for quick preview.
    Full workout extraction happens during the import step.

    Processing uses batch requests with max 5 concurrent connections.
    """
    # Parse URLs from form input (newline or comma-separated)
    url_list = []
    for line in urls.replace(",", "\n").split("\n"):
        url = line.strip()
        if url:
            url_list.append(url)

    if not url_list:
        raise HTTPException(
            status_code=400,
            detail="No URLs provided"
        )

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="urls",
        sources=url_list,
    )


@router.post(
    "/detect/images",
    response_model=BulkDetectResponse,
    summary="Detect from images (OCR)",
    description="Step 1 variant: Extract workout data from images using Vision AI",
)
async def bulk_import_detect_images(
    profile_id: str = Form(..., description="User profile ID"),
    files: list[UploadFile] = FastAPIFile(..., description="Image files to process"),
    current_user=Depends(get_current_user),
):
    """
    Detect and parse workout items from images.

    Step 1 of the bulk import workflow (Image variant).

    Accepts image uploads:
    - PNG, JPG, JPEG, WebP, HEIC, GIF
    - Max 20 images per request

    Uses Vision AI (GPT-4o-mini by default) to extract workout data.
    Returns structured workout data with confidence scores.

    Processing uses batch requests with max 3 concurrent connections
    (lower than URLs due to cost and rate limits).
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail="No images provided"
        )

    # Limit to 20 images
    if len(files) > 20:
        raise HTTPException(
            status_code=400,
            detail=f"Too many images ({len(files)}). Maximum is 20."
        )

    # Read files and convert to base64
    image_sources = []
    for file in files:
        content = await file.read()
        b64_data = base64.b64encode(content).decode("utf-8")
        image_sources.append({
            "data": b64_data,
            "filename": file.filename or "image.jpg",
        })

    return await bulk_import_service.detect_items(
        profile_id=profile_id,
        source_type="images",
        sources=image_sources,
    )


# ============================================================================
# Step 2: Map - Apply column mappings (files only)
# ============================================================================


@router.post(
    "/map",
    response_model=BulkMapResponse,
    summary="Apply column mappings",
    description="Step 2 of bulk import: Map CSV/Excel columns to workout fields (files only)",
)
async def bulk_import_map(
    request: BulkMapRequest,
    current_user=Depends(get_current_user),
):
    """
    Apply column mappings to detected file data.

    Step 2 of the bulk import workflow (only for file imports).

    Transforms raw CSV/Excel data into structured workout data
    based on user-provided column mappings.
    """
    column_mappings = [
        ColumnMapping(**m) if isinstance(m, dict) else m
        for m in request.column_mappings
    ]
    return await bulk_import_service.apply_column_mappings(
        job_id=request.job_id,
        profile_id=request.profile_id,
        column_mappings=column_mappings,
    )


# ============================================================================
# Step 3: Match - Match exercises to Garmin database
# ============================================================================


@router.post(
    "/match",
    response_model=BulkMatchResponse,
    summary="Match exercises to Garmin database",
    description="Step 3 of bulk import: Fuzzy-match exercise names to Garmin equivalents",
)
async def bulk_import_match(
    request: BulkMatchRequest,
    current_user=Depends(get_current_user),
):
    """
    Match exercises to Garmin exercise database.

    Step 3 of the bulk import workflow.

    Uses fuzzy matching to find Garmin equivalents for exercise names.
    Returns confidence scores and suggestions for ambiguous matches.
    """
    return await bulk_import_service.match_exercises(
        job_id=request.job_id,
        profile_id=request.profile_id,
        user_mappings=request.user_mappings,
    )


# ============================================================================
# Step 4: Preview - Generate preview before commit
# ============================================================================


@router.post(
    "/preview",
    response_model=BulkPreviewResponse,
    summary="Generate preview of workouts",
    description="Step 4 of bulk import: Preview final workouts and validation issues",
)
async def bulk_import_preview(
    request: BulkPreviewRequest,
    current_user=Depends(get_current_user),
):
    """
    Generate preview of workouts to be imported.

    Step 4 of the bulk import workflow.

    Shows final workout structures, validation issues,
    and statistics before committing the import.
    """
    return await bulk_import_service.generate_preview(
        job_id=request.job_id,
        profile_id=request.profile_id,
        selected_ids=request.selected_ids,
    )


# ============================================================================
# Step 5: Execute - Commit the import
# ============================================================================


@router.post(
    "/execute",
    response_model=BulkExecuteResponse,
    summary="Execute bulk import",
    description="Step 5 of bulk import: Commit workouts to database (async by default)",
)
async def bulk_import_execute(
    request: BulkExecuteRequest,
    current_user=Depends(get_current_user),
):
    """
    Execute the bulk import of workouts.

    Step 5 of the bulk import workflow.

    In async_mode (default), starts a background job and returns immediately.
    Use GET /import/status/{job_id} to track progress.
    """
    return await bulk_import_service.execute_import(
        job_id=request.job_id,
        profile_id=request.profile_id,
        workout_ids=request.workout_ids,
        device=request.device,
        async_mode=request.async_mode,
    )


# ============================================================================
# Monitoring & Control
# ============================================================================


@router.get(
    "/status/{job_id}",
    response_model=BulkStatusResponse,
    summary="Get import job status",
    description="Poll the status of a bulk import job (progress, results, errors)",
)
async def bulk_import_status(
    job_id: str,
    profile_id: str = Query(..., description="User profile ID"),
    current_user=Depends(get_current_user),
):
    """
    Get status of a bulk import job.

    Returns progress percentage, current item being processed,
    and results for completed items.
    """
    return await bulk_import_service.get_import_status(
        job_id=job_id,
        profile_id=profile_id,
    )


@router.post(
    "/cancel/{job_id}",
    response_model=BulkCancelResponse,
    summary="Cancel import job",
    description="Cancel a running bulk import job (completed jobs cannot be cancelled)",
)
async def bulk_import_cancel(
    job_id: str,
    profile_id: str = Query(..., description="User profile ID"),
    current_user=Depends(get_current_user),
):
    """
    Cancel a running bulk import job.

    Only works for jobs with status 'running'.
    Completed imports cannot be cancelled.
    """
    success = await bulk_import_service.cancel_import(
        job_id=job_id,
        profile_id=profile_id,
    )
    return {
        "success": success,
        "message": "Import cancelled" if success else "Failed to cancel import",
    }
