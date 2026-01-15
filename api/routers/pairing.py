"""
Pairing router for mobile device pairing and authentication.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-382: Move pairing endpoints from app.py
Updated in AMA-388: Refactor to use dependency injection for repositories

This router contains endpoints for:
- /mobile/pairing/generate - Generate pairing token for QR code
- /mobile/pairing/pair - Exchange token for JWT
- /mobile/pairing/refresh - Refresh expired JWT
- /mobile/pairing/status/{token} - Check pairing status (polling)
- /mobile/pairing/revoke - Revoke all tokens
- /mobile/pairing/devices - List paired devices
- /mobile/pairing/devices/{device_id} - Revoke specific device
- /mobile/profile - Get user profile for mobile apps
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user, get_device_repo, get_user_profile_repo
from application.ports import DeviceRepository, UserProfileRepository
from backend.mobile_pairing import (
    GeneratePairingResponse,
    PairDeviceRequest,
    PairDeviceResponse,
    PairingStatusResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    fetch_clerk_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["Pairing"],
)


# =============================================================================
# Mobile Pairing Endpoints (AMA-61: iOS Companion App Authentication)
# =============================================================================


@router.post("/mobile/pairing/generate", response_model=GeneratePairingResponse)
async def generate_pairing_token_endpoint(
    user_id: str = Depends(get_current_user),
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Generate a new pairing token for iOS Companion App authentication.

    Returns a secure token (for QR code) and human-readable short code (for manual entry).
    Both expire after 5 minutes.

    Requires valid authentication (Clerk JWT or API key).
    """
    try:
        result = device_repo.create_pairing_token(user_id)
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to create pairing token")
        if "error" in result:
            if result["error"] == "rate_limit":
                raise HTTPException(status_code=429, detail=result.get("message", "Rate limit exceeded"))
            raise HTTPException(status_code=400, detail=result.get("message", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate pairing token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mobile/pairing/pair", response_model=PairDeviceResponse)
async def pair_device_endpoint(
    request: PairDeviceRequest,
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Exchange a pairing token for a JWT (called by iOS app).

    This endpoint is public - the iOS app calls it after scanning a QR code
    or entering a short code. The token proves the user authorized the pairing.

    Returns a JWT that the iOS app stores and uses for authenticated API calls.
    """
    try:
        result = device_repo.validate_and_use_token(
            token=request.token,
            short_code=request.short_code,
            device_info=request.device_info
        )

        if result is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid, expired, or already used pairing token"
            )

        if "error" in result:
            raise HTTPException(
                status_code=400,
                detail=result.get("message", result["error"])
            )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pair device: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mobile/pairing/refresh", response_model=RefreshTokenResponse)
async def refresh_jwt_endpoint(
    request: RefreshTokenRequest,
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Refresh JWT for a paired device (AMA-220).

    This endpoint allows the iOS app to get a new JWT when the current one
    expires, without requiring the user to re-pair. The device_id is the
    iOS UIDevice.current.identifierForVendor that was sent during initial pairing.

    This endpoint is public (no auth required) because the old JWT may be expired.
    The device_id serves as proof of previous pairing.

    Returns:
    - jwt: New JWT token
    - expires_at: When the new JWT expires
    - refreshed_at: When this refresh occurred
    """
    try:
        result = device_repo.refresh_jwt(request.device_id)

        if not result.get("success"):
            error_code = result.get("error_code", "UNKNOWN")
            if error_code == "DEVICE_NOT_FOUND":
                raise HTTPException(status_code=401, detail=result.get("error"))
            elif error_code == "DEVICE_NOT_PAIRED":
                raise HTTPException(status_code=401, detail=result.get("error"))
            else:
                raise HTTPException(status_code=500, detail=result.get("error"))

        return RefreshTokenResponse(
            jwt=result["jwt"],
            expires_at=result["expires_at"],
            refreshed_at=result["refreshed_at"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to refresh JWT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mobile/pairing/status/{token}", response_model=PairingStatusResponse)
async def check_pairing_status_endpoint(
    token: str,
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Check if a pairing token has been used (web app polling endpoint).

    The web app polls this endpoint after displaying the QR code to detect
    when the iOS app has successfully completed pairing.

    Returns:
    - paired: true if token was used, false otherwise
    - expired: true if token has expired
    - paired_at: timestamp when pairing occurred (if paired)
    """
    try:
        result = device_repo.get_pairing_status(token)
        return result
    except Exception as e:
        logger.error(f"Failed to check pairing status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mobile/pairing/revoke")
async def revoke_pairing_tokens_endpoint(
    user_id: str = Depends(get_current_user),
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Revoke all active pairing tokens for the authenticated user.

    Call this if the user wants to cancel pairing or generate a fresh token.
    Also useful as a security measure if tokens may have been compromised.
    """
    try:
        count = device_repo.revoke_user_tokens(user_id)
        return {
            "success": True,
            "message": f"Revoked {count} pairing token(s)",
            "revoked_count": count
        }
    except Exception as e:
        logger.error(f"Failed to revoke pairing tokens: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mobile/pairing/devices")
async def list_paired_devices_endpoint(
    user_id: str = Depends(get_current_user),
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    List all paired iOS devices for the authenticated user (AMA-184).

    Returns a list of devices that have successfully completed pairing,
    including device info (model, OS version) and when they were paired.
    """
    try:
        devices = device_repo.get_paired_devices(user_id)
        return {
            "success": True,
            "devices": devices,
            "count": len(devices)
        }
    except Exception as e:
        logger.error(f"Failed to list paired devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mobile/pairing/devices/{device_id}")
async def revoke_device_endpoint(
    device_id: str,
    user_id: str = Depends(get_current_user),
    device_repo: DeviceRepository = Depends(get_device_repo),
):
    """
    Revoke a specific paired device (AMA-184).

    This removes the device's pairing, requiring the user to re-pair
    if they want to use the iOS app on that device again.
    """
    try:
        result = device_repo.revoke_device(user_id, device_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("message", "Device not found"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Mobile Profile Endpoint (AMA-268, AMA-269)
# =============================================================================


@router.get("/mobile/profile")
async def get_mobile_profile_endpoint(
    user_id: str = Depends(get_current_user),
    user_profile_repo: UserProfileRepository = Depends(get_user_profile_repo),
):
    """
    Get current user's profile for mobile apps (AMA-268, AMA-269).

    Returns the authenticated user's profile information.
    Fetches from Clerk API for accurate data, with database fallback.
    Supports both JWT authentication and X-Test-Auth for E2E testing.
    """
    # Try Clerk API first for most accurate profile data (AMA-269)
    clerk_profile = fetch_clerk_profile(user_id)
    if clerk_profile:
        # Combine first_name + last_name for name field
        name_parts = []
        if clerk_profile.get("first_name"):
            name_parts.append(clerk_profile["first_name"])
        if clerk_profile.get("last_name"):
            name_parts.append(clerk_profile["last_name"])
        name = " ".join(name_parts) if name_parts else None

        return {
            "success": True,
            "profile": {
                "id": clerk_profile["id"],
                "email": clerk_profile.get("email"),
                "name": name,
                "avatar_url": clerk_profile.get("image_url")
            }
        }

    # Fallback to database profile
    db_profile = user_profile_repo.get_profile(user_id)
    if db_profile:
        return {
            "success": True,
            "profile": db_profile
        }

    # Return minimal profile if neither source has data
    return {
        "success": True,
        "profile": {
            "id": user_id,
            "email": None,
            "name": None,
            "avatar_url": None
        }
    }
