"""Board sync — bridge between Meridian state and board providers."""

from __future__ import annotations

import logging
import sqlite3

from scripts.board.provider import get_provider

# Import axis to trigger its register_provider call
import scripts.board.axis  # noqa: F401

logger = logging.getLogger(__name__)

# Meridian status → generic board status
STATUS_MAP = {
    "planned": "backlog",
    "context_gathered": "backlog",
    "planned_out": "todo",
    "executing": "in_progress",
    "verifying": "in_progress",
    "reviewing": "in_review",
    "complete": "done",
    "blocked": "blocked",
}


def sync_phase(
    conn: sqlite3.Connection,
    phase_id: int,
    project_id: str = "default",
) -> dict:
    """Sync a single phase's status to its board ticket."""
    from scripts.state import get_phase, get_project, get_setting

    project = get_project(conn, project_id)
    if not project or not project.get("board_project_id"):
        return {"status": "skipped", "message": "No board project configured"}

    provider_name = get_setting(conn, "board_provider", project_id=project_id)
    if not provider_name:
        return {"status": "skipped", "message": "No board_provider setting"}

    phase = get_phase(conn, phase_id)
    if not phase or not phase.get("board_ticket_id"):
        return {"status": "skipped", "message": "Phase has no board ticket"}

    provider = get_provider(provider_name)
    board_status = STATUS_MAP.get(phase["status"], "backlog")

    try:
        provider.move_ticket(phase["board_ticket_id"], board_status)
        return {
            "status": "synced",
            "ticket": phase["board_ticket_id"],
            "board_status": board_status,
        }
    except Exception as e:
        logger.error("Board sync failed for phase %d: %s", phase_id, e)
        return {"status": "error", "error": str(e)}


def create_tickets_for_phases(
    conn: sqlite3.Connection,
    milestone_id: str,
    project_id: str = "default",
) -> list[dict]:
    """Create board tickets for phases that don't have them yet."""
    from scripts.state import get_project, get_setting, list_phases, update_phase

    project = get_project(conn, project_id)
    if not project or not project.get("board_project_id"):
        return [{"status": "skipped", "message": "No board project configured"}]

    provider_name = get_setting(conn, "board_provider", project_id=project_id)
    if not provider_name:
        return [{"status": "skipped", "message": "No board_provider setting"}]

    provider = get_provider(provider_name)
    board_project = project["board_project_id"]
    phases = list_phases(conn, milestone_id)
    created = []

    for phase in phases:
        if phase.get("board_ticket_id"):
            continue

        try:
            ticket_id = provider.create_ticket(
                board_project, phase["name"], phase.get("description", "")
            )
            if ticket_id:
                update_phase(conn, phase["id"], board_ticket_id=ticket_id)
                created.append({"phase": phase["name"], "ticket_id": ticket_id})
            else:
                created.append({"phase": phase["name"], "error": "Provider returned None"})
        except Exception as e:
            logger.error("Ticket creation failed for phase %s: %s", phase["name"], e)
            created.append({"phase": phase["name"], "error": str(e)})

    return created
