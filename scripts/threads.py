#!/usr/bin/env python3
"""Meridian thread system — lightweight persistent discussion threads."""

import sqlite3
from pathlib import Path

from scripts.utils import now_iso as _now, row_to_dict as _row_to_dict, sanitize_slug as _sanitize_slug


# ── CRUD ─────────────────────────────────────────────────────────────────────


def create_thread(
    conn: sqlite3.Connection,
    title: str,
    body: str,
    project_id: str = "default",
    slug: str | None = None,
) -> dict:
    """Create a new open thread.

    Args:
        conn: Database connection.
        title: Human-readable title (used to derive slug if slug not given).
        body: Thread content (no code execution — treated as plain text).
        project_id: Project to attach to.
        slug: Optional explicit slug; derived from title if omitted.

    Returns:
        Dict representation of the new thread row.

    Raises:
        ValueError: If slug already exists or cannot be derived.
        sqlite3.IntegrityError: Propagated if slug collides after sanitization.
    """
    if slug is None:
        slug = _sanitize_slug(title)
    now = _now()
    conn.execute(
        """
        INSERT INTO thread (project_id, slug, body, status, created_at, updated_at)
        VALUES (?, ?, ?, 'open', ?, ?)
        """,
        (project_id, slug, body, now, now),
    )
    return get_thread(conn, slug)  # type: ignore[return-value]


def get_thread(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Fetch a thread by slug. Returns None if not found."""
    row = conn.execute(
        "SELECT * FROM thread WHERE slug = ?", (slug,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def list_threads(
    conn: sqlite3.Connection,
    status: str | None = None,
    project_id: str = "default",
) -> list[dict]:
    """List threads, optionally filtered by status.

    Args:
        conn: Database connection.
        status: 'open', 'resolved', or None for all.
        project_id: Project scope.

    Returns:
        List of thread dicts, newest first.
    """
    if status is not None and status not in ("open", "resolved"):
        raise ValueError(f"Invalid status filter: {status!r}. Must be 'open' or 'resolved'.")
    if status:
        rows = conn.execute(
            "SELECT * FROM thread WHERE project_id = ? AND status = ?"
            " ORDER BY created_at DESC, id DESC",
            (project_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM thread WHERE project_id = ? ORDER BY created_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def close_thread(conn: sqlite3.Connection, slug: str) -> dict:
    """Mark a thread as resolved.

    Raises:
        ValueError: If thread not found or already resolved.
    """
    thread = get_thread(conn, slug)
    if thread is None:
        raise ValueError(f"Thread not found: {slug!r}")
    if thread["status"] == "resolved":
        raise ValueError(f"Thread {slug!r} is already resolved")
    now = _now()
    conn.execute(
        "UPDATE thread SET status = 'resolved', updated_at = ? WHERE slug = ?",
        (now, slug),
    )
    return get_thread(conn, slug)  # type: ignore[return-value]


def reopen_thread(conn: sqlite3.Connection, slug: str) -> dict:
    """Re-open a resolved thread (resume mode).

    Raises:
        ValueError: If thread not found or already open.
    """
    thread = get_thread(conn, slug)
    if thread is None:
        raise ValueError(f"Thread not found: {slug!r}")
    if thread["status"] == "open":
        raise ValueError(f"Thread {slug!r} is already open")
    now = _now()
    conn.execute(
        "UPDATE thread SET status = 'open', updated_at = ? WHERE slug = ?",
        (now, slug),
    )
    return get_thread(conn, slug)  # type: ignore[return-value]


def update_thread_body(conn: sqlite3.Connection, slug: str, body: str) -> dict:
    """Append or replace thread body content.

    Raises:
        ValueError: If thread not found.
    """
    thread = get_thread(conn, slug)
    if thread is None:
        raise ValueError(f"Thread not found: {slug!r}")
    now = _now()
    conn.execute(
        "UPDATE thread SET body = ?, updated_at = ? WHERE slug = ?",
        (body, now, slug),
    )
    return get_thread(conn, slug)  # type: ignore[return-value]


# ── Promotion helpers ─────────────────────────────────────────────────────────


def promote_to_backlog(
    conn: sqlite3.Connection,
    slug: str,
    project_dir: Path,
) -> dict:
    """Export thread as a backlog entry and close it.

    Writes a markdown file to .planning/backlog/{slug}.md.
    Returns dict with thread info and file path.
    """
    thread = get_thread(conn, slug)
    if thread is None:
        raise ValueError(f"Thread not found: {slug!r}")

    backlog_dir = project_dir / ".planning" / "backlog"
    backlog_dir.mkdir(parents=True, exist_ok=True)
    target = backlog_dir / f"{slug}.md"
    target.write_text(
        f"# Thread: {slug}\n\n{thread['body']}\n\n"
        f"_Promoted from thread on {_now()}_\n",
        encoding="utf-8",
    )

    close_thread(conn, slug)
    return {
        "slug": slug,
        "file": str(target),
        "thread": get_thread(conn, slug),
    }
