"""
API endpoint tests for mobile pairing (AMA-61, AMA-175, AMA-178).

Tests the FastAPI endpoints for mobile device pairing flow.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


class TestMobilePairingEndpoints:
    """Tests for /mobile/pairing/* API endpoints."""

    # -------------------------------------------------------------------------
    # POST /mobile/pairing/generate
    # -------------------------------------------------------------------------

    def test_generate_requires_auth(self, client: TestClient):
        """Generate endpoint should require authentication."""
        # Remove auth override temporarily
        from backend.app import app
        from backend.auth import get_current_user

        # Save and remove override
        original_override = app.dependency_overrides.get(get_current_user)
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        try:
            response = client.post("/mobile/pairing/generate")
            assert response.status_code == 401
        finally:
            # Restore override
            if original_override:
                app.dependency_overrides[get_current_user] = original_override

    @patch("backend.app.create_pairing_token")
    def test_generate_success(self, mock_create, client: TestClient):
        """Generate endpoint should return token data on success."""
        mock_create.return_value = {
            "token": "abc123",
            "short_code": "XYZ789",
            "qr_data": '{"type":"amakaflow_pairing"}',
            "expires_at": "2025-01-01T00:05:00Z",
            "expires_in_seconds": 300,
        }

        response = client.post("/mobile/pairing/generate")

        assert response.status_code == 200
        data = response.json()
        assert data["token"] == "abc123"
        assert data["short_code"] == "XYZ789"
        assert data["qr_data"] == '{"type":"amakaflow_pairing"}'
        assert data["expires_in_seconds"] == 300

    @patch("backend.app.create_pairing_token")
    def test_generate_returns_500_on_failure(self, mock_create, client: TestClient):
        """Generate endpoint should return 500 when token creation fails."""
        mock_create.return_value = None

        response = client.post("/mobile/pairing/generate")

        assert response.status_code == 500
        assert "Failed to create pairing token" in response.json()["detail"]

    @patch("backend.app.create_pairing_token")
    def test_generate_returns_429_on_rate_limit(self, mock_create, client: TestClient):
        """Generate endpoint should return 429 when rate limited."""
        mock_create.return_value = {
            "error": "rate_limit",
            "message": "Maximum 5 active tokens allowed"
        }

        response = client.post("/mobile/pairing/generate")

        assert response.status_code == 429
        assert "Maximum 5 active tokens" in response.json()["detail"]

    # -------------------------------------------------------------------------
    # POST /mobile/pairing/pair
    # -------------------------------------------------------------------------

    @patch("backend.app.validate_and_use_token")
    def test_pair_is_public(self, mock_validate, client: TestClient):
        """Pair endpoint should be public (no auth required)."""
        mock_validate.return_value = {"error": "invalid_token", "message": "Token not found"}

        response = client.post(
            "/mobile/pairing/pair",
            json={"short_code": "INVALID"}
        )

        # Should get 400 (bad request) not 401 (unauthorized)
        assert response.status_code == 400

    @patch("backend.app.validate_and_use_token")
    def test_pair_with_token_success(self, mock_validate, client: TestClient):
        """Pair endpoint should return JWT when valid token provided."""
        mock_validate.return_value = {
            "jwt": "eyJhbGciOiJIUzI1NiJ9.test.signature",
            "profile": {"id": "user-123", "email": "test@example.com", "name": "Test"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={"token": "valid-token-123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "jwt" in data
        assert data["profile"]["id"] == "user-123"

    @patch("backend.app.validate_and_use_token")
    def test_pair_with_short_code_success(self, mock_validate, client: TestClient):
        """Pair endpoint should accept short_code instead of token."""
        mock_validate.return_value = {
            "jwt": "eyJhbGciOiJIUzI1NiJ9.test.signature",
            "profile": {"id": "user-123", "email": "test@example.com", "name": "Test"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={"short_code": "ABC123"}
        )

        assert response.status_code == 200
        mock_validate.assert_called_once()
        # Verify short_code was passed
        call_kwargs = mock_validate.call_args[1]
        assert call_kwargs["short_code"] == "ABC123"

    @patch("backend.app.validate_and_use_token")
    def test_pair_with_device_info(self, mock_validate, client: TestClient):
        """Pair endpoint should accept device_info."""
        mock_validate.return_value = {
            "jwt": "test-jwt",
            "profile": {"id": "user-123"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        device_info = {"device": "iPhone 15 Pro", "os": "iOS 17.0"}
        response = client.post(
            "/mobile/pairing/pair",
            json={"token": "valid-token", "device_info": device_info}
        )

        assert response.status_code == 200
        # Verify device_info was passed
        call_kwargs = mock_validate.call_args[1]
        assert call_kwargs["device_info"] == device_info

    @patch("backend.app.validate_and_use_token")
    def test_pair_invalid_token(self, mock_validate, client: TestClient):
        """Pair endpoint should return 400 for invalid token."""
        mock_validate.return_value = {
            "error": "invalid_token",
            "message": "Token not found"
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={"token": "nonexistent-token"}
        )

        assert response.status_code == 400
        assert "Token not found" in response.json()["detail"]

    @patch("backend.app.validate_and_use_token")
    def test_pair_already_used_token(self, mock_validate, client: TestClient):
        """Pair endpoint should return 400 for already used token."""
        mock_validate.return_value = {
            "error": "token_used",
            "message": "Token has already been used"
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={"token": "used-token"}
        )

        assert response.status_code == 400
        assert "already been used" in response.json()["detail"]

    @patch("backend.app.validate_and_use_token")
    def test_pair_expired_token(self, mock_validate, client: TestClient):
        """Pair endpoint should return 400 for expired token."""
        mock_validate.return_value = {
            "error": "token_expired",
            "message": "Token has expired"
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={"short_code": "OLDCODE"}
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"]

    @patch("backend.app.validate_and_use_token")
    def test_pair_missing_both_token_and_code(self, mock_validate, client: TestClient):
        """Pair endpoint should return 400 when neither token nor short_code provided."""
        mock_validate.return_value = {
            "error": "invalid_request",
            "message": "Either token or short_code is required"
        }

        response = client.post(
            "/mobile/pairing/pair",
            json={}
        )

        assert response.status_code == 400

    @patch("backend.app.validate_and_use_token")
    def test_pair_returns_400_on_none(self, mock_validate, client: TestClient):
        """Pair endpoint should return 400 when validation returns None."""
        mock_validate.return_value = None

        response = client.post(
            "/mobile/pairing/pair",
            json={"token": "test"}
        )

        assert response.status_code == 400

    # -------------------------------------------------------------------------
    # GET /mobile/pairing/status/{token}
    # -------------------------------------------------------------------------

    @patch("backend.app.get_pairing_status")
    def test_status_is_public(self, mock_status, client: TestClient):
        """Status endpoint should be public (web app polls it)."""
        mock_status.return_value = {"paired": False, "expired": False, "device_info": None}

        response = client.get("/mobile/pairing/status/test-token")

        # Should succeed without auth
        assert response.status_code == 200

    @patch("backend.app.get_pairing_status")
    def test_status_not_paired(self, mock_status, client: TestClient):
        """Status endpoint should return paired=false for unpaired token."""
        mock_status.return_value = {
            "paired": False,
            "expired": False,
            "device_info": None
        }

        response = client.get("/mobile/pairing/status/my-token-123")

        assert response.status_code == 200
        data = response.json()
        assert data["paired"] is False
        assert data["expired"] is False

    @patch("backend.app.get_pairing_status")
    def test_status_paired(self, mock_status, client: TestClient):
        """Status endpoint should return paired=true after successful pairing."""
        mock_status.return_value = {
            "paired": True,
            "expired": False,
            "device_info": {"device": "iPhone 15"}
        }

        response = client.get("/mobile/pairing/status/paired-token")

        assert response.status_code == 200
        data = response.json()
        assert data["paired"] is True
        assert data["device_info"]["device"] == "iPhone 15"

    @patch("backend.app.get_pairing_status")
    def test_status_expired(self, mock_status, client: TestClient):
        """Status endpoint should return expired=true for expired token."""
        mock_status.return_value = {
            "paired": False,
            "expired": True,
            "device_info": None
        }

        response = client.get("/mobile/pairing/status/old-token")

        assert response.status_code == 200
        data = response.json()
        assert data["expired"] is True

    # -------------------------------------------------------------------------
    # DELETE /mobile/pairing/revoke
    # -------------------------------------------------------------------------

    def test_revoke_requires_auth(self, client: TestClient):
        """Revoke endpoint should require authentication."""
        from backend.app import app
        from backend.auth import get_current_user

        # Save and remove override
        original_override = app.dependency_overrides.get(get_current_user)
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]

        try:
            response = client.delete("/mobile/pairing/revoke")
            assert response.status_code == 401
        finally:
            if original_override:
                app.dependency_overrides[get_current_user] = original_override

    @patch("backend.app.revoke_user_tokens")
    def test_revoke_success(self, mock_revoke, client: TestClient):
        """Revoke endpoint should return count of revoked tokens."""
        mock_revoke.return_value = 3

        response = client.delete("/mobile/pairing/revoke")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["revoked_count"] == 3
        assert "3 pairing token" in data["message"]

    @patch("backend.app.revoke_user_tokens")
    def test_revoke_zero_tokens(self, mock_revoke, client: TestClient):
        """Revoke endpoint should handle case with no tokens to revoke."""
        mock_revoke.return_value = 0

        response = client.delete("/mobile/pairing/revoke")

        assert response.status_code == 200
        data = response.json()
        assert data["revoked_count"] == 0


class TestMobilePairingEndToEnd:
    """End-to-end tests for the pairing flow (with mocked database)."""

    @patch("backend.app.create_pairing_token")
    def test_full_pairing_flow_generate(self, mock_create, client: TestClient):
        """Test token generation returns expected format."""
        from backend.mobile_pairing import TOKEN_EXPIRY_MINUTES

        mock_create.return_value = {
            "token": "a" * 64,
            "short_code": "XYZ123",
            "qr_data": '{"type":"amakaflow_pairing"}',
            "expires_at": "2025-01-01T00:05:00Z",
            "expires_in_seconds": TOKEN_EXPIRY_MINUTES * 60,
        }

        response = client.post("/mobile/pairing/generate")
        assert response.status_code == 200

        data = response.json()
        assert len(data["token"]) == 64
        assert len(data["short_code"]) == 6
        assert data["expires_in_seconds"] == TOKEN_EXPIRY_MINUTES * 60

    @patch("backend.app.get_pairing_status")
    def test_polling_flow(self, mock_status, client: TestClient):
        """Test that status polling works correctly."""
        # First poll - not paired
        mock_status.return_value = {"paired": False, "expired": False, "device_info": None}
        response1 = client.get("/mobile/pairing/status/test-token")
        assert response1.json()["paired"] is False

        # Second poll - still not paired
        response2 = client.get("/mobile/pairing/status/test-token")
        assert response2.json()["paired"] is False

        # Third poll - now paired
        mock_status.return_value = {"paired": True, "expired": False, "device_info": {"device": "iPhone"}}
        response3 = client.get("/mobile/pairing/status/test-token")
        assert response3.json()["paired"] is True


class TestShortCodeCaseInsensitivity:
    """Tests for short code case handling."""

    @patch("backend.app.validate_and_use_token")
    def test_short_code_passed_to_validator(self, mock_validate, client: TestClient):
        """Short codes should be passed to validator."""
        mock_validate.return_value = {
            "jwt": "test-jwt",
            "profile": {"id": "user-123"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        # Send lowercase short code
        response = client.post(
            "/mobile/pairing/pair",
            json={"short_code": "abc123"}
        )

        assert response.status_code == 200
        # Verify the validator was called
        mock_validate.assert_called_once()


class TestResponseFormats:
    """Tests for API response format consistency."""

    @patch("backend.app.create_pairing_token")
    def test_generate_response_uses_snake_case(self, mock_create, client: TestClient):
        """Generate response should use snake_case for field names."""
        mock_create.return_value = {
            "token": "abc",
            "short_code": "XYZ123",
            "qr_data": "{}",
            "expires_at": "2025-01-01T00:00:00Z",
            "expires_in_seconds": 300,
        }

        response = client.post("/mobile/pairing/generate")
        data = response.json()

        # Verify snake_case keys
        assert "short_code" in data
        assert "qr_data" in data
        assert "expires_at" in data
        assert "expires_in_seconds" in data

        # Verify camelCase is NOT used
        assert "shortCode" not in data
        assert "qrData" not in data
        assert "expiresAt" not in data

    @patch("backend.app.get_pairing_status")
    def test_status_response_format(self, mock_status, client: TestClient):
        """Status response should have consistent format."""
        mock_status.return_value = {
            "paired": True,
            "expired": False,
            "device_info": {"device": "iPhone"}
        }

        response = client.get("/mobile/pairing/status/test")
        data = response.json()

        # Check expected structure
        assert "paired" in data
        assert "expired" in data
        assert "device_info" in data
        assert isinstance(data["paired"], bool)
        assert isinstance(data["expired"], bool)


# =============================================================================
# POST /mobile/pairing/refresh Tests (AMA-220)
# =============================================================================


class TestJWTRefreshEndpoint:
    """Tests for /mobile/pairing/refresh endpoint."""

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_is_public(self, mock_refresh, client: TestClient):
        """Refresh endpoint should be public (no auth required)."""
        mock_refresh.return_value = {
            "success": False,
            "error": "Device not found",
            "error_code": "DEVICE_NOT_FOUND"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "12345678-1234-1234-1234-123456789ABC"}
        )

        # Should get 401 (not found) not 403 (forbidden for missing auth)
        assert response.status_code == 401

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_success(self, mock_refresh, client: TestClient):
        """Refresh endpoint should return new JWT on success."""
        mock_refresh.return_value = {
            "success": True,
            "jwt": "eyJhbGciOiJIUzI1NiJ9.new.token",
            "expires_at": "2026-02-01T00:00:00+00:00",
            "refreshed_at": "2026-01-02T12:00:00+00:00"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "12345678-1234-1234-1234-123456789ABC"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "jwt" in data
        assert data["jwt"] == "eyJhbGciOiJIUzI1NiJ9.new.token"
        assert "expires_at" in data
        assert "refreshed_at" in data

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_device_not_found(self, mock_refresh, client: TestClient):
        """Refresh endpoint should return 401 when device not found."""
        mock_refresh.return_value = {
            "success": False,
            "error": "Device not found or not paired",
            "error_code": "DEVICE_NOT_FOUND"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "nonexistent-device-id"}
        )

        assert response.status_code == 401
        assert "not found" in response.json()["detail"].lower()

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_device_not_paired(self, mock_refresh, client: TestClient):
        """Refresh endpoint should return 401 when device exists but not paired."""
        mock_refresh.return_value = {
            "success": False,
            "error": "Device not paired",
            "error_code": "DEVICE_NOT_PAIRED"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "unpaired-device-id"}
        )

        assert response.status_code == 401
        assert "not paired" in response.json()["detail"].lower()

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_db_unavailable(self, mock_refresh, client: TestClient):
        """Refresh endpoint should return 500 on database error."""
        mock_refresh.return_value = {
            "success": False,
            "error": "Database connection unavailable",
            "error_code": "DB_UNAVAILABLE"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "any-device-id"}
        )

        assert response.status_code == 500

    def test_refresh_missing_device_id(self, client: TestClient):
        """Refresh endpoint should return 422 when device_id missing."""
        response = client.post(
            "/mobile/pairing/refresh",
            json={}
        )

        assert response.status_code == 422

    @patch("backend.app.refresh_jwt_for_device")
    def test_refresh_response_format(self, mock_refresh, client: TestClient):
        """Refresh response should use snake_case for field names."""
        mock_refresh.return_value = {
            "success": True,
            "jwt": "test.jwt.token",
            "expires_at": "2026-02-01T00:00:00+00:00",
            "refreshed_at": "2026-01-02T00:00:00+00:00"
        }

        response = client.post(
            "/mobile/pairing/refresh",
            json={"device_id": "test-device"}
        )

        data = response.json()

        # Verify snake_case keys
        assert "expires_at" in data
        assert "refreshed_at" in data

        # Verify camelCase is NOT used
        assert "expiresAt" not in data
        assert "refreshedAt" not in data
