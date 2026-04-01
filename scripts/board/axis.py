"""Axis PM kanban board provider."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from scripts.board.provider import register_provider

logger = logging.getLogger(__name__)

# Axis status <-> Meridian phase status mapping
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

PM_SCRIPT = Path.home() / "zeroclaw" / "skills" / "kanban" / "pm.sh"


def _run_pm_command(args: list[str]) -> str | None:
    """Run a pm.sh command. Returns stdout or None if script missing."""
    if not PM_SCRIPT.exists():
        logger.warning("PM script not found at %s — skipping", PM_SCRIPT)
        return None
    try:
        result = subprocess.run(
            ["bash", str(PM_SCRIPT)] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.error("PM command failed: %s", e)
        return None


def _parse_ticket_id(output: str) -> str | None:
    """Parse ticket ID from pm.sh output like 'Created ticket PROJ-123'."""
    for word in output.split():
        if "-" in word and any(c.isdigit() for c in word):
            return word
    return None


class AxisProvider:
    """Axis PM kanban board integration via pm.sh shell script."""

    def create_ticket(
        self,
        project_id: str,
        name: str,
        description: str = "",
    ) -> str | None:
        output = _run_pm_command(
            ["ticket", "add", project_id, name, "--description", description]
        )
        if output is None:
            return None
        return _parse_ticket_id(output)

    def move_ticket(
        self,
        ticket_id: str,
        status: str,
    ) -> str | None:
        output = _run_pm_command(["ticket", "move", ticket_id, status])
        if output is None:
            return None
        return ticket_id


register_provider("axis", AxisProvider)
