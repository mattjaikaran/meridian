#!/usr/bin/env python3
"""Session awareness — detect concurrent Meridian sessions via PID files."""

import os
import signal
from datetime import UTC, datetime
from pathlib import Path


def _sessions_dir(meridian_dir: str | Path) -> Path:
    """Get the sessions directory path."""
    return Path(meridian_dir) / ".meridian" / "sessions"


def _is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def register_session(project_dir: str | Path) -> Path:
    """Register current process as an active Meridian session.

    Creates a PID file in .meridian/sessions/<pid>.
    Returns the PID file path.
    """
    sessions = _sessions_dir(project_dir)
    sessions.mkdir(parents=True, exist_ok=True)

    pid = os.getpid()
    pid_file = sessions / str(pid)
    pid_file.write_text(datetime.now(UTC).isoformat())
    return pid_file


def unregister_session(project_dir: str | Path) -> bool:
    """Remove current process's session PID file.

    Returns True if file was removed, False if not found.
    """
    pid_file = _sessions_dir(project_dir) / str(os.getpid())
    if pid_file.exists():
        pid_file.unlink()
        return True
    return False


def cleanup_stale(project_dir: str | Path) -> int:
    """Remove PID files for processes that are no longer running.

    Returns count of stale sessions removed.
    """
    sessions = _sessions_dir(project_dir)
    if not sessions.exists():
        return 0

    removed = 0
    for pid_file in sessions.iterdir():
        if not pid_file.name.isdigit():
            continue
        pid = int(pid_file.name)
        if not _is_pid_alive(pid):
            pid_file.unlink()
            removed += 1
    return removed


def count_active_sessions(project_dir: str | Path) -> int:
    """Count active Meridian sessions, pruning stale ones first."""
    sessions = _sessions_dir(project_dir)
    if not sessions.exists():
        return 0

    cleanup_stale(project_dir)

    count = 0
    for pid_file in sessions.iterdir():
        if pid_file.name.isdigit():
            count += 1
    return count


def is_multi_session(project_dir: str | Path, threshold: int = 3) -> bool:
    """Check if there are multiple concurrent sessions above threshold."""
    return count_active_sessions(project_dir) >= threshold


def format_session_status(project_dir: str | Path) -> str:
    """Format session count for display."""
    count = count_active_sessions(project_dir)
    if count <= 1:
        return f"Active sessions: {count}"
    return f"Active sessions: {count} (multi-session mode)"
