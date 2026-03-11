#!/usr/bin/env python3
"""Export Meridian SQLite state to JSON for git tracking and Nero consumption."""

import json
from collections import defaultdict
from pathlib import Path

from scripts.db import open_project
from scripts.state import (
    get_project,
    get_status,
    list_checkpoints,
    list_decisions,
    list_milestones,
    list_phases,
)


def export_state(project_dir: str | Path | None = None, project_id: str = "default") -> Path:
    """Export full Meridian state to JSON file."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn, project_id)
        if not project:
            raise ValueError("Project not initialized")

        milestones = list_milestones(conn, project_id)

        # Bulk fetch all plans to avoid N+1 queries
        all_plan_rows = conn.execute(
            """SELECT p.*, ph.milestone_id FROM plan p
            JOIN phase ph ON p.phase_id = ph.id
            WHERE ph.milestone_id IN (SELECT id FROM milestone WHERE project_id = ?)""",
            (project_id,),
        ).fetchall()
        plans_by_phase: dict[str, list[dict]] = defaultdict(list)
        for plan in all_plan_rows:
            plans_by_phase[plan["phase_id"]].append(dict(plan))

        # Build full state tree
        milestone_data = []
        for ms in milestones:
            phases = list_phases(conn, ms["id"])
            phase_data = []
            for phase in phases:
                plans = plans_by_phase.get(phase["id"], [])
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


def export_status_summary(
    project_dir: str | Path | None = None, project_id: str = "default"
) -> str:
    """Export a human-readable status summary."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
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


if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else None

    if "--summary" in sys.argv:
        print(export_status_summary(project_dir))
    else:
        path = export_state(project_dir)
        print(f"State exported to {path}")
