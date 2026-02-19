"""
Replay Engine - Core module for session replay and diffing.

This module provides functionality to:
- Load captured snapshots/sessions
- Replay them through pipeline stages
- Generate structured diffs
"""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import fnmatch


# Maximum session file size (10MB)
MAX_SESSION_FILE_SIZE = 10 * 1024 * 1024


def safe_str(value: Any) -> str:
    """Safely convert a value to string, handling non-stringifiable objects."""
    try:
        return str(value)
    except Exception:
        return repr(value)


@dataclass
class Session:
    """Represents a captured session/snapshot."""
    id: str
    name: str
    data: dict
    tags: list[str] = field(default_factory=list)
    hops: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> 'Session':
        """Load a session from a JSON file."""
        # Check file size to prevent loading arbitrarily large files
        file_size = path.stat().st_size
        if file_size > MAX_SESSION_FILE_SIZE:
            raise ValueError(f"Session file too large: {file_size} bytes (max: {MAX_SESSION_FILE_SIZE})")

        with open(path) as f:
            data = json.load(f)
        return cls(
            id=data.get('id', path.stem),
            name=data.get('name', path.stem),
            data=data.get('data', data),
            tags=data.get('tags', []),
            hops=data.get('hops', []),
            metadata=data.get('metadata', {})
        )

    def to_file(self, path: Path) -> None:
        """Save the session to a JSON file."""
        data = {
            'id': self.id,
            'name': self.name,
            'data': self.data,
            'tags': self.tags,
            'hops': self.hops,
            'metadata': self.metadata
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)


@dataclass
class DiffItem:
    """A single difference between two sessions."""
    path: str
    value_a: Any
    value_b: Any
    diff_type: str  # 'added', 'removed', 'changed', 'reordered'


@dataclass
class DiffResult:
    """Result of comparing two sessions."""
    session_a: str
    session_b: str
    differences: list[DiffItem]
    identical: bool

    @property
    def has_diffs(self) -> bool:
        return not self.identical


class IgnoreConfig:
    """Configuration for ignoring certain fields/patterns in diffs."""

    def __init__(self, patterns: list[str] = None):
        self.patterns = patterns or []

    @classmethod
    def from_file(cls, path: Path) -> 'IgnoreConfig':
        """Load ignore config from a .replayignore file."""
        patterns = []
        if path.exists():
            with open(path) as f:
                patterns = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        return cls(patterns)

    def should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored."""
        # Normalize path: convert bracket notation to dot notation
        normalized_path = path.replace('[', '.').replace(']', '')

        for pattern in self.patterns:
            # Exact match
            if normalized_path == pattern:
                return True
            # Full fnmatch
            if fnmatch.fnmatch(normalized_path, pattern):
                return True
            # Support wildcards in path components
            pattern_parts = pattern.split('.')
            path_parts = normalized_path.split('.')
            if len(pattern_parts) <= len(path_parts):
                # Check prefix match with wildcards
                if all(fnmatch.fnmatch(p, pat) for p, pat in zip(path_parts, pattern_parts)):
                    return True
        return False


class DiffEngine:
    """Engine for computing differences between sessions."""

    def __init__(self, ignore_config: IgnoreConfig = None):
        self.ignore_config = ignore_config or IgnoreConfig()

    def compute_diff(self, session_a: Session, session_b: Session) -> DiffResult:
        """Compute differences between two sessions."""
        differences = []
        self._diff_recursive(
            session_a.data,
            session_b.data,
            '',
            differences
        )

        # Filter out ignored paths
        differences = [d for d in differences if not self.ignore_config.should_ignore(d.path)]

        return DiffResult(
            session_a=session_a.name,
            session_b=session_b.name,
            differences=differences,
            identical=len(differences) == 0
        )

    def _diff_recursive(self, a: Any, b: Any, path: str, differences: list[DiffItem]) -> None:
        """Recursively compare two values."""
        # Handle None vs null
        if a is None and b is None:
            return

        # Type mismatch
        if type(a) != type(b):
            differences.append(DiffItem(
                path=path,
                value_a=a,
                value_b=b,
                diff_type='changed'
            ))
            return

        # Handle dicts
        if isinstance(a, dict):
            all_keys = set(a.keys()) | set(b.keys())
            for key in all_keys:
                new_path = f"{path}.{key}" if path else key
                if key not in a:
                    differences.append(DiffItem(
                        path=new_path,
                        value_a=None,
                        value_b=b[key],
                        diff_type='added'
                    ))
                elif key not in b:
                    differences.append(DiffItem(
                        path=new_path,
                        value_a=a[key],
                        value_b=None,
                        diff_type='removed'
                    ))
                else:
                    self._diff_recursive(a[key], b[key], new_path, differences)
            return

        # Handle lists - with reordering support
        if isinstance(a, list):
            # Check for reordering
            if len(a) != len(b):
                differences.append(DiffItem(
                    path=path,
                    value_a=a,
                    value_b=b,
                    diff_type='changed'
                ))
            else:
                # Check if same elements but different order
                a_sorted = sorted(a, key=safe_str)
                b_sorted = sorted(b, key=safe_str)
                if a == b:
                    return  # Identical
                elif a_sorted == b_sorted:
                    differences.append(DiffItem(
                        path=path,
                        value_a=a,
                        value_b=b,
                        diff_type='reordered'
                    ))
                else:
                    # Check element by element for partial reordering
                    for i, (av, bv) in enumerate(zip(a, b)):
                        if av != bv:
                            self._diff_recursive(av, bv, f"{path}[{i}]", differences)
            return

        # Handle numeric precision
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            # Consider equal if within small epsilon
            if abs(a - b) < 1e-9:
                return
            differences.append(DiffItem(
                path=path,
                value_a=a,
                value_b=b,
                diff_type='changed'
            ))
            return

        # Simple equality check
        if a != b:
            differences.append(DiffItem(
                path=path,
                value_a=a,
                value_b=b,
                diff_type='changed'
            ))


class ReplayEngine:
    """Engine for replaying sessions through pipeline stages."""

    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir

    def load_session(self, session_name: str) -> Session:
        """Load a session by name."""
        session_path = self.sessions_dir / f"{session_name}.json"
        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_name}")
        return Session.from_file(session_path)

    def list_sessions(self) -> list[Session]:
        """List all available sessions."""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            if path.name.startswith('.'):
                continue
            sessions.append(Session.from_file(path))
        return sessions

    def get_session_health(self, session: Session) -> dict:
        """Calculate health metrics for a session based on hops."""
        hops = session.hops

        if not hops:
            return {
                'status': 'invalid',
                'message': 'No hops recorded',
                'consecutive_hops': 0
            }

        # Check for missing hops (gaps in sequence)
        hop_numbers = [h.get('hop_number', i) for i, h in enumerate(hops)]
        expected = list(range(1, len(hops) + 1))
        missing = set(expected) - set(hop_numbers)

        # Count consecutive hops from start
        consecutive = 0
        for i, hn in enumerate(hop_numbers):
            if hn == i + 1:
                consecutive += 1
            else:
                break

        if missing:
            return {
                'status': 'valid_with_gaps',
                'message': f'Missing hops: {sorted(missing)}',
                'consecutive_hops': consecutive,
                'total_hops': len(hops)
            }
        elif consecutive >= 2:
            return {
                'status': 'valid',
                'message': 'Healthy session',
                'consecutive_hops': consecutive,
                'total_hops': len(hops)
            }
        else:
            return {
                'status': 'invalid',
                'message': 'Less than 2 consecutive hops',
                'consecutive_hops': consecutive,
                'total_hops': len(hops)
            }

    def replay_session(self, session: Session, pipeline: list[callable]) -> dict:
        """Replay a session through a pipeline of stages."""
        result = session.data.copy()
        hop_data = []

        for i, stage in enumerate(pipeline):
            before = result.copy()
            try:
                result = stage(result)
            except (ValueError, TypeError, KeyError) as e:
                result = {'error': str(e)}

            hop_data.append({
                'hop_number': i + 1,
                'stage': stage.__name__ if hasattr(stage, '__name__') else f'stage_{i}',
                'before': before,
                'after': result,
                'success': 'error' not in result
            })

        # Update session with hop data
        session.hops = hop_data
        return result
