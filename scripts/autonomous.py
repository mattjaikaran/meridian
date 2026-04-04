#!/usr/bin/env python3
"""Autonomous run planning — determine phase ranges and next steps for unattended execution."""

import logging
import sqlite3

from scripts.db import retry_on_busy
from scripts.state import get_milestone, get_phase, list_phases

logger = logging.getLogger(__name__)

# Maps phase status to the autonomous step that should run next
_STATUS_TO_STEP: dict[str, str] = {
    "planned": "discuss",
    "context_gathered": "plan",
    "planned_out": "execute",
    "executing": "execute",
    "verifying": "verify",
    "reviewing": "complete",
    "complete": "complete",
}


def validate_autonomous_range(
    conn: sqlite3.Connection,
    milestone_id: str,
    from_phase: int | None,
    to_phase: int | None,
    only_phase: int | None,
) -> dict:
    """Validate phase range constraints against actual milestone phases.

    Returns {"valid": bool, "phases": list[dict], "error": str | None}.
    """
    milestone = get_milestone(conn, milestone_id)
    if not milestone:
        return {
            "valid": False,
            "phases": [],
            "error": f"Milestone {milestone_id!r} not found",
        }

    phases = list_phases(conn, milestone_id)
    if not phases:
        return {
            "valid": False,
            "phases": [],
            "error": f"No phases found for milestone {milestone_id!r}",
        }

    phase_ids = {p["id"] for p in phases}

    if only_phase is not None:
        if only_phase not in phase_ids:
            return {
                "valid": False,
                "phases": [],
                "error": (f"Phase {only_phase} not in milestone {milestone_id!r}"),
            }
        return {
            "valid": True,
            "phases": [p for p in phases if p["id"] == only_phase],
            "error": None,
        }

    if from_phase is not None and from_phase not in phase_ids:
        return {
            "valid": False,
            "phases": [],
            "error": (f"from_phase {from_phase} not in milestone {milestone_id!r}"),
        }

    if to_phase is not None and to_phase not in phase_ids:
        return {
            "valid": False,
            "phases": [],
            "error": (f"to_phase {to_phase} not in milestone {milestone_id!r}"),
        }

    filtered = phases
    if from_phase is not None:
        filtered = [p for p in filtered if p["sequence"] >= _seq(phases, from_phase)]
    if to_phase is not None:
        filtered = [p for p in filtered if p["sequence"] <= _seq(phases, to_phase)]

    return {"valid": True, "phases": filtered, "error": None}


def _seq(phases: list[dict], phase_id: int) -> int:
    """Look up sequence number for a phase id."""
    for p in phases:
        if p["id"] == phase_id:
            return p["sequence"]
    return 0


@retry_on_busy()
def get_autonomous_step(
    conn: sqlite3.Connection,
    phase_id: int,
) -> dict:
    """Determine the next autonomous step for a phase.

    Returns {"phase_id": int, "phase_name": str, "step": str, "status": str}.
    """
    phase = get_phase(conn, phase_id)
    if not phase:
        raise ValueError(f"Phase {phase_id} not found")

    status = phase["status"]
    step = _STATUS_TO_STEP.get(status)
    if step is None:
        logger.warning(
            "Phase %d has unmapped status %r, defaulting to discuss",
            phase_id,
            status,
        )
        step = "discuss"

    return {
        "phase_id": phase["id"],
        "phase_name": phase["name"],
        "step": step,
        "status": status,
    }


@retry_on_busy()
def plan_autonomous_run(
    conn: sqlite3.Connection,
    milestone_id: str,
    project_id: str = "default",
    from_phase: int | None = None,
    to_phase: int | None = None,
    only_phase: int | None = None,
) -> dict:
    """Plan an autonomous run across milestone phases.

    Determines which phases need discuss->plan->execute, filters by
    range constraints, and skips already-complete phases.

    Returns {"phases": list[dict], "total": int, "skipped": int, "message": str}.
    """
    validation = validate_autonomous_range(conn, milestone_id, from_phase, to_phase, only_phase)
    if not validation["valid"]:
        return {
            "phases": [],
            "total": 0,
            "skipped": 0,
            "message": validation["error"] or "Validation failed",
        }

    all_phases = validation["phases"]
    skipped = 0
    actionable: list[dict] = []

    for phase in all_phases:
        if phase["status"] == "complete":
            skipped += 1
            logger.debug(
                "Skipping complete phase %d (%s)",
                phase["id"],
                phase["name"],
            )
            continue

        step_info = get_autonomous_step(conn, phase["id"])
        actionable.append(
            {
                "phase_id": phase["id"],
                "phase_name": phase["name"],
                "sequence": phase["sequence"],
                "current_status": phase["status"],
                "next_step": step_info["step"],
            }
        )

    total = len(all_phases)
    active = len(actionable)

    if active == 0:
        message = f"All {total} phases already complete"
    else:
        message = f"{active} phase(s) to process, {skipped} skipped (complete)"

    return {
        "phases": actionable,
        "total": total,
        "skipped": skipped,
        "message": message,
    }
