#!/usr/bin/env python3
"""Structured retrospective — velocity trends, shipping streaks, and action items."""

import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.metrics import compute_cycle_times, compute_velocity, detect_stalls


def _now() -> datetime:
    return datetime.now(UTC)


def _since_clause(since_days: int) -> str:
    return f"-{since_days} days"


def compute_shipping_streak(conn: sqlite3.Connection, project_id: str = "default") -> int:
    """Count consecutive completed phases (most recent first, no failures in between).

    A streak breaks when a phase is not 'complete' (e.g., blocked, executing).
    Only counts phases in active or complete milestones.
    """
    rows = conn.execute(
        """SELECT ph.status FROM phase ph
           JOIN milestone m ON ph.milestone_id = m.id
           WHERE m.project_id = ?
             AND m.status IN ('active', 'complete')
           ORDER BY ph.completed_at DESC, ph.sequence DESC""",
        (project_id,),
    ).fetchall()

    streak = 0
    for row in rows:
        if row["status"] == "complete":
            streak += 1
        else:
            break
    return streak


def compute_failure_rate(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> dict:
    """Compute plan failure rate over a time window.

    Returns:
        {total: int, failed: int, rate: float}
    """
    rows = conn.execute(
        """SELECT p.status FROM plan p
           JOIN phase ph ON p.phase_id = ph.id
           JOIN milestone m ON ph.milestone_id = m.id
           WHERE m.project_id = ?
             AND p.started_at >= datetime('now', ? || ' days')""",
        (project_id, f"-{since_days}"),
    ).fetchall()

    total = len(rows)
    failed = sum(1 for r in rows if r["status"] == "failed")
    rate = (failed / total * 100) if total > 0 else 0.0
    return {"total": total, "failed": failed, "rate": round(rate, 1)}


def get_period_phases(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> list[dict]:
    """Get phases completed within the time window."""
    rows = conn.execute(
        """SELECT ph.id, ph.name, ph.status, ph.started_at, ph.completed_at,
                  (SELECT COUNT(*) FROM plan WHERE phase_id = ph.id) as plan_count
           FROM phase ph
           JOIN milestone m ON ph.milestone_id = m.id
           WHERE m.project_id = ?
             AND ph.status = 'complete'
             AND ph.completed_at >= datetime('now', ? || ' days')
           ORDER BY ph.completed_at DESC""",
        (project_id, f"-{since_days}"),
    ).fetchall()
    return [dict(r) for r in rows]


def get_period_decisions(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> list[dict]:
    """Get decisions made within the time window."""
    rows = conn.execute(
        """SELECT d.decision_id, d.category, d.summary
           FROM decision d
           WHERE d.project_id = ?
             AND d.created_at >= datetime('now', ? || ' days')
           ORDER BY d.created_at DESC""",
        (project_id, f"-{since_days}"),
    ).fetchall()
    return [dict(r) for r in rows]


def get_period_learnings(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> list[dict]:
    """Get learnings captured within the time window."""
    rows = conn.execute(
        """SELECT id, rule, source, scope
           FROM learning
           WHERE project_id = ?
             AND created_at >= datetime('now', ? || ' days')
           ORDER BY created_at DESC""",
        (project_id, f"-{since_days}"),
    ).fetchall()
    return [dict(r) for r in rows]


def get_review_rejections(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> dict:
    """Get review pass/fail stats for the period."""
    rows = conn.execute(
        """SELECT r.result FROM review r
           JOIN phase ph ON r.phase_id = ph.id
           JOIN milestone m ON ph.milestone_id = m.id
           WHERE m.project_id = ?
             AND r.created_at >= datetime('now', ? || ' days')""",
        (project_id, f"-{since_days}"),
    ).fetchall()

    total = len(rows)
    failed = sum(1 for r in rows if r["result"] == "fail")
    rate = (failed / total * 100) if total > 0 else 0.0
    return {"total": total, "failed": failed, "rate": round(rate, 1)}


def generate_retro(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since_days: int = 7,
) -> dict:
    """Generate a full retrospective report.

    Returns structured data for formatting.
    """
    now = _now()
    start = now - timedelta(days=since_days)

    return {
        "period": {
            "start": start.strftime("%Y-%m-%d"),
            "end": now.strftime("%Y-%m-%d"),
            "days": since_days,
        },
        "shipped": get_period_phases(conn, project_id, since_days),
        "streak": compute_shipping_streak(conn, project_id),
        "velocity": compute_velocity(conn, project_id),
        "cycle_times": compute_cycle_times(conn, project_id),
        "failures": compute_failure_rate(conn, project_id, since_days),
        "stalls": detect_stalls(conn, project_id),
        "review_rejections": get_review_rejections(conn, project_id, since_days),
        "decisions": get_period_decisions(conn, project_id, since_days),
        "learnings": get_period_learnings(conn, project_id, since_days),
    }


def format_retro(retro: dict) -> str:
    """Format retro data as markdown."""
    lines = [
        f"## Retrospective — {retro['period']['start']} to {retro['period']['end']}",
        "",
    ]

    # What shipped
    lines.append("### What Shipped")
    if retro["shipped"]:
        for phase in retro["shipped"]:
            lines.append(f"- **{phase['name']}** ({phase['plan_count']} plans)")
        lines.append(f"- Shipping streak: {retro['streak']} consecutive phases")
    else:
        lines.append("- No phases completed this period")
    lines.append("")

    # Velocity
    vel = retro["velocity"]
    ct = retro["cycle_times"]
    lines.append("### Velocity")
    lines.append(f"- Plans/day: {vel['velocity']} ({vel['completed_count']} in {vel['window_days']}d)")
    if ct["plan_avg_hours"] is not None:
        lines.append(f"- Avg cycle time: {ct['plan_avg_hours']} hrs/plan")
    lines.append("")

    # What went wrong
    lines.append("### What Went Wrong")
    failures = retro["failures"]
    if failures["failed"] > 0:
        lines.append(f"- {failures['failed']} plan failures ({failures['rate']}% failure rate)")
    stalls = retro["stalls"]
    if stalls:
        for stall in stalls:
            lines.append(
                f"- Stall: {stall['name']} ({stall['entity_type']}) "
                f"stuck {stall['stuck_hours']}h in {stall['status']}"
            )
    reviews = retro["review_rejections"]
    if reviews["failed"] > 0:
        lines.append(f"- Review rejection rate: {reviews['rate']}%")
    if not failures["failed"] and not stalls and not reviews["failed"]:
        lines.append("- Nothing notable — smooth sailing")
    lines.append("")

    # Decisions
    lines.append("### Key Decisions")
    if retro["decisions"]:
        for dec in retro["decisions"]:
            dec_id = dec.get("decision_id") or "?"
            lines.append(f"- [{dec_id}] {dec['summary']}")
    else:
        lines.append("- No decisions recorded this period")
    lines.append("")

    # Learnings
    lines.append("### Learnings Captured")
    learning_count = len(retro["learnings"])
    if learning_count:
        lines.append(f"- {learning_count} new learnings added")
        for lr in retro["learnings"][:5]:
            lines.append(f"  - [{lr['source']}] {lr['rule']}")
    else:
        lines.append("- No learnings captured this period")
    lines.append("")

    return "\n".join(lines)
