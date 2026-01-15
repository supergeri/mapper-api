"""
Workouts router for workout CRUD and library management.

Part of AMA-378: Create api/routers skeleton and wiring

This router will contain endpoints for:
- Workout CRUD operations
- Workout library management
- Program management
- Tags management
- Follow-along workouts
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/workouts",
    tags=["Workouts"],
)

# Endpoints will be moved here in subsequent PRs
