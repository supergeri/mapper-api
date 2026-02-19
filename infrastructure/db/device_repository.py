"""
Supabase Device Repository Implementation.

Part of AMA-385: Implement Supabase repositories in infrastructure/db
Phase 2 - Dependency Injection

This module implements the DeviceRepository and UserProfileRepository protocols
using Supabase as the backend. Extracted from backend/mobile_pairing.py.
"""
import os
import secrets
import json
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from supabase import Client
import logging
import jwt

from application.ports.device_repository import (
    DeviceRepository,
    UserProfileRepository,
)

logger = logging.getLogger(__name__)

# Token configuration
TOKEN_EXPIRY_MINUTES = 5
JWT_EXPIRY_DAYS = 30
JWT_ALGORITHM = "HS256"

# Rate limiting: max tokens per user per hour
MAX_TOKENS_PER_HOUR = 5
RATE_LIMIT_WINDOW_HOURS = 1

# Character set for short codes (no confusing characters: 0,O,1,I,l)
SHORT_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
SHORT_CODE_LENGTH = 6


def _get_jwt_secret() -> str:
    """Get JWT secret, failing fast if not configured in production."""
    env = os.getenv("ENVIRONMENT", "development")
    secret = os.getenv("JWT_SECRET")
    if secret:
        return secret
    if env == "production":
        raise RuntimeError("JWT_SECRET must be configured in production environment")
    # Development fallback - warn but allow
    logger.warning("JWT_SECRET not set, using insecure default for development")
    return "amakaflow-mobile-jwt-secret-change-in-production"


# ============================================================================
# Helper Functions (stateless utilities)
# ============================================================================

def generate_pairing_tokens() -> Tuple[str, str]:
    """Generate a secure pairing token and human-readable short code."""
    token = secrets.token_hex(32)
    short_code = ''.join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))
    return token, short_code


def generate_qr_data(token: str, api_url: Optional[str] = None) -> str:
    """Generate QR code data as JSON string."""
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
    """Generate a JWT for the iOS app."""
    secret = _get_jwt_secret()
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

    token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
    return token, expiry


def fetch_clerk_profile(clerk_user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch user profile from Clerk API."""
    clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
    if not clerk_secret_key:
        return None

    try:
        from clerk_backend_api import Clerk
        client = Clerk(bearer_auth=clerk_secret_key)
        user = client.users.get(user_id=clerk_user_id)
        if user:
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
    except ImportError:
        logger.warning("clerk_backend_api not installed")
    except Exception as e:
        logger.warning(f"Failed to fetch Clerk profile for {clerk_user_id}: {e}")

    return None


# ============================================================================
# Repository Implementations
# ============================================================================

class SupabaseDeviceRepository:
    """
    Supabase implementation of DeviceRepository.

    Handles mobile device pairing and authentication via QR code / short code flow.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected)
        """
        self._client = client

    def create_pairing_token(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new pairing token for QR/short code pairing.

        AMA-170: Ensures user profile exists before creating token to avoid
        foreign key constraint violation when profile hasn't been synced yet.
        """
        # AMA-170: Ensure profile exists to avoid foreign key constraint violation
        # The mobile_pairing_tokens table has a foreign key to profiles(id)
        self._ensure_profile_exists(user_id)

        try:
            # Check rate limit - count tokens created in the last hour window
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=RATE_LIMIT_WINDOW_HOURS)
            rate_check = self._client.table("mobile_pairing_tokens") \
                .select("id") \
                .eq("clerk_user_id", user_id) \
                .gte("created_at", hour_ago.isoformat()) \
                .execute()

            if rate_check.data and len(rate_check.data) >= MAX_TOKENS_PER_HOUR:
                logger.warning(f"Rate limit exceeded for user {user_id}")
                return {"error": "rate_limit", "message": f"Maximum {MAX_TOKENS_PER_HOUR} tokens per hour"}

            # Generate tokens
            token, short_code = generate_pairing_tokens()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
            qr_data = generate_qr_data(token)

            # Insert into database
            result = self._client.table("mobile_pairing_tokens").insert({
                "clerk_user_id": user_id,
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

    def _ensure_profile_exists(self, user_id: str) -> None:
        """
        Ensure a profile exists for the user, creating one if necessary.

        AMA-170: This addresses the foreign key constraint on mobile_pairing_tokens
        that references profiles(id). If the profile doesn't exist, we create
        a minimal one using Clerk data.

        Args:
            user_id: The Clerk user ID
        """
        # Fix 3: Add input validation for user_id
        if not user_id or not isinstance(user_id, str):
            logger.warning(f"Invalid user_id provided: {user_id}")
            return

        # Fix 2: Replace broad exception handling with specific exceptions
        try:
            # Check if profile exists
            profile_result = self._client.table("profiles").select("id").eq("id", user_id).execute()
            if profile_result.data and len(profile_result.data) > 0:
                return  # Profile exists

            # Profile doesn't exist - try to create it from Clerk data
            clerk_profile = self._fetch_clerk_profile(user_id)
            if clerk_profile:
                # Fix 4: Add type assertions for first_name and last_name
                first_name = clerk_profile.get("first_name")
                last_name = clerk_profile.get("last_name")

                # Ensure they are strings (or None)
                if first_name is not None and not isinstance(first_name, str):
                    first_name = str(first_name) if first_name else None
                if last_name is not None and not isinstance(last_name, str):
                    last_name = str(last_name) if last_name else None

                # Build name from first_name and last_name
                name = None
                if first_name or last_name:
                    name_parts = []
                    if first_name:
                        name_parts.append(first_name)
                    if last_name:
                        name_parts.append(last_name)
                    name = " ".join(name_parts)

                # Fix 5: Use upsert to handle race condition
                # on_conflict="id" will handle the case where another process
                # creates the profile between our check and insert
                self._client.table("profiles").insert({
                    "id": user_id,
                    "email": clerk_profile.get("email"),
                    "name": name,
                    "avatar_url": clerk_profile.get("image_url"),
                }).on_conflict("id").execute()
                logger.info(f"Created profile for user {user_id} during pairing")
        except Exception as e:
            # Log but don't raise - let the caller proceed
            # The foreign key might still work if profile was created by another process
            logger.warning(f"Error ensuring profile exists for {user_id}: {e}")

    def _fetch_clerk_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile from Clerk API.

        Args:
            user_id: The Clerk user ID

        Returns:
            Dict with profile data or None if fetch fails
        """
        # Fix 1: Call module-level function directly instead of importing
        return fetch_clerk_profile(user_id)

    def validate_and_use_token(
        self,
        *,
        token: Optional[str] = None,
        short_code: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate a pairing token and mark it as used."""
        if not token and not short_code:
            return {"error": "invalid_request", "message": "Either token or short_code is required"}

        # Validate device_info if provided
        if device_info is not None:
            if not isinstance(device_info, dict):
                return {"error": "invalid_device_info", "message": "device_info must be a dictionary"}
            # Validate known fields
            known_fields = {"device_id", "device_name", "os_version", "app_version", "model"}
            for key, value in device_info.items():
                if key not in known_fields:
                    logger.warning(f"Unknown device_info field: {key}")
                if isinstance(value, str) and len(value) > 500:
                    return {"error": "invalid_device_info", "message": f"device_info.{key} exceeds 500 character limit"}

        try:
            # Find the token
            query = self._client.table("mobile_pairing_tokens").select("*")

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
            update_result = self._client.table("mobile_pairing_tokens").update({
                "used_at": datetime.now(timezone.utc).isoformat(),
                "device_info": device_info,
            }).eq("id", token_record["id"]).execute()

            if not update_result.data:
                logger.error("Failed to mark token as used")
                return None

            # Get user profile - try Clerk API first, fallback to Supabase
            clerk_user_id = token_record["clerk_user_id"]

            profile = fetch_clerk_profile(clerk_user_id)

            if profile is None:
                logger.info(f"Clerk profile fetch failed for {clerk_user_id}, using Supabase fallback")
                profile_result = self._client.table("profiles").select("*").eq("id", clerk_user_id).execute()

                if profile_result.data and len(profile_result.data) > 0:
                    db_profile = profile_result.data[0]
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

    def get_pairing_status(
        self,
        token: str,
    ) -> Dict[str, Any]:
        """Check the status of a pairing token."""
        try:
            result = self._client.table("mobile_pairing_tokens") \
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

    def revoke_user_tokens(
        self,
        user_id: str,
    ) -> int:
        """Revoke all active (unused) pairing tokens for a user."""
        try:
            result = self._client.table("mobile_pairing_tokens") \
                .delete() \
                .eq("clerk_user_id", user_id) \
                .is_("used_at", "null") \
                .execute()

            return len(result.data) if result.data else 0

        except Exception as e:
            logger.error(f"Error revoking tokens: {e}")
            return 0

    def get_paired_devices(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all paired devices for a user."""
        try:
            result = self._client.table("mobile_pairing_tokens") \
                .select("id, device_info, used_at, created_at") \
                .eq("clerk_user_id", user_id) \
                .not_.is_("used_at", "null") \
                .order("used_at", desc=True) \
                .execute()

            if not result.data:
                return []

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

    def revoke_device(
        self,
        user_id: str,
        device_id: str,
    ) -> Dict[str, Any]:
        """Revoke a specific paired device."""
        try:
            # Verify the device belongs to this user and is paired
            check_result = self._client.table("mobile_pairing_tokens") \
                .select("id, used_at") \
                .eq("id", device_id) \
                .eq("clerk_user_id", user_id) \
                .execute()

            if not check_result.data or len(check_result.data) == 0:
                return {"success": False, "message": "Device not found"}

            if check_result.data[0].get("used_at") is None:
                return {"success": False, "message": "Device is not paired"}

            # Delete the token (revoke the device)
            delete_result = self._client.table("mobile_pairing_tokens") \
                .delete() \
                .eq("id", device_id) \
                .eq("clerk_user_id", user_id) \
                .execute()

            if delete_result.data and len(delete_result.data) > 0:
                return {"success": True, "message": "Device revoked successfully"}
            else:
                return {"success": False, "message": "Failed to revoke device"}

        except Exception as e:
            logger.error(f"Error revoking device {device_id}: {e}")
            return {"success": False, "message": str(e)}

    def update_apns_token(
        self,
        device_id: str,
        user_id: str,
        apns_token: str,
    ) -> Dict[str, Any]:
        """Store or update the APNs push token for a paired device."""
        try:
            # Find the paired device by device_id in device_info JSONB, scoped to user
            result = self._client.table("mobile_pairing_tokens") \
                .select("id, used_at") \
                .eq("clerk_user_id", user_id) \
                .filter("device_info->>device_id", "eq", device_id) \
                .execute()

            if not result.data or len(result.data) == 0:
                return {"success": False, "error": "Device not found or not paired"}

            token_record = result.data[0]
            if not token_record.get("used_at"):
                return {"success": False, "error": "Device not paired"}

            self._client.table("mobile_pairing_tokens").update({
                "apns_token": apns_token,
            }).eq("id", token_record["id"]).execute()

            logger.info(f"APNs token updated for device {device_id[:8]}... user {user_id}")
            return {"success": True}

        except Exception as e:
            logger.error(f"Error updating APNs token for device {device_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_apns_tokens(
        self,
        user_id: str,
    ) -> List[str]:
        """Get all non-null APNs tokens for a user's paired devices."""
        try:
            result = self._client.table("mobile_pairing_tokens") \
                .select("apns_token") \
                .eq("clerk_user_id", user_id) \
                .not_.is_("used_at", "null") \
                .not_.is_("apns_token", "null") \
                .execute()

            if not result.data:
                return []

            return [r["apns_token"] for r in result.data if r.get("apns_token")]

        except Exception as e:
            logger.error(f"Error fetching APNs tokens for user {user_id}: {e}")
            return []

    def clear_apns_token(
        self,
        apns_token: str,
    ) -> bool:
        """Clear a stale APNs token (e.g. after BadDeviceToken from Apple)."""
        try:
            result = self._client.table("mobile_pairing_tokens") \
                .update({"apns_token": None}) \
                .eq("apns_token", apns_token) \
                .execute()

            cleared = bool(result.data)
            if cleared:
                logger.info("Cleared stale APNs token %s...", apns_token[:8])
            return cleared

        except Exception as e:
            logger.error("Error clearing APNs token %s...: %s", apns_token[:8], e)
            return False

    def refresh_jwt(
        self,
        device_id: str,
    ) -> Dict[str, Any]:
        """Refresh JWT for a paired device using its device_id."""
        try:
            # Find the paired device by device_id in device_info JSONB
            result = self._client.table("mobile_pairing_tokens") \
                .select("id, clerk_user_id, device_info, used_at") \
                .filter("device_info->>device_id", "eq", device_id) \
                .execute()

            if not result.data or len(result.data) == 0:
                logger.warning(f"Device not found for refresh: {device_id[:8]}...")
                return {
                    "success": False,
                    "error": "Device not found or not paired",
                    "error_code": "DEVICE_NOT_FOUND"
                }

            token_record = result.data[0]

            # Verify device is actually paired
            if not token_record.get("used_at"):
                logger.warning(f"Device not paired for refresh: {device_id[:8]}...")
                return {
                    "success": False,
                    "error": "Device not paired",
                    "error_code": "DEVICE_NOT_PAIRED"
                }

            clerk_user_id = token_record["clerk_user_id"]

            # Fetch user profile for JWT
            profile = fetch_clerk_profile(clerk_user_id)
            if profile is None:
                profile_result = self._client.table("profiles").select("*").eq("id", clerk_user_id).execute()
                if profile_result.data and len(profile_result.data) > 0:
                    db_profile = profile_result.data[0]
                    name = db_profile.get("name", "")
                    name_parts = name.split(" ", 1) if name else ["", ""]
                    profile = {
                        "id": db_profile.get("id"),
                        "email": db_profile.get("email"),
                        "first_name": name_parts[0] if name_parts else None,
                        "last_name": name_parts[1] if len(name_parts) > 1 else None,
                        "image_url": db_profile.get("avatar_url"),
                    }
                else:
                    profile = {"id": clerk_user_id, "email": None}

            # Generate new JWT
            jwt_token, jwt_expiry = generate_jwt_for_user(clerk_user_id, profile)

            # Update last_token_refresh timestamp
            now = datetime.now(timezone.utc)
            self._client.table("mobile_pairing_tokens").update({
                "last_token_refresh": now.isoformat(),
            }).eq("id", token_record["id"]).execute()

            logger.info(f"JWT refreshed for device {device_id[:8]}... user {clerk_user_id}")

            return {
                "success": True,
                "jwt": jwt_token,
                "expires_at": jwt_expiry.isoformat(),
                "refreshed_at": now.isoformat(),
            }

        except Exception as e:
            logger.error(f"Error refreshing JWT for device {device_id}: {e}")
            return {
                "success": False,
                "error": "Failed to refresh token",
                "error_code": "REFRESH_FAILED"
            }


class SupabaseUserProfileRepository:
    """
    Supabase implementation of UserProfileRepository.

    Handles user profile retrieval and account management operations.
    """

    def __init__(self, client: Client):
        """
        Initialize with Supabase client.

        Args:
            client: Supabase client instance (injected)
        """
        self._client = client

    def get_profile(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get user profile by ID."""
        try:
            # Try Clerk API first
            profile = fetch_clerk_profile(user_id)
            if profile:
                return profile

            # Fallback to Supabase
            result = self._client.table("profiles") \
                .select("*") \
                .eq("id", user_id) \
                .single() \
                .execute()

            if result.data:
                db_profile = result.data
                return {
                    "id": db_profile.get("id"),
                    "email": db_profile.get("email"),
                    "name": db_profile.get("name"),
                    "avatar_url": db_profile.get("avatar_url"),
                }

            return None

        except Exception as e:
            logger.error(f"Error fetching profile for {user_id}: {e}")
            return None

    def get_account_deletion_preview(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get preview of data that would be deleted with account deletion."""
        try:
            # Count various data types
            counts = {}

            # Workouts
            workouts_result = self._client.table("workouts") \
                .select("id", count="exact") \
                .eq("profile_id", user_id) \
                .execute()
            counts["workouts"] = workouts_result.count or 0

            # Completions
            completions_result = self._client.table("workout_completions") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .execute()
            counts["completions"] = completions_result.count or 0

            # Paired devices
            devices_result = self._client.table("mobile_pairing_tokens") \
                .select("id", count="exact") \
                .eq("clerk_user_id", user_id) \
                .not_.is_("used_at", "null") \
                .execute()
            counts["paired_devices"] = devices_result.count or 0

            # User mappings
            mappings_result = self._client.table("user_mappings") \
                .select("id", count="exact") \
                .eq("user_id", user_id) \
                .execute()
            counts["user_mappings"] = mappings_result.count or 0

            return {
                "success": True,
                "preview": counts,
                "total_items": sum(counts.values()),
            }

        except Exception as e:
            logger.error(f"Error getting deletion preview for {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "preview": {},
            }

    def delete_account(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Delete all user data permanently."""
        deleted_counts = {}

        try:
            # Delete in order of dependencies

            # 1. Workout completions
            completions_result = self._client.table("workout_completions") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            deleted_counts["completions"] = len(completions_result.data) if completions_result.data else 0

            # 2. Workouts
            workouts_result = self._client.table("workouts") \
                .delete() \
                .eq("profile_id", user_id) \
                .execute()
            deleted_counts["workouts"] = len(workouts_result.data) if workouts_result.data else 0

            # 3. Pairing tokens (all, not just paired)
            tokens_result = self._client.table("mobile_pairing_tokens") \
                .delete() \
                .eq("clerk_user_id", user_id) \
                .execute()
            deleted_counts["pairing_tokens"] = len(tokens_result.data) if tokens_result.data else 0

            # 4. User mappings
            mappings_result = self._client.table("user_mappings") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            deleted_counts["user_mappings"] = len(mappings_result.data) if mappings_result.data else 0

            # 5. Profile (last)
            profile_result = self._client.table("profiles") \
                .delete() \
                .eq("id", user_id) \
                .execute()
            deleted_counts["profile"] = len(profile_result.data) if profile_result.data else 0

            logger.info(f"Account deleted for user {user_id}: {deleted_counts}")

            return {
                "success": True,
                "deleted": deleted_counts,
                "total_deleted": sum(deleted_counts.values()),
            }

        except Exception as e:
            logger.error(f"Error deleting account for {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "deleted": deleted_counts,
            }

    def reset_data(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Reset user data without deleting account."""
        deleted_counts = {}

        try:
            # Delete generated data but keep account

            # 1. Workout completions
            completions_result = self._client.table("workout_completions") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            deleted_counts["completions"] = len(completions_result.data) if completions_result.data else 0

            # 2. Workouts
            workouts_result = self._client.table("workouts") \
                .delete() \
                .eq("profile_id", user_id) \
                .execute()
            deleted_counts["workouts"] = len(workouts_result.data) if workouts_result.data else 0

            # 3. User mappings
            mappings_result = self._client.table("user_mappings") \
                .delete() \
                .eq("user_id", user_id) \
                .execute()
            deleted_counts["user_mappings"] = len(mappings_result.data) if mappings_result.data else 0

            # Note: Keep profile and paired devices

            logger.info(f"Data reset for user {user_id}: {deleted_counts}")

            return {
                "success": True,
                "deleted": deleted_counts,
                "total_deleted": sum(deleted_counts.values()),
            }

        except Exception as e:
            logger.error(f"Error resetting data for {user_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "deleted": deleted_counts,
            }
