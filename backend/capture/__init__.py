"""Capture middleware for recording API traffic.

Usage::

    from backend.capture import CaptureMiddleware

    # In your FastAPI app factory:
    if os.environ.get("REPLAY_CAPTURE_ENABLED"):
        app.add_middleware(CaptureMiddleware, capture_dir="./captures")

Activate per-request with the header::

    X-Replay-Capture: session-name=my-test-session

Or globally with the env var::

    REPLAY_CAPTURE_ENABLED=true
"""

from .middleware import CaptureMiddleware, DEFAULT_CAPTURE_POINTS
from .session import CaptureSession, resolve_session
from .writer import write_snapshot

__all__ = [
    "CaptureMiddleware",
    "CaptureSession",
    "DEFAULT_CAPTURE_POINTS",
    "resolve_session",
    "write_snapshot",
]
