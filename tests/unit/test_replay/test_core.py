"""Unit tests for the Replay Engine."""

import pytest
import json
import tempfile
from pathlib import Path

from backend.replay.core import (
    Session,
    ReplayEngine,
    DiffEngine,
    IgnoreConfig,
    DiffItem
)


class TestSession:
    """Tests for Session class."""

    def test_session_from_file(self, tmp_path):
        """Test loading a session from a JSON file."""
        session_data = {
            'id': 'test-001',
            'name': 'test-session',
            'data': {'key': 'value'},
            'tags': ['test', 'unit'],
            'hops': [{'hop_number': 1, 'stage': 'start'}]
        }

        session_file = tmp_path / 'test-session.json'
        with open(session_file, 'w') as f:
            json.dump(session_data, f)

        session = Session.from_file(session_file)

        assert session.id == 'test-001'
        assert session.name == 'test-session'
        assert session.data == {'key': 'value'}
        assert session.tags == ['test', 'unit']
        assert len(session.hops) == 1

    def test_session_to_file(self, tmp_path):
        """Test saving a session to a JSON file."""
        session = Session(
            id='test-002',
            name='save-test',
            data={'foo': 'bar'},
            tags=['save'],
            hops=[]
        )

        session_file = tmp_path / 'save-test.json'
        session.to_file(session_file)

        with open(session_file) as f:
            loaded = json.load(f)

        assert loaded['id'] == 'test-002'
        assert loaded['name'] == 'save-test'
        assert loaded['data'] == {'foo': 'bar'}


class TestDiffEngine:
    """Tests for DiffEngine class."""

    def test_identical_sessions(self):
        """Test that identical sessions have no differences."""
        session_a = Session('a', 'a', {'key': 'value'})
        session_b = Session('b', 'b', {'key': 'value'})

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is True
        assert len(result.differences) == 0

    def test_changed_value(self):
        """Test detecting changed values."""
        session_a = Session('a', 'a', {'count': 10})
        session_b = Session('b', 'b', {'count': 20})

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        assert len(result.differences) == 1
        assert result.differences[0].diff_type == 'changed'
        assert result.differences[0].path == 'count'

    def test_added_field(self):
        """Test detecting added fields."""
        session_a = Session('a', 'a', {'a': 1})
        session_b = Session('b', 'b', {'a': 1, 'b': 2})

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        assert any(d.diff_type == 'added' and d.path == 'b' for d in result.differences)

    def test_removed_field(self):
        """Test detecting removed fields."""
        session_a = Session('a', 'a', {'a': 1, 'b': 2})
        session_b = Session('b', 'b', {'a': 1})

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        assert result.identical is False
        assert any(d.diff_type == 'removed' and d.path == 'b' for d in result.differences)

    def test_numeric_precision(self):
        """Test numeric precision handling."""
        session_a = Session('a', 'a', {'val': 1.0})
        session_b = Session('b', 'b', {'val': 1.0000000001})

        engine = DiffEngine()
        result = engine.compute_diff(session_a, session_b)

        # Should be considered equal within epsilon
        assert result.identical is True

    def test_ignore_config(self):
        """Test that ignore config filters out differences."""
        session_a = Session('a', 'a', {'title': 'A', 'value': 1})
        session_b = Session('b', 'b', {'title': 'B', 'value': 2})

        ignore_config = IgnoreConfig(patterns=['title'])
        engine = DiffEngine(ignore_config)
        result = engine.compute_diff(session_a, session_b)

        # Only 'value' should be in differences, not 'title'
        assert len(result.differences) == 1
        assert result.differences[0].path == 'value'


class TestIgnoreConfig:
    """Tests for IgnoreConfig class."""

    def test_exact_match(self):
        """Test exact path matching."""
        config = IgnoreConfig(['title', 'description'])

        assert config.should_ignore('title') is True
        assert config.should_ignore('description') is True
        assert config.should_ignore('content') is False

    def test_wildcard_match(self):
        """Test wildcard pattern matching."""
        config = IgnoreConfig(['exercises.*reps'])

        # Convert bracket notation
        assert config.should_ignore('exercises[0].reps') is True
        assert config.should_ignore('exercises.0.reps') is True
        assert config.should_ignore('exercises.reps') is True
        assert config.should_ignore('exercises.sets') is False


class TestReplayEngine:
    """Tests for ReplayEngine class."""

    def test_load_session(self, tmp_path):
        """Test loading a session by name."""
        session_data = {
            'id': 'load-001',
            'name': 'load-test',
            'data': {'test': True},
            'tags': [],
            'hops': []
        }

        sessions_dir = tmp_path / 'sessions'
        sessions_dir.mkdir()

        session_file = sessions_dir / 'load-test.json'
        with open(session_file, 'w') as f:
            json.dump(session_data, f)

        engine = ReplayEngine(sessions_dir)
        session = engine.load_session('load-test')

        assert session.name == 'load-test'
        assert session.data == {'test': True}

    def test_list_sessions(self, tmp_path):
        """Test listing all sessions."""
        sessions_dir = tmp_path / 'sessions'
        sessions_dir.mkdir()

        # Create test sessions
        for name in ['session-a', 'session-b', 'session-c']:
            session_file = sessions_dir / f'{name}.json'
            with open(session_file, 'w') as f:
                json.dump({'id': name, 'name': name, 'data': {}}, f)

        engine = ReplayEngine(sessions_dir)
        sessions = engine.list_sessions()

        assert len(sessions) == 3
        names = {s.name for s in sessions}
        assert names == {'session-a', 'session-b', 'session-c'}

    def test_session_health_valid(self):
        """Test health check for valid session."""
        session = Session('a', 'a', {}, hops=[
            {'hop_number': 1},
            {'hop_number': 2},
            {'hop_number': 3}
        ])

        engine = ReplayEngine(Path('/tmp'))
        health = engine.get_session_health(session)

        assert health['status'] == 'valid'
        assert health['consecutive_hops'] == 3

    def test_session_health_with_gaps(self):
        """Test health check for session with missing hops."""
        session = Session('a', 'a', {}, hops=[
            {'hop_number': 1},
            {'hop_number': 3}  # Missing hop 2
        ])

        engine = ReplayEngine(Path('/tmp'))
        health = engine.get_session_health(session)

        assert health['status'] == 'valid_with_gaps'
        assert health['consecutive_hops'] == 1

    def test_session_health_invalid(self):
        """Test health check for invalid session (no hops)."""
        session = Session('a', 'a', {}, hops=[])

        engine = ReplayEngine(Path('/tmp'))
        health = engine.get_session_health(session)

        assert health['status'] == 'invalid'
