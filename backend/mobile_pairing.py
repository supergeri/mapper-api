"""
Mobile Pairing module for iOS Companion App authentication (AMA-61).
Handles QR code / short code pairing between web app and iOS app.
"""
import os
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel
import logging
import jwt

logger = logging.getLogger(__name__)

# Clerk client for fetching user profiles (lazy initialized)
_clerk_client = None

# Token configuration
TOKEN_EXPIRY_MINUTES = 5
JWT_EXPIRY_DAYS = 30
JWT_SECRET = os.getenv("JWT_SECRET", "amakaflow-mobile-jwt-secret-change-in-production")
JWT_ALGORITHM = "HS256"

# Rate limiting: max tokens per user per hour
MAX_TOKENS_PER_HOUR = 5

# Character set for short codes (no confusing characters: 0,O,1,I,l)
SHORT_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SHORT_CODE_LENGTH = 6


# ============================================================================
# Clerk Integration
# ============================================================================

def get_clerk_client():
    """Get or create the Clerk client for fetching user profiles."""
    global _clerk_client
    if _clerk_client is None:
        clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
        if clerk_secret_key:
            try:
                from clerk_backend_api import Clerk
                _clerk_client = Clerk(bearer_auth=clerk_secret_key)
            except ImportError:
                logger.warning("clerk_backend_api not installed, Clerk profile fetch disabled")
            except Exception as e:
                logger.warning(f"Failed to initialize Clerk client: {e}")
    return _clerk_client


def fetch_clerk_profile(clerk_user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user profile from Clerk API.

    Args:
        clerk_user_id: The Clerk user ID

    Returns:
        Dict with profile data or None if fetch fails
    """
    client = get_clerk_client()
    if not client:
        return None

    try:
        user = client.users.get(user_id=clerk_user_id)
        if user:
            # Extract primary email
            email = None
            if user.email_addresses:
                email = user.email_addresses[0].email_address

            return {
                "id": user.id,
                "email": email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "image_url": user.image_url,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch Clerk profile for {clerk_user_id}: {e}")

    return None


# ============================================================================
# Pydantic Models
# ============================================================================

class GeneratePairingRequest(BaseModel):
    """Request to generate a new pairing token."""
    pass  # No body needed, user ID comes from header


class GeneratePairingResponse(BaseModel):
    """Response with pairing token and QR data."""
    token: str
    short_code: str
    qr_data: str
    expires_at: str
    expires_in_seconds: int


class PairDeviceRequest(BaseModel):
    """Request from iOS to pair using a token."""
    token: Optional[str] = None
    short_code: Optional[str] = None
    device_info: Optional[Dict[str, Any]] = None


class PairDeviceResponse(BaseModel):
    """Response with JWT for iOS app."""
    jwt: str
    profile: Dict[str, Any]
    expires_at: str


class PairingStatusResponse(BaseModel):
    """Response for polling pairing status."""
    paired: bool
    expired: bool
    device_info: Optional[Dict[str, Any]] = None


# ============================================================================
# Token Generation
# ============================================================================

def generate_pairing_tokens() -> Tuple[str, str]:
    """
    Generate a secure pairing token and human-readable short code.

    Returns:
        Tuple of (token, short_code)
    """
    # Secure 32-byte random token (64 hex chars)
    token = secrets.token_hex(32)

    # Human-readable short code
    short_code = ''.join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))

    return token, short_code


def generate_qr_data(token: str, api_url: Optional[str] = None) -> str:
    """
    Generate QR code data as JSON string.

    Args:
        token: The pairing token
        api_url: Optional API URL override

    Returns:
        JSON string for QR code
    """
    if api_url is None:
        api_url = os.getenv("MAPPER_API_PUBLIC_URL", "https://api.amakaflow.com")

    qr_data = {
        "type": "amakaflow_pairing",
        "version": 1,
        "token": token,
        "api_url": api_url
    }
    return json.dumps(qr_data, separators=(',', ':'))


def generate_jwt_for_user(clerk_user_id: str, profile: Dict[str, Any]) -> Tuple[str, datetime]:
    """
    Generate a JWT for the iOS app.

    Args:
        clerk_user_id: The Clerk user ID
        profile: User profile data

    Returns:
        Tuple of (jwt_token, expiry_datetime)
    """
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=JWT_EXPIRY_DAYS)

    payload = {
        "sub": clerk_user_id,
        "iat": int(now.timestamp()),
        "exp": int(expiry.timestamp()),
        "iss": "amakaflow",
        "aud": "ios_companion",
        "email": profile.get("email"),
        "name": profile.get("name"),
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expiry


# ============================================================================
# Database Operations
# ============================================================================

def get_supabase_client():
    """Get Supabase client - imported from database module."""
    from backend.database import get_supabase_client as _get_client
    return _get_client()


def create_pairing_token(clerk_user_id: str) -> Optional[Dict[str, Any]]:
    """
    Create a new pairing token in the database.

    Args:
        clerk_user_id: The Clerk user ID

    Returns:
        Dict with token info or None if failed
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return None

    try:
        # Check rate limit - only count active (non-expired, unused) tokens
        now = datetime.now(timezone.utc)
        rate_check = supabase.table("mobile_pairing_tokens") \
            .select("id") \
            .eq("clerk_user_id", clerk_user_id) \
            .is_("used_at", "null") \
            .gte("expires_at", now.isoformat()) \
            .execute()

        if rate_check.data and len(rate_check.data) >= MAX_TOKENS_PER_HOUR:
            logger.warning(f"Rate limit exceeded for user {clerk_user_id}")
            return {"error": "rate_limit", "message": f"Maximum {MAX_TOKENS_PER_HOUR} active tokens allowed"}

        # Generate tokens
        token, short_code = generate_pairing_tokens()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        qr_data = generate_qr_data(token)

        # Insert into database
        result = supabase.table("mobile_pairing_tokens").insert({
            "clerk_user_id": clerk_user_id,
            "token": token,
            "short_code": short_code,
            "expires_at": expires_at.isoformat(),
        }).execute()

        if result.data and len(result.data) > 0:
            return {
                "token": token,
                "short_code": short_code,
                "qr_data": qr_data,
                "expires_at": expires_at.isoformat(),
                "expires_in_seconds": TOKEN_EXPIRY_MINUTES * 60,
            }
        else:
            logger.error("Failed to insert pairing token")
            return None

    except Exception as e:
        logger.error(f"Error creating pairing token: {e}")
        return None


def validate_and_use_token(token: Optional[str] = None, short_code: Optional[str] = None, device_info: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Validate a pairing token and mark it as used.

    Args:
        token: The full pairing token (from QR)
        short_code: The short code (manual entry)
        device_info: iOS device metadata

    Returns:
        Dict with user info or None if invalid
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return None

    if not token and not short_code:
        return {"error": "invalid_request", "message": "Either token or short_code is required"}

    try:
        # Find the token
        query = supabase.table("mobile_pairing_tokens").select("*")

        if token:
            query = query.eq("token", token)
        else:
            query = query.eq("short_code", short_code.upper())

        result = query.execute()

        if not result.data or len(result.data) == 0:
            return {"error": "invalid_token", "message": "Token not found"}

        token_record = result.data[0]

        # Check if already used
        if token_record.get("used_at"):
            return {"error": "token_used", "message": "Token has already been used"}

        # Check expiration
        expires_at = datetime.fromisoformat(token_record["expires_at"].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > expires_at:
            return {"error": "token_expired", "message": "Token has expired"}

        # Mark as used
        update_result = supabase.table("mobile_pairing_tokens").update({
            "used_at": datetime.now(timezone.utc).isoformat(),
            "device_info": device_info,
        }).eq("id", token_record["id"]).execute()

        if not update_result.data:
            logger.error("Failed to mark token as used")
            return None

        # Get user profile - try Clerk API first, fallback to Supabase
        clerk_user_id = token_record["clerk_user_id"]

        # Try to fetch from Clerk API for most accurate profile data
        profile = fetch_clerk_profile(clerk_user_id)

        if profile is None:
            # Fallback to Supabase profiles table
            logger.info(f"Clerk profile fetch failed for {clerk_user_id}, using Supabase fallback")
            profile_result = supabase.table("profiles").select("*").eq("id", clerk_user_id).execute()

            if profile_result.data and len(profile_result.data) > 0:
                db_profile = profile_result.data[0]
                # Map Supabase profile to expected format
                # Split name into first/last if possible
                name = db_profile.get("name", "")
                name_parts = name.split(" ", 1) if name else ["", ""]
                first_name = name_parts[0] if name_parts else None
                last_name = name_parts[1] if len(name_parts) > 1 else None

                profile = {
                    "id": db_profile.get("id"),
                    "email": db_profile.get("email"),
                    "first_name": first_name,
                    "last_name": last_name,
                    "image_url": db_profile.get("avatar_url"),
                }
            else:
                # Minimal fallback profile with just the ID
                profile = {
                    "id": clerk_user_id,
                    "email": None,
                    "first_name": None,
                    "last_name": None,
                    "image_url": None,
                }

        # Generate JWT
        jwt_token, jwt_expiry = generate_jwt_for_user(clerk_user_id, profile)

        return {
            "jwt": jwt_token,
            "profile": profile,
            "expires_at": jwt_expiry.isoformat(),
        }

    except Exception as e:
        logger.error(f"Error validating pairing token: {e}")
        return None


def get_pairing_status(token: str) -> Dict[str, Any]:
    """
    Check the status of a pairing token.

    Args:
        token: The pairing token

    Returns:
        Dict with paired and expired status
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"paired": False, "expired": True, "error": "Database unavailable"}

    try:
        result = supabase.table("mobile_pairing_tokens") \
            .select("used_at, expires_at, device_info") \
            .eq("token", token) \
            .execute()

        if not result.data or len(result.data) == 0:
            return {"paired": False, "expired": True, "error": "Token not found"}

        token_record = result.data[0]

        # Check expiration
        expires_at = datetime.fromisoformat(token_record["expires_at"].replace('Z', '+00:00'))
        is_expired = datetime.now(timezone.utc) > expires_at

        # Check if paired
        is_paired = token_record.get("used_at") is not None

        return {
            "paired": is_paired,
            "expired": is_expired,
            "device_info": token_record.get("device_info") if is_paired else None,
        }

    except Exception as e:
        logger.error(f"Error checking pairing status: {e}")
        return {"paired": False, "expired": True, "error": str(e)}


def revoke_user_tokens(clerk_user_id: str) -> int:
    """
    Revoke all active pairing tokens for a user.

    Args:
        clerk_user_id: The Clerk user ID

    Returns:
        Number of tokens revoked
    """
    supabase = get_supabase_client()
    if not supabase:
        return 0

    try:
        # Delete all unused tokens for this user
        result = supabase.table("mobile_pairing_tokens") \
            .delete() \
            .eq("clerk_user_id", clerk_user_id) \
            .is_("used_at", "null") \
            .execute()

        return len(result.data) if result.data else 0

    except Exception as e:
        logger.error(f"Error revoking tokens: {e}")
        return 0


# ============================================================================
# Paired Devices Management (AMA-184)
# ============================================================================

def get_paired_devices(clerk_user_id: str) -> list[Dict[str, Any]]:
    """
    Get all paired devices for a user.

    Args:
        clerk_user_id: The Clerk user ID

    Returns:
        List of paired device records
    """
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Supabase client not available")
        return []

    try:
        # Query tokens that have been used (paired)
        result = supabase.table("mobile_pairing_tokens") \
            .select("id, device_info, used_at, created_at") \
            .eq("clerk_user_id", clerk_user_id) \
            .not_.is_("used_at", "null") \
            .order("used_at", desc=True) \
            .execute()

        if not result.data:
            return []

        # Transform to response format
        devices = []
        for record in result.data:
            device_info = record.get("device_info") or {}
            devices.append({
                "id": record["id"],
                "device_info": device_info,
                "paired_at": record["used_at"],
                "created_at": record["created_at"],
            })

        return devices

    except Exception as e:
        logger.error(f"Error fetching paired devices: {e}")
        return []


def revoke_device(clerk_user_id: str, device_id: str) -> Dict[str, Any]:
    """
    Revoke a specific paired device.

    Args:
        clerk_user_id: The Clerk user ID
        device_id: The device/token ID to revoke

    Returns:
        Dict with success status and message
    """
    supabase = get_supabase_client()
    if not supabase:
        return {"success": False, "message": "Database unavailable"}

    try:
        # Verify the device belongs to this user and is paired
        check_result = supabase.table("mobile_pairing_tokens") \
            .select("id, used_at") \
            .eq("id", device_id) \
            .eq("clerk_user_id", clerk_user_id) \
            .execute()

        if not check_result.data or len(check_result.data) == 0:
            return {"success": False, "message": "Device not found"}

        if check_result.data[0].get("used_at") is None:
            return {"success": False, "message": "Device is not paired"}

        # Delete the token (revoke the device)
        delete_result = supabase.table("mobile_pairing_tokens") \
            .delete() \
            .eq("id", device_id) \
            .eq("clerk_user_id", clerk_user_id) \
            .execute()

        if delete_result.data and len(delete_result.data) > 0:
            return {"success": True, "message": "Device revoked successfully"}
        else:
            return {"success": False, "message": "Failed to revoke device"}

    except Exception as e:
        logger.error(f"Error revoking device {device_id}: {e}")
        return {"success": False, "message": str(e)}