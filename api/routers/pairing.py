"""
Pairing router for mobile device pairing and authentication.

Part of AMA-378: Create api/routers skeleton and wiring

This router will contain endpoints for:
- Generate pairing token
- Pair device
- Get pairing status
- Refresh tokens
- Revoke devices
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/mobile/pairing",
    tags=["Pairing"],
)

# Endpoints will be moved here in subsequent PRs
