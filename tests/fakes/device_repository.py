"""
Fake Device and User Profile Repositories for testing.

Part of AMA-387: Add in-memory fake repositories for tests
Phase 2 - Dependency Injection

This module provides in-memory implementations of DeviceRepository and
UserProfileRepository for fast, isolated testing without database dependencies.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import secrets
import json
import copy


def _generate_pairing_tokens() -> tuple:
    """Generate a pairing token and short code."""
    token = secrets.token_hex(32)
    short_code = "".join(secrets.choice("0123456789") for _ in range(6))
    return token, short_code


def _generate_qr_data(token: str, api_url: str = "https://api.test.com") -> str:
    """Generate QR code data for pairing."""
    return json.dumps({
        "type": "amakaflow_pairing",
        "version": 1,
        "token": token,
        "api_url": api_url,
    })


class FakeDeviceRepository:
    """
    In-memory fake implementation of DeviceRepository for testing.

    Stores pairing tokens and paired devices in dicts.

    Usage:
        repo = FakeDeviceRepository()
        result = repo.create_pairing_token(user_id="user1")
        repo.validate_and_use_token(token=result["token"], device_info={...})
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._tokens: Dict[str, Dict[str, Any]] = {}  # token -> token_record
        self._short_codes: Dict[str, str] = {}  # short_code -> token
        self._paired_devices: Dict[str, Dict[str, Any]] = {}  # device_id -> device_record
        self._max_active_tokens = 5
        self._token_expiry_minutes = 15
        self._jwt_expiry_days = 30

    def reset(self) -> None:
        """Clear all stored tokens and devices."""
        self._tokens.clear()
        self._short_codes.clear()
        self._paired_devices.clear()

    def seed_tokens(self, tokens: List[Dict[str, Any]]) -> None:
        """Seed with pairing tokens for testing."""
        for token_data in tokens:
            token = token_data.get("token") or secrets.token_hex(32)
            short_code = token_data.get("short_code") or "123456"
            self._tokens[token] = {**token_data, "token": token, "short_code": short_code}
            self._short_codes[short_code] = token

    def seed_devices(self, devices: List[Dict[str, Any]]) -> None:
        """Seed with paired devices for testing."""
        for device in devices:
            device_id = device.get("device_id") or str(uuid.uuid4())
            self._paired_devices[device_id] = {**device, "device_id": device_id}

    # =========================================================================
    # DeviceRepository Protocol Methods
    # =========================================================================

    def create_pairing_token(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Create a new pairing token for QR/short code pairing."""
        # Check rate limit
        active_count = sum(
            1 for t in self._tokens.values()
            if t.get("user_id") == user_id
            and not t.get("used")
            and t.get("expires_at", "") > datetime.now(timezone.utc).isoformat()
        )
        if active_count >= self._max_active_tokens:
            return {
                "error": "rate_limit",
                "message": f"Maximum {self._max_active_tokens} active tokens allowed",
            }

        token, short_code = _generate_pairing_tokens()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self._token_expiry_minutes)

        token_record = {
            "token": token,
            "short_code": short_code,
            "user_id": user_id,
            "used": False,
            "device_info": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at.isoformat(),
        }

        self._tokens[token] = token_record
        self._short_codes[short_code] = token

        return {
            "token": token,
            "short_code": short_code,
            "qr_data": _generate_qr_data(token),
            "expires_at": expires_at.isoformat(),
            "expires_in_seconds": self._token_expiry_minutes * 60,
        }

    def validate_and_use_token(
        self,
        *,
        token: Optional[str] = None,
        short_code: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Validate a pairing token and mark it as used."""
        # Resolve token from short_code if needed
        if short_code and not token:
            token = self._short_codes.get(short_code)

        if not token or token not in self._tokens:
            return {"error": "invalid_token", "message": "Token not found"}

        token_record = self._tokens[token]

        # Check if already used
        if token_record.get("used"):
            return {"error": "token_used", "message": "Token has already been used"}

        # Check if expired
        if token_record.get("expires_at", "") < datetime.now(timezone.utc).isoformat():
            return {"error": "token_expired", "message": "Token has expired"}

        # Mark as used
        token_record["used"] = True
        token_record["device_info"] = device_info
        token_record["used_at"] = datetime.now(timezone.utc).isoformat()

        # Create paired device record
        device_id = (device_info or {}).get("device_id") or str(uuid.uuid4())
        jwt_expires = datetime.now(timezone.utc) + timedelta(days=self._jwt_expiry_days)

        device_record = {
            "device_id": device_id,
            "user_id": token_record["user_id"],
            "device_info": device_info,
            "jwt": f"fake_jwt_{secrets.token_hex(16)}",
            "jwt_expires_at": jwt_expires.isoformat(),
            "paired_at": datetime.now(timezone.utc).isoformat(),
            "revoked": False,
        }
        self._paired_devices[device_id] = device_record

        return {
            "jwt": device_record["jwt"],
            "profile": {
                "user_id": token_record["user_id"],
                "email": "test@example.com",
                "name": "Test User",
            },
            "expires_at": jwt_expires.isoformat(),
        }

    def get_pairing_status(
        self,
        token: str,
    ) -> Dict[str, Any]:
        """Check the status of a pairing token."""
        if token not in self._tokens:
            return {"paired": False, "expired": True, "device_info": None}

        token_record = self._tokens[token]
        expired = token_record.get("expires_at", "") < datetime.now(timezone.utc).isoformat()

        return {
            "paired": token_record.get("used", False),
            "expired": expired,
            "device_info": token_record.get("device_info"),
        }

    def revoke_user_tokens(
        self,
        user_id: str,
    ) -> int:
        """Revoke all active (unused) pairing tokens for a user."""
        revoked = 0
        tokens_to_remove = []
        for token, record in self._tokens.items():
            if record.get("user_id") == user_id and not record.get("used"):
                tokens_to_remove.append(token)
                if record.get("short_code") in self._short_codes:
                    del self._short_codes[record["short_code"]]
                revoked += 1

        for token in tokens_to_remove:
            del self._tokens[token]

        return revoked

    def get_paired_devices(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """Get all paired devices for a user."""
        devices = []
        for device in self._paired_devices.values():
            if device.get("user_id") == user_id and not device.get("revoked"):
                devices.append({
                    "id": device["device_id"],
                    "device_info": device.get("device_info"),
                    "paired_at": device.get("paired_at"),
                })
        return devices

    def revoke_device(
        self,
        user_id: str,
        device_id: str,
    ) -> Dict[str, Any]:
        """Revoke a specific paired device."""
        device = self._paired_devices.get(device_id)
        if not device or device.get("user_id") != user_id:
            return {"success": False, "message": "Device not found"}

        device["revoked"] = True
        device["revoked_at"] = datetime.now(timezone.utc).isoformat()

        return {"success": True, "message": "Device revoked"}

    def refresh_jwt(
        self,
        device_id: str,
    ) -> Dict[str, Any]:
        """Refresh JWT for a paired device."""
        device = self._paired_devices.get(device_id)

        if not device:
            return {
                "success": False,
                "error": "Device not found",
                "error_code": "DEVICE_NOT_FOUND",
            }

        if device.get("revoked"):
            return {
                "success": False,
                "error": "Device has been revoked",
                "error_code": "DEVICE_REVOKED",
            }

        # Generate new JWT
        new_jwt = f"fake_jwt_{secrets.token_hex(16)}"
        new_expires = datetime.now(timezone.utc) + timedelta(days=self._jwt_expiry_days)

        device["jwt"] = new_jwt
        device["jwt_expires_at"] = new_expires.isoformat()

        return {
            "success": True,
            "jwt": new_jwt,
            "expires_at": new_expires.isoformat(),
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }


class FakeUserProfileRepository:
    """
    In-memory fake implementation of UserProfileRepository for testing.

    Stores user profiles in a dict keyed by user ID.

    Usage:
        repo = FakeUserProfileRepository()
        repo.seed([{"id": "user1", "email": "test@example.com", ...}])
        profile = repo.get_profile("user1")
    """

    def __init__(self):
        """Initialize with empty storage."""
        self._profiles: Dict[str, Dict[str, Any]] = {}
        # Track counts for deletion preview (simulate counts from other tables)
        self._user_data_counts: Dict[str, Dict[str, int]] = {}

    def reset(self) -> None:
        """Clear all stored profiles."""
        self._profiles.clear()
        self._user_data_counts.clear()

    def seed(self, profiles: List[Dict[str, Any]]) -> None:
        """
        Seed the repository with test data.

        Args:
            profiles: List of profile dicts. Must include 'id'.
        """
        for profile in profiles:
            user_id = profile.get("id") or str(uuid.uuid4())
            self._profiles[user_id] = {**profile, "id": user_id}

    def set_data_counts(self, user_id: str, counts: Dict[str, int]) -> None:
        """Set simulated data counts for deletion preview testing."""
        self._user_data_counts[user_id] = counts

    # =========================================================================
    # UserProfileRepository Protocol Methods
    # =========================================================================

    def get_profile(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get user profile by ID."""
        profile = self._profiles.get(user_id)
        if profile:
            return copy.deepcopy(profile)
        return None

    def get_account_deletion_preview(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Get preview of data that would be deleted."""
        counts = self._user_data_counts.get(user_id, {})
        return {
            "workouts": counts.get("workouts", 0),
            "completions": counts.get("completions", 0),
            "programs": counts.get("programs", 0),
            "tags": counts.get("tags", 0),
            "mappings": counts.get("mappings", 0),
            "paired_devices": counts.get("paired_devices", 0),
        }

    def delete_account(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Delete all user data permanently."""
        counts = self._user_data_counts.get(user_id, {})
        deleted_counts = copy.deepcopy(counts)

        # Clear user data
        if user_id in self._profiles:
            del self._profiles[user_id]
        if user_id in self._user_data_counts:
            del self._user_data_counts[user_id]

        return {
            "success": True,
            "deleted": deleted_counts,
        }

    def reset_data(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """Reset user data without deleting account."""
        counts = self._user_data_counts.get(user_id, {})
        deleted_counts = copy.deepcopy(counts)

        # Reset counts but keep profile
        self._user_data_counts[user_id] = {
            "workouts": 0,
            "completions": 0,
            "programs": 0,
            "tags": 0,
            "mappings": 0,
            "paired_devices": 0,
        }

        return {
            "success": True,
            "deleted": deleted_counts,
        }
