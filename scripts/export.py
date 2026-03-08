#!/usr/bin/env python3
"""Export Meridian SQLite state to JSON for git tracking and Nero consumption."""

import json
from pathlib import Path

from scripts.db import connect, get_db_path
from scripts.state import (
    get_project,
    get_status,
    list_checkpoints,
    list_decisions,
    list_milestones,
    list_phases,
    list_plans,
)


def export_state(project_dir: str | Path | None = None, project_id: str = "default") -> Path:
    """Export full Meridian state to JSON file."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    db_path = get_db_path(project_dir)
    conn = connect(db_path)

    try:
        project = get_project(conn, project_id)
        if not project:
            raise ValueError("Project not initialized")

        milestones = list_milestones(conn, project_id)

        # Build full state tree
        milestone_data = []
        for ms in milestones:
            phases = list_phases(conn, ms["id"])
            phase_data = []
            for phase in phases:
                plans = list_plans(conn, phase["id"])
                phase_data.append({**phase, "plans": plans})
            milestone_data.append({**ms, "phases": phase_data})

        state = {
            "version": 1,
            "project": project,
            "milestones": milestone_data,
            "decisions": list_decisions(conn, project_id, limit=100),
            "checkpoints": list_checkpoints(conn, project_id, limit=10),
        }

        # Write JSON
        output_path = project_dir / ".meridian" / "meridian-state.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

        return output_path

    finally:
        conn.close()


def export_status_summary(
    project_dir: str | Path | None = None, project_id: str = "default"
) -> str:
    """Export a human-readable status summary."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    db_path = get_db_path(project_dir)
    conn = connect(db_path)

    try:
        status = get_status(conn, project_id)
        if "error" in status:
            return status["error"]

        lines = []
        project = status["project"]
        lines.append(f"# Meridian Status — {project['name']}")
        lines.append("")

        if status["active_milestone"]:
            ms = status["active_milestone"]
            lines.append(f"## Milestone: {ms['name']} ({ms['status']})")
            lines.append("")

        if status["phases"]:
            lines.append("### Phases")
            lines.append("| # | Phase | Status |")
            lines.append("|---|-------|--------|")
            for p in status["phases"]:
                lines.append(f"| {p['sequence']} | {p['name']} | {p['status']} |")
            lines.append("")

        if status["current_phase"]:
            cp = status["current_phase"]
            lines.append(f"### Current: Phase {cp['sequence']} — {cp['name']} ({cp['status']})")
            lines.append("")

        if status["plans"]:
            lines.append("### Plans")
            lines.append("| Wave | Plan | Status |")
            lines.append("|------|------|--------|")
            for p in status["plans"]:
                lines.append(f"| {p['wave']} | {p['name']} | {p['status']} |")
            lines.append("")

        action = status["next_action"]
        lines.append("### Next Action")
        lines.append(f"→ {action['message']}")

        return "\n".join(lines)

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else None

    if "--summary" in sys.argv:
        print(export_status_summary(project_dir))
    else:
        path = export_state(project_dir)
        print(f"State exported to {path}")
