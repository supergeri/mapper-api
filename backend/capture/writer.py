"""Snapshot writer — serializes capture data to JSON files on disk."""

import json
import time
from pathlib import Path
from typing import Any

from .session import CaptureSession


def write_snapshot(
    session: CaptureSession,
    *,
    capture_point: str,
    endpoint: str,
    method: str,
    request_payload: Any = None,
    request_headers: dict[str, str] | None = None,
    response_status: int | None = None,
    response_payload: Any = None,
    streaming: bool = False,
    chat_context: dict[str, Any] | None = None,
) -> Path:
    """Write a single capture snapshot to disk.

    Returns the path to the written file.
    """
    snapshot = {
        "capture_point": capture_point,
        "session": session.name,
        "timestamp": time.time(),
        "endpoint": endpoint,
        "method": method,
        "request_payload": request_payload,
        "request_headers": _sanitize_headers(request_headers),
        "response_status": response_status,
        "response_payload": response_payload,
        "streaming": streaming,
        "chat_context": chat_context,
    }

    filepath = session.next_filename(capture_point)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    return filepath


def _sanitize_headers(headers: dict[str, str] | None) -> dict[str, str] | None:
    """Remove sensitive headers from captured data."""
    if headers is None:
        return None

    sensitive = {"authorization", "cookie", "x-test-auth", "x-api-key"}
    return {
        k: ("***" if k.lower() in sensitive else v)
        for k, v in headers.items()
    }
