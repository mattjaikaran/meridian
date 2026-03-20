#!/usr/bin/env python3
"""Meridian note capture — append, list, and promote notes to tasks."""

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scripts.state import create_quick_task

# Default notes file location
NOTES_FILENAME = "notes.md"


def _notes_path(project_dir: Path) -> Path:
    """Get the path to the notes file."""
    return project_dir / ".meridian" / NOTES_FILENAME


def _next_note_id(content: str) -> str:
    """Compute the next note ID from existing content.

    Notes are formatted as [N001], [N002], etc.
    """
    ids = re.findall(r"\[N(\d+)\]", content)
    if not ids:
        return "N001"
    max_id = max(int(i) for i in ids)
    return f"N{max_id + 1:03d}"


def _now_str() -> str:
    """Return current UTC time as a formatted string."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M")


def append_note(project_dir: Path, text: str) -> dict:
    """Append a timestamped note to .meridian/notes.md.

    Args:
        project_dir: Project root directory.
        text: The note text.

    Returns:
        Dict with id, timestamp, text, and file path.
    """
    notes_file = _notes_path(project_dir)
    notes_file.parent.mkdir(parents=True, exist_ok=True)

    if notes_file.exists():
        content = notes_file.read_text(encoding="utf-8")
    else:
        content = "## Notes\n\n"

    note_id = _next_note_id(content)
    timestamp = _now_str()
    note_line = f"- [{note_id}] {timestamp} — {text}\n"

    # Append the note
    if not content.endswith("\n"):
        content += "\n"
    content += note_line

    notes_file.write_text(content, encoding="utf-8")

    return {
        "id": note_id,
        "timestamp": timestamp,
        "text": text,
        "file": str(notes_file),
    }


def list_notes(project_dir: Path) -> list[dict]:
    """List all notes from .meridian/notes.md.

    Returns:
        List of dicts with id, timestamp, text, promoted.
    """
    notes_file = _notes_path(project_dir)
    if not notes_file.exists():
        return []

    content = notes_file.read_text(encoding="utf-8")
    notes: list[dict] = []

    for match in re.finditer(
        r"- \[(N\d+)\] (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) — (.+?)(?:\s*\[PROMOTED\])?\s*$",
        content,
        re.MULTILINE,
    ):
        note_id = match.group(1)
        timestamp = match.group(2)
        text = match.group(3).strip()
        promoted = "[PROMOTED]" in match.group(0)
        notes.append({
            "id": note_id,
            "timestamp": timestamp,
            "text": text,
            "promoted": promoted,
        })

    return notes


def promote_note(
    project_dir: Path,
    note_id: str,
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> dict:
    """Promote a note to a quick_task in the DB.

    Args:
        project_dir: Project root directory.
        note_id: The note ID (e.g., "N001").
        conn: Database connection.
        project_id: Project identifier.

    Returns:
        Dict with note info and the created task.

    Raises:
        ValueError: If note_id not found or already promoted.
    """
    notes_file = _notes_path(project_dir)
    if not notes_file.exists():
        raise ValueError(f"Notes file not found: {notes_file}")

    content = notes_file.read_text(encoding="utf-8")

    # Find the note
    pattern = re.compile(
        rf"(- \[{re.escape(note_id)}\] (\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}) — (.+?))(\s*\[PROMOTED\])?\s*$",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        raise ValueError(f"Note {note_id} not found")

    if match.group(4):
        raise ValueError(f"Note {note_id} is already promoted")

    text = match.group(3).strip()

    # Create a quick_task from the note
    task = create_quick_task(conn, f"[from note {note_id}] {text}", project_id)

    # Mark the note as promoted in the file
    old_line = match.group(0)
    new_line = old_line.rstrip() + " [PROMOTED]"
    content = content.replace(old_line, new_line)
    notes_file.write_text(content, encoding="utf-8")

    return {
        "note_id": note_id,
        "text": text,
        "task_id": task["id"],
        "task": task,
    }
