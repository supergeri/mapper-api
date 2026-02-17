"""Pytest fixtures for replay harness tests."""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

import pytest
import json
import tempfile
from pathlib import Path
from typing import Any

from replay.core import Session


@pytest.fixture
def valid_session() -> Session:
    """Fixture for a valid session with complete data."""
    return Session(
        id='valid-001',
        name='valid-session',
        data={
            'workout': {
                'idout-123': 'work',
                'name': 'Morning Workout',
                'exercises': [
                    {'name': 'Squats', 'sets': 3, 'reps': 10},
                    {'name': 'Pushups', 'sets': 3, 'reps': 15}
                ]
            }
        },
        tags=['valid', 'complete'],
        hops=[
            {'hop_number': 1, 'stage': 'capture', 'before': {}, 'after': {'workout': {'id': 'workout-123'}}},
            {'hop_number': 2, 'stage': 'process', 'before': {'workout': {'id': 'workout-123'}}, 'after': {'workout': {'id': 'workout-123', 'name': 'Morning Workout'}}}
        ]
    )


@pytest.fixture
def partial_session() -> Session:
    """Fixture for a session with missing data/hops."""
    return Session(
        id='partial-001',
        name='partial-session',
        data={
            'workout': {
                'id': 'workout-456'
                # Missing 'name' and 'exercises'
            }
        },
        tags=['partial'],
        hops=[
            {'hop_number': 1, 'stage': 'capture', 'before': {}, 'after': {'workout': {'id': 'workout-456'}}}
            # Missing hop_number 2
        ]
    )


@pytest.fixture
def corrupted_session(tmp_path: Path) -> Path:
    """Fixture for a corrupted session file (invalid JSON)."""
    session_file = tmp_path / 'corrupted.json'
    session_file.write_text('{ invalid json }')
    return session_file


@pytest.fixture
def sample_workout_payload() -> dict:
    """Sample workout data for testing."""
    return {
        'id': 'workout-789',
        'name': 'Test Workout',
        'date': '2024-01-15T10:00:00Z',
        'exercises': [
            {
                'name': 'Deadlift',
                'sets': 5,
                'reps': 5,
                'weight': 225
            },
            {
                'name': 'Bench Press',
                'sets': 3,
                'reps': 10,
                'weight': 135
            }
        ],
        'duration': 3600,
        'calories': 500
    }


@pytest.fixture
def sessions_dir(tmp_path: Path) -> Path:
    """Fixture for a temporary sessions directory."""
    sessions = tmp_path / 'sessions'
    sessions.mkdir()
    return sessions


@pytest.fixture
def session_file(tmp_path: Path, valid_session: Session) -> Path:
    """Fixture for a valid session file on disk."""
    session_file = tmp_path / 'valid-session.json'
    valid_session.to_file(session_file)
    return session_file
