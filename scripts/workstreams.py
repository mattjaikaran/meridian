#!/usr/bin/env python3
"""Meridian workstream system — multi-track parallel milestone management."""

import sqlite3
from pathlib import Path

from scripts.utils import now_iso as _now, row_to_dict as _row_to_dict, sanitize_slug as _sanitize_slug


# ── CRUD ─────────────────────────────────────────────────────────────────────


def create_workstream(
    conn: sqlite3.Connection,
    name: str,
    description: str = "",
    project_id: str = "default",
    slug: str | None = None,
) -> dict:
    """Create a new workstream.

    Args:
        conn: Database connection.
        name: Human-readable name (slug derived from it if not given).
        description: Optional description of this workstream's scope.
        project_id: Project to attach to.
        slug: Optional explicit slug; derived from name if omitted.

    Returns:
        Dict representation of the new workstream row.

    Raises:
        ValueError: If slug cannot be derived or already exists.
    """
    if slug is None:
        slug = _sanitize_slug(name)
    now = _now()
    conn.execute(
        """
        INSERT INTO workstream (project_id, slug, name, description, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?)
        """,
        (project_id, slug, name, description, now, now),
    )
    return get_workstream(conn, slug)  # type: ignore[return-value]


def get_workstream(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Fetch a workstream by slug. Returns None if not found."""
    row = conn.execute(
        "SELECT * FROM workstream WHERE slug = ?", (slug,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def get_workstream_by_id(conn: sqlite3.Connection, workstream_id: int) -> dict | None:
    """Fetch a workstream by id. Returns None if not found."""
    row = conn.execute(
        "SELECT * FROM workstream WHERE id = ?", (workstream_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_workstreams(
    conn: sqlite3.Connection,
    status: str | None = None,
    project_id: str = "default",
) -> list[dict]:
    """List workstreams, optionally filtered by status.

    Args:
        conn: Database connection.
        status: 'active', 'paused', 'complete', 'archived', or None for all.
        project_id: Project scope.

    Returns:
        List of workstream dicts, newest first.
    """
    valid = {"active", "paused", "complete", "archived"}
    if status is not None and status not in valid:
        raise ValueError(f"Invalid status filter: {status!r}. Must be one of {valid}.")
    if status:
        rows = conn.execute(
            "SELECT * FROM workstream WHERE project_id = ? AND status = ?"
            " ORDER BY created_at DESC, id DESC",
            (project_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM workstream WHERE project_id = ? ORDER BY created_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def pause_workstream(conn: sqlite3.Connection, slug: str) -> dict:
    """Pause an active workstream (switch away from it).

    Raises:
        ValueError: If workstream not found or not active.
    """
    ws = get_workstream(conn, slug)
    if ws is None:
        raise ValueError(f"Workstream not found: {slug!r}")
    if ws["status"] != "active":
        raise ValueError(f"Workstream {slug!r} is not active (status={ws['status']!r})")
    conn.execute(
        "UPDATE workstream SET status = 'paused', updated_at = ? WHERE slug = ?",
        (_now(), slug),
    )
    return get_workstream(conn, slug)  # type: ignore[return-value]


def resume_workstream(conn: sqlite3.Connection, slug: str) -> dict:
    """Resume a paused workstream.

    Raises:
        ValueError: If workstream not found or not paused.
    """
    ws = get_workstream(conn, slug)
    if ws is None:
        raise ValueError(f"Workstream not found: {slug!r}")
    if ws["status"] != "paused":
        raise ValueError(f"Workstream {slug!r} is not paused (status={ws['status']!r})")
    conn.execute(
        "UPDATE workstream SET status = 'active', updated_at = ? WHERE slug = ?",
        (_now(), slug),
    )
    return get_workstream(conn, slug)  # type: ignore[return-value]


def complete_workstream(conn: sqlite3.Connection, slug: str) -> dict:
    """Mark a workstream as complete.

    Raises:
        ValueError: If workstream not found or already complete/archived.
    """
    ws = get_workstream(conn, slug)
    if ws is None:
        raise ValueError(f"Workstream not found: {slug!r}")
    if ws["status"] in ("complete", "archived"):
        raise ValueError(f"Workstream {slug!r} is already {ws['status']!r}")
    now = _now()
    conn.execute(
        "UPDATE workstream SET status = 'complete', updated_at = ?, completed_at = ? WHERE slug = ?",
        (now, now, slug),
    )
    return get_workstream(conn, slug)  # type: ignore[return-value]


def assign_milestone(
    conn: sqlite3.Connection,
    milestone_id: str,
    workstream_slug: str,
) -> None:
    """Assign a milestone to a workstream.

    Raises:
        ValueError: If workstream not found.
    """
    ws = get_workstream(conn, workstream_slug)
    if ws is None:
        raise ValueError(f"Workstream not found: {workstream_slug!r}")
    conn.execute(
        "UPDATE milestone SET workstream_id = ? WHERE id = ?",
        (ws["id"], milestone_id),
    )


# ── Session-aware switching ───────────────────────────────────────────────────

ACTIVE_WORKSTREAM_KEY = "active_workstream"


def get_active_workstream(conn: sqlite3.Connection, project_id: str = "default") -> dict | None:
    """Return the currently active workstream for this session, or None."""
    row = conn.execute(
        "SELECT value FROM settings WHERE project_id = ? AND key = ?",
        (project_id, ACTIVE_WORKSTREAM_KEY),
    ).fetchone()
    if not row:
        return None
    slug = row["value"]
    return get_workstream(conn, slug)


def switch_workstream(
    conn: sqlite3.Connection,
    slug: str,
    project_id: str = "default",
) -> dict:
    """Switch the active session workstream to the given slug.

    Pauses the current active workstream (if any and different).
    Resumes the target if paused. Sets active_workstream in settings.

    Returns:
        The newly active workstream dict.

    Raises:
        ValueError: If target workstream not found or complete/archived.
    """
    target = get_workstream(conn, slug)
    if target is None:
        raise ValueError(f"Workstream not found: {slug!r}")
    if target["status"] in ("complete", "archived"):
        raise ValueError(
            f"Cannot switch to workstream {slug!r} — status is {target['status']!r}"
        )

    # Pause current active workstream if it's a different one
    current = get_active_workstream(conn, project_id)
    if current and current["slug"] != slug and current["status"] == "active":
        pause_workstream(conn, current["slug"])

    # Resume target if paused
    if target["status"] == "paused":
        resume_workstream(conn, slug)

    # Persist session setting
    now = _now()
    conn.execute(
        """
        INSERT INTO settings (project_id, key, value, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(project_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (project_id, ACTIVE_WORKSTREAM_KEY, slug, now, now),
    )
    return get_workstream(conn, slug)  # type: ignore[return-value]


# ── Progress ──────────────────────────────────────────────────────────────────


def get_workstream_progress(
    conn: sqlite3.Connection,
    slug: str,
    project_id: str = "default",
) -> dict:
    """Compute progress for a workstream across its milestones and phases.

    Returns:
        Dict with workstream metadata, milestones list, and aggregate counters.

    Raises:
        ValueError: If workstream not found.
    """
    ws = get_workstream(conn, slug)
    if ws is None:
        raise ValueError(f"Workstream not found: {slug!r}")

    milestones = conn.execute(
        "SELECT * FROM milestone WHERE workstream_id = ? AND project_id = ?"
        " ORDER BY created_at ASC",
        (ws["id"], project_id),
    ).fetchall()

    milestone_data = []
    total_phases = 0
    complete_phases = 0

    for ms in milestones:
        phases = conn.execute(
            "SELECT status FROM phase WHERE milestone_id = ?",
            (ms["id"],),
        ).fetchall()
        phase_count = len(phases)
        phase_done = sum(1 for p in phases if p["status"] == "complete")
        total_phases += phase_count
        complete_phases += phase_done
        pct = round(100 * phase_done / phase_count) if phase_count else 0
        milestone_data.append({
            "id": ms["id"],
            "name": ms["name"],
            "status": ms["status"],
            "phase_count": phase_count,
            "phase_done": phase_done,
            "pct": pct,
        })

    overall_pct = round(100 * complete_phases / total_phases) if total_phases else 0

    return {
        "workstream": ws,
        "milestones": milestone_data,
        "total_phases": total_phases,
        "complete_phases": complete_phases,
        "overall_pct": overall_pct,
    }


def get_all_workstreams_progress(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> list[dict]:
    """Return progress for every workstream in the project."""
    workstreams = list_workstreams(conn, project_id=project_id)
    return [get_workstream_progress(conn, ws["slug"], project_id) for ws in workstreams]
