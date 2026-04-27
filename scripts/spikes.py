#!/usr/bin/env python3
"""Meridian spike workflow — pre-commitment exploration units."""

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sanitize_slug(text: str) -> str:
    """Convert freeform text to a lowercase hyphenated slug (max 60 chars)."""
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    slug = slug[:60].rstrip("-")
    if not slug:
        raise ValueError(f"Cannot derive a valid slug from: {text!r}")
    return slug


def _row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def _spike_dir(project_dir: Path, slug: str) -> Path:
    return project_dir / ".planning" / "spikes" / slug


def _write_manifest(spike_dir: Path, spike: dict) -> None:
    """Write or overwrite MANIFEST.md in a spike directory."""
    spike_dir.mkdir(parents=True, exist_ok=True)
    phase_line = f"Phase: {spike['phase_id']}" if spike.get("phase_id") else "Phase: (none)"
    outcome_section = ""
    if spike.get("outcome"):
        outcome_section = f"\n## Outcome\n\n{spike['outcome']}\n"
    content = (
        f"# Spike: {spike['title']}\n\n"
        f"**Status:** {spike['status']}  \n"
        f"**{phase_line}**  \n"
        f"**Created:** {spike['created_at']}  \n"
        f"**Updated:** {spike['updated_at']}\n\n"
        f"## Question\n\n{spike['question']}\n"
        f"{outcome_section}"
    )
    (spike_dir / "MANIFEST.md").write_text(content, encoding="utf-8")


# ── CRUD ─────────────────────────────────────────────────────────────────────


def create_spike(
    conn: sqlite3.Connection,
    title: str,
    question: str,
    project_dir: Path,
    project_id: str = "default",
    phase_id: int | None = None,
    slug: str | None = None,
) -> dict:
    """Create a new spike and write .planning/spikes/{slug}/MANIFEST.md.

    Args:
        conn: Database connection.
        title: Human-readable title (slug derived from it if not given).
        question: The exploration question this spike answers.
        project_dir: Project root (for writing artifact files).
        project_id: Project to attach to.
        phase_id: Optional phase that triggered this spike.
        slug: Explicit slug; derived from title if omitted.

    Returns:
        Dict representation of the new spike row.

    Raises:
        ValueError: If slug already exists or cannot be derived.
        sqlite3.IntegrityError: On slug collision.
    """
    if slug is None:
        slug = _sanitize_slug(title)
    now = _now()
    conn.execute(
        """
        INSERT INTO spike (project_id, slug, title, question, status, phase_id,
                           created_at, updated_at)
        VALUES (?, ?, ?, ?, 'open', ?, ?, ?)
        """,
        (project_id, slug, title, question, phase_id, now, now),
    )
    spike = get_spike(conn, slug)
    assert spike is not None
    _write_manifest(_spike_dir(project_dir, slug), spike)
    (spike_dir := _spike_dir(project_dir, slug) / "findings").mkdir(
        parents=True, exist_ok=True
    )
    _ = spike_dir  # ensure findings/ subdir exists
    return spike


def get_spike(conn: sqlite3.Connection, slug: str) -> dict | None:
    """Fetch a spike by slug. Returns None if not found."""
    row = conn.execute("SELECT * FROM spike WHERE slug = ?", (slug,)).fetchone()
    return _row_to_dict(row) if row else None


def list_spikes(
    conn: sqlite3.Connection,
    status: str | None = None,
    project_id: str = "default",
) -> list[dict]:
    """List spikes, optionally filtered by status.

    Args:
        status: 'open', 'closed', or None for all.
        project_id: Project scope.

    Returns:
        List of spike dicts, newest first.
    """
    if status is not None and status not in ("open", "closed"):
        raise ValueError(f"Invalid status filter: {status!r}. Must be 'open' or 'closed'.")
    if status:
        rows = conn.execute(
            "SELECT * FROM spike WHERE project_id = ? AND status = ?"
            " ORDER BY created_at DESC, id DESC",
            (project_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM spike WHERE project_id = ? ORDER BY created_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add_finding(
    slug: str,
    filename: str,
    content: str,
    project_dir: Path,
) -> Path:
    """Write a finding file into .planning/spikes/{slug}/findings/.

    Returns the written file path.
    """
    findings_dir = _spike_dir(project_dir, slug) / "findings"
    findings_dir.mkdir(parents=True, exist_ok=True)
    target = findings_dir / filename
    target.write_text(content, encoding="utf-8")
    return target


def close_spike(
    conn: sqlite3.Connection,
    slug: str,
    outcome: str,
    project_dir: Path,
) -> dict:
    """Close a spike with a recorded outcome.

    Updates DB status to 'closed', writes outcome to MANIFEST.md.

    Raises:
        ValueError: If spike not found or already closed.
    """
    spike = get_spike(conn, slug)
    if spike is None:
        raise ValueError(f"Spike not found: {slug!r}")
    if spike["status"] == "closed":
        raise ValueError(f"Spike {slug!r} is already closed")
    now = _now()
    conn.execute(
        """
        UPDATE spike
        SET status = 'closed', outcome = ?, updated_at = ?, closed_at = ?
        WHERE slug = ?
        """,
        (outcome, now, now, slug),
    )
    spike = get_spike(conn, slug)
    assert spike is not None
    _write_manifest(_spike_dir(project_dir, slug), spike)
    return spike


def wrap_up_spike(
    conn: sqlite3.Connection,
    slug: str,
    outcome: str,
    learnings: list[str],
    project_dir: Path,
    project_id: str = "default",
) -> dict:
    """Close a spike and record extracted learnings in the DB.

    Args:
        outcome: Summary of what was discovered.
        learnings: List of rule strings to add to the learning table.
        project_dir: Project root for artifact writes.

    Returns:
        Dict with spike and list of created learning ids.
    """
    spike = close_spike(conn, slug, outcome, project_dir)
    phase_id = spike.get("phase_id")
    learning_ids: list[int] = []
    for rule in learnings:
        cursor = conn.execute(
            """
            INSERT INTO learning (project_id, scope, phase_id, rule, source)
            VALUES (?, 'project', ?, ?, 'execution')
            """,
            (project_id, phase_id, rule),
        )
        learning_ids.append(cursor.lastrowid)
    return {"spike": spike, "learning_ids": learning_ids}


# ── Frontier scan ─────────────────────────────────────────────────────────────


def frontier_scan(
    conn: sqlite3.Connection,
    project_dir: Path,
    project_id: str = "default",
) -> dict:
    """Scan existing spikes and surface open questions.

    Returns:
        Dict with:
          - open_spikes: list of open spike dicts
          - closed_spikes: list of closed spike dicts
          - orphaned_dirs: spike dirs with no DB record
          - proposals: suggested next spike titles based on unanswered questions
    """
    open_spikes = list_spikes(conn, status="open", project_id=project_id)
    closed_spikes = list_spikes(conn, status="closed", project_id=project_id)

    spikes_root = project_dir / ".planning" / "spikes"
    known_slugs = {s["slug"] for s in open_spikes + closed_spikes}
    orphaned_dirs: list[str] = []
    if spikes_root.exists():
        for entry in sorted(spikes_root.iterdir()):
            if entry.is_dir() and entry.name not in known_slugs:
                orphaned_dirs.append(entry.name)

    # Derive proposals: phases that have no associated spike yet
    phases_without_spikes = conn.execute("""
        SELECT ph.id, ph.name
        FROM phase ph
        LEFT JOIN spike sp ON sp.phase_id = ph.id
        WHERE sp.id IS NULL
          AND ph.status NOT IN ('complete', 'archived')
        ORDER BY ph.sequence
        LIMIT 5
    """).fetchall()
    proposals = [
        {"phase_id": row["id"], "suggested_title": f"Explore: {row['name']}"}
        for row in phases_without_spikes
    ]

    return {
        "open_spikes": open_spikes,
        "closed_spikes": closed_spikes,
        "orphaned_dirs": orphaned_dirs,
        "proposals": proposals,
    }


# ── Gate check ────────────────────────────────────────────────────────────────


def check_spike_gate(
    conn: sqlite3.Connection,
    phase_id: int,
) -> list[dict]:
    """Return open spikes linked to phase_id that would block planning.

    An empty list means the gate is clear.
    """
    rows = conn.execute(
        "SELECT * FROM spike WHERE phase_id = ? AND status = 'open'",
        (phase_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]
