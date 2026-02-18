"""Tests for replay CLI commands."""

import pytest
import json
import sys
import tempfile
from pathlib import Path
from io import StringIO

from replay.core import Session, ReplayEngine
from replay.cli import (
    cmd_run, cmd_diff, cmd_list, cmd_validate, cmd_tags,
    validate_session_name, get_sessions_dir
)
import argparse


class TestCLISessionValidation:
    """Test session name validation."""

    def test_valid_session_names(self):
        """Test valid session names are accepted."""
        assert validate_session_name('valid-session') is True
        assert validate_session_name('session123') is True
        assert validate_session_name('my_session') is True
        assert validate_session_name('test-session-1') is True

    def test_invalid_session_names(self):
        """Test invalid session names are rejected."""
        assert validate_session_name('') is False
        assert validate_session_name('../etc/passwd') is False
        assert validate_session_name('session/../../../etc') is False
        assert validate_session_name('session\\path') is False
        assert validate_session_name('session with spaces') is False
        assert validate_session_name('session@special') is False


class TestReplayCLI:
    """Test replay CLI commands."""

    @pytest.fixture
    def sessions_dir(self, tmp_path):
        """Create a temporary sessions directory."""
        sessions = tmp_path / 'sessions'
        sessions.mkdir()
        return sessions

    def test_cmd_run_shows_session_info(self, sessions_dir, capsys):
        """Test that run command shows session info."""
        # Create a test session
        session = Session(
            id='test-run',
            name='test-run',
            data={'key': 'value'},
            tags=['test'],
            hops=[{'hop_number': 1}]
        )
        session.to_file(sessions_dir / 'test-run.json')

        # Create args object
        args = argparse.Namespace(session='test-run', baseline=None)

        # Monkeypatch get_sessions_dir
        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_run(args)
        except SystemExit:
            pass  # Expected for some exit codes

        replay.cli.get_sessions_dir = original_get_sessions_dir

        captured = capsys.readouterr()
        assert 'test-run' in captured.out

    def test_cmd_run_with_invalid_name(self, sessions_dir, capsys):
        """Test that run command rejects invalid session names."""
        args = argparse.Namespace(session='../etc/passwd', baseline=None)

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_run(args)
        except SystemExit as e:
            assert e.code == 2

        replay.cli.get_sessions_dir = original_get_sessions_dir

    def test_cmd_diff_identical_sessions(self, sessions_dir, capsys):
        """Test diff command with identical sessions."""
        # Create two identical sessions
        for name in ['session-a', 'session-b']:
            session = Session(
                id=name,
                name=name,
                data={'key': 'value'},
                tags=[]
            )
            session.to_file(sessions_dir / f'{name}.json')

        args = argparse.Namespace(session_a='session-a', session_b='session-b')

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_diff(args)
        except SystemExit as e:
            assert e.code == 0  # Should exit with 0 for identical

        replay.cli.get_sessions_dir = original_get_sessions_dir

    def test_cmd_diff_different_sessions(self, sessions_dir, capsys):
        """Test diff command with different sessions."""
        session_a = Session(id='a', name='a', data={'key': 'value1'})
        session_b = Session(id='b', name='b', data={'key': 'value2'})

        session_a.to_file(sessions_dir / 'a.json')
        session_b.to_file(sessions_dir / 'b.json')

        args = argparse.Namespace(session_a='a', session_b='b')

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_diff(args)
        except SystemExit as e:
            assert e.code == 1  # Should exit with 1 for different

        replay.cli.get_sessions_dir = original_get_sessions_dir

    def test_cmd_list_empty(self, sessions_dir, capsys):
        """Test list command with no sessions."""
        args = argparse.Namespace()

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        cmd_list(args)

        replay.cli.get_sessions_dir = original_get_sessions_dir

        captured = capsys.readouterr()
        assert 'No sessions found' in captured.out

    def test_cmd_list_with_sessions(self, sessions_dir, capsys):
        """Test list command with sessions."""
        # Create test sessions
        for name in ['session-1', 'session-2']:
            session = Session(
                id=name,
                name=name,
                data={},
                tags=['test'],
                hops=[{'hop_number': 1}]
            )
            session.to_file(sessions_dir / f'{name}.json')

        args = argparse.Namespace()

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        cmd_list(args)

        replay.cli.get_sessions_dir = original_get_sessions_dir

        captured = capsys.readouterr()
        assert 'session-1' in captured.out

    def test_cmd_validate_valid_session(self, sessions_dir, capsys):
        """Test validate command with valid session."""
        session = Session(
            id='valid',
            name='valid',
            data={},
            hops=[{'hop_number': 1}, {'hop_number': 2}]
        )
        session.to_file(sessions_dir / 'valid.json')

        args = argparse.Namespace(session='valid')

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_validate(args)
        except SystemExit as e:
            assert e.code == 0  # Valid session exits with 0

        replay.cli.get_sessions_dir = original_get_sessions_dir

    def test_cmd_validate_invalid_session(self, sessions_dir, capsys):
        """Test validate command with invalid session (no hops)."""
        session = Session(
            id='invalid',
            name='invalid',
            data={},
            hops=[]
        )
        session.to_file(sessions_dir / 'invalid.json')

        args = argparse.Namespace(session='invalid')

        import replay.cli
        original_get_sessions_dir = replay.cli.get_sessions_dir
        replay.cli.get_sessions_dir = lambda: sessions_dir

        try:
            cmd_validate(args)
        except SystemExit as e:
            assert e.code == 1  # Invalid session exits with 1

        replay.cli.get_sessions_dir = original_get_sessions_dir

        captured = capsys.readouterr()
        # Invalid session should have no hops
        assert 'No hops recorded' in captured.out or 'invalid' in captured.out


class TestReplayEnginePartialSessions:
    """Test replay engine handling of partial sessions."""

    def test_load_nonexistent_session_raises(self, tmp_path):
        """Test that loading nonexistent session raises FileNotFoundError."""
        engine = ReplayEngine(tmp_path)

        with pytest.raises(FileNotFoundError):
            engine.load_session('nonexistent')

    def test_session_health_partial_hops(self, tmp_path):
        """Test health check with partial hops."""
        session = Session(
            id='partial',
            name='partial',
            data={},
            hops=[
                {'hop_number': 1},
                {'hop_number': 3}  # Gap - missing hop 2
            ]
        )

        engine = ReplayEngine(tmp_path)
        health = engine.get_session_health(session)

        assert health['status'] == 'valid_with_gaps'
        assert health['total_hops'] == 2

    def test_replay_session_with_pipeline(self, tmp_path):
        """Test replay_session with a simple pipeline."""
        session = Session(
            id='test',
            name='test',
            data={'input': 5}
        )

        def double_stage(data):
            return {'input': data['input'] * 2}

        def add_ten_stage(data):
            return {'input': data['input'] + 10}

        engine = ReplayEngine(tmp_path)
        result = engine.replay_session(session, [double_stage, add_ten_stage])

        # 5 * 2 + 10 = 20
        assert result['input'] == 20
        assert len(session.hops) == 2
