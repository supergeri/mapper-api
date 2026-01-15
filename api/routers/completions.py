"""
Completions router for workout completion tracking.

Part of AMA-378: Create api/routers skeleton and wiring

This router will contain endpoints for:
- Record workout completion
- Get user completions
- Voice workout completions
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/completions",
    tags=["Completions"],
)

# Endpoints will be moved here in subsequent PRs
