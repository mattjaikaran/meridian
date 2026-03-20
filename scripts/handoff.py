#!/usr/bin/env python3
"""Structured session handoff — create and consume HANDOFF.json for richer resume context."""

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scripts.db import get_db_path, open_project
from scripts.state import (
    _run_git,
    compute_next_action,
    get_latest_checkpoint,
    list_decisions,
    list_phases,
    list_plans,
)

logger = logging.getLogger(__name__)

HANDOFF_FILENAME = "HANDOFF.json"


def _get_handoff_path(project_dir: str | Path) -> Path:
    """Return path to HANDOFF.json in .meridian/ directory."""
    return Path(project_dir) / ".meridian" / HANDOFF_FILENAME


def _get_active_phase_and_plans(
    conn: sqlite3.Connection, project_id: str = "default",
) -> tuple[dict | None, list[dict]]:
    """Find the active phase and its plans from DB state."""
    milestone = conn.execute(
        "SELECT * FROM milestone WHERE project_id = ? AND status = 'active'"
        " ORDER BY created_at LIMIT 1",
        (project_id,),
    ).fetchone()
    if not milestone:
        return None, []

    phases = list_phases(conn, milestone["id"])
    current_phase = next(
        (p for p in phases if p["status"] not in ("complete",)), None,
    )
    if not current_phase:
        return None, []

    plans = list_plans(conn, current_phase["id"])
    return current_phase, plans


def _get_files_modified(repo_path: str) -> list[str]:
    """Get files modified since last commit (from git diff + untracked)."""
    diff_output = _run_git(["diff", "--name-only"], repo_path, default="")
    staged_output = _run_git(["diff", "--cached", "--name-only"], repo_path, default="")
    untracked = _run_git(
        ["ls-files", "--others", "--exclude-standard"], repo_path, default="",
    )
    files: set[str] = set()
    for output in (diff_output, staged_output, untracked):
        if output:
            files.update(line.strip() for line in output.splitlines() if line.strip())
    return sorted(files)


def create_handoff(
    project_dir: str | Path,
    user_notes: str | None = None,
    project_id: str = "default",
) -> dict:
    """Create a HANDOFF.json file capturing current session context.

    Returns the handoff data dict that was written.
    """
    project_dir = Path(project_dir)
    db_path = get_db_path(project_dir)

    handoff: dict = {
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "active_phase": None,
        "active_plan": None,
        "blockers": [],
        "decisions_made": [],
        "files_modified": [],
        "next_action": None,
        "user_notes": user_notes,
    }

    if db_path.exists():
        with open_project(project_dir) as conn:
            # Active phase/plan
            phase, plans = _get_active_phase_and_plans(conn, project_id)
            if phase:
                handoff["active_phase"] = {
                    "id": phase["id"],
                    "name": phase["name"],
                    "status": phase["status"],
                    "sequence": phase["sequence"],
                }
                executing = [p for p in plans if p["status"] == "executing"]
                if executing:
                    ep = executing[0]
                    handoff["active_plan"] = {
                        "id": ep["id"],
                        "name": ep["name"],
                        "status": ep["status"],
                        "wave": ep.get("wave"),
                    }

            # Blockers from checkpoint
            checkpoint = get_latest_checkpoint(conn, project_id)
            if checkpoint and checkpoint.get("blockers"):
                try:
                    blockers = json.loads(checkpoint["blockers"])
                    if isinstance(blockers, list):
                        handoff["blockers"] = blockers
                except (json.JSONDecodeError, TypeError):
                    pass

            # Recent decisions
            decisions = list_decisions(conn, project_id, limit=5)
            handoff["decisions_made"] = [
                {"category": d["category"], "summary": d["summary"]}
                for d in decisions
            ]

            # Next action
            next_action = compute_next_action(conn, project_id)
            handoff["next_action"] = next_action.get("message")

    # Files modified (git)
    handoff["files_modified"] = _get_files_modified(str(project_dir))

    # Write HANDOFF.json
    handoff_path = _get_handoff_path(project_dir)
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff, indent=2) + "\n", encoding="utf-8")
    logger.info("Handoff created at %s", handoff_path)

    return handoff


def consume_handoff(project_dir: str | Path) -> dict | None:
    """Read and delete HANDOFF.json, returning its contents.

    Returns None if the file doesn't exist (graceful fallback).
    """
    handoff_path = _get_handoff_path(project_dir)
    if not handoff_path.exists():
        return None

    try:
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
        handoff_path.unlink()
        logger.info("Handoff consumed and deleted: %s", handoff_path)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to consume handoff: %s", exc)
        return None


def format_handoff_section(handoff: dict) -> str:
    """Format handoff data as a markdown section for the resume prompt."""
    lines: list[str] = []
    lines.append("## Session Handoff")
    lines.append(f"_Captured at: {handoff.get('created_at', 'unknown')}_")
    lines.append("")

    if handoff.get("active_phase"):
        ph = handoff["active_phase"]
        lines.append(f"- **Active Phase:** {ph.get('name', '?')} ({ph.get('status', '?')})")

    if handoff.get("active_plan"):
        pl = handoff["active_plan"]
        lines.append(f"- **Active Plan:** {pl.get('name', '?')} (wave {pl.get('wave', '?')})")

    if handoff.get("blockers"):
        lines.append("")
        lines.append("**Blockers:**")
        for b in handoff["blockers"]:
            lines.append(f"- {b}")

    if handoff.get("decisions_made"):
        lines.append("")
        lines.append("**Recent Decisions:**")
        for d in handoff["decisions_made"]:
            lines.append(f"- [{d.get('category', '?')}] {d.get('summary', '?')}")

    if handoff.get("files_modified"):
        lines.append("")
        lines.append("**Files Modified:**")
        for f in handoff["files_modified"]:
            lines.append(f"- {f}")

    if handoff.get("next_action"):
        lines.append("")
        lines.append(f"**Next Action:** {handoff['next_action']}")

    if handoff.get("user_notes"):
        lines.append("")
        lines.append(f"**User Notes:** {handoff['user_notes']}")

    return "\n".join(lines)
