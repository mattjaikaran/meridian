#!/usr/bin/env python3
"""Milestone lifecycle management — audit, complete, archive, and summarize."""

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scripts.audit import collect_verification_debt
from scripts.db import retry_on_busy
from scripts.gates import detect_stubs
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


def _check_uat_debt(planning_dir: Path) -> list[str]:
    """Return issue strings for any outstanding UAT verification debt."""
    issues: list[str] = []
    try:
        debt_phases = collect_verification_debt(planning_dir)
        for phase in debt_phases:
            if not phase["has_debt"]:
                continue
            items = phase["unchecked_signoff"] + [
                h["item"] for h in phase["pending_human"]
            ]
            for item in items:
                issues.append(
                    f"UAT debt in {phase['phase_name']}: {item[:80]}"
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("UAT debt check failed: %s", exc)
    return issues


def _check_stubs(repo_path: Path) -> list[str]:
    """Return issue strings for any stub/placeholder patterns in scripts/."""
    issues: list[str] = []
    try:
        scripts_dir = repo_path / "scripts"
        if not scripts_dir.is_dir():
            return issues
        py_files = list(scripts_dir.glob("*.py"))
        findings = detect_stubs(py_files)
        for f in findings:
            issues.append(
                f"Stub in {Path(f['file']).name}:{f['line']} — {f['context'][:60]}"
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Stub detection failed: %s", exc)
    return issues


def audit_milestone(
    conn: sqlite3.Connection,
    milestone_id: str,
    *,
    repo_path: Path | str | None = None,
    planning_dir: Path | str | None = None,
    check_uat: bool = True,
    check_stubs: bool = True,
) -> dict:
    """Check milestone readiness.

    Verifies:
    - All phases are complete
    - No failed or skipped plans
    - No outstanding UAT verification debt (optional)
    - No stub/placeholder code in scripts/ (optional)
    """
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

    uat_issues: list[str] = []
    stub_issues: list[str] = []

    if check_uat:
        pdir = Path(planning_dir) if planning_dir else Path(".planning")
        uat_issues = _check_uat_debt(pdir)
        issues.extend(uat_issues)

    if check_stubs:
        rpath = Path(repo_path) if repo_path else Path(".")
        stub_issues = _check_stubs(rpath)
        issues.extend(stub_issues)

    ready = len(issues) == 0

    logger.info(
        "Milestone %s audit: ready=%s, issues=%d (uat=%d, stubs=%d)",
        milestone_id,
        ready,
        len(issues),
        len(uat_issues),
        len(stub_issues),
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
            "uat_issues": len(uat_issues),
            "stub_issues": len(stub_issues),
        },
    }


def persist_milestone_summary(
    conn: sqlite3.Connection,
    milestone_id: str,
    planning_dir: Path | str = ".planning",
) -> Path:
    """Write milestone summary markdown to .planning/milestones/."""
    planning_path = Path(planning_dir)
    milestones_dir = planning_path / "milestones"
    milestones_dir.mkdir(parents=True, exist_ok=True)

    summary_md = generate_milestone_summary(conn, milestone_id)
    out_path = milestones_dir / f"{milestone_id}-SUMMARY.md"
    out_path.write_text(summary_md, encoding="utf-8")

    logger.info("Milestone %s summary written to %s", milestone_id, out_path)
    return out_path


@retry_on_busy()
def complete_milestone(
    conn: sqlite3.Connection,
    milestone_id: str,
    *,
    repo_path: Path | str | None = None,
    planning_dir: Path | str | None = None,
    check_uat: bool = True,
    check_stubs: bool = True,
    persist_summary: bool = True,
) -> dict:
    """Validate all phases complete and transition milestone to complete.

    Returns a dict with milestone_id, status, summary stats, git_tag name,
    and the path where the summary was persisted (if persist_summary=True).
    """
    audit = audit_milestone(
        conn,
        milestone_id,
        repo_path=repo_path,
        planning_dir=planning_dir,
        check_uat=check_uat,
        check_stubs=check_stubs,
    )
    if not audit["ready"]:
        raise ValueError(
            f"Milestone {milestone_id} not ready for completion: "
            + "; ".join(audit["issues"][:5])
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

    summary_path: str | None = None
    if persist_summary:
        pdir = Path(planning_dir) if planning_dir else Path(".planning")
        written = persist_milestone_summary(conn, milestone_id, pdir)
        summary_path = str(written)

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
        "summary_path": summary_path,
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

    total_plans_all = sum(len(list_plans(conn, p["id"])) for p in phases)
    complete_phases = sum(1 for p in phases if p["status"] == "complete")

    # Velocity: plans per day
    velocity: float | None = None
    if duration_days and duration_days > 0:
        velocity = round(total_plans_all / duration_days, 2)

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
    if velocity is not None:
        lines.append(f"**Velocity:** {velocity} plans/day")
    lines.append("")

    lines.append("## Phases")
    lines.append("")

    for phase in phases:
        plans = list_plans(conn, phase["id"])
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
                lines.append(
                    f"| {plan['name']} | {plan['status']} | {plan.get('wave', '-')} |"
                )
            lines.append("")

    lines.append("## Summary Statistics")
    lines.append("")
    lines.append(f"- **Phases:** {len(phases)} ({complete_phases} complete)")
    lines.append(f"- **Plans:** {total_plans_all}")
    if duration_days is not None:
        lines.append(f"- **Duration:** {duration_days} days")
    if velocity is not None:
        lines.append(f"- **Velocity:** {velocity} plans/day")
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
                f"- **{d.get('title', 'Untitled')}**: "
                f"{d.get('summary', d.get('rationale', ''))}"
            )
        lines.append("")

    return "\n".join(lines)
