"""
Exports router for workout export endpoints.

Part of AMA-378: Create api/routers skeleton and wiring

This router will contain endpoints for:
- FIT file exports
- ZWO file exports
- Garmin sync endpoints
- Export status tracking
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/exports",
    tags=["Exports"],
)

# Endpoints will be moved here in subsequent PRs
