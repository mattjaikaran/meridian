#!/usr/bin/env python3
"""Axis PM ticket sync — sync Meridian phases with Axis kanban board."""

import json
import sqlite3
import subprocess
from pathlib import Path

from scripts.db import open_project
from scripts.state import get_project, list_phases, update_phase

# Axis status ↔ Meridian phase status mapping
MERIDIAN_TO_AXIS = {
    "planned": "backlog",
    "context_gathered": "backlog",
    "planned_out": "todo",
    "executing": "in_progress",
    "verifying": "in_progress",
    "reviewing": "in_review",
    "complete": "done",
    "blocked": "blocked",
}

AXIS_TO_MERIDIAN = {
    "created": "planned",
    "backlog": "planned",
    "ready": "planned_out",
    "todo": "planned_out",
    "in_progress": "executing",
    "in_review": "reviewing",
    "done": "complete",
    "blocked": "blocked",
}


def _run_pm_command(args: list[str]) -> str:
    """Run a pm.sh command and return output.

    Args are passed as a list to avoid shell splitting issues with spaces.

    Raises:
        FileNotFoundError: If pm.sh script is not found.
        subprocess.SubprocessError: If the command fails or times out.
    """
    pm_script = Path.home() / "zeroclaw" / "skills" / "kanban" / "pm.sh"
    if not pm_script.exists():
        raise FileNotFoundError(f"PM script not found at {pm_script}")
    result = subprocess.run(
        ["bash", str(pm_script)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()


def sync_phase_to_axis(
    project_dir: str | Path | None = None,
    phase_id: int | None = None,
    project_id: str = "default",
) -> dict:
    """Sync a Meridian phase status to its Axis ticket."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn, project_id)
        if not project or not project.get("axis_project_id"):
            return {"status": "skipped", "message": "No Axis project configured"}

        phases = list_phases(conn, _get_active_milestone_id(conn, project_id))

        synced = []
        for phase in phases:
            if phase_id and phase["id"] != phase_id:
                continue
            if not phase.get("axis_ticket_id"):
                continue

            axis_status = MERIDIAN_TO_AXIS.get(phase["status"], "backlog")
            ticket_id = phase["axis_ticket_id"]

            try:
                _run_pm_command(["ticket", "move", ticket_id, axis_status])
                synced.append(
                    {
                        "phase": phase["name"],
                        "ticket": ticket_id,
                        "status": axis_status,
                    }
                )
            except (OSError, subprocess.SubprocessError) as e:
                synced.append(
                    {
                        "phase": phase["name"],
                        "ticket": ticket_id,
                        "error": str(e),
                    }
                )

        return {"status": "synced", "results": synced}


def create_axis_tickets_for_phases(
    project_dir: str | Path | None = None,
    milestone_id: str | None = None,
    project_id: str = "default",
) -> list[dict]:
    """Create Axis tickets for phases that don't have them yet."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn, project_id)
        if not project or not project.get("axis_project_id"):
            return [{"status": "skipped", "message": "No Axis project configured"}]

        if not milestone_id:
            milestone_id = _get_active_milestone_id(conn, project_id)

        phases = list_phases(conn, milestone_id)
        created = []

        for phase in phases:
            if phase.get("axis_ticket_id"):
                continue  # Already has a ticket

            axis_project = project["axis_project_id"]
            try:
                output = _run_pm_command(
                    ["ticket", "add", axis_project, phase["name"],
                     "--description", phase.get("description", "")]
                )
                # Parse ticket ID from output (format: "Created ticket PROJ-123")
                ticket_id = None
                for word in output.split():
                    if "-" in word and any(c.isdigit() for c in word):
                        ticket_id = word
                        break

                if ticket_id:
                    update_phase(conn, phase["id"], axis_ticket_id=ticket_id)
                    created.append({"phase": phase["name"], "ticket_id": ticket_id})
                else:
                    created.append(
                        {
                            "phase": phase["name"],
                            "error": f"Could not parse ticket ID from: {output}",
                        }
                    )
            except (OSError, subprocess.SubprocessError) as e:
                created.append({"phase": phase["name"], "error": str(e)})

        return created


def _get_active_milestone_id(conn: sqlite3.Connection, project_id: str) -> str | None:
    row = conn.execute(
        "SELECT id FROM milestone WHERE project_id = ? AND status = 'active'"
        " ORDER BY created_at LIMIT 1",
        (project_id,),
    ).fetchone()
    return row["id"] if row else None


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python axis_sync.py <sync|create-tickets> [project_dir]")
        sys.exit(1)

    cmd = sys.argv[1]
    project_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "sync":
        result = sync_phase_to_axis(project_dir)
        print(json.dumps(result, indent=2, default=str))
    elif cmd == "create-tickets":
        results = create_axis_tickets_for_phases(project_dir)
        print(json.dumps(results, indent=2, default=str))
