"""
Trace Viewer - Interactive visualization tool for capture sessions.

This module provides a web-based UI for viewing and comparing capture sessions
as an interactive pipeline timeline.
"""

from backend.replay.viewer.server import run_viewer

__all__ = ['run_viewer']
