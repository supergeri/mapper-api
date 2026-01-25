"""
Health check router.

Part of AMA-461: Create program-api service scaffold

This router provides health check endpoints for monitoring and load balancers.
"""

from fastapi import APIRouter

router = APIRouter(
    tags=["Health"],
)


@router.get("/health")
def health():
    """
    Simple liveness endpoint for program-api.

    Returns:
        dict: Status indicator for health checks
    """
    return {"status": "ok", "service": "program-api"}
