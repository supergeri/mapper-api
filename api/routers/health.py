"""
Health check router.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-597: Move debug/testing endpoints to health router

This router provides health check endpoints for monitoring and load balancers,
as well as debug and testing endpoints.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend.auth import get_current_user
from backend.settings import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Health"],
)


# =============================================================================
# Health Check Endpoints
# =============================================================================


@router.get("/health")
def health():
    """
    Simple liveness endpoint for mapper-api.

    Returns:
        dict: Status indicator for health checks
    """
    return {"status": "ok"}


# =============================================================================
# Debug Endpoints (AMA-597)
# =============================================================================


@router.get("/debug/garmin-test")
def test_garmin_debug(settings: Settings = Depends(get_settings)):
    """
    Test endpoint to verify GARMIN_EXPORT_DEBUG logging is working.

    Only available in development environments.
    
    Returns a simple message and triggers debug logs if enabled.
    """
    # Guard: Only available in development
    if not settings.is_development:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in development environment"
        )
    
    if settings.garmin_export_debug:
        logger.warning("=== GARMIN_DEBUG_TEST_ENDPOINT ===")
        print("=== GARMIN_EXPORT_STEP ===")
        print(json.dumps({
            "original_name": "Test Exercise",
            "normalized_name": "test exercise",
            "mapped_name": "Test Exercise",
            "confidence": 1.0,
            "garmin_name_final": "Test Exercise",
            "sets": "N/A",
            "reps": "10",
            "target_type": "reps",
            "target_value": "10"
        }, indent=2))
        
        print("=== GARMIN_CATEGORY_ASSIGN ===")
        print(json.dumps({
            "garmin_name_before": "Test Exercise",
            "assigned_category": "TEST",
            "garmin_name_after": "Test Exercise [category: TEST]"
        }, indent=2))
        
        return {
            "status": "success",
            "message": "GARMIN_EXPORT_DEBUG is ACTIVE - check Docker logs for debug output",
            "debug_enabled": True
        }
    else:
        return {
            "status": "info",
            "message": "GARMIN_EXPORT_DEBUG is disabled - set GARMIN_EXPORT_DEBUG=true to enable",
            "debug_enabled": False
        }


# =============================================================================
# Testing Endpoints (AMA-597)
# =============================================================================


@router.post("/testing/reset-user-data")
async def reset_user_data_endpoint(
    user_id: str = Depends(get_current_user),
    x_test_secret: Optional[str] = Header(None, alias="X-Test-Secret"),
    settings: Settings = Depends(get_settings),
):
    """
    Reset all user data without deleting the account.

    **WARNING:** This endpoint permanently deletes user data.
    Only available in test environments.

    Security requirements:
    - Must be authenticated (valid JWT or API key)
    - Only works in test environments (not production, not development)
    - X-Test-Secret header is optional (validated if provided for automated testing)

    Deletes:
    - All workouts
    - All workout completions
    - All programs and tags
    - All follow-along workouts
    - All paired devices
    - Voice settings and corrections
    - Calendar events

    Keeps:
    - Clerk user account (authentication continues to work)
    - External service connections (Strava, Garmin)
    - User profile entry
    """
    from backend.database import reset_user_data

    # Guard: Only available in test environment
    if not settings.is_test:
        raise HTTPException(
            status_code=403,
            detail="This endpoint is only available in test environment"
        )

    # Security check: X-Test-Secret is optional when user is authenticated via JWT
    # The JWT authentication (get_current_user) already ensures:
    # - User is authenticated
    # - User can only reset their own data
    # If test_reset_secret is configured and header is provided, validate it
    # (supports automated testing scenarios)
    if settings.test_reset_secret and x_test_secret:
        if x_test_secret != settings.test_reset_secret:
            logger.warning(f"Reset user data attempted by {user_id} with invalid secret")
            raise HTTPException(
                status_code=403,
                detail="Invalid X-Test-Secret header"
            )

    # All checks passed - perform the reset
    logger.info(f"Resetting user data for {user_id} (environment: {settings.environment})")

    try:
        result = reset_user_data(user_id)

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to reset user data")
            )

        return {
            "success": True,
            "deleted": result.get("deleted", {}),
            "user_id": user_id,
            "reset_at": datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset user data for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
