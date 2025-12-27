"""
Authentication module for Clerk JWT and API key validation.
Provides FastAPI dependencies for securing endpoints.
"""
import os
import jwt
from fastapi import HTTPException, Header
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Clerk JWKS for JWT validation
CLERK_DOMAIN = os.getenv("CLERK_DOMAIN", "")
CLERK_JWKS_URL = f"https://{CLERK_DOMAIN}/.well-known/jwks.json" if CLERK_DOMAIN else ""
_jwks_client = None


def get_jwks_client():
    """Get or create the JWKS client for Clerk JWT validation."""
    global _jwks_client
    if _jwks_client is None and CLERK_DOMAIN:
        _jwks_client = jwt.PyJWKClient(CLERK_JWKS_URL)
    return _jwks_client


async def get_current_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    Authenticate via API key OR Clerk JWT.
    Returns user_id string.

    Usage:
        @app.get("/protected")
        async def protected_route(user_id: str = Depends(get_current_user)):
            return {"user_id": user_id}
    """
    # Option 1: API Key authentication
    if x_api_key:
        return validate_api_key(x_api_key)

    # Option 2: Clerk JWT authentication
    if authorization:
        return validate_jwt(authorization)

    raise HTTPException(
        status_code=401,
        detail="Missing authentication. Provide Authorization header or X-API-Key."
    )


def validate_api_key(api_key: str) -> str:
    """
    Validate API key and return user_id.

    API key format options:
    - Simple: "sk_test_abc123" -> returns "admin"
    - With user: "sk_test_abc123:user_12345" -> returns "user_12345"
    """
    valid_keys = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]

    if not valid_keys:
        logger.warning("No API keys configured (API_KEYS env var empty)")
        raise HTTPException(status_code=401, detail="API key authentication not configured")

    # Check if key (without user suffix) is valid
    key_part = api_key.split(":")[0]

    if key_part not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Extract user_id if provided (format: "key:user_id")
    if ":" in api_key:
        return api_key.split(":", 1)[1]

    return "admin"  # Default for simple API keys


def validate_jwt(authorization: str) -> str:
    """Validate Clerk JWT and return user_id."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")

    token = authorization.split(" ", 1)[1]
    jwks_client = get_jwks_client()

    if not jwks_client:
        raise HTTPException(
            status_code=500,
            detail="JWT validation not configured (missing CLERK_DOMAIN)"
        )

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False}
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Token missing user ID")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    Returns user_id if authenticated, None otherwise.
    Use for endpoints that work differently when authenticated.
    """
    try:
        return await get_current_user(authorization, x_api_key)
    except HTTPException:
        return None
