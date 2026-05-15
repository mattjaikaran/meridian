#!/usr/bin/env python3
"""Project statistics — read-only aggregate view of phases, plans, git, and tests."""

from __future__ import annotations

import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return ""


def _phase_plan_counts(conn: sqlite3.Connection, project_id: str) -> dict:
    phase_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_phases,
            SUM(CASE WHEN ph.status = 'complete' THEN 1 ELSE 0 END) AS done_phases
        FROM phase ph
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    plan_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_plans,
            SUM(CASE WHEN p.status IN ('complete','skipped') THEN 1 ELSE 0 END) AS done_plans
        FROM plan p
        JOIN phase ph ON p.phase_id = ph.id
        JOIN milestone m ON ph.milestone_id = m.id
        WHERE m.project_id = ?
        """,
        (project_id,),
    ).fetchone()
    # Combine into a single row-like dict
    row = {
        "total_phases": phase_row["total_phases"] or 0,
        "done_phases": phase_row["done_phases"] or 0,
        "total_plans": plan_row["total_plans"] or 0,
        "done_plans": plan_row["done_plans"] or 0,
    }

    total_phases = row["total_phases"]
    done_phases = row["done_phases"]
    total_plans = row["total_plans"]
    done_plans = row["done_plans"]

    return {
        "total_phases": total_phases,
        "done_phases": done_phases,
        "phase_pct": round(done_phases / total_phases * 100) if total_phases else 0,
        "total_plans": total_plans,
        "done_plans": done_plans,
        "plan_pct": round(done_plans / total_plans * 100) if total_plans else 0,
    }


def _milestone_summary(conn: sqlite3.Connection, project_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT m.id AS milestone_id, m.name, m.status,
               COUNT(DISTINCT ph.id) AS phase_count,
               SUM(CASE WHEN ph.status = 'complete' THEN 1 ELSE 0 END) AS done_phases
        FROM milestone m
        LEFT JOIN phase ph ON ph.milestone_id = m.id
        WHERE m.project_id = ?
        GROUP BY m.id
        ORDER BY m.id
        """,
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _git_metrics(project_dir: Path) -> dict:
    commit_count_str = _git(["rev-list", "--count", "HEAD"], project_dir)
    commit_count = int(commit_count_str) if commit_count_str.isdigit() else 0

    first_commit_date = _git(
        ["log", "--reverse", "--format=%cs", "--max-count=1"], project_dir
    )
    last_commit_date = _git(["log", "--format=%cs", "--max-count=1"], project_dir)

    # Files changed and LOC across all commits
    shortstat = _git(
        ["diff", "--shortstat", "HEAD~1", "HEAD"], project_dir
    )
    # Total insertions/deletions across entire history
    numstat_raw = _git(
        ["log", "--oneline", "--numstat", "--format="], project_dir
    )
    total_insertions = 0
    total_deletions = 0
    for line in numstat_raw.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            total_insertions += int(parts[0])
            total_deletions += int(parts[1])

    files_tracked_str = _git(["ls-files", "--", ".", ":!tests"], project_dir)
    files_tracked = len(files_tracked_str.splitlines()) if files_tracked_str else 0

    return {
        "commit_count": commit_count,
        "first_commit_date": first_commit_date or None,
        "last_commit_date": last_commit_date or None,
        "total_insertions": total_insertions,
        "total_deletions": total_deletions,
        "files_tracked": files_tracked,
    }


def _test_count(project_dir: Path) -> dict:
    tests_dir = project_dir / "tests"
    if not tests_dir.exists():
        return {"test_files": 0, "test_functions": 0}

    test_files = list(tests_dir.rglob("test_*.py")) + list(tests_dir.rglob("*_test.py"))
    test_function_count = 0
    for f in test_files:
        try:
            text = f.read_text(errors="ignore")
            test_function_count += text.count("def test_")
        except OSError:
            pass

    return {
        "test_files": len(test_files),
        "test_functions": test_function_count,
    }


def _timeline(first_commit: str | None) -> dict:
    if not first_commit:
        return {"project_age_days": None, "started": None}
    try:
        start = datetime.strptime(first_commit, "%Y-%m-%d").replace(tzinfo=UTC)
        age = (datetime.now(UTC) - start).days
        return {"project_age_days": age, "started": first_commit}
    except ValueError:
        return {"project_age_days": None, "started": first_commit}


def compute_stats(
    conn: sqlite3.Connection,
    project_dir: Path,
    project_id: str = "default",
) -> dict:
    """Return a stats dict covering phases, plans, git, tests, and timeline."""
    from scripts.metrics import compute_velocity

    counts = _phase_plan_counts(conn, project_id)
    milestones = _milestone_summary(conn, project_id)
    git = _git_metrics(project_dir)
    tests = _test_count(project_dir)
    velocity = compute_velocity(conn, project_id)
    timeline = _timeline(git.get("first_commit_date"))

    return {
        "phases": counts,
        "milestones": milestones,
        "git": git,
        "tests": tests,
        "velocity": velocity,
        "timeline": timeline,
    }


def format_stats(data: dict) -> str:
    """Render stats dict as human-readable text."""
    lines: list[str] = ["## Project Statistics"]

    # Phases / Plans
    p = data["phases"]
    phase_bar = _bar(p["done_phases"], p["total_phases"])
    plan_bar = _bar(p["done_plans"], p["total_plans"])
    lines += [
        "",
        "### Progress",
        f"Phases  {phase_bar} {p['done_phases']}/{p['total_phases']} ({p['phase_pct']}%)",
        f"Plans   {plan_bar} {p['done_plans']}/{p['total_plans']} ({p['plan_pct']}%)",
    ]

    # Milestones table
    if data["milestones"]:
        lines += ["", "### Milestones"]
        lines.append(f"{'ID':<12} {'Name':<30} {'Status':<10} {'Phases'}")
        lines.append("-" * 62)
        for m in data["milestones"]:
            done = m.get("done_phases") or 0
            total = m.get("phase_count") or 0
            lines.append(
                f"{m['milestone_id']:<12} {m['name'][:29]:<30} {m['status']:<10} {done}/{total}"
            )

    # Velocity
    v = data["velocity"]
    lines += [
        "",
        "### Velocity",
        f"Plans/day: {v['velocity']} (last {v['window_days']} days, {v['completed_count']} completed)",
    ]

    # Git
    g = data["git"]
    if g["commit_count"]:
        lines += [
            "",
            "### Git",
            f"Commits:     {g['commit_count']}",
            f"Insertions:  +{g['total_insertions']}",
            f"Deletions:   -{g['total_deletions']}",
            f"Files:       {g['files_tracked']}",
        ]
        if g.get("last_commit_date"):
            lines.append(f"Last commit: {g['last_commit_date']}")

    # Tests
    t = data["tests"]
    if t["test_files"]:
        lines += [
            "",
            "### Tests",
            f"Test files:     {t['test_files']}",
            f"Test functions: {t['test_functions']}",
        ]

    # Timeline
    tl = data["timeline"]
    if tl.get("started"):
        lines += [
            "",
            "### Timeline",
            f"Started: {tl['started']}",
        ]
        if tl.get("project_age_days") is not None:
            lines.append(f"Age:     {tl['project_age_days']} days")

    return "\n".join(lines)


def _bar(done: int, total: int, width: int = 10) -> str:
    if total == 0:
        return "[" + "░" * width + "]"
    filled = round(done / total * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"
