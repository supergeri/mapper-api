"""
Trace Viewer Server - Local HTTP server for the Trace Viewer UI.

Provides a web interface for visualizing capture sessions as an interactive
pipeline timeline. Serves static files and provides API endpoints for session data.
"""

from __future__ import annotations

import http.server
import json
import os
import webbrowser
from pathlib import Path
from typing import Any
from functools import lru_cache

# Default sessions directory
DEFAULT_SESSIONS_DIR = Path.home() / '.replay' / 'sessions'


class ViewerHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP request handler for the Trace Viewer."""

    def __init__(self, *args, directory: str = None, **kwargs):
        self.sessions_dir = DEFAULT_SESSIONS_DIR
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        """Handle GET requests."""
        # API endpoint for sessions list
        if self.path == '/api/sessions':
            self.send_json_response(self.get_sessions())
            return

        # API endpoint for a specific session
        if self.path.startswith('/api/session/'):
            session_name = self.path[14:]  # Remove '/api/session/' prefix
            try:
                session = self.get_session(session_name)
                self.send_json_response(session)
            except FileNotFoundError:
                self.send_error(404, f"Session not found: {session_name}")
            return

        # API endpoint for comparing two sessions
        if self.path.startswith('/api/diff/'):
            parts = self.path[10:].split('/')
            if len(parts) >= 2:
                session_a, session_b = parts[0], parts[1]
                try:
                    diff = self.compute_diff(session_a, session_b)
                    self.send_json_response(diff)
                except FileNotFoundError as e:
                    self.send_error(404, str(e))
            else:
                self.send_error(400, "Need two session names: /api/diff/sessionA/sessionB")
            return

        # Serve static files
        super().do_GET()

    def send_json_response(self, data: Any, status: int = 200) -> None:
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    @lru_cache(maxsize=32)
    def get_sessions(self) -> list[dict]:
        """Get list of all available sessions."""
        sessions = []

        # Get sessions from ~/.replay/sessions
        if self.sessions_dir.exists():
            for path in self.sessions_dir.glob("*.json"):
                if path.name.startswith('.'):
                    continue
                try:
                    with open(path) as f:
                        data = json.load(f)

                    # Calculate health based on hops
                    hops = data.get('hops', [])
                    health = 'unknown'
                    if hops:
                        # Check for valid consecutive hops
                        hop_numbers = [h.get('hop_number', i) for i, h in enumerate(hops)]
                        expected = list(range(1, len(hops) + 1))
                        if set(hop_numbers) == set(expected) and len(hops) >= 2:
                            health = 'valid'
                        elif len(hops) >= 2:
                            health = 'gaps'
                        else:
                            health = 'invalid'

                    sessions.append({
                        'id': data.get('id', path.stem),
                        'name': data.get('name', path.stem),
                        'date': data.get('metadata', {}).get('created', 'unknown'),
                        'tags': data.get('tags', []),
                        'hop_count': len(hops),
                        'health': health
                    })
                except (json.JSONDecodeError, IOError):
                    continue

        return sorted(sessions, key=lambda s: s['name'])

    @lru_cache(maxsize=32)
    def get_session(self, session_name: str) -> dict:
        """Get a specific session by name."""
        session_path = self.sessions_dir / f"{session_name}.json"
        if not session_path.exists():
            raise FileNotFoundError(f"Session not found: {session_name}")

        with open(session_path) as f:
            data = json.load(f)

        return data

    def compute_diff(self, session_a: str, session_b: str) -> dict:
        """Compute diff between two sessions."""
        from backend.replay.core import DiffEngine, IgnoreConfig, Session as ReplaySession

        data_a = self.get_session(session_a)
        data_b = self.get_session(session_b)

        sess_a = ReplaySession(
            id=data_a.get('id', session_a),
            name=data_a.get('name', session_a),
            data=data_a.get('data', {}),
            hops=data_a.get('hops', []),
            tags=data_a.get('tags', []),
            metadata=data_a.get('metadata', {})
        )

        sess_b = ReplaySession(
            id=data_b.get('id', session_b),
            name=data_b.get('name', session_b),
            data=data_b.get('data', {}),
            hops=data_b.get('hops', []),
            tags=data_b.get('tags', []),
            metadata=data_b.get('metadata', {})
        )

        diff_engine = DiffEngine(IgnoreConfig())
        result = diff_engine.compute_diff(sess_a, sess_b)

        return {
            'session_a': session_a,
            'session_b': session_b,
            'identical': result.identical,
            'differences': [
                {
                    'path': d.path,
                    'type': d.diff_type,
                    'value_a': d.value_a,
                    'value_b': d.value_b
                }
                for d in result.differences
            ]
        }

    def log_message(self, format: str, *args) -> None:
        """Suppress default logging to keep output clean."""
        pass


def get_static_dir() -> Path:
    """Get the directory containing static files."""
    # This file is in backend/replay/viewer/, static is in backend/replay/viewer/static/
    return Path(__file__).parent / 'static'


def run_viewer(host: str = 'localhost', port: int = 8080, open_browser: bool = True) -> None:
    """
    Start the Trace Viewer HTTP server.

    Args:
        host: Host to bind to
        port: Port to listen on
        open_browser: Whether to open the browser automatically
    """
    static_dir = get_static_dir()

    # Change to static directory to serve files from there
    os.chdir(static_dir)

    handler = lambda *args, **kwargs: ViewerHandler(*args, directory=str(static_dir), **kwargs)

    server = http.server.HTTPServer((host, port), handler)

    url = f"http://{host}:{port}"
    print(f"🎯 Trace Viewer starting at {url}")
    print(f"   Serving sessions from: {DEFAULT_SESSIONS_DIR}")
    print(f"   Press Ctrl+C to stop")

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Viewer stopped")
        server.shutdown()


if __name__ == '__main__':
    run_viewer()
