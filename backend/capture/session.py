"""Capture session management.

A CaptureSession tracks a named recording session, maintaining state
about which capture points have been hit and generating sequential
filenames for snapshots.
"""

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

# Header used to activate per-request capture
CAPTURE_HEADER = "x-replay-capture"

# Env var for global capture enablement
CAPTURE_ENV_VAR = "REPLAY_CAPTURE_ENABLED"

# Valid session name pattern (alphanumeric, dash, underscore)
_SESSION_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


@dataclass
class CaptureSession:
    """A named capture session that writes snapshots to a directory."""

    name: str
    capture_dir: Path
    started_at: float = field(default_factory=time.time)
    _sequence: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self) -> None:
        if not _SESSION_NAME_RE.match(self.name):
            raise ValueError(
                f"Invalid session name: {self.name!r}. "
                "Use only alphanumeric, dash, or underscore characters."
            )

    @property
    def session_dir(self) -> Path:
        return self.capture_dir / self.name

    def next_filename(self, capture_point: str) -> Path:
        """Generate the next sequential snapshot filename."""
        with self._lock:
            self._sequence += 1
            seq = self._sequence
        filename = f"{seq:03d}_{capture_point}.json"
        return self.session_dir / filename

    @property
    def sequence_count(self) -> int:
        return self._sequence


def resolve_session(
    headers: dict[str, str],
    default_capture_dir: Path,
) -> CaptureSession | None:
    """Determine if capture is active for this request.

    Checks (in order):
    1. X-Replay-Capture header: ``session-name=foo``
    2. REPLAY_CAPTURE_ENABLED env var: uses ``default`` as session name

    Returns a CaptureSession if capture is active, None otherwise.
    """
    header_val = headers.get(CAPTURE_HEADER, "").strip()
    if header_val:
        return _parse_header(header_val, default_capture_dir)

    if os.environ.get(CAPTURE_ENV_VAR, "").lower() in ("1", "true", "yes"):
        return CaptureSession(name="default", capture_dir=default_capture_dir)

    return None


def _parse_header(value: str, default_capture_dir: Path) -> CaptureSession | None:
    """Parse the X-Replay-Capture header value.

    Format: ``session-name=foo``
    """
    parts = {}
    for segment in value.split(","):
        segment = segment.strip()
        if "=" in segment:
            k, v = segment.split("=", 1)
            parts[k.strip()] = v.strip()

    session_name = parts.get("session-name")
    if not session_name:
        return None

    try:
        return CaptureSession(name=session_name, capture_dir=default_capture_dir)
    except ValueError:
        return None
