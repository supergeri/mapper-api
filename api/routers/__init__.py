"""
Router package for AmakaFlow Mapper API.

Part of AMA-378: Create api/routers skeleton and wiring
Updated in AMA-299: Add exercises router for exercise matching
Updated in AMA-594: Add tags router for user tag management
Updated in AMA-591: Add bulk import router
Updated in AMA-596: Add account router
Updated in AMA-597: Move debug/testing endpoints to health router

This package contains all API routers organized by domain:
- health: Health check and debug/testing endpoints (AMA-597)
- mapping: Exercise mapping and transformation endpoints
- exports: Workout export endpoints (Garmin, FIT, ZWO, etc.)
- workouts: Workout CRUD and library management
- pairing: Mobile device pairing and authentication
- completions: Workout completion tracking
- exercises: Canonical exercise lookup and matching (AMA-299)
- tags: User tag management (AMA-594)
- bulk_import: Bulk import workflow (AMA-591)
- account: Account management (AMA-596)
"""

from api.routers.account import router as account_router
from api.routers.health import router as health_router
from api.routers.mapping import router as mapping_router
from api.routers.exports import router as exports_router
from api.routers.workouts import router as workouts_router
from api.routers.pairing import router as pairing_router
from api.routers.completions import router as completions_router
from api.routers.exercises import router as exercises_router
from api.routers.progression import router as progression_router
from api.routers.programs import router as programs_router
from api.routers.tags import router as tags_router
from api.routers.settings import router as settings_router
from api.routers.follow_along import router as follow_along_router
from api.routers.sync import router as sync_router
from api.routers.bulk_import import router as bulk_import_router
from api.routers.chat import router as chat_router

__all__ = [
    "account_router",
    "health_router",
    "mapping_router",
    "exports_router",
    "workouts_router",
    "pairing_router",
    "completions_router",
    "exercises_router",
    "progression_router",
    "programs_router",
    "tags_router",
    "settings_router",
    "follow_along_router",
    "sync_router",
    "bulk_import_router",
    "chat_router",
]
