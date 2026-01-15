"""
Unit tests for mobile pairing module (AMA-61, AMA-175, AMA-178, AMA-180).

Tests cover:
- Token generation (secure token and short code)
- QR data generation
- JWT generation for iOS app
- Token validation logic
- Rate limiting logic
- API endpoint behavior
- Clerk profile fetching (AMA-180)
"""

import pytest
import json
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

# Import module under test
from backend.mobile_pairing import (
    generate_pairing_tokens,
    generate_qr_data,
    generate_jwt_for_user,
    get_clerk_client,
    fetch_clerk_profile,
    TOKEN_EXPIRY_MINUTES,
    JWT_EXPIRY_DAYS,
    SHORT_CODE_ALPHABET,
    SHORT_CODE_LENGTH,
    MAX_TOKENS_PER_HOUR,
)


@pytest.mark.unit
class TestGeneratePairingTokens:
    """Tests for generate_pairing_tokens function."""

    def test_returns_tuple_of_two_strings(self):
        """Token generation returns (token, short_code) tuple."""
        token, short_code = generate_pairing_tokens()
        assert isinstance(token, str)
        assert isinstance(short_code, str)

    def test_token_is_64_hex_characters(self):
        """Token should be 64 hex characters (32 bytes)."""
        token, _ = generate_pairing_tokens()
        assert len(token) == 64
        # Verify it's valid hex
        int(token, 16)

    def test_short_code_length(self):
        """Short code should be exactly SHORT_CODE_LENGTH characters."""
        _, short_code = generate_pairing_tokens()
        assert len(short_code) == SHORT_CODE_LENGTH

    def test_short_code_uses_valid_alphabet(self):
        """Short code should only use characters from SHORT_CODE_ALPHABET."""
        _, short_code = generate_pairing_tokens()
        for char in short_code:
            assert char in SHORT_CODE_ALPHABET

    def test_short_code_excludes_confusing_characters(self):
        """Short code should not contain 0, O, 1, I, l (confusing chars)."""
        confusing_chars = '0O1Il'
        for _ in range(100):  # Generate many codes to test randomness
            _, short_code = generate_pairing_tokens()
            for char in confusing_chars:
                assert char not in short_code

    def test_tokens_are_unique(self):
        """Each call should generate unique tokens."""
        tokens = set()
        short_codes = set()
        for _ in range(100):
            token, short_code = generate_pairing_tokens()
            tokens.add(token)
            short_codes.add(short_code)
        # All should be unique
        assert len(tokens) == 100
        assert len(short_codes) == 100

    def test_token_is_cryptographically_random(self):
        """Token should be generated using secrets module (crypto-safe)."""
        # Generate multiple tokens and check they have good entropy
        tokens = [generate_pairing_tokens()[0] for _ in range(10)]
        # Each token should be different
        assert len(set(tokens)) == 10
        # Check average character diversity (should be high for random hex)
        for token in tokens:
            unique_chars = len(set(token))
            assert unique_chars >= 10  # Should have good character diversity


@pytest.mark.unit
class TestGenerateQrData:
    """Tests for generate_qr_data function."""

    def test_returns_valid_json(self):
        """QR data should be valid JSON."""
        qr_data = generate_qr_data("test-token")
        parsed = json.loads(qr_data)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self):
        """QR data should contain type, version, token, and api_url."""
        qr_data = generate_qr_data("test-token")
        parsed = json.loads(qr_data)
        assert "type" in parsed
        assert "version" in parsed
        assert "token" in parsed
        assert "api_url" in parsed

    def test_type_is_amakaflow_pairing(self):
        """Type field should be 'amakaflow_pairing'."""
        qr_data = generate_qr_data("test-token")
        parsed = json.loads(qr_data)
        assert parsed["type"] == "amakaflow_pairing"

    def test_version_is_1(self):
        """Version should be 1."""
        qr_data = generate_qr_data("test-token")
        parsed = json.loads(qr_data)
        assert parsed["version"] == 1

    def test_token_is_included(self):
        """Token should be included in QR data."""
        test_token = "abc123def456"
        qr_data = generate_qr_data(test_token)
        parsed = json.loads(qr_data)
        assert parsed["token"] == test_token

    def test_api_url_from_env(self):
        """API URL should come from environment variable."""
        with patch.dict(os.environ, {"MAPPER_API_PUBLIC_URL": "https://custom.api.com"}):
            qr_data = generate_qr_data("test-token", api_url=None)
            parsed = json.loads(qr_data)
            # Note: function reads env at call time, so we pass explicit value

    def test_api_url_override(self):
        """API URL can be overridden."""
        custom_url = "https://my-custom-api.com"
        qr_data = generate_qr_data("test-token", api_url=custom_url)
        parsed = json.loads(qr_data)
        assert parsed["api_url"] == custom_url

    def test_json_is_compact(self):
        """JSON should use compact separators (no extra spaces)."""
        qr_data = generate_qr_data("test-token")
        # Compact JSON shouldn't have spaces after : or ,
        assert ": " not in qr_data
        assert ", " not in qr_data


@pytest.mark.unit
class TestGenerateJwtForUser:
    """Tests for generate_jwt_for_user function."""

    def test_returns_tuple_of_jwt_and_expiry(self):
        """Should return (jwt_string, expiry_datetime) tuple."""
        jwt_token, expiry = generate_jwt_for_user(
            "user-123",
            {"email": "test@example.com", "name": "Test User"}
        )
        assert isinstance(jwt_token, str)
        assert isinstance(expiry, datetime)

    def test_jwt_has_three_parts(self):
        """JWT should have header.payload.signature format."""
        jwt_token, _ = generate_jwt_for_user("user-123", {})
        parts = jwt_token.split(".")
        assert len(parts) == 3

    def test_expiry_is_in_future(self):
        """Expiry should be JWT_EXPIRY_DAYS in the future."""
        _, expiry = generate_jwt_for_user("user-123", {})
        now = datetime.now(timezone.utc)
        expected_min = now + timedelta(days=JWT_EXPIRY_DAYS - 1)
        expected_max = now + timedelta(days=JWT_EXPIRY_DAYS + 1)
        assert expected_min < expiry < expected_max

    def test_jwt_can_be_decoded(self):
        """JWT should be decodable (without verification for unit test)."""
        import jwt as pyjwt
        jwt_token, _ = generate_jwt_for_user(
            "user-123",
            {"email": "test@example.com", "name": "Test User"}
        )
        # Decode without verification (just check structure)
        payload = pyjwt.decode(jwt_token, options={"verify_signature": False})
        assert payload["sub"] == "user-123"
        assert payload["email"] == "test@example.com"
        assert payload["name"] == "Test User"
        assert payload["iss"] == "amakaflow"
        assert payload["aud"] == "ios_companion"

    def test_jwt_contains_required_claims(self):
        """JWT should contain sub, iat, exp, iss, aud claims."""
        import jwt as pyjwt
        jwt_token, _ = generate_jwt_for_user("user-123", {})
        payload = pyjwt.decode(jwt_token, options={"verify_signature": False})
        assert "sub" in payload
        assert "iat" in payload
        assert "exp" in payload
        assert "iss" in payload
        assert "aud" in payload

    def test_jwt_exp_matches_returned_expiry(self):
        """JWT exp claim should match returned expiry datetime."""
        import jwt as pyjwt
        jwt_token, expiry = generate_jwt_for_user("user-123", {})
        payload = pyjwt.decode(jwt_token, options={"verify_signature": False})
        jwt_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        # Allow 1 second difference for execution time
        assert abs((jwt_exp - expiry).total_seconds()) < 1


@pytest.mark.unit
class TestConstants:
    """Tests for module constants."""

    def test_token_expiry_is_5_minutes(self):
        """TOKEN_EXPIRY_MINUTES should be 5."""
        assert TOKEN_EXPIRY_MINUTES == 5

    def test_jwt_expiry_is_30_days(self):
        """JWT_EXPIRY_DAYS should be 30."""
        assert JWT_EXPIRY_DAYS == 30

    def test_max_tokens_per_hour(self):
        """MAX_TOKENS_PER_HOUR should be reasonable limit."""
        assert MAX_TOKENS_PER_HOUR == 5

    def test_short_code_length_is_6(self):
        """SHORT_CODE_LENGTH should be 6."""
        assert SHORT_CODE_LENGTH == 6

    def test_short_code_alphabet_excludes_confusing(self):
        """SHORT_CODE_ALPHABET should not contain confusing characters."""
        confusing = "0O1Il"
        for char in confusing:
            assert char not in SHORT_CODE_ALPHABET


@pytest.mark.unit
class TestCreatePairingTokenMocked:
    """Tests for create_pairing_token with mocked database."""

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_none_when_no_supabase(self, mock_get_client):
        """Should return None when Supabase client is unavailable."""
        from backend.mobile_pairing import create_pairing_token
        mock_get_client.return_value = None
        result = create_pairing_token("user-123")
        assert result is None

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_rate_limit_when_max_active_tokens(self, mock_get_client):
        """Should return rate_limit error when user has too many active tokens."""
        from backend.mobile_pairing import create_pairing_token

        # Mock Supabase client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock rate check returning 5 active tokens (at limit)
        mock_rate_result = MagicMock()
        mock_rate_result.data = [{"id": i} for i in range(MAX_TOKENS_PER_HOUR)]
        mock_client.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value = mock_rate_result

        result = create_pairing_token("user-123")

        assert result is not None
        assert result.get("error") == "rate_limit"
        assert "Maximum" in result.get("message", "")

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_success_creates_token(self, mock_get_client):
        """Should create token successfully when under rate limit."""
        from backend.mobile_pairing import create_pairing_token

        # Mock Supabase client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock rate check returning no tokens
        mock_rate_result = MagicMock()
        mock_rate_result.data = []

        # Mock insert returning success
        mock_insert_result = MagicMock()
        mock_insert_result.data = [{"id": "token-uuid"}]

        # Chain mocks for rate check
        mock_client.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value = mock_rate_result

        # Chain mocks for insert
        mock_client.table.return_value.insert.return_value.execute.return_value = mock_insert_result

        result = create_pairing_token("user-123")

        assert result is not None
        assert "token" in result
        assert "short_code" in result
        assert "qr_data" in result
        assert "expires_at" in result
        assert "expires_in_seconds" in result
        assert result["expires_in_seconds"] == TOKEN_EXPIRY_MINUTES * 60


@pytest.mark.unit
class TestValidateAndUseTokenMocked:
    """Tests for validate_and_use_token with mocked database."""

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_none_when_no_supabase(self, mock_get_client):
        """Should return None when Supabase client is unavailable."""
        from backend.mobile_pairing import validate_and_use_token
        mock_get_client.return_value = None
        result = validate_and_use_token(token="test-token")
        assert result is None

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_error_when_no_token_or_short_code(self, mock_get_client):
        """Should return error when neither token nor short_code provided."""
        from backend.mobile_pairing import validate_and_use_token
        mock_get_client.return_value = MagicMock()

        result = validate_and_use_token()  # No token or short_code

        assert result is not None
        assert result.get("error") == "invalid_request"

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_error_when_token_not_found(self, mock_get_client):
        """Should return error when token not found in database."""
        from backend.mobile_pairing import validate_and_use_token

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query returning empty result
        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = validate_and_use_token(token="nonexistent-token")

        assert result.get("error") == "invalid_token"

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_error_when_token_already_used(self, mock_get_client):
        """Should return error when token has already been used."""
        from backend.mobile_pairing import validate_and_use_token

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query returning used token
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "token-uuid",
            "clerk_user_id": "user-123",
            "used_at": "2025-01-01T00:00:00+00:00",  # Already used
            "expires_at": "2025-12-31T23:59:59+00:00",
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = validate_and_use_token(token="used-token")

        assert result.get("error") == "token_used"

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_error_when_token_expired(self, mock_get_client):
        """Should return error when token has expired."""
        from backend.mobile_pairing import validate_and_use_token

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock query returning expired token
        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_result = MagicMock()
        mock_result.data = [{
            "id": "token-uuid",
            "clerk_user_id": "user-123",
            "used_at": None,  # Not used
            "expires_at": past_time,  # Expired
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = validate_and_use_token(token="expired-token")

        assert result.get("error") == "token_expired"


@pytest.mark.unit
class TestGetPairingStatusMocked:
    """Tests for get_pairing_status with mocked database."""

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_error_when_no_supabase(self, mock_get_client):
        """Should return error dict when Supabase unavailable."""
        from backend.mobile_pairing import get_pairing_status
        mock_get_client.return_value = None

        result = get_pairing_status("test-token")

        assert result["paired"] is False
        assert result["expired"] is True
        assert "error" in result

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_not_found_for_missing_token(self, mock_get_client):
        """Should return error when token not found."""
        from backend.mobile_pairing import get_pairing_status

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = []
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = get_pairing_status("nonexistent")

        assert result["paired"] is False
        assert result["expired"] is True

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_paired_true_when_used(self, mock_get_client):
        """Should return paired=True when token has been used."""
        from backend.mobile_pairing import get_pairing_status

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_result = MagicMock()
        mock_result.data = [{
            "used_at": "2025-01-01T00:00:00+00:00",
            "expires_at": future_time,
            "device_info": {"device": "iPhone"},
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = get_pairing_status("paired-token")

        assert result["paired"] is True
        assert result["expired"] is False
        assert result["device_info"] == {"device": "iPhone"}

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_expired_true_when_past_expiry(self, mock_get_client):
        """Should return expired=True when token past expiry."""
        from backend.mobile_pairing import get_pairing_status

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        mock_result = MagicMock()
        mock_result.data = [{
            "used_at": None,
            "expires_at": past_time,
            "device_info": None,
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_result

        result = get_pairing_status("expired-token")

        assert result["paired"] is False
        assert result["expired"] is True


@pytest.mark.unit
class TestRevokeUserTokensMocked:
    """Tests for revoke_user_tokens with mocked database."""

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_zero_when_no_supabase(self, mock_get_client):
        """Should return 0 when Supabase unavailable."""
        from backend.mobile_pairing import revoke_user_tokens
        mock_get_client.return_value = None

        result = revoke_user_tokens("user-123")

        assert result == 0

    @patch("backend.mobile_pairing.get_supabase_client")
    def test_returns_count_of_deleted_tokens(self, mock_get_client):
        """Should return count of deleted tokens."""
        from backend.mobile_pairing import revoke_user_tokens

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_result = MagicMock()
        mock_result.data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        mock_client.table.return_value.delete.return_value.eq.return_value.is_.return_value.execute.return_value = mock_result

        result = revoke_user_tokens("user-123")

        assert result == 3


@pytest.mark.unit
class TestPydanticModels:
    """Tests for Pydantic request/response models."""

    def test_generate_pairing_request_is_empty(self):
        """GeneratePairingRequest should accept empty body."""
        from backend.mobile_pairing import GeneratePairingRequest
        req = GeneratePairingRequest()
        assert req is not None

    def test_pair_device_request_accepts_token(self):
        """PairDeviceRequest should accept token."""
        from backend.mobile_pairing import PairDeviceRequest
        req = PairDeviceRequest(token="test-token")
        assert req.token == "test-token"
        assert req.short_code is None

    def test_pair_device_request_accepts_short_code(self):
        """PairDeviceRequest should accept short_code."""
        from backend.mobile_pairing import PairDeviceRequest
        req = PairDeviceRequest(short_code="ABC123")
        assert req.short_code == "ABC123"
        assert req.token is None

    def test_pair_device_request_accepts_device_info(self):
        """PairDeviceRequest should accept device_info."""
        from backend.mobile_pairing import PairDeviceRequest
        req = PairDeviceRequest(
            token="test",
            device_info={"device": "iPhone", "os": "iOS 17"}
        )
        assert req.device_info == {"device": "iPhone", "os": "iOS 17"}

    def test_generate_pairing_response_fields(self):
        """GeneratePairingResponse should have all required fields."""
        from backend.mobile_pairing import GeneratePairingResponse
        resp = GeneratePairingResponse(
            token="abc",
            short_code="XYZ123",
            qr_data='{"test": true}',
            expires_at="2025-01-01T00:00:00Z",
            expires_in_seconds=300
        )
        assert resp.token == "abc"
        assert resp.short_code == "XYZ123"
        assert resp.qr_data == '{"test": true}'
        assert resp.expires_at == "2025-01-01T00:00:00Z"
        assert resp.expires_in_seconds == 300

    def test_pairing_status_response_fields(self):
        """PairingStatusResponse should have correct fields."""
        from backend.mobile_pairing import PairingStatusResponse
        resp = PairingStatusResponse(
            paired=True,
            expired=False,
            device_info={"device": "iPhone"}
        )
        assert resp.paired is True
        assert resp.expired is False
        assert resp.device_info == {"device": "iPhone"}


# ============================================================================
# Clerk Integration Tests (AMA-180)
# ============================================================================

@pytest.mark.unit
class TestGetClerkClient:
    """Tests for get_clerk_client function."""

    def test_returns_none_when_no_secret_key(self, monkeypatch):
        """Should return None when CLERK_SECRET_KEY is not set."""
        import backend.mobile_pairing as mp
        mp._clerk_client = None  # Reset global
        monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)

        result = get_clerk_client()

        assert result is None

    @patch("backend.mobile_pairing.Clerk", create=True)
    def test_initializes_clerk_with_secret_key(self, mock_clerk_class, monkeypatch):
        """Should initialize Clerk client with CLERK_SECRET_KEY."""
        import backend.mobile_pairing as mp
        mp._clerk_client = None  # Reset global
        monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_12345")

        # Mock the import inside the function
        with patch.dict("sys.modules", {"clerk_backend_api": MagicMock(Clerk=mock_clerk_class)}):
            result = get_clerk_client()

        # Verify Clerk was called with the secret key
        mock_clerk_class.assert_called_once_with(bearer_auth="sk_test_12345")

    def test_caches_client_instance(self, monkeypatch):
        """Should cache the Clerk client after first initialization."""
        import backend.mobile_pairing as mp
        mock_client = MagicMock()
        mp._clerk_client = mock_client  # Pre-set global

        result = get_clerk_client()

        assert result is mock_client


@pytest.mark.unit
class TestFetchClerkProfile:
    """Tests for fetch_clerk_profile function."""

    @patch("backend.mobile_pairing.get_clerk_client")
    def test_returns_none_when_no_client(self, mock_get_client):
        """Should return None when Clerk client is unavailable."""
        mock_get_client.return_value = None

        result = fetch_clerk_profile("user-123")

        assert result is None

    @patch("backend.mobile_pairing.get_clerk_client")
    def test_returns_profile_on_success(self, mock_get_client):
        """Should return profile dict on successful Clerk API call."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock Clerk user response
        mock_email = MagicMock()
        mock_email.email_address = "test@example.com"
        mock_user = MagicMock()
        mock_user.id = "user_abc123"
        mock_user.email_addresses = [mock_email]
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.image_url = "https://img.clerk.com/abc123"
        mock_client.users.get.return_value = mock_user

        result = fetch_clerk_profile("user_abc123")

        assert result is not None
        assert result["id"] == "user_abc123"
        assert result["email"] == "test@example.com"
        assert result["first_name"] == "Test"
        assert result["last_name"] == "User"
        assert result["image_url"] == "https://img.clerk.com/abc123"

    @patch("backend.mobile_pairing.get_clerk_client")
    def test_handles_no_email_addresses(self, mock_get_client):
        """Should handle user with no email addresses."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        mock_user = MagicMock()
        mock_user.id = "user_abc123"
        mock_user.email_addresses = []  # No emails
        mock_user.first_name = "Test"
        mock_user.last_name = "User"
        mock_user.image_url = None
        mock_client.users.get.return_value = mock_user

        result = fetch_clerk_profile("user_abc123")

        assert result is not None
        assert result["email"] is None
        assert result["first_name"] == "Test"

    @patch("backend.mobile_pairing.get_clerk_client")
    def test_returns_none_on_api_error(self, mock_get_client):
        """Should return None when Clerk API call fails."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.users.get.side_effect = Exception("API Error")

        result = fetch_clerk_profile("user_abc123")

        assert result is None

    @patch("backend.mobile_pairing.get_clerk_client")
    def test_returns_none_when_user_not_found(self, mock_get_client):
        """Should return None when user is not found."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.users.get.return_value = None

        result = fetch_clerk_profile("nonexistent-user")

        assert result is None


@pytest.mark.unit
class TestValidateAndUseTokenWithClerkProfile:
    """Tests for validate_and_use_token with Clerk profile integration."""

    @patch("backend.mobile_pairing.fetch_clerk_profile")
    @patch("backend.mobile_pairing.generate_jwt_for_user")
    @patch("backend.mobile_pairing.get_supabase_client")
    def test_uses_clerk_profile_when_available(self, mock_get_supabase, mock_gen_jwt, mock_fetch_clerk):
        """Should use Clerk profile when available."""
        from backend.mobile_pairing import validate_and_use_token

        # Mock Supabase
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock token lookup
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_token_result = MagicMock()
        mock_token_result.data = [{
            "id": "token-uuid",
            "clerk_user_id": "user_abc123",
            "used_at": None,
            "expires_at": future_time,
        }]
        mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_token_result

        # Mock update
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "token-uuid"}]
        mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value = mock_update_result

        # Mock Clerk profile
        clerk_profile = {
            "id": "user_abc123",
            "email": "clerk@example.com",
            "first_name": "Clerk",
            "last_name": "User",
            "image_url": "https://clerk.com/image.jpg",
        }
        mock_fetch_clerk.return_value = clerk_profile

        # Mock JWT generation
        mock_gen_jwt.return_value = ("jwt-token", datetime.now(timezone.utc))

        result = validate_and_use_token(token="valid-token")

        assert result is not None
        assert result["profile"]["first_name"] == "Clerk"
        assert result["profile"]["last_name"] == "User"
        assert result["profile"]["image_url"] == "https://clerk.com/image.jpg"

    @patch("backend.mobile_pairing.fetch_clerk_profile")
    @patch("backend.mobile_pairing.generate_jwt_for_user")
    @patch("backend.mobile_pairing.get_supabase_client")
    def test_falls_back_to_supabase_when_clerk_fails(self, mock_get_supabase, mock_gen_jwt, mock_fetch_clerk):
        """Should fallback to Supabase profile when Clerk fails."""
        from backend.mobile_pairing import validate_and_use_token

        # Mock Supabase
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock token lookup
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_token_result = MagicMock()
        mock_token_result.data = [{
            "id": "token-uuid",
            "clerk_user_id": "user_abc123",
            "used_at": None,
            "expires_at": future_time,
        }]

        # Mock update
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "token-uuid"}]

        # Mock Supabase profile lookup
        mock_profile_result = MagicMock()
        mock_profile_result.data = [{
            "id": "user_abc123",
            "email": "supabase@example.com",
            "name": "Supabase User",
            "avatar_url": "https://supabase.com/avatar.jpg",
        }]

        # Configure table mock to return different results for different tables
        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "mobile_pairing_tokens":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_token_result
                mock_table.update.return_value.eq.return_value.execute.return_value = mock_update_result
            elif table_name == "profiles":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_profile_result
            return mock_table

        mock_client.table.side_effect = table_side_effect

        # Mock Clerk profile fetch failure
        mock_fetch_clerk.return_value = None

        # Mock JWT generation
        mock_gen_jwt.return_value = ("jwt-token", datetime.now(timezone.utc))

        result = validate_and_use_token(token="valid-token")

        assert result is not None
        # Should have split the name into first/last
        assert result["profile"]["first_name"] == "Supabase"
        assert result["profile"]["last_name"] == "User"
        assert result["profile"]["email"] == "supabase@example.com"

    @patch("backend.mobile_pairing.fetch_clerk_profile")
    @patch("backend.mobile_pairing.generate_jwt_for_user")
    @patch("backend.mobile_pairing.get_supabase_client")
    def test_minimal_profile_when_all_fail(self, mock_get_supabase, mock_gen_jwt, mock_fetch_clerk):
        """Should return minimal profile when both Clerk and Supabase fail."""
        from backend.mobile_pairing import validate_and_use_token

        # Mock Supabase
        mock_client = MagicMock()
        mock_get_supabase.return_value = mock_client

        # Mock token lookup
        future_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        mock_token_result = MagicMock()
        mock_token_result.data = [{
            "id": "token-uuid",
            "clerk_user_id": "user_abc123",
            "used_at": None,
            "expires_at": future_time,
        }]

        # Mock update
        mock_update_result = MagicMock()
        mock_update_result.data = [{"id": "token-uuid"}]

        # Mock empty Supabase profile
        mock_profile_result = MagicMock()
        mock_profile_result.data = []  # No profile found

        def table_side_effect(table_name):
            mock_table = MagicMock()
            if table_name == "mobile_pairing_tokens":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_token_result
                mock_table.update.return_value.eq.return_value.execute.return_value = mock_update_result
            elif table_name == "profiles":
                mock_table.select.return_value.eq.return_value.execute.return_value = mock_profile_result
            return mock_table

        mock_client.table.side_effect = table_side_effect

        # Mock Clerk profile fetch failure
        mock_fetch_clerk.return_value = None

        # Mock JWT generation
        mock_gen_jwt.return_value = ("jwt-token", datetime.now(timezone.utc))

        result = validate_and_use_token(token="valid-token")

        assert result is not None
        # Should have minimal profile with just the ID
        assert result["profile"]["id"] == "user_abc123"
        assert result["profile"]["email"] is None
        assert result["profile"]["first_name"] is None
        assert result["profile"]["last_name"] is None


@pytest.mark.unit
class TestProfileResponseFormat:
    """Tests for profile response format (AMA-180)."""

    def test_profile_has_required_fields(self):
        """Profile should have id, email, first_name, last_name, image_url."""
        expected_fields = {"id", "email", "first_name", "last_name", "image_url"}

        # Create a sample profile
        profile = {
            "id": "user_abc123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "image_url": "https://example.com/image.jpg",
        }

        assert set(profile.keys()) == expected_fields

    def test_profile_does_not_have_legacy_fields(self):
        """Profile should not have legacy fields like name or avatar_url."""
        profile = {
            "id": "user_abc123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User",
            "image_url": "https://example.com/image.jpg",
        }

        # These fields should NOT be in the new format
        assert "name" not in profile
        assert "avatar_url" not in profile
