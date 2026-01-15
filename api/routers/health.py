"""
Health check router.

Part of AMA-378: Create api/routers skeleton and wiring

This router provides health check endpoints for monitoring and load balancers.
"""

from fastapi import APIRouter

router = APIRouter(
    tags=["Health"],
)


@router.get("/health")
def health():
    """
    Simple liveness endpoint for mapper-api.

    Returns:
        dict: Status indicator for health checks
    """
    return {"status": "ok"}
