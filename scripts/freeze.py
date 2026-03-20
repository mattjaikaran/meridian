#!/usr/bin/env python3
"""Edit scope lock — restrict file edits to a specific directory."""

import os
import sqlite3

from scripts.state import get_setting, set_setting

FREEZE_KEY = "freeze_directory"


def set_freeze(conn: sqlite3.Connection, directory: str, project_id: str = "default") -> dict:
    """Lock edits to a specific directory.

    Stores the absolute path in settings. Returns freeze info dict.
    Raises ValueError if directory is empty.
    """
    directory = directory.strip()
    if not directory:
        raise ValueError("Directory cannot be empty")
    abs_dir = os.path.abspath(directory)
    set_setting(conn, FREEZE_KEY, abs_dir, project_id)
    return {"frozen_directory": abs_dir, "active": True}


def get_freeze(conn: sqlite3.Connection, project_id: str = "default") -> str | None:
    """Get current frozen directory, or None if not frozen."""
    return get_setting(conn, FREEZE_KEY, project_id=project_id)


def clear_freeze(conn: sqlite3.Connection, project_id: str = "default") -> bool:
    """Remove freeze lock. Returns True if a freeze was active."""
    current = get_freeze(conn, project_id)
    if current is None:
        return False
    conn.execute(
        "DELETE FROM settings WHERE project_id = ? AND key = ?",
        (project_id, FREEZE_KEY),
    )
    conn.commit()
    return True


def is_path_allowed(frozen_dir: str, file_path: str) -> bool:
    """Check if file_path is within the frozen directory.

    Both paths are resolved to absolute before comparison.
    Returns True if the file is inside the frozen dir (edit allowed).
    Returns False if outside (edit should be blocked/warned).
    """
    abs_frozen = os.path.abspath(frozen_dir)
    abs_file = os.path.abspath(file_path)
    # Ensure the frozen dir ends with separator for prefix check
    prefix = abs_frozen if abs_frozen.endswith(os.sep) else abs_frozen + os.sep
    return abs_file.startswith(prefix) or abs_file == abs_frozen


def check_freeze(conn: sqlite3.Connection, file_path: str, project_id: str = "default") -> dict:
    """Check if a file edit is allowed under current freeze state.

    Returns:
        {"allowed": True/False, "frozen_directory": str|None, "file_path": str}
    """
    frozen = get_freeze(conn, project_id)
    if frozen is None:
        return {"allowed": True, "frozen_directory": None, "file_path": file_path}
    allowed = is_path_allowed(frozen, file_path)
    return {"allowed": allowed, "frozen_directory": frozen, "file_path": file_path}


def format_freeze_status(conn: sqlite3.Connection, project_id: str = "default") -> str:
    """Format current freeze state for display."""
    frozen = get_freeze(conn, project_id)
    if frozen is None:
        return "Edit lock: none"
    return f"Edit lock: {frozen} (active)"
