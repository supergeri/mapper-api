"""
API endpoint tests for mobile pairing (AMA-61, AMA-175, AMA-178).

Tests the FastAPI endpoints for mobile device pairing flow.
Updated in AMA-388 to use dependency overrides instead of patches.
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.app import app
from api.deps import get_device_repo

# All tests in this module use TestClient - mark as integration
pytestmark = pytest.mark.integration


class TestMobilePairingEndpoints:
    """Tests for /mobile/pairing/* API endpoints."""

    # -------------------------------------------------------------------------
    # POST /mobile/pairing/generate
    # -------------------------------------------------------------------------

    def test_generate_requires_auth(self, client: TestClient):
        """Generate endpoint should require authentication."""
        # Remove auth override temporarily
        from backend.app import app
        from backend.auth import get_current_user as backend_get_current_user
        from api.deps import get_current_user as deps_get_current_user

        # Save and remove overrides (both old and new import paths)
        original_backend = app.dependency_overrides.get(backend_get_current_user)
        original_deps = app.dependency_overrides.get(deps_get_current_user)
        if backend_get_current_user in app.dependency_overrides:
            del app.dependency_overrides[backend_get_current_user]
        if deps_get_current_user in app.dependency_overrides:
            del app.dependency_overrides[deps_get_current_user]

        try:
            response = client.post("/mobile/pairing/generate")
            assert response.status_code == 401
        finally:
            # Restore overrides
            if original_backend:
                app.dependency_overrides[backend_get_current_user] = original_backend
            if original_deps:
                app.dependency_overrides[deps_get_current_user] = original_deps

    def test_generate_success(self, client: TestClient):
        """Generate endpoint should return token data on success."""
        mock_repo = Mock()
        mock_repo.create_pairing_token.return_value = {
            "token": "abc123",
            "short_code": "XYZ789",
            "qr_data": '{"type":"amakaflow_pairing"}',
            "expires_at": "2025-01-01T00:05:00Z",
            "expires_in_seconds": 300,
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post("/mobile/pairing/generate")

            assert response.status_code == 200
            data = response.json()
            assert data["token"] == "abc123"
            assert data["short_code"] == "XYZ789"
            assert data["qr_data"] == '{"type":"amakaflow_pairing"}'
            assert data["expires_in_seconds"] == 300
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_generate_returns_500_on_failure(self, client: TestClient):
        """Generate endpoint should return 500 when token creation fails."""
        mock_repo = Mock()
        mock_repo.create_pairing_token.return_value = None

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post("/mobile/pairing/generate")

            assert response.status_code == 500
            assert "Failed to create pairing token" in response.json()["detail"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_generate_returns_429_on_rate_limit(self, client: TestClient):
        """Generate endpoint should return 429 when rate limited."""
        mock_repo = Mock()
        mock_repo.create_pairing_token.return_value = {
            "error": "rate_limit",
            "message": "Maximum 5 active tokens allowed"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post("/mobile/pairing/generate")

            assert response.status_code == 429
            assert "Maximum 5 active tokens" in response.json()["detail"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    # -------------------------------------------------------------------------
    # POST /mobile/pairing/pair
    # -------------------------------------------------------------------------

    def test_pair_is_public(self, client: TestClient):
        """Pair endpoint should be public (no auth required)."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {"error": "invalid_token", "message": "Token not found"}

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"short_code": "INVALID"}
            )

            # Should get 400 (bad request) not 401 (unauthorized)
            assert response.status_code == 400
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_with_token_success(self, client: TestClient):
        """Pair endpoint should return JWT when valid token provided."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "jwt": "eyJhbGciOiJIUzI1NiJ9.test.signature",
            "profile": {"id": "user-123", "email": "test@example.com", "name": "Test"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"token": "valid-token-123"}
            )

            assert response.status_code == 200
            data = response.json()
            assert "jwt" in data
            assert data["profile"]["id"] == "user-123"
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_with_short_code_success(self, client: TestClient):
        """Pair endpoint should accept short_code instead of token."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "jwt": "eyJhbGciOiJIUzI1NiJ9.test.signature",
            "profile": {"id": "user-123", "email": "test@example.com", "name": "Test"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"short_code": "ABC123"}
            )

            assert response.status_code == 200
            mock_repo.validate_and_use_token.assert_called_once()
            # Verify short_code was passed
            call_kwargs = mock_repo.validate_and_use_token.call_args[1]
            assert call_kwargs["short_code"] == "ABC123"
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_with_device_info(self, client: TestClient):
        """Pair endpoint should accept device_info."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "jwt": "test-jwt",
            "profile": {"id": "user-123"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        device_info = {"device": "iPhone 15 Pro", "os": "iOS 17.0"}
        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"token": "valid-token", "device_info": device_info}
            )

            assert response.status_code == 200
            # Verify device_info was passed
            call_kwargs = mock_repo.validate_and_use_token.call_args[1]
            assert call_kwargs["device_info"] == device_info
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_invalid_token(self, client: TestClient):
        """Pair endpoint should return 400 for invalid token."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "error": "invalid_token",
            "message": "Token not found"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"token": "nonexistent-token"}
            )

            assert response.status_code == 400
            assert "Token not found" in response.json()["detail"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_already_used_token(self, client: TestClient):
        """Pair endpoint should return 400 for already used token."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "error": "token_used",
            "message": "Token has already been used"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"token": "used-token"}
            )

            assert response.status_code == 400
            assert "already been used" in response.json()["detail"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_expired_token(self, client: TestClient):
        """Pair endpoint should return 400 for expired token."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "error": "token_expired",
            "message": "Token has expired"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"short_code": "OLDCODE"}
            )

            assert response.status_code == 400
            assert "expired" in response.json()["detail"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_missing_both_token_and_code(self, client: TestClient):
        """Pair endpoint should return 400 when neither token nor short_code provided."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "error": "invalid_request",
            "message": "Either token or short_code is required"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={}
            )

            assert response.status_code == 400
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_pair_returns_400_on_none(self, client: TestClient):
        """Pair endpoint should return 400 when validation returns None."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = None

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/pair",
                json={"token": "test"}
            )

            assert response.status_code == 400
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    # -------------------------------------------------------------------------
    # GET /mobile/pairing/status/{token}
    # -------------------------------------------------------------------------

    def test_status_is_public(self, client: TestClient):
        """Status endpoint should be public (web app polls it)."""
        mock_repo = Mock()
        mock_repo.get_pairing_status.return_value = {"paired": False, "expired": False, "device_info": None}

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.get("/mobile/pairing/status/test-token")

            # Should succeed without auth
            assert response.status_code == 200
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_status_not_paired(self, client: TestClient):
        """Status endpoint should return paired=false for unpaired token."""
        mock_repo = Mock()
        mock_repo.get_pairing_status.return_value = {
            "paired": False,
            "expired": False,
            "device_info": None
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.get("/mobile/pairing/status/my-token-123")

            assert response.status_code == 200
            data = response.json()
            assert data["paired"] is False
            assert data["expired"] is False
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_status_paired(self, client: TestClient):
        """Status endpoint should return paired=true after successful pairing."""
        mock_repo = Mock()
        mock_repo.get_pairing_status.return_value = {
            "paired": True,
            "expired": False,
            "device_info": {"device": "iPhone 15"}
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.get("/mobile/pairing/status/paired-token")

            assert response.status_code == 200
            data = response.json()
            assert data["paired"] is True
            assert data["device_info"]["device"] == "iPhone 15"
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_status_expired(self, client: TestClient):
        """Status endpoint should return expired=true for expired token."""
        mock_repo = Mock()
        mock_repo.get_pairing_status.return_value = {
            "paired": False,
            "expired": True,
            "device_info": None
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.get("/mobile/pairing/status/old-token")

            assert response.status_code == 200
            data = response.json()
            assert data["expired"] is True
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    # -------------------------------------------------------------------------
    # DELETE /mobile/pairing/revoke
    # -------------------------------------------------------------------------

    def test_revoke_requires_auth(self, client: TestClient):
        """Revoke endpoint should require authentication."""
        from backend.app import app
        from backend.auth import get_current_user as backend_get_current_user
        from api.deps import get_current_user as deps_get_current_user

        # Save and remove overrides (both old and new import paths)
        original_backend = app.dependency_overrides.get(backend_get_current_user)
        original_deps = app.dependency_overrides.get(deps_get_current_user)
        if backend_get_current_user in app.dependency_overrides:
            del app.dependency_overrides[backend_get_current_user]
        if deps_get_current_user in app.dependency_overrides:
            del app.dependency_overrides[deps_get_current_user]

        try:
            response = client.delete("/mobile/pairing/revoke")
            assert response.status_code == 401
        finally:
            # Restore overrides
            if original_backend:
                app.dependency_overrides[backend_get_current_user] = original_backend
            if original_deps:
                app.dependency_overrides[deps_get_current_user] = original_deps

    def test_revoke_success(self, client: TestClient):
        """Revoke endpoint should return count of revoked tokens."""
        mock_repo = Mock()
        mock_repo.revoke_user_tokens.return_value = 3

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.delete("/mobile/pairing/revoke")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["revoked_count"] == 3
            assert "3 pairing token" in data["message"]
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_revoke_zero_tokens(self, client: TestClient):
        """Revoke endpoint should handle case with no tokens to revoke."""
        mock_repo = Mock()
        mock_repo.revoke_user_tokens.return_value = 0

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.delete("/mobile/pairing/revoke")

            assert response.status_code == 200
            data = response.json()
            assert data["revoked_count"] == 0
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]


class TestMobilePairingEndToEnd:
    """End-to-end tests for the pairing flow (with mocked database)."""

    def test_full_pairing_flow_generate(self, client: TestClient):
        """Test token generation returns expected format."""
        from backend.mobile_pairing import TOKEN_EXPIRY_MINUTES

        mock_repo = Mock()
        mock_repo.create_pairing_token.return_value = {
            "token": "a" * 64,
            "short_code": "XYZ123",
            "qr_data": '{"type":"amakaflow_pairing"}',
            "expires_at": "2025-01-01T00:05:00Z",
            "expires_in_seconds": TOKEN_EXPIRY_MINUTES * 60,
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post("/mobile/pairing/generate")
            assert response.status_code == 200

            data = response.json()
            assert len(data["token"]) == 64
            assert len(data["short_code"]) == 6
            assert data["expires_in_seconds"] == TOKEN_EXPIRY_MINUTES * 60
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_polling_flow(self, client: TestClient):
        """Test that status polling works correctly."""
        mock_repo = Mock()

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            # First poll - not paired
            mock_repo.get_pairing_status.return_value = {"paired": False, "expired": False, "device_info": None}
            response1 = client.get("/mobile/pairing/status/test-token")
            assert response1.json()["paired"] is False

            # Second poll - still not paired
            response2 = client.get("/mobile/pairing/status/test-token")
            assert response2.json()["paired"] is False

            # Third poll - now paired
            mock_repo.get_pairing_status.return_value = {"paired": True, "expired": False, "device_info": {"device": "iPhone"}}
            response3 = client.get("/mobile/pairing/status/test-token")
            assert response3.json()["paired"] is True
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]


class TestShortCodeCaseInsensitivity:
    """Tests for short code case handling."""

    def test_short_code_passed_to_validator(self, client: TestClient):
        """Short codes should be passed to validator."""
        mock_repo = Mock()
        mock_repo.validate_and_use_token.return_value = {
            "jwt": "test-jwt",
            "profile": {"id": "user-123"},
            "expires_at": "2025-02-01T00:00:00Z",
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            # Send lowercase short code
            response = client.post(
                "/mobile/pairing/pair",
                json={"short_code": "abc123"}
            )

            assert response.status_code == 200
            # Verify the validator was called
            mock_repo.validate_and_use_token.assert_called_once()
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]


class TestResponseFormats:
    """Tests for API response format consistency."""

    def test_generate_response_uses_snake_case(self, client: TestClient):
        """Generate response should use snake_case for field names."""
        mock_repo = Mock()
        mock_repo.create_pairing_token.return_value = {
            "token": "abc",
            "short_code": "XYZ123",
            "qr_data": "{}",
            "expires_at": "2025-01-01T00:00:00Z",
            "expires_in_seconds": 300,
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
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
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_status_response_format(self, client: TestClient):
        """Status response should have consistent format."""
        mock_repo = Mock()
        mock_repo.get_pairing_status.return_value = {
            "paired": True,
            "expired": False,
            "device_info": {"device": "iPhone"}
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.get("/mobile/pairing/status/test")
            data = response.json()

            # Check expected structure
            assert "paired" in data
            assert "expired" in data
            assert "device_info" in data
            assert isinstance(data["paired"], bool)
            assert isinstance(data["expired"], bool)
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]


# =============================================================================
# POST /mobile/pairing/refresh Tests (AMA-220)
# =============================================================================


class TestJWTRefreshEndpoint:
    """Tests for /mobile/pairing/refresh endpoint."""

    def test_refresh_is_public(self, client: TestClient):
        """Refresh endpoint should be public (no auth required)."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": False,
            "error": "Device not found",
            "error_code": "DEVICE_NOT_FOUND"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/refresh",
                json={"device_id": "12345678-1234-1234-1234-123456789ABC"}
            )

            # Should get 401 (not found) not 403 (forbidden for missing auth)
            assert response.status_code == 401
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_refresh_success(self, client: TestClient):
        """Refresh endpoint should return new JWT on success."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": True,
            "jwt": "eyJhbGciOiJIUzI1NiJ9.new.token",
            "expires_at": "2026-02-01T00:00:00+00:00",
            "refreshed_at": "2026-01-02T12:00:00+00:00"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
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
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_refresh_device_not_found(self, client: TestClient):
        """Refresh endpoint should return 401 when device not found."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": False,
            "error": "Device not found or not paired",
            "error_code": "DEVICE_NOT_FOUND"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/refresh",
                json={"device_id": "nonexistent-device-id"}
            )

            assert response.status_code == 401
            assert "not found" in response.json()["detail"].lower()
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_refresh_device_not_paired(self, client: TestClient):
        """Refresh endpoint should return 401 when device exists but not paired."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": False,
            "error": "Device not paired",
            "error_code": "DEVICE_NOT_PAIRED"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/refresh",
                json={"device_id": "unpaired-device-id"}
            )

            assert response.status_code == 401
            assert "not paired" in response.json()["detail"].lower()
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_refresh_db_unavailable(self, client: TestClient):
        """Refresh endpoint should return 500 on database error."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": False,
            "error": "Database connection unavailable",
            "error_code": "DB_UNAVAILABLE"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
            response = client.post(
                "/mobile/pairing/refresh",
                json={"device_id": "any-device-id"}
            )

            assert response.status_code == 500
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]

    def test_refresh_missing_device_id(self, client: TestClient):
        """Refresh endpoint should return 422 when device_id missing."""
        response = client.post(
            "/mobile/pairing/refresh",
            json={}
        )

        assert response.status_code == 422

    def test_refresh_response_format(self, client: TestClient):
        """Refresh response should use snake_case for field names."""
        mock_repo = Mock()
        mock_repo.refresh_jwt.return_value = {
            "success": True,
            "jwt": "test.jwt.token",
            "expires_at": "2026-02-01T00:00:00+00:00",
            "refreshed_at": "2026-01-02T00:00:00+00:00"
        }

        original = app.dependency_overrides.get(get_device_repo)
        app.dependency_overrides[get_device_repo] = lambda: mock_repo
        try:
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
        finally:
            if original:
                app.dependency_overrides[get_device_repo] = original
            elif get_device_repo in app.dependency_overrides:
                del app.dependency_overrides[get_device_repo]
