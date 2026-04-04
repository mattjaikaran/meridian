#!/usr/bin/env python3
"""Milestone lifecycle management — audit, complete, archive, and summarize."""

import logging
import sqlite3
from datetime import UTC, datetime

from scripts.db import retry_on_busy
from scripts.state import (
    get_milestone,
    list_decisions,
    list_phases,
    list_plans,
    transition_milestone,
)

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def audit_milestone(conn: sqlite3.Connection, milestone_id: str) -> dict:
    """Check milestone readiness: all phases complete, no failed/skipped plans."""
    milestone = get_milestone(conn, milestone_id)
    if not milestone:
        raise ValueError(f"Milestone {milestone_id} not found")

    phases = list_phases(conn, milestone_id)
    issues: list[str] = []

    total_plans = 0
    complete_plans = 0
    failed_plans = 0
    complete_phases = 0

    for phase in phases:
        if phase["status"] == "complete":
            complete_phases += 1
        else:
            issues.append(
                f"Phase '{phase['name']}' (id={phase['id']}) "
                f"status is '{phase['status']}', expected 'complete'"
            )

        plans = list_plans(conn, phase["id"])
        for plan in plans:
            total_plans += 1
            if plan["status"] == "complete":
                complete_plans += 1
            elif plan["status"] == "failed":
                failed_plans += 1
                issues.append(
                    f"Plan '{plan['name']}' (id={plan['id']}) "
                    f"in phase '{phase['name']}' has status 'failed'"
                )
            elif plan["status"] == "skipped":
                issues.append(
                    f"Plan '{plan['name']}' (id={plan['id']}) "
                    f"in phase '{phase['name']}' has status 'skipped'"
                )
            else:
                issues.append(
                    f"Plan '{plan['name']}' (id={plan['id']}) "
                    f"in phase '{phase['name']}' has status "
                    f"'{plan['status']}', expected 'complete'"
                )

    ready = len(issues) == 0

    logger.info(
        "Milestone %s audit: ready=%s, issues=%d",
        milestone_id,
        ready,
        len(issues),
    )

    return {
        "milestone_id": milestone_id,
        "ready": ready,
        "issues": issues,
        "stats": {
            "total_phases": len(phases),
            "complete_phases": complete_phases,
            "total_plans": total_plans,
            "complete_plans": complete_plans,
            "failed_plans": failed_plans,
        },
    }


@retry_on_busy()
def complete_milestone(conn: sqlite3.Connection, milestone_id: str) -> dict:
    """Validate all phases complete and transition milestone to complete."""
    audit = audit_milestone(conn, milestone_id)
    if not audit["ready"]:
        raise ValueError(
            f"Milestone {milestone_id} not ready for completion: " + "; ".join(audit["issues"][:5])
        )

    milestone = get_milestone(conn, milestone_id)
    transition_milestone(conn, milestone_id, "complete")

    completed = get_milestone(conn, milestone_id)
    created = _parse_iso(milestone["created_at"])
    finished = _parse_iso(completed["completed_at"])
    duration_days = (finished - created).days if created and finished else 0

    git_tag = f"milestone/{milestone_id}"

    summary = {
        "phases_count": audit["stats"]["total_phases"],
        "plans_count": audit["stats"]["total_plans"],
        "duration_days": duration_days,
        "completion_date": completed["completed_at"],
    }

    logger.info(
        "Milestone %s completed: %d phases, %d plans, %d days",
        milestone_id,
        summary["phases_count"],
        summary["plans_count"],
        summary["duration_days"],
    )

    return {
        "milestone_id": milestone_id,
        "status": "complete",
        "summary": summary,
        "git_tag": git_tag,
    }


@retry_on_busy()
def archive_milestone(conn: sqlite3.Connection, milestone_id: str) -> dict:
    """Transition a completed milestone to archived status."""
    transition_milestone(conn, milestone_id, "archived")

    logger.info("Milestone %s archived", milestone_id)

    return {
        "milestone_id": milestone_id,
        "status": "archived",
    }


def generate_milestone_summary(conn: sqlite3.Connection, milestone_id: str) -> str:
    """Generate a markdown summary of the milestone."""
    milestone = get_milestone(conn, milestone_id)
    if not milestone:
        raise ValueError(f"Milestone {milestone_id} not found")

    phases = list_phases(conn, milestone_id)

    created = _parse_iso(milestone["created_at"])
    completed = _parse_iso(milestone.get("completed_at"))
    duration_days = (completed - created).days if created and completed else None

    lines: list[str] = []
    lines.append(f"# Milestone: {milestone['name']}")
    lines.append("")
    if milestone.get("description"):
        lines.append(milestone["description"])
        lines.append("")
    lines.append(f"**Status:** {milestone['status']}")
    lines.append(f"**Created:** {milestone['created_at']}")
    if milestone.get("completed_at"):
        lines.append(f"**Completed:** {milestone['completed_at']}")
    if duration_days is not None:
        lines.append(f"**Duration:** {duration_days} days")
    lines.append("")

    lines.append("## Phases")
    lines.append("")

    total_plans = 0
    for phase in phases:
        plans = list_plans(conn, phase["id"])
        total_plans += len(plans)
        complete = sum(1 for p in plans if p["status"] == "complete")
        lines.append(f"### {phase['sequence']}. {phase['name']} [{phase['status']}]")
        lines.append("")
        if phase.get("description"):
            lines.append(phase["description"])
            lines.append("")
        lines.append(f"- Plans: {complete}/{len(plans)} complete")
        lines.append("")

        if plans:
            lines.append("| Plan | Status | Wave |")
            lines.append("|------|--------|------|")
            for plan in plans:
                lines.append(f"| {plan['name']} | {plan['status']} | {plan.get('wave', '-')} |")
            lines.append("")

    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"- **Phases:** {len(phases)}")
    lines.append(f"- **Plans:** {total_plans}")
    if duration_days is not None:
        lines.append(f"- **Duration:** {duration_days} days")
    lines.append("")

    # Key decisions
    decisions = list_decisions(conn, phase_id=None, limit=50)
    milestone_phase_ids = {p["id"] for p in phases}
    relevant = [d for d in decisions if d.get("phase_id") in milestone_phase_ids]

    if relevant:
        lines.append("## Key Decisions")
        lines.append("")
        for d in relevant:
            lines.append(
                f"- **{d.get('title', 'Untitled')}**: {d.get('summary', d.get('rationale', ''))}"
            )
        lines.append("")

    return "\n".join(lines)
