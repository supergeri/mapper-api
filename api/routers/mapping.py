"""
Mapping router for exercise mapping and transformation endpoints.

Part of AMA-378: Create api/routers skeleton and wiring

This router will contain endpoints for:
- /map/final - Convert old format to Garmin YAML via CIR
- /map/auto-map - Auto-convert blocks JSON to Garmin YAML
- /map/to-hiit - Convert to Garmin HIIT format
- /map/to-workoutkit - Convert to Apple WorkoutKit format
- Exercise suggestion and alternative mapping endpoints
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/map",
    tags=["Mapping"],
)

# Endpoints will be moved here in subsequent PRs
