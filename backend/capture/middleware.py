"""FastAPI capture middleware.

Intercepts requests to configured capture points and writes JSON
snapshots to disk. Zero overhead for non-matched endpoints.

Usage::

    from backend.capture import CaptureMiddleware

    app.add_middleware(CaptureMiddleware, capture_dir="./captures")
"""

import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp

from .session import CaptureSession, resolve_session
from .writer import write_snapshot

logger = logging.getLogger(__name__)

# Default mapping of URL path patterns to capture point names.
# Keys are (method, path) tuples; values are capture point names.
# Updated to match mapper-api's actual router endpoints.
DEFAULT_CAPTURE_POINTS: dict[tuple[str, str], str] = {
    ("POST", "/workouts/save"): "backend-stored",
    ("GET", "/workouts"): "workouts-list",
    ("GET", "/workouts/incoming"): "phone-sync-request",
    ("POST", "/workouts/completions"): "completion-received",
    ("POST", "/workouts/complete"): "completion-received",
    ("POST", "/workflow/process"): "workflow-process",
    ("POST", "/map/final"): "map-final-export",
    ("POST", "/map/auto-map"): "map-auto",
    ("POST", "/import/stream"): "web-ingest",
    ("POST", "/import/image/stream"): "image-ingest",
}

# Paths that return SSE streams — we capture request only, not response body
SSE_PATHS: set[str] = {
    "/import/stream",
    "/import/image/stream",
    "/import/bulk/stream",
}


class CaptureMiddleware(BaseHTTPMiddleware):
    """Middleware that captures API traffic for replay testing."""

    def __init__(
        self,
        app: ASGIApp,
        capture_dir: str | Path = "./captures",
        capture_points: dict[tuple[str, str], str] | None = None,
    ) -> None:
        super().__init__(app)
        self.capture_dir = Path(capture_dir)
        self.capture_points = capture_points or DEFAULT_CAPTURE_POINTS
        self._sessions: dict[str, CaptureSession] = {}
        self._sessions_lock = Lock()

    def _get_or_create_session(self, name: str) -> CaptureSession:
        """Return an existing session or create a new one, keyed by name."""
        with self._sessions_lock:
            if name not in self._sessions:
                self._sessions[name] = CaptureSession(
                    name=name, capture_dir=self.capture_dir
                )
            return self._sessions[name]

    async def dispatch(self, request: Request, call_next) -> Response:
        # Check if this endpoint is a capture point
        capture_point = self.capture_points.get(
            (request.method, request.url.path)
        )
        if capture_point is None:
            return await call_next(request)

        # Check if capture is active (header or env var)
        headers_dict = dict(request.headers)
        session_template = resolve_session(headers_dict, self.capture_dir)
        if session_template is None:
            return await call_next(request)

        # Reuse or create a cached session by name
        session = self._get_or_create_session(session_template.name)

        return await self._capture_and_forward(
            request, call_next, session, capture_point
        )

    async def _capture_and_forward(
        self,
        request: Request,
        call_next,
        session: CaptureSession,
        capture_point: str,
    ) -> Response:
        """Read request body, forward to handler, capture snapshot."""
        # Read and cache request body
        request_body = await request.body()
        request_payload = _try_parse_json(request_body)

        is_sse = request.url.path in SSE_PATHS

        # Forward to the actual handler
        response: Response = await call_next(request)

        # Capture response body for non-SSE endpoints
        response_payload: Any = None
        if not is_sse:
            # BaseHTTPMiddleware returns StreamingResponse — consume the body
            response_body = b""
            async for chunk in response.body_iterator:
                response_body += chunk
            response_payload = _try_parse_json(response_body)

            # Reconstruct the response with the consumed body
            response = StarletteResponse(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type,
            )

        # Write snapshot
        try:
            filepath = write_snapshot(
                session,
                capture_point=capture_point,
                endpoint=request.url.path,
                method=request.method,
                request_payload=request_payload,
                request_headers=dict(request.headers),
                response_status=response.status_code,
                response_payload=response_payload,
                streaming=is_sse,
            )
            logger.debug("Captured %s → %s", capture_point, filepath)
        except Exception:
            logger.exception("Failed to write capture snapshot for %s", capture_point)

        return response


def _try_parse_json(data: bytes | None) -> Any:
    """Try to parse bytes as JSON, return raw string on failure."""
    if not data:
        return None
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return data.decode("utf-8", errors="replace")
