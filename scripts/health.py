#!/usr/bin/env python3
"""Meridian health check — DB integrity, artifact consistency, stuck phase detection."""

import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from scripts.db import SCHEMA_VERSION, get_db_path, open_project


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return None


def _phase_slug(phase: dict) -> str:
    name = phase["name"].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return f"{phase['sequence']:02d}-{slug}"


# ── DB integrity ──────────────────────────────────────────────────────────────


def check_db_integrity(conn: sqlite3.Connection) -> list[dict]:
    """Run SQLite PRAGMA integrity_check and foreign_key_check."""
    findings = []

    rows = conn.execute("PRAGMA integrity_check").fetchall()
    for row in rows:
        msg = row[0]
        if msg != "ok":
            findings.append({"level": "error", "check": "integrity_check", "message": msg})

    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    for row in rows:
        findings.append({
            "level": "error",
            "check": "foreign_key_check",
            "message": (
                f"FK violation in table '{row[0]}' rowid {row[1]}"
                f" -> '{row[2]}' rowid {row[3]}"
            ),
        })

    return findings


def check_schema_version(conn: sqlite3.Connection) -> list[dict]:
    """Verify the DB schema version matches the expected version."""
    findings = []
    try:
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        actual = row["version"] if row else 0
        if actual < SCHEMA_VERSION:
            findings.append({
                "level": "warning",
                "check": "schema_version",
                "message": (
                    f"Schema version {actual} < expected {SCHEMA_VERSION}."
                    " Run /meridian:migrate."
                ),
            })
        elif actual > SCHEMA_VERSION:
            findings.append({
                "level": "warning",
                "check": "schema_version",
                "message": (
                    f"Schema version {actual} > expected {SCHEMA_VERSION} (newer DB?)"
                ),
            })
    except sqlite3.OperationalError as e:
        findings.append({"level": "error", "check": "schema_version", "message": str(e)})
    return findings


def check_orphaned_rows(conn: sqlite3.Connection) -> list[dict]:
    """Find plans or phases with no valid parent record."""
    findings = []

    rows = conn.execute("""
        SELECT p.id, p.phase_id FROM plan p
        LEFT JOIN phase ph ON p.phase_id = ph.id
        WHERE ph.id IS NULL
    """).fetchall()
    for row in rows:
        findings.append({
            "level": "warning",
            "check": "orphaned_rows",
            "message": f"Plan id={row[0]} references non-existent phase_id={row[1]}",
            "repair": {"action": "delete_plan", "plan_id": row[0]},
        })

    rows = conn.execute("""
        SELECT ph.id, ph.milestone_id FROM phase ph
        LEFT JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.id IS NULL
    """).fetchall()
    for row in rows:
        findings.append({
            "level": "warning",
            "check": "orphaned_rows",
            "message": (
                f"Phase id={row[0]} references non-existent milestone_id={row[1]}"
            ),
            "repair": {"action": "delete_phase", "phase_id": row[0]},
        })

    return findings


# ── Artifact consistency ──────────────────────────────────────────────────────


def check_artifact_consistency(
    conn: sqlite3.Connection,
    project_dir: Path,
) -> list[dict]:
    """Compare .planning/phases/ artifact dirs against DB phase records."""
    findings = []
    planning_dir = project_dir / ".planning" / "phases"

    milestones = conn.execute("SELECT id FROM milestone").fetchall()
    db_phases: dict[str, dict] = {}
    for m in milestones:
        phases = conn.execute(
            "SELECT * FROM phase WHERE milestone_id = ? ORDER BY sequence",
            (m["id"],),
        ).fetchall()
        for ph in phases:
            slug = _phase_slug(dict(ph))
            db_phases[slug] = dict(ph)

    if not planning_dir.exists():
        return []

    for entry in sorted(planning_dir.iterdir()):
        if not entry.is_dir():
            continue
        slug = entry.name
        if slug not in db_phases:
            findings.append({
                "level": "info",
                "check": "artifact_consistency",
                "message": f"Artifact dir '{slug}' has no matching DB phase record",
            })

    active_statuses = {"planned_out", "executing", "verifying", "reviewing", "complete"}
    for slug, phase in db_phases.items():
        if phase["status"] in active_statuses:
            phase_dir = planning_dir / slug
            if not phase_dir.exists():
                findings.append({
                    "level": "warning",
                    "check": "artifact_consistency",
                    "message": (
                        f"Phase '{phase['name']}' (id={phase['id']},"
                        f" status={phase['status']}) has no artifact dir"
                        f" at .planning/phases/{slug}/"
                    ),
                })

    return findings


# ── Stuck phase detection ─────────────────────────────────────────────────────


def check_stuck_phases(
    conn: sqlite3.Connection,
    stuck_threshold_hours: int = 4,
) -> list[dict]:
    """Detect phases stuck in 'executing' longer than the threshold."""
    findings = []
    now = _now()
    threshold = timedelta(hours=stuck_threshold_hours)

    rows = conn.execute("""
        SELECT ph.id, ph.name, ph.started_at, m.name AS milestone_name
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE ph.status = 'executing' AND ph.started_at IS NOT NULL
    """).fetchall()

    for row in rows:
        started = _parse_dt(row["started_at"])
        if started is None:
            continue
        age = now - started
        if age > threshold:
            hours = age.total_seconds() / 3600
            findings.append({
                "level": "warning",
                "check": "stuck_phases",
                "message": (
                    f"Phase '{row['name']}' (id={row['id']}) in milestone"
                    f" '{row['milestone_name']}' has been executing for"
                    f" {hours:.1f}h (threshold: {stuck_threshold_hours}h)"
                ),
                "phase_id": row["id"],
                "age_hours": round(hours, 1),
                "repair": {"action": "revert_to_planned_out", "phase_id": row["id"]},
            })

    return findings


# ── Repair ────────────────────────────────────────────────────────────────────


def repair(conn: sqlite3.Connection, findings: list[dict]) -> list[str]:
    """Apply auto-repair for repairable findings. Returns list of applied repairs."""
    messages = []

    for finding in findings:
        repair_info = finding.get("repair")
        if not repair_info:
            continue
        action = repair_info.get("action")

        if action == "delete_plan":
            plan_id = repair_info["plan_id"]
            conn.execute("DELETE FROM plan WHERE id = ?", (plan_id,))
            messages.append(f"Deleted orphaned plan id={plan_id}")

        elif action == "delete_phase":
            phase_id = repair_info["phase_id"]
            conn.execute("DELETE FROM plan WHERE phase_id = ?", (phase_id,))
            conn.execute("DELETE FROM phase WHERE id = ?", (phase_id,))
            messages.append(f"Deleted orphaned phase id={phase_id} and its plans")

        elif action == "revert_to_planned_out":
            phase_id = repair_info["phase_id"]
            conn.execute(
                "UPDATE phase SET status = 'planned_out', started_at = NULL WHERE id = ?",
                (phase_id,),
            )
            conn.execute(
                """INSERT INTO state_event
                (entity_type, entity_id, old_status, new_status, metadata)
                VALUES ('phase', ?, 'executing', 'planned_out', '{"repair":"health_check"}')""",
                (str(phase_id),),
            )
            messages.append(f"Reverted stuck phase id={phase_id} to 'planned_out'")

    conn.commit()
    return messages


# ── Top-level runner ──────────────────────────────────────────────────────────


def run_health_check(
    project_dir: Path | None = None,
    do_repair: bool = False,
    stuck_threshold_hours: int = 4,
) -> dict:
    """Run all health checks and optionally apply repairs.

    Returns structured result: {status, findings, errors, warnings, infos, repair_log}
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    db_path = get_db_path(project_dir)
    if not db_path.exists():
        return {
            "status": "no_db",
            "message": "No Meridian database found. Run /meridian:init.",
            "findings": [],
            "repair_log": [],
        }

    all_findings: list[dict] = []
    repair_log: list[str] = []

    def _collect_findings(conn: sqlite3.Connection) -> list[dict]:
        findings: list[dict] = []
        findings.extend(check_db_integrity(conn))
        findings.extend(check_schema_version(conn))
        findings.extend(check_orphaned_rows(conn))
        findings.extend(check_artifact_consistency(conn, project_dir))
        findings.extend(check_stuck_phases(conn, stuck_threshold_hours))
        return findings

    with open_project(project_dir) as conn:
        all_findings = _collect_findings(conn)

        if do_repair:
            repair_log = repair(conn, all_findings)
            # Re-run checks to reflect post-repair state
            all_findings = _collect_findings(conn)

    errors = [f for f in all_findings if f["level"] == "error"]
    warnings = [f for f in all_findings if f["level"] == "warning"]
    infos = [f for f in all_findings if f["level"] == "info"]

    status = "error" if errors else ("warning" if warnings else "ok")

    return {
        "status": status,
        "findings": all_findings,
        "errors": len(errors),
        "warnings": len(warnings),
        "infos": len(infos),
        "repair_log": repair_log,
    }
