#!/usr/bin/env python3
"""PM metrics engine — compute velocity, cycle times, stalls, and forecasts."""

import sqlite3
from collections import defaultdict
from datetime import UTC, datetime, timedelta


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_ts(ts: str | None) -> datetime | None:
    """Parse a timestamp string to a UTC-aware datetime."""
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def compute_velocity(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Compute plans completed per day over a rolling window.

    Reads velocity_window_days from settings (default 7).

    Returns:
        {velocity: float, completed_count: int, window_days: int}
    """
    from scripts.state import get_setting

    window_days = int(get_setting(conn, "velocity_window_days", "7", project_id))

    row = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
          AND p.status = 'complete'
          AND p.completed_at >= datetime('now', ? || ' days')
        """,
        (project_id, f"-{window_days}"),
    ).fetchone()

    completed = row["cnt"] if row else 0
    velocity = completed / float(window_days)

    return {
        "velocity": round(velocity, 2),
        "completed_count": completed,
        "window_days": window_days,
    }


def compute_cycle_times(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Compute average time (hours) for phases and plans to complete.

    Returns:
        {phase_avg_hours: float|None, plan_avg_hours: float|None,
         phases_sampled: int, plans_sampled: int}
    """
    # Phase cycle time: started_at → completed_at
    phase_row = conn.execute(
        """
        SELECT AVG(
            (julianday(ph.completed_at) - julianday(ph.started_at)) * 24
        ) as avg_hours,
        COUNT(*) as cnt
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
          AND ph.started_at IS NOT NULL
          AND ph.completed_at IS NOT NULL
        """,
        (project_id,),
    ).fetchone()

    # Plan cycle time: started_at → completed_at
    plan_row = conn.execute(
        """
        SELECT AVG(
            (julianday(p.completed_at) - julianday(p.started_at)) * 24
        ) as avg_hours,
        COUNT(*) as cnt
        FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
          AND p.started_at IS NOT NULL
          AND p.completed_at IS NOT NULL
        """,
        (project_id,),
    ).fetchone()

    return {
        "phase_avg_hours": round(phase_row["avg_hours"], 2) if phase_row["avg_hours"] else None,
        "plan_avg_hours": round(plan_row["avg_hours"], 2) if plan_row["avg_hours"] else None,
        "phases_sampled": phase_row["cnt"],
        "plans_sampled": plan_row["cnt"],
    }


def detect_stalls(
    conn: sqlite3.Connection,
    project_id: str = "default",
    plan_threshold_hours: float | None = None,
    phase_threshold_hours: float | None = None,
) -> list[dict]:
    """Detect phases and plans stuck in the same state beyond threshold.

    Reads stall_plan_hours / stall_phase_hours from settings when params not passed.

    Returns list of stall records: [{entity_type, entity_id, name, status, stuck_hours}]
    """
    from scripts.state import get_setting

    if plan_threshold_hours is None:
        plan_threshold_hours = float(
            get_setting(conn, "stall_plan_hours", "24.0", project_id)
        )
    if phase_threshold_hours is None:
        phase_threshold_hours = float(
            get_setting(conn, "stall_phase_hours", "48.0", project_id)
        )
    stalls = []

    # Stalled plans: executing or paused for too long
    plan_rows = conn.execute(
        """
        SELECT p.id, p.name, p.status, p.started_at
        FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
          AND p.status IN ('executing', 'paused')
          AND p.started_at IS NOT NULL
          AND (julianday('now') - julianday(p.started_at)) * 24 > ?
        """,
        (project_id, plan_threshold_hours),
    ).fetchall()

    for row in plan_rows:
        started = _parse_ts(row["started_at"])
        hours = ((_now() - started).total_seconds() / 3600) if started else 0
        stalls.append(
            {
                "entity_type": "plan",
                "entity_id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "stuck_hours": round(hours, 1),
            }
        )

    # Stalled phases: in non-terminal state with started_at too old
    phase_rows = conn.execute(
        """
        SELECT ph.id, ph.name, ph.status, ph.started_at
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
          AND ph.status IN ('executing', 'verifying', 'reviewing')
          AND ph.started_at IS NOT NULL
          AND (julianday('now') - julianday(ph.started_at)) * 24 > ?
        """,
        (project_id, phase_threshold_hours),
    ).fetchall()

    for row in phase_rows:
        started = _parse_ts(row["started_at"])
        hours = ((_now() - started).total_seconds() / 3600) if started else 0
        stalls.append(
            {
                "entity_type": "phase",
                "entity_id": row["id"],
                "name": row["name"],
                "status": row["status"],
                "stuck_hours": round(hours, 1),
            }
        )

    return stalls


def forecast_completion(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Estimate time to complete current milestone based on velocity.

    Returns:
        {remaining_plans: int, velocity: float, eta_days: float|None, eta_date: str|None}
    """
    # Get active milestone
    milestone = conn.execute(
        "SELECT id FROM milestone WHERE project_id = ? AND status = 'active' LIMIT 1",
        (project_id,),
    ).fetchone()

    if not milestone:
        return {"remaining_plans": 0, "velocity": 0, "eta_days": None, "eta_date": None}

    # Count remaining plans
    remaining = conn.execute(
        """
        SELECT COUNT(*) as cnt FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        WHERE ph.milestone_id = ?
          AND p.status NOT IN ('complete', 'skipped')
        """,
        (milestone["id"],),
    ).fetchone()

    remaining_count = remaining["cnt"]
    vel = compute_velocity(conn, project_id)
    velocity = vel["velocity"]

    if velocity <= 0 or remaining_count == 0:
        eta_days = 0.0 if remaining_count == 0 else None
        return {
            "remaining_plans": remaining_count,
            "velocity": velocity,
            "eta_days": eta_days,
            "eta_date": None if eta_days is None else _now().strftime("%Y-%m-%d"),
        }

    eta_days = remaining_count / velocity
    eta_date = (_now() + timedelta(days=eta_days)).strftime("%Y-%m-%d")

    return {
        "remaining_plans": remaining_count,
        "velocity": velocity,
        "eta_days": round(eta_days, 1),
        "eta_date": eta_date,
    }


def compute_progress(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Compute completion percentage at milestone, phase, and plan levels.

    Returns:
        {milestone: {name, pct}, phases: [{name, status, pct, done, total}]}
    """
    milestone = conn.execute(
        "SELECT * FROM milestone WHERE project_id = ? AND status = 'active' LIMIT 1",
        (project_id,),
    ).fetchone()

    if not milestone:
        return {"milestone": None, "phases": []}

    phases = conn.execute(
        "SELECT * FROM phase WHERE milestone_id = ? ORDER BY sequence",
        (milestone["id"],),
    ).fetchall()

    # Bulk fetch all plans for this milestone to avoid N+1
    all_plans = conn.execute(
        """SELECT p.phase_id, p.status FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        WHERE ph.milestone_id = ?""",
        (milestone["id"],),
    ).fetchall()
    plans_by_phase: dict[str, list[dict]] = defaultdict(list)
    for plan in all_plans:
        plans_by_phase[plan["phase_id"]].append(dict(plan))

    phase_progress = []
    total_plans = 0
    done_plans = 0

    for phase in phases:
        plans = plans_by_phase.get(phase["id"], [])

        plan_total = len(plans)
        plan_done = sum(1 for p in plans if p["status"] in ("complete", "skipped"))
        total_plans += plan_total
        done_plans += plan_done

        pct = (
            round(plan_done / plan_total * 100)
            if plan_total > 0
            else (100 if phase["status"] == "complete" else 0)
        )

        phase_progress.append(
            {
                "id": phase["id"],
                "name": phase["name"],
                "status": phase["status"],
                "pct": pct,
                "done": plan_done,
                "total": plan_total,
            }
        )

    milestone_pct = round(done_plans / total_plans * 100) if total_plans > 0 else 0

    return {
        "milestone": {
            "id": milestone["id"],
            "name": milestone["name"],
            "pct": milestone_pct,
        },
        "phases": phase_progress,
    }
