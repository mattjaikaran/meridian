#!/usr/bin/env python3
"""Meridian sketch workflow — multi-variant HTML mockup generation and selection."""

import json
import shutil
import sqlite3
from pathlib import Path

from scripts.utils import now_iso as _now, row_to_dict as _row_to_dict, sanitize_slug as _sanitize_slug

VARIANT_NAMES = ["variant-a", "variant-b", "variant-c"]


def _sketch_dir(project_dir: Path, slug: str) -> Path:
    return project_dir / ".planning" / "sketches" / slug


def _write_manifest(sketch_dir: Path, sketch: dict) -> None:
    sketch_dir.mkdir(parents=True, exist_ok=True)
    phase_line = f"Phase: {sketch['phase_id']}" if sketch.get("phase_id") else "Phase: (none)"
    variants = _parse_variants(sketch.get("variants"))
    winner = sketch.get("winner_variant") or ""

    variant_lines = ""
    for v in variants:
        marker = " ← winner" if v == winner else ""
        variant_lines += f"- `{v}.html`{marker}\n"
    if not variant_lines:
        variant_lines = "- (no variants yet)\n"

    winner_section = f"\n## Winner\n\n`{winner}.html`\n" if winner else ""

    content = (
        f"# Sketch: {sketch['title']}\n\n"
        f"**Status:** {sketch['status']}  \n"
        f"**{phase_line}**  \n"
        f"**Created:** {sketch['created_at']}  \n"
        f"**Updated:** {sketch['updated_at']}\n\n"
        f"## Description\n\n{sketch.get('description') or '(none)'}\n\n"
        f"## Variants\n\n{variant_lines}"
        f"{winner_section}"
    )
    (sketch_dir / "MANIFEST.md").write_text(content, encoding="utf-8")


def _parse_variants(raw: str | list | None) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return []


# ── CRUD ──────────────────────────────────────────────────────────────────────


def create_sketch(
    conn: sqlite3.Connection,
    title: str,
    description: str,
    project_dir: Path,
    project_id: str = "default",
    phase_id: int | None = None,
    slug: str | None = None,
) -> dict:
    """Create a new sketch session and write .planning/sketches/{slug}/MANIFEST.md."""
    if slug is None:
        slug = _sanitize_slug(title)
    now = _now()
    conn.execute(
        """
        INSERT INTO sketch (project_id, slug, title, description, status, phase_id,
                            variants, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'open', ?, '[]', ?, ?)
        """,
        (project_id, slug, title, description, phase_id, now, now),
    )
    sketch = get_sketch(conn, slug)
    assert sketch is not None
    sketch_dir = _sketch_dir(project_dir, slug)
    sketch_dir.mkdir(parents=True, exist_ok=True)
    (sketch_dir / "archived").mkdir(exist_ok=True)
    _write_manifest(sketch_dir, sketch)
    return sketch


def get_sketch(conn: sqlite3.Connection, slug: str) -> dict | None:
    row = conn.execute("SELECT * FROM sketch WHERE slug = ?", (slug,)).fetchone()
    return _row_to_dict(row) if row else None


def list_sketches(
    conn: sqlite3.Connection,
    status: str | None = None,
    project_id: str = "default",
) -> list[dict]:
    if status is not None and status not in ("open", "closed"):
        raise ValueError(f"Invalid status filter: {status!r}. Must be 'open' or 'closed'.")
    if status:
        rows = conn.execute(
            "SELECT * FROM sketch WHERE project_id = ? AND status = ?"
            " ORDER BY created_at DESC, id DESC",
            (project_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sketch WHERE project_id = ? ORDER BY created_at DESC, id DESC",
            (project_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def add_variant(
    conn: sqlite3.Connection,
    slug: str,
    variant_name: str,
    html_content: str,
    project_dir: Path,
) -> Path:
    """Write a variant HTML file into .planning/sketches/{slug}/."""
    sketch = get_sketch(conn, slug)
    if sketch is None:
        raise ValueError(f"Sketch not found: {slug!r}")
    if sketch["status"] == "closed":
        raise ValueError(f"Sketch {slug!r} is already closed")

    sketch_dir = _sketch_dir(project_dir, slug)
    sketch_dir.mkdir(parents=True, exist_ok=True)
    target = sketch_dir / f"{variant_name}.html"
    target.write_text(html_content, encoding="utf-8")

    variants = _parse_variants(sketch.get("variants"))
    if variant_name not in variants:
        variants.append(variant_name)
    now = _now()
    conn.execute(
        "UPDATE sketch SET variants = ?, updated_at = ? WHERE slug = ?",
        (json.dumps(variants), now, slug),
    )
    sketch = get_sketch(conn, slug)
    assert sketch is not None
    _write_manifest(sketch_dir, sketch)
    return target


def wrap_up_sketch(
    conn: sqlite3.Connection,
    slug: str,
    winner_variant: str,
    project_dir: Path,
    ui_phase_id: int | None = None,
) -> dict:
    """Pick a winner variant, archive losers, and close the sketch.

    Moves all non-winner HTML files to .planning/sketches/{slug}/archived/.
    Updates DB with winner_variant, ui_phase_id, status=closed, closed_at.
    """
    sketch = get_sketch(conn, slug)
    if sketch is None:
        raise ValueError(f"Sketch not found: {slug!r}")
    if sketch["status"] == "closed":
        raise ValueError(f"Sketch {slug!r} is already closed")

    sketch_dir = _sketch_dir(project_dir, slug)
    archived_dir = sketch_dir / "archived"
    archived_dir.mkdir(parents=True, exist_ok=True)

    variants = _parse_variants(sketch.get("variants"))
    archived: list[str] = []
    for v in variants:
        if v != winner_variant:
            src = sketch_dir / f"{v}.html"
            if src.exists():
                dst = archived_dir / f"{v}.html"
                shutil.move(str(src), str(dst))
                archived.append(v)

    now = _now()
    conn.execute(
        """
        UPDATE sketch
        SET status = 'closed', winner_variant = ?, ui_phase_id = ?,
            updated_at = ?, closed_at = ?
        WHERE slug = ?
        """,
        (winner_variant, ui_phase_id, now, now, slug),
    )
    sketch = get_sketch(conn, slug)
    assert sketch is not None
    _write_manifest(sketch_dir, sketch)
    return {"sketch": sketch, "winner": winner_variant, "archived": archived}


# ── Gate check ────────────────────────────────────────────────────────────────


def check_sketch_gate(conn: sqlite3.Connection, phase_id: int) -> list[dict]:
    """Return open sketches linked to phase_id that would block UI phase start."""
    rows = conn.execute(
        "SELECT * FROM sketch WHERE phase_id = ? AND status = 'open'",
        (phase_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── CLI helper ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    from scripts.db import connect, get_db_path

    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    conn = connect(get_db_path("."))
    if action == "list":
        sketches = list_sketches(conn)
        print(json.dumps(sketches, indent=2))
    elif action == "status" and len(sys.argv) > 2:
        s = get_sketch(conn, sys.argv[2])
        print(json.dumps(s, indent=2))
    conn.close()
