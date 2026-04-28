#!/usr/bin/env python3
"""Meridian workflow forensics — post-mortem analysis of failed/stuck workflow states."""

import sqlite3
import subprocess
from datetime import timedelta
from pathlib import Path

from scripts.db import get_db_path, open_project
from scripts.utils import now_dt as _now, now_iso as _now_iso, parse_dt as _parse_dt, phase_slug as _phase_slug


def _run_git(project_dir: Path, *args: str) -> str:
    """Run a git command in project_dir. Returns stdout or empty string on error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


# ── Detection functions ───────────────────────────────────────────────────────


def detect_stuck_loops(
    conn: sqlite3.Connection,
    stuck_threshold_hours: int = 4,
) -> list[dict]:
    """Phases stuck in 'executing' for too long — potential crash or abandoned session."""
    findings = []
    now = _now()
    threshold = timedelta(hours=stuck_threshold_hours)

    rows = conn.execute("""
        SELECT ph.id, ph.name, ph.sequence, ph.started_at, m.name AS milestone_name
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
                "type": "stuck_loop",
                "severity": "warning",
                "phase_id": row["id"],
                "phase_name": row["name"],
                "milestone_name": row["milestone_name"],
                "message": (
                    f"Phase '{row['name']}' (id={row['id']}) in milestone"
                    f" '{row['milestone_name']}' has been executing for {hours:.1f}h"
                ),
                "age_hours": round(hours, 1),
                "suggestion": (
                    "Run /meridian:health --repair to revert, or /meridian:resume to continue."
                ),
            })

    return findings


def detect_missing_artifacts(
    conn: sqlite3.Connection,
    project_dir: Path,
) -> list[dict]:
    """Phases in active states with no artifact directory or missing PLAN.md."""
    findings = []
    planning_dir = project_dir / ".planning" / "phases"

    rows = conn.execute("""
        SELECT ph.id, ph.name, ph.sequence, ph.status, m.name AS milestone_name
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE ph.status IN ('planned_out', 'executing', 'verifying', 'reviewing')
    """).fetchall()

    for row in rows:
        phase = dict(row)
        slug = _phase_slug(phase)
        phase_dir = planning_dir / slug

        if not phase_dir.exists():
            if row["status"] != "planned_out":
                findings.append({
                    "type": "missing_artifact",
                    "severity": "warning",
                    "phase_id": row["id"],
                    "phase_name": row["name"],
                    "milestone_name": row["milestone_name"],
                    "message": (
                        f"Phase '{row['name']}' (status={row['status']})"
                        f" has no artifact dir at .planning/phases/{slug}/"
                    ),
                    "suggestion": "Artifact directory was never created or was deleted.",
                })
            continue

        # Dir exists — check for PLAN.md when past planning stage
        if row["status"] in {"executing", "verifying", "reviewing"}:
            plan_file = phase_dir / "PLAN.md"
            if not plan_file.exists():
                findings.append({
                    "type": "missing_artifact",
                    "severity": "warning",
                    "phase_id": row["id"],
                    "phase_name": row["name"],
                    "milestone_name": row["milestone_name"],
                    "message": (
                        f"Phase '{row['name']}' (status={row['status']})"
                        f" has artifact dir but no PLAN.md"
                    ),
                    "suggestion": "Planning step may have been interrupted.",
                })

    return findings


def detect_abandoned_work(
    conn: sqlite3.Connection,
    project_dir: Path,
    abandoned_threshold_days: int = 3,
) -> list[dict]:
    """Phases started but with no recent git activity, suggesting an abandoned session."""
    findings = []
    planning_dir = project_dir / ".planning" / "phases"
    threshold = timedelta(days=abandoned_threshold_days)
    now = _now()

    rows = conn.execute("""
        SELECT ph.id, ph.name, ph.sequence, ph.status, ph.started_at, m.name AS milestone_name
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE ph.status IN ('executing', 'planned_out') AND ph.started_at IS NOT NULL
    """).fetchall()

    for row in rows:
        started = _parse_dt(row["started_at"])
        if started is None:
            continue
        age = now - started
        if age < threshold:
            continue

        # Check git activity in phase artifact dir
        phase = dict(row)
        slug = _phase_slug(phase)
        phase_dir = planning_dir / slug

        if phase_dir.exists():
            rel = str(phase_dir.relative_to(project_dir))
            last_commit_ts = _run_git(project_dir, "log", "-1", "--format=%aI", "--", rel)
            if last_commit_ts:
                last_commit = _parse_dt(last_commit_ts)
                if last_commit and (now - last_commit) < threshold:
                    continue  # Recent git activity — not abandoned

        days = age.total_seconds() / 86400
        findings.append({
            "type": "abandoned_work",
            "severity": "info",
            "phase_id": row["id"],
            "phase_name": row["name"],
            "milestone_name": row["milestone_name"],
            "message": (
                f"Phase '{row['name']}' (status={row['status']}) started {days:.0f}d ago"
                f" with no recent git activity"
            ),
            "age_days": round(days, 1),
            "suggestion": "Run /meridian:resume or /meridian:revert to reset state.",
        })

    return findings


_MIN_MEANINGFUL_BYTES = 50
_KEY_FILES = {"PLAN.md", "VERIFICATION.md", "UAT.md"}


def detect_crash_signatures(project_dir: Path) -> list[dict]:
    """Find empty/truncated artifact files that may indicate a crashed session."""
    findings = []
    planning_dir = project_dir / ".planning" / "phases"

    if not planning_dir.exists():
        return []

    for phase_dir in sorted(planning_dir.iterdir()):
        if not phase_dir.is_dir():
            continue

        contents = list(phase_dir.iterdir())
        if not contents:
            findings.append({
                "type": "crash_signature",
                "severity": "info",
                "path": str(phase_dir.relative_to(project_dir)),
                "message": f"Phase artifact dir '{phase_dir.name}/' is empty",
                "suggestion": (
                    "May have been created during a planning session that was interrupted."
                ),
            })
            continue

        for fname in _KEY_FILES:
            fpath = phase_dir / fname
            if not fpath.exists():
                continue
            size = fpath.stat().st_size
            if size < _MIN_MEANINGFUL_BYTES:
                preview = fpath.read_text(encoding="utf-8", errors="ignore").strip()
                findings.append({
                    "type": "crash_signature",
                    "severity": "warning" if fname == "PLAN.md" else "info",
                    "path": str(fpath.relative_to(project_dir)),
                    "message": (
                        f"'{fname}' in '{phase_dir.name}/' is suspiciously small ({size} bytes)"
                    ),
                    "content_preview": preview[:120],
                    "suggestion": (
                        "File may be truncated or a placeholder. Re-run the planning step."
                    ),
                })

    return findings


def collect_git_context(project_dir: Path) -> dict:
    """Gather git log, diff, and status context for the forensics report."""
    log = _run_git(project_dir, "log", "--oneline", "-20")
    diff_stat = _run_git(project_dir, "diff", "--stat", "HEAD")
    branch = _run_git(project_dir, "rev-parse", "--abbrev-ref", "HEAD")
    status_out = _run_git(project_dir, "status", "--short")

    uncommitted = [line.strip() for line in status_out.splitlines() if line.strip()]

    return {
        "branch": branch or "unknown",
        "recent_log": log,
        "diff_stat": diff_stat,
        "uncommitted_files": uncommitted,
        "uncommitted_count": len(uncommitted),
    }


def _severity_rank(s: str) -> int:
    return {"warning": 0, "info": 1}.get(s, 2)


# ── Top-level runner ──────────────────────────────────────────────────────────


def run_forensics(
    project_dir: Path | None = None,
    stuck_threshold_hours: int = 4,
    abandoned_threshold_days: int = 3,
    include_git: bool = True,
) -> dict:
    """Run all forensics checks and return a structured report dict."""
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
            "git": {},
            "generated_at": _now().isoformat(),
        }

    all_findings: list[dict] = []

    with open_project(project_dir) as conn:
        all_findings.extend(detect_stuck_loops(conn, stuck_threshold_hours))
        all_findings.extend(detect_missing_artifacts(conn, project_dir))
        all_findings.extend(detect_abandoned_work(conn, project_dir, abandoned_threshold_days))

    all_findings.extend(detect_crash_signatures(project_dir))
    all_findings.sort(key=lambda f: _severity_rank(f.get("severity", "info")))

    git_ctx: dict = {}
    if include_git:
        git_ctx = collect_git_context(project_dir)

    warnings = [f for f in all_findings if f.get("severity") == "warning"]
    infos = [f for f in all_findings if f.get("severity") == "info"]
    status = "issues_found" if warnings else ("notes" if infos else "clean")

    return {
        "status": status,
        "findings": all_findings,
        "warnings": len(warnings),
        "infos": len(infos),
        "git": git_ctx,
        "generated_at": _now().isoformat(),
    }


# ── Report writer ─────────────────────────────────────────────────────────────

_TYPE_LABELS: dict[str, str] = {
    "stuck_loop": "Stuck Execution Loops",
    "missing_artifact": "Missing Artifacts",
    "abandoned_work": "Abandoned Work",
    "crash_signature": "Crash Signatures",
}


def write_report(report: dict, project_dir: Path) -> Path:
    """Write forensics report to .planning/forensics/report-{timestamp}.md.

    Returns the path of the written file.
    """
    ts = _now_iso().replace(":", "").replace("-", "")
    forensics_dir = project_dir / ".planning" / "forensics"
    forensics_dir.mkdir(parents=True, exist_ok=True)
    report_path = forensics_dir / f"report-{ts}.md"

    lines: list[str] = [
        "# Meridian Workflow Forensics Report",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**Status:** {report['status']}  ",
        f"**Warnings:** {report['warnings']}  **Notes:** {report['infos']}",
        "",
    ]

    by_type: dict[str, list[dict]] = {}
    for f in report["findings"]:
        by_type.setdefault(f["type"], []).append(f)

    for ftype, label in _TYPE_LABELS.items():
        findings = by_type.get(ftype, [])
        lines.append(f"## {label}")
        lines.append("")
        if not findings:
            lines.append("_No issues found._")
        else:
            for f in findings:
                icon = "⚠" if f.get("severity") == "warning" else "ℹ"
                lines.append(f"- {icon} {f['message']}")
                if f.get("suggestion"):
                    lines.append(f"  - _Suggestion: {f['suggestion']}_")
        lines.append("")

    git = report.get("git", {})
    if git:
        lines.append("## Git Context")
        lines.append("")
        lines.append(f"**Branch:** {git.get('branch', 'unknown')}  ")
        uncommitted = git.get("uncommitted_count", 0)
        if uncommitted:
            lines.append(f"**Uncommitted changes:** {uncommitted} files  ")
        recent_log = git.get("recent_log", "")
        if recent_log:
            lines.append("")
            lines.append("### Recent Commits")
            lines.append("")
            lines.append("```")
            lines.append(recent_log)
            lines.append("```")
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
