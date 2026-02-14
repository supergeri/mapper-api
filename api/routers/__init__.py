"""
Router package for AmakaFlow Mapper API.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-299: Add exercises router for exercise matching

This package contains all API routers organized by domain:
- health: Health check endpoints
- mapping: Exercise mapping and transformation endpoints
- exports: Workout export endpoints (Garmin, FIT, ZWO, etc.)
- workouts: Workout CRUD and library management
- pairing: Mobile device pairing and authentication
- completions: Workout completion tracking
- exercises: Canonical exercise lookup and matching (AMA-299)
"""

from api.routers.health import router as health_router
from api.routers.mapping import router as mapping_router
from api.routers.exports import router as exports_router
from api.routers.workouts import router as workouts_router
from api.routers.pairing import router as pairing_router
from api.routers.completions import router as completions_router
from api.routers.exercises import router as exercises_router
from api.routers.progression import router as progression_router
from api.routers.programs import router as programs_router
from api.routers.settings import router as settings_router

__all__ = [
    "health_router",
    "mapping_router",
    "exports_router",
    "workouts_router",
    "pairing_router",
    "completions_router",
    "exercises_router",
    "progression_router",
    "programs_router",
    "settings_router",
]
