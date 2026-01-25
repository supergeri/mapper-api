"""
Router package for AmakaFlow Program API.

Part of AMA-461: Create program-api service scaffold

This package contains all API routers organized by domain:
- health: Health check endpoints
- programs: Training program CRUD operations
- generation: AI-powered program generation
- progression: Exercise progression tracking
"""

from api.routers.health import router as health_router
from api.routers.programs import router as programs_router
from api.routers.generation import router as generation_router
from api.routers.progression import router as progression_router

__all__ = [
    "health_router",
    "programs_router",
    "generation_router",
    "progression_router",
]
