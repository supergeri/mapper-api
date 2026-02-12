"""
Device Repository Interface (Port).

Part of AMA-384: Define repository interfaces (ports)
Phase 2 - Dependency Injection

This module defines the abstract interface for mobile device pairing
and authentication. Handles QR code / short code pairing flow.
"""
from typing import Protocol, Optional, List, Dict, Any


class DeviceRepository(Protocol):
    """
    Abstract interface for device pairing and authentication.

    This protocol defines the contract for managing mobile device
    pairing tokens and paired device records.
    """

    def create_pairing_token(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new pairing token for QR/short code pairing.

        Rate limited to prevent abuse (e.g., max 5 active tokens per user).

        Args:
            user_id: User ID (Clerk user ID)

        Returns:
            Dict with token, short_code, qr_data, expires_at, expires_in_seconds
            on success, or dict with "error" and "message" on rate limit/failure.
        """
        ...

    def validate_and_use_token(
        self,
        *,
        token: Optional[str] = None,
        short_code: Optional[str] = None,
        device_info: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Validate a pairing token and mark it as used.

        Either token (from QR) or short_code (manual entry) must be provided.

        Args:
            token: Full pairing token from QR code
            short_code: Human-readable short code
            device_info: Device metadata from iOS/Android

        Returns:
            Dict with jwt, profile, expires_at on success,
            or dict with "error" and "message" on failure (invalid, used, expired).
        """
        ...

    def get_pairing_status(
        self,
        token: str,
    ) -> Dict[str, Any]:
        """
        Check the status of a pairing token.

        Used by web app to poll for pairing completion.

        Args:
            token: The pairing token

        Returns:
            Dict with "paired" (bool), "expired" (bool), "device_info" (if paired)
        """
        ...

    def revoke_user_tokens(
        self,
        user_id: str,
    ) -> int:
        """
        Revoke all active (unused) pairing tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Number of tokens revoked
        """
        ...

    def get_paired_devices(
        self,
        user_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Get all paired devices for a user.

        Args:
            user_id: User ID

        Returns:
            List of paired device records with id, device_info, paired_at
        """
        ...

    def revoke_device(
        self,
        user_id: str,
        device_id: str,
    ) -> Dict[str, Any]:
        """
        Revoke a specific paired device.

        Args:
            user_id: User ID
            device_id: Device/token ID to revoke

        Returns:
            Dict with "success" (bool) and "message"
        """
        ...

    def update_apns_token(
        self,
        device_id: str,
        user_id: str,
        apns_token: str,
    ) -> Dict[str, Any]:
        """
        Store or update the APNs push token for a paired device.

        Args:
            device_id: iOS device UUID (identifierForVendor)
            user_id: User ID (Clerk user ID)
            apns_token: Hex-encoded APNs device token from Apple

        Returns:
            Dict with "success" (bool) and optional "error"
        """
        ...

    def get_apns_tokens(
        self,
        user_id: str,
    ) -> List[str]:
        """
        Get all non-null APNs tokens for a user's paired devices.

        Args:
            user_id: User ID (Clerk user ID)

        Returns:
            List of APNs token hex strings
        """
        ...

    def clear_apns_token(
        self,
        apns_token: str,
    ) -> bool:
        """
        Clear a stale APNs token (e.g. after BadDeviceToken from Apple).

        Args:
            apns_token: The APNs token to clear

        Returns:
            True if a token was cleared, False otherwise
        """
        ...

    def refresh_jwt(
        self,
        device_id: str,
    ) -> Dict[str, Any]:
        """
        Refresh JWT for a paired device using its device_id.

        Allows silent token refresh without re-pairing.

        Args:
            device_id: iOS device UUID (identifierForVendor)

        Returns:
            Dict with success, jwt, expires_at, refreshed_at on success,
            or success=False with error and error_code on failure.
        """
        ...


class UserProfileRepository(Protocol):
    """
    Abstract interface for user profile operations.

    Handles profile data retrieval for JWT generation and display.
    """

    def get_profile(
        self,
        user_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get user profile by ID.

        Args:
            user_id: User ID (Clerk user ID)

        Returns:
            Profile dict with id, email, name, avatar_url, or None if not found
        """
        ...

    def get_account_deletion_preview(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Get preview of data that would be deleted with account deletion.

        Args:
            user_id: User ID

        Returns:
            Dict with counts of workouts, completions, programs, tags, etc.
        """
        ...

    def delete_account(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Delete all user data permanently.

        Args:
            user_id: User ID

        Returns:
            Dict with success status and deleted counts per table
        """
        ...

    def reset_data(
        self,
        user_id: str,
    ) -> Dict[str, Any]:
        """
        Reset user data without deleting account.

        Clears generated data while keeping account and external connections.

        Args:
            user_id: User ID

        Returns:
            Dict with success status and deleted counts per table
        """
        ...
