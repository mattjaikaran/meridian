#!/usr/bin/env python3
"""Tests for session awareness (scripts/sessions.py)."""

import os

from scripts.sessions import (
    cleanup_stale,
    count_active_sessions,
    format_session_status,
    is_multi_session,
    register_session,
    unregister_session,
)


class TestRegisterSession:
    def test_creates_pid_file(self, tmp_path):
        pid_file = register_session(tmp_path)
        assert pid_file.exists()
        assert pid_file.name == str(os.getpid())

    def test_pid_file_has_timestamp(self, tmp_path):
        pid_file = register_session(tmp_path)
        content = pid_file.read_text()
        assert len(content) > 0  # Has ISO timestamp

    def test_creates_sessions_dir(self, tmp_path):
        register_session(tmp_path)
        assert (tmp_path / ".meridian" / "sessions").is_dir()

    def test_idempotent(self, tmp_path):
        register_session(tmp_path)
        register_session(tmp_path)
        sessions_dir = tmp_path / ".meridian" / "sessions"
        pid_files = list(sessions_dir.iterdir())
        assert len(pid_files) == 1


class TestUnregisterSession:
    def test_removes_pid_file(self, tmp_path):
        pid_file = register_session(tmp_path)
        assert unregister_session(tmp_path) is True
        assert not pid_file.exists()

    def test_returns_false_when_not_registered(self, tmp_path):
        assert unregister_session(tmp_path) is False


class TestCleanupStale:
    def test_removes_dead_pids(self, tmp_path):
        sessions_dir = tmp_path / ".meridian" / "sessions"
        sessions_dir.mkdir(parents=True)
        # Create a PID file for a definitely-dead process
        (sessions_dir / "99999999").write_text("2026-01-01T00:00:00")
        removed = cleanup_stale(tmp_path)
        assert removed == 1
        assert not (sessions_dir / "99999999").exists()

    def test_keeps_alive_pids(self, tmp_path):
        register_session(tmp_path)
        removed = cleanup_stale(tmp_path)
        assert removed == 0

    def test_no_sessions_dir(self, tmp_path):
        assert cleanup_stale(tmp_path) == 0

    def test_ignores_non_pid_files(self, tmp_path):
        sessions_dir = tmp_path / ".meridian" / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "readme.txt").write_text("ignore me")
        removed = cleanup_stale(tmp_path)
        assert removed == 0
        assert (sessions_dir / "readme.txt").exists()


class TestCountActiveSessions:
    def test_zero_when_empty(self, tmp_path):
        assert count_active_sessions(tmp_path) == 0

    def test_counts_current_session(self, tmp_path):
        register_session(tmp_path)
        assert count_active_sessions(tmp_path) == 1

    def test_prunes_stale_before_counting(self, tmp_path):
        sessions_dir = tmp_path / ".meridian" / "sessions"
        sessions_dir.mkdir(parents=True)
        (sessions_dir / "99999999").write_text("stale")
        register_session(tmp_path)
        count = count_active_sessions(tmp_path)
        assert count == 1  # Only current process, stale was pruned


class TestIsMultiSession:
    def test_single_session_not_multi(self, tmp_path):
        register_session(tmp_path)
        assert is_multi_session(tmp_path) is False

    def test_threshold_default_3(self, tmp_path):
        register_session(tmp_path)
        assert is_multi_session(tmp_path, threshold=1) is True

    def test_no_sessions(self, tmp_path):
        assert is_multi_session(tmp_path) is False


class TestFormatSessionStatus:
    def test_no_sessions(self, tmp_path):
        status = format_session_status(tmp_path)
        assert "Active sessions: 0" in status

    def test_single_session(self, tmp_path):
        register_session(tmp_path)
        status = format_session_status(tmp_path)
        assert "Active sessions: 1" in status
        assert "multi-session" not in status
