"""CLI-based kanban board provider.

Syncs Meridian phase status to any board tool that has a CLI.
Configure via environment variables:

    BOARD_PM_SCRIPT   — path to your board CLI script (default: ~/bin/pm.sh)

The script must support these subcommands:
    <script> ticket add <project_id> <name> --description <desc>
    <script> ticket move <ticket_id> <status>

The 'add' command must print a ticket ID (e.g. "Created ticket PROJ-123").
The 'move' command can print anything (stdout is ignored).

Status mapping (Meridian → board) is built-in and covers common
Linear/Jira/kanban column names. Override MERIDIAN_TO_BOARD or
subclass CliProvider to customize.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from scripts.board.provider import register_provider

logger = logging.getLogger(__name__)

# Meridian phase status → generic board column mapping
# Works with Linear, Jira, or any kanban tool using standard column names
MERIDIAN_TO_BOARD = {
    "planned": "backlog",
    "context_gathered": "backlog",
    "planned_out": "todo",
    "executing": "in_progress",
    "verifying": "in_progress",
    "reviewing": "in_review",
    "complete": "done",
    "blocked": "blocked",
}

BOARD_TO_MERIDIAN = {
    "created": "planned",
    "backlog": "planned",
    "ready": "planned_out",
    "todo": "planned_out",
    "in_progress": "executing",
    "in_review": "reviewing",
    "done": "complete",
    "blocked": "blocked",
}

# Path to board CLI script — set BOARD_PM_SCRIPT env var to override
PM_SCRIPT = Path(os.environ.get("BOARD_PM_SCRIPT", str(Path.home() / "bin" / "pm.sh")))


def _run_pm_command(args: list[str]) -> str | None:
    """Run a board CLI command. Returns stdout or None if script missing."""
    if not PM_SCRIPT.exists():
        logger.warning("Board CLI script not found at %s — skipping", PM_SCRIPT)
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
        logger.error("Board CLI command failed: %s", e)
        return None


def _parse_ticket_id(output: str) -> str | None:
    """Parse ticket ID from CLI output like 'Created ticket PROJ-123'."""
    for word in output.split():
        if "-" in word and any(c.isdigit() for c in word):
            return word
    return None


class CliProvider:
    """CLI-based kanban board integration via a shell script.

    Set BOARD_PM_SCRIPT env var to point to your board's CLI tool.
    The script must support `ticket add` and `ticket move` subcommands.
    """

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


# Register as "cli" (primary) and "axis" (backward compat alias)
register_provider("cli", CliProvider)
register_provider("axis", CliProvider)
