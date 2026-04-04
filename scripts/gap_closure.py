#!/usr/bin/env python3
"""Meridian gap closure — find and retry failed/skipped plans in a phase."""

import logging
import sqlite3

from scripts.db import retry_on_busy
from scripts.state import (
    _log_event,
    get_phase,
    list_phases,
    list_plans,
    transition_plan,
)

logger = logging.getLogger(__name__)

_GAP_STATUSES = ("failed", "skipped")


def find_gaps(conn: sqlite3.Connection, phase_id: int) -> list[dict]:
    """Query plans for the given phase where status is failed or skipped."""
    plans = list_plans(conn, phase_id)
    return [p for p in plans if p.get("status") in _GAP_STATUSES]


def find_gaps_in_milestone(conn: sqlite3.Connection, milestone_id: int) -> list[dict]:
    """Across all phases in milestone, find failed/skipped plans grouped by phase."""
    phases = list_phases(conn, milestone_id)
    result: list[dict] = []
    for phase in phases:
        gaps = find_gaps(conn, phase["id"])
        if gaps:
            result.append({"phase": phase, "gaps": gaps})
    return result


@retry_on_busy()
def prepare_gap_execution(conn: sqlite3.Connection, phase_id: int) -> dict:
    """Find gaps and reset failed plans to pending, respecting wave ordering.

    Plans in wave N+1 are not reset if wave N still has gaps.
    """
    gaps = find_gaps(conn, phase_id)
    if not gaps:
        return {
            "phase_id": phase_id,
            "reset_count": 0,
            "plans": [],
            "waves": [],
        }

    waves_with_gaps: dict[int, list[dict]] = {}
    for plan in gaps:
        wave = plan.get("wave", 1) or 1
        waves_with_gaps.setdefault(wave, []).append(plan)

    sorted_waves = sorted(waves_with_gaps.keys())
    reset_plans: list[dict] = []
    reset_waves: list[int] = []

    for wave in sorted_waves:
        wave_plans = waves_with_gaps[wave]
        resettable = [p for p in wave_plans if p["status"] == "failed"]
        if not resettable:
            # Wave has only skipped plans — block higher waves
            logger.info(
                "Wave %d has skipped (non-resettable) plans, blocking higher waves",
                wave,
            )
            break
        for plan in resettable:
            transition_plan(conn, plan["id"], "pending")
            logger.info(
                "Reset plan %d (%s) from failed to pending",
                plan["id"],
                plan.get("name", "unnamed"),
            )
            reset_plans.append(plan)
        reset_waves.append(wave)

    return {
        "phase_id": phase_id,
        "reset_count": len(reset_plans),
        "plans": reset_plans,
        "waves": reset_waves,
    }


def execute_gaps_only(
    conn: sqlite3.Connection,
    phase_id: int,
    project_id: str = "default",
) -> dict:
    """Find gaps, reset to pending, and return execution plan.

    Skips phases with no gaps.
    """
    gaps = find_gaps(conn, phase_id)
    if not gaps:
        return {
            "phase_id": phase_id,
            "has_gaps": False,
            "gap_count": 0,
            "plans_to_retry": [],
            "message": f"Phase {phase_id} has no gaps",
        }

    result = prepare_gap_execution(conn, phase_id)
    plans_to_retry = list_plans(conn, phase_id)
    plans_to_retry = [p for p in plans_to_retry if p["status"] == "pending"]

    _log_event(
        conn,
        "phase",
        phase_id,
        None,
        "gap_closure",
        metadata={
            "project_id": project_id,
            "gap_count": len(gaps),
            "reset_count": result["reset_count"],
        },
    )
    conn.commit()

    return {
        "phase_id": phase_id,
        "has_gaps": True,
        "gap_count": len(gaps),
        "plans_to_retry": plans_to_retry,
        "message": (
            f"Phase {phase_id}: {result['reset_count']} plans reset across waves {result['waves']}"
        ),
    }
