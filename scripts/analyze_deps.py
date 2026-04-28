#!/usr/bin/env python3
"""Meridian dependency analysis — detect phase ordering constraints within a milestone."""

import json
import re
import sqlite3
from pathlib import Path

from scripts.db import get_db_path, open_project
from scripts.utils import now_dt as _now, now_iso as _now_iso


def _parse_file_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(p) for p in parsed]
    except (json.JSONDecodeError, TypeError):
        pass
    return [p.strip() for p in raw.split(",") if p.strip()]


def _phases_for_milestone(
    conn: sqlite3.Connection, milestone_id: str
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, sequence, description, status, depends_on
        FROM phase
        WHERE milestone_id = ?
        ORDER BY sequence
        """,
        (milestone_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _plans_for_phase(conn: sqlite3.Connection, phase_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, description, files_to_create, files_to_modify
        FROM plan
        WHERE phase_id = ?
        ORDER BY sequence
        """,
        (phase_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Detection functions ───────────────────────────────────────────────────────


def detect_file_overlaps(
    conn: sqlite3.Connection, milestone_id: str
) -> list[dict]:
    """Phases that write or touch the same files — strong ordering signal."""
    phases = _phases_for_milestone(conn, milestone_id)
    # Build map: file path → list of (phase_id, phase_name, phase_seq, role)
    file_map: dict[str, list[dict]] = {}

    for ph in phases:
        plans = _plans_for_phase(conn, ph["id"])
        for plan in plans:
            for fpath in _parse_file_list(plan["files_to_create"]):
                file_map.setdefault(fpath, []).append(
                    {"phase_id": ph["id"], "name": ph["name"], "seq": ph["sequence"], "role": "creates"}
                )
            for fpath in _parse_file_list(plan["files_to_modify"]):
                file_map.setdefault(fpath, []).append(
                    {"phase_id": ph["id"], "name": ph["name"], "seq": ph["sequence"], "role": "modifies"}
                )

    findings = []
    for fpath, touches in file_map.items():
        if len(touches) < 2:
            continue

        # Separate creators from modifiers
        creators = [t for t in touches if t["role"] == "creates"]
        modifiers = [t for t in touches if t["role"] == "modifies"]

        # A modifier that appears after a creator → dependency
        for mod in modifiers:
            for cre in creators:
                if cre["phase_id"] == mod["phase_id"]:
                    continue
                severity = "warning" if mod["seq"] < cre["seq"] else "info"
                findings.append({
                    "type": "file_overlap",
                    "severity": severity,
                    "file": fpath,
                    "dependent_phase_id": mod["phase_id"],
                    "dependent_phase_name": mod["name"],
                    "dependency_phase_id": cre["phase_id"],
                    "dependency_phase_name": cre["name"],
                    "message": (
                        f"Phase '{mod['name']}' modifies '{fpath}' "
                        f"which is created by phase '{cre['name']}'"
                    ),
                    "suggested_dep": {"phase_id": mod["phase_id"], "depends_on": cre["phase_id"]},
                })

        # Two phases both creating the same file → conflict
        if len(creators) >= 2:
            for i, a in enumerate(creators):
                for b in creators[i + 1:]:
                    findings.append({
                        "type": "file_conflict",
                        "severity": "warning",
                        "file": fpath,
                        "phase_a_id": a["phase_id"],
                        "phase_a_name": a["name"],
                        "phase_b_id": b["phase_id"],
                        "phase_b_name": b["name"],
                        "message": (
                            f"Phases '{a['name']}' and '{b['name']}' "
                            f"both declare they create '{fpath}'"
                        ),
                    })

    return findings


def detect_name_references(
    conn: sqlite3.Connection, milestone_id: str
) -> list[dict]:
    """Phase plan descriptions that textually reference another phase's name."""
    phases = _phases_for_milestone(conn, milestone_id)
    findings = []

    for ph in phases:
        plans = _plans_for_phase(conn, ph["id"])
        combined_text = " ".join(
            f"{p['name']} {p['description'] or ''}" for p in plans
        ).lower()

        for other in phases:
            if other["id"] == ph["id"]:
                continue
            other_name = other["name"].lower()
            # Require at least a 4-char name to avoid trivial matches
            if len(other_name) < 4:
                continue
            pattern = re.compile(r"\b" + re.escape(other_name) + r"\b")
            if pattern.search(combined_text):
                findings.append({
                    "type": "name_reference",
                    "severity": "info",
                    "referencing_phase_id": ph["id"],
                    "referencing_phase_name": ph["name"],
                    "referenced_phase_id": other["id"],
                    "referenced_phase_name": other["name"],
                    "message": (
                        f"Phase '{ph['name']}' plan text references "
                        f"phase '{other['name']}' by name"
                    ),
                    "suggested_dep": {
                        "phase_id": ph["id"],
                        "depends_on": other["id"],
                    },
                })

    return findings


def detect_sequence_gaps(
    conn: sqlite3.Connection, milestone_id: str
) -> list[dict]:
    """Phases with no explicit depends_on but with inferred ordering risk."""
    phases = _phases_for_milestone(conn, milestone_id)
    findings = []
    for ph in phases:
        if ph.get("depends_on") is None and ph["sequence"] > 1:
            findings.append({
                "type": "missing_explicit_dep",
                "severity": "info",
                "phase_id": ph["id"],
                "phase_name": ph["name"],
                "sequence": ph["sequence"],
                "message": (
                    f"Phase '{ph['name']}' (seq={ph['sequence']}) "
                    f"has no explicit depends_on"
                ),
            })
    return findings


# ── Suggestion synthesis ──────────────────────────────────────────────────────


def build_suggestions(findings: list[dict]) -> dict[int, list[int]]:
    """Synthesize a phase_id → [dep_phase_ids] map from all file/name findings."""
    suggestions: dict[int, set[int]] = {}
    for f in findings:
        dep = f.get("suggested_dep")
        if dep:
            phase_id = dep["phase_id"]
            dep_id = dep["depends_on"]
            suggestions.setdefault(phase_id, set()).add(dep_id)
    return {k: sorted(v) for k, v in suggestions.items()}


# ── DB write-back ─────────────────────────────────────────────────────────────


def apply_suggestions(
    conn: sqlite3.Connection, suggestions: dict[int, list[int]]
) -> list[dict]:
    """Write suggested depends_on values back to phase rows. Returns applied list."""
    applied = []
    for phase_id, dep_ids in suggestions.items():
        existing_raw = conn.execute(
            "SELECT depends_on, name FROM phase WHERE id = ?", (phase_id,)
        ).fetchone()
        if not existing_raw:
            continue

        existing_deps: list[int] = []
        if existing_raw["depends_on"]:
            try:
                existing_deps = json.loads(existing_raw["depends_on"])
            except (json.JSONDecodeError, TypeError):
                existing_deps = []

        merged = sorted(set(existing_deps) | set(dep_ids))
        if merged == existing_deps:
            continue  # No change

        conn.execute(
            "UPDATE phase SET depends_on = ? WHERE id = ?",
            (json.dumps(merged), phase_id),
        )
        applied.append({
            "phase_id": phase_id,
            "phase_name": existing_raw["name"],
            "depends_on": merged,
        })

    conn.commit()
    return applied


# ── Top-level runner ──────────────────────────────────────────────────────────


def run_analysis(
    project_dir: Path | None = None,
    milestone_id: str | None = None,
    apply: bool = False,
) -> dict:
    """Run dependency analysis and optionally write suggestions back to the DB."""
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
            "suggestions": {},
            "applied": [],
            "generated_at": _now().isoformat(),
        }

    all_findings: list[dict] = []
    suggestions: dict[int, list[int]] = {}
    applied: list[dict] = []
    milestone_name: str = ""

    with open_project(project_dir) as conn:
        # Resolve milestone_id
        if milestone_id is None:
            row = conn.execute(
                "SELECT id, name FROM milestone WHERE status = 'active' ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT id, name FROM milestone ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
            if row is None:
                return {
                    "status": "no_milestone",
                    "message": "No milestones found. Run /meridian:init.",
                    "findings": [],
                    "suggestions": {},
                    "applied": [],
                    "generated_at": _now().isoformat(),
                }
            milestone_id = row["id"]
            milestone_name = row["name"]
        else:
            row = conn.execute(
                "SELECT name FROM milestone WHERE id = ?", (milestone_id,)
            ).fetchone()
            milestone_name = row["name"] if row else milestone_id

        all_findings.extend(detect_file_overlaps(conn, milestone_id))
        all_findings.extend(detect_name_references(conn, milestone_id))
        all_findings.extend(detect_sequence_gaps(conn, milestone_id))

        suggestions = build_suggestions(all_findings)

        if apply and suggestions:
            applied = apply_suggestions(conn, suggestions)

    warnings = [f for f in all_findings if f.get("severity") == "warning"]
    infos = [f for f in all_findings if f.get("severity") == "info"]
    status = "issues_found" if warnings else ("suggestions" if infos else "clean")

    return {
        "status": status,
        "milestone_id": milestone_id,
        "milestone_name": milestone_name,
        "findings": all_findings,
        "warnings": len(warnings),
        "infos": len(infos),
        "suggestions": suggestions,
        "applied": applied,
        "generated_at": _now().isoformat(),
    }


# ── Report writer ─────────────────────────────────────────────────────────────

_TYPE_LABELS: dict[str, str] = {
    "file_overlap": "File Overlap Dependencies",
    "file_conflict": "File Creation Conflicts",
    "name_reference": "Semantic Name References",
    "missing_explicit_dep": "Phases Without Explicit Ordering",
}


def write_report(report: dict, project_dir: Path) -> Path:
    """Write analysis report to .planning/deps/report-{timestamp}.md."""
    ts = _now_iso().replace(":", "").replace("-", "")
    deps_dir = project_dir / ".planning" / "deps"
    deps_dir.mkdir(parents=True, exist_ok=True)
    report_path = deps_dir / f"report-{ts}.md"

    lines: list[str] = [
        "# Meridian Dependency Analysis Report",
        "",
        f"**Generated:** {report['generated_at']}  ",
        f"**Milestone:** {report.get('milestone_name', 'unknown')}  ",
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
        lines.append("")

    suggestions = report.get("suggestions", {})
    if suggestions:
        lines.append("## Suggested depends_on Entries")
        lines.append("")
        for phase_id, dep_ids in suggestions.items():
            lines.append(f"- Phase {phase_id} → depends on: {dep_ids}")
        lines.append("")

    applied = report.get("applied", [])
    if applied:
        lines.append("## Applied to Database")
        lines.append("")
        for entry in applied:
            lines.append(
                f"- Phase '{entry['phase_name']}' (id={entry['phase_id']})"
                f" → depends_on: {entry['depends_on']}"
            )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path
