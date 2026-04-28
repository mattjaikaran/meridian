#!/usr/bin/env python3
"""Spec phase support — Socratic ambiguity scoring, artifact writing, gate checks."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from scripts.db import connect, get_db_path
from scripts.state import get_phase, list_milestones, list_phases


# ── Ambiguity Model ───────────────────────────────────────────────────────────

DIMENSIONS = {
    "goal_clarity": {"weight": 0.35, "minimum": 0.75, "label": "Goal Clarity"},
    "boundary_clarity": {"weight": 0.25, "minimum": 0.70, "label": "Boundary Clarity"},
    "constraint_clarity": {"weight": 0.20, "minimum": 0.65, "label": "Constraint Clarity"},
    "acceptance_criteria": {"weight": 0.20, "minimum": 0.70, "label": "Acceptance Criteria"},
}

GATE_THRESHOLD = 0.20  # ambiguity ≤ 0.20 means sufficiently clear


def compute_ambiguity(scores: dict[str, float]) -> float:
    """Compute ambiguity score (0.0 = perfectly clear, 1.0 = completely unclear).

    ambiguity = 1.0 - weighted_sum_of_dimension_scores
    """
    weighted = sum(
        scores.get(dim, 0.0) * meta["weight"]
        for dim, meta in DIMENSIONS.items()
    )
    return round(1.0 - weighted, 4)


def gate_passed(scores: dict[str, float]) -> tuple[bool, list[str]]:
    """Return (passed, list_of_failing_dimensions).

    Gate requires: ambiguity ≤ GATE_THRESHOLD AND all dimensions ≥ their minimums.
    """
    failing = [
        dim
        for dim, meta in DIMENSIONS.items()
        if scores.get(dim, 0.0) < meta["minimum"]
    ]
    ambiguity = compute_ambiguity(scores)
    passed = ambiguity <= GATE_THRESHOLD and not failing
    return passed, failing


def format_scores(scores: dict[str, float]) -> str:
    """Format dimension scores for display."""
    lines = []
    for dim, meta in DIMENSIONS.items():
        score = scores.get(dim, 0.0)
        status = "✓" if score >= meta["minimum"] else "↑ needed"
        lines.append(
            f"  {meta['label']:<22} {score:.2f} (min {meta['minimum']:.2f}) [{status}]"
        )
    ambiguity = compute_ambiguity(scores)
    gate_ok = ambiguity <= GATE_THRESHOLD
    gate_mark = "✓ PASS" if gate_ok else "✗ FAIL"
    lines.append(f"  Ambiguity: {ambiguity:.2f} (gate: ≤ {GATE_THRESHOLD}) [{gate_mark}]")
    return "\n".join(lines)


def initial_scores_from_context(phase_name: str, description: str, criteria: list[str]) -> dict[str, float]:
    """Estimate initial ambiguity scores from existing phase metadata.

    Used before the interview starts to determine if --auto can skip questioning.
    Heuristic: more text and specific criteria = higher clarity.
    """
    desc_len = len(description or "")
    crit_count = len(criteria or [])

    # Goal clarity — based on description richness
    goal = min(0.60, 0.30 + (desc_len / 500) * 0.30)

    # Boundary clarity — low until interview specifies scope
    boundary = 0.30

    # Constraint clarity — low by default
    constraint = 0.30

    # Acceptance criteria — based on how many criteria exist
    acceptance = min(0.65, 0.25 + (crit_count * 0.10))

    return {
        "goal_clarity": round(goal, 2),
        "boundary_clarity": round(boundary, 2),
        "constraint_clarity": round(constraint, 2),
        "acceptance_criteria": round(acceptance, 2),
    }


# ── Context Retrieval ─────────────────────────────────────────────────────────


def get_spec_context(conn: sqlite3.Connection, phase_id: int | None = None) -> dict:
    """Return phase context needed to run spec-phase.

    If phase_id is None, finds the first phase in pending/planned_out status.
    Returns dict with keys: phase_id, phase_name, description, acceptance_criteria,
    tech_stack, phase_dir, slug, milestone_id.
    Returns {"error": "..."} if no suitable phase is found.
    """
    phase: dict | None = None

    if phase_id is not None:
        phase = get_phase(conn, phase_id)
        if phase is None:
            return {"error": f"Phase {phase_id} not found"}
    else:
        milestones = list_milestones(conn)
        active = [m for m in milestones if m.get("status") == "active"]
        search_order = active + [m for m in milestones if m not in active]
        for milestone in search_order:
            phases = list_phases(conn, milestone["id"])
            for p in phases:
                if p.get("status") in ("planned", "planned_out"):
                    phase = p
                    break
            if phase:
                break

    if phase is None:
        return {"error": "No planned or planned_out phase found. Run /meridian:plan first."}

    name_slug = phase["name"].lower().replace(" ", "-").replace("/", "-")
    seq = phase.get("sequence_number") or phase.get("id")
    slug = f"{seq:02d}-{name_slug}" if isinstance(seq, int) else name_slug

    project_row = conn.execute(
        "SELECT tech_stack FROM project WHERE id = 'default'"
    ).fetchone()
    tech_stack = (project_row["tech_stack"] if project_row else None) or "Not specified"

    criteria = phase.get("acceptance_criteria") or []
    if isinstance(criteria, str):
        try:
            criteria = json.loads(criteria)
        except (json.JSONDecodeError, ValueError):
            criteria = [criteria]

    initial_scores = initial_scores_from_context(
        phase["name"],
        phase.get("description") or "",
        criteria,
    )

    return {
        "phase_id": phase["id"],
        "phase_name": phase["name"],
        "description": phase.get("description") or "",
        "acceptance_criteria": criteria,
        "tech_stack": tech_stack,
        "slug": slug,
        "phase_dir": f".planning/phases/{slug}",
        "milestone_id": phase.get("milestone_id"),
        "initial_scores": initial_scores,
        "initial_ambiguity": compute_ambiguity(initial_scores),
    }


# ── Artifact Checks ───────────────────────────────────────────────────────────


def check_spec_artifact(phase_dir: Path) -> bool:
    """Return True if a non-empty SPEC.md exists in phase_dir."""
    path = Path(phase_dir) / "SPEC.md"
    return path.is_file() and path.stat().st_size > 100


# ── Artifact Writing ──────────────────────────────────────────────────────────


def write_spec_md(
    phase_dir: Path,
    phase_name: str,
    phase_id: int,
    goal: str,
    requirements: list[str],
    in_scope: list[str],
    out_of_scope: list[str],
    acceptance_criteria: list[str],
    constraints: list[str],
    final_scores: dict[str, float],
    unresolved_dimensions: list[str] | None = None,
) -> Path:
    """Write SPEC.md artifact to the phase artifact directory.

    Creates the directory if it doesn't exist. Returns path to written SPEC.md.
    """
    phase_dir = Path(phase_dir)
    phase_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ambiguity = compute_ambiguity(final_scores)
    unresolved = unresolved_dimensions or []

    def fmt_list(items: list[str], prefix: str = "-") -> str:
        return "\n".join(f"{prefix} {item}" for item in items) if items else f"{prefix} (none)"

    ambiguity_report_lines = []
    for dim, meta in DIMENSIONS.items():
        score = final_scores.get(dim, 0.0)
        flag = " ⚠ Below minimum — planner must treat as assumption" if dim in unresolved else ""
        ambiguity_report_lines.append(
            f"| {meta['label']} | {score:.2f} | {meta['minimum']:.2f} |{flag} |"
        )

    ac_checkboxes = "\n".join(f"- [ ] {ac}" for ac in acceptance_criteria) if acceptance_criteria else "- [ ] (none defined)"

    req_block = ""
    for i, req in enumerate(requirements, 1):
        req_block += f"\n### REQ-{i:02d}\n\n{req}\n"

    content = f"""# Phase {phase_id}: {phase_name} — SPEC

**Specced:** {now}
**Phase ID:** {phase_id}
**Ambiguity Score:** {ambiguity:.2f} (gate: ≤ {GATE_THRESHOLD})

## Goal

{goal}

## Requirements
{req_block}
## Scope

### In Scope

{fmt_list(in_scope)}

### Out of Scope

{fmt_list(out_of_scope)}

## Constraints

{fmt_list(constraints)}

## Acceptance Criteria

{ac_checkboxes}

## Ambiguity Report

| Dimension | Score | Minimum | |
|-----------|-------|---------|---|
{chr(10).join(ambiguity_report_lines)}

---

*Generated by /meridian:spec-phase*
"""
    out = phase_dir / "SPEC.md"
    out.write_text(content, encoding="utf-8")
    return out


# ── Completion Marker ─────────────────────────────────────────────────────────


def mark_spec_complete(
    conn: sqlite3.Connection,
    phase_id: int,
    ambiguity_score: float,
    requirement_count: int,
) -> None:
    """Store spec completion metadata in phase notes column."""
    now = datetime.now(timezone.utc).isoformat()
    existing = conn.execute(
        "SELECT notes FROM phase WHERE id = ?", (phase_id,)
    ).fetchone()
    existing_notes: dict = {}
    if existing and existing["notes"]:
        try:
            existing_notes = json.loads(existing["notes"])
        except (json.JSONDecodeError, ValueError):
            existing_notes = {}
    existing_notes["spec_complete"] = True
    existing_notes["spec_date"] = now
    existing_notes["spec_ambiguity"] = ambiguity_score
    existing_notes["spec_requirement_count"] = requirement_count
    conn.execute(
        "UPDATE phase SET notes = ? WHERE id = ?",
        (json.dumps(existing_notes), phase_id),
    )
    conn.commit()


def is_spec_complete(conn: sqlite3.Connection, phase_id: int) -> bool:
    """Return True if phase has been marked spec_complete in DB."""
    row = conn.execute(
        "SELECT notes FROM phase WHERE id = ?", (phase_id,)
    ).fetchone()
    if not row or not row["notes"]:
        return False
    try:
        notes = json.loads(row["notes"])
        return bool(notes.get("spec_complete"))
    except (json.JSONDecodeError, ValueError):
        return False


def get_spec_metadata(conn: sqlite3.Connection, phase_id: int) -> dict | None:
    """Return spec metadata dict from phase notes, or None if not found."""
    row = conn.execute(
        "SELECT notes FROM phase WHERE id = ?", (phase_id,)
    ).fetchone()
    if not row or not row["notes"]:
        return None
    try:
        notes = json.loads(row["notes"])
        if notes.get("spec_complete"):
            return {
                "spec_date": notes.get("spec_date"),
                "spec_ambiguity": notes.get("spec_ambiguity"),
                "spec_requirement_count": notes.get("spec_requirement_count"),
            }
    except (json.JSONDecodeError, ValueError):
        pass
    return None


# ── Gate Check ────────────────────────────────────────────────────────────────


def spec_gate(
    phase_dir: Path,
    conn: sqlite3.Connection | None = None,
    phase_id: int | None = None,
) -> dict:
    """Soft gate: check if spec is complete before discuss/plan/execute starts.

    Returns dict with: passed, warning, spec_path, requirement_count.
    Passed=True means SPEC.md exists (proceed). Passed=False is a soft warning.
    """
    artifact_ok = check_spec_artifact(phase_dir)
    meta = None
    if conn is not None and phase_id is not None:
        meta = get_spec_metadata(conn, phase_id)

    if artifact_ok:
        spec_path = str(Path(phase_dir) / "SPEC.md")
        req_count = meta.get("spec_requirement_count") if meta else None
        return {
            "passed": True,
            "warning": None,
            "spec_path": spec_path,
            "requirement_count": req_count,
        }

    return {
        "passed": False,
        "warning": (
            "SPEC.md not found. Run /meridian:spec-phase to clarify requirements "
            "before planning. Use --skip-spec to bypass (not recommended)."
        ),
        "spec_path": None,
        "requirement_count": None,
    }


# ── CLI Helper ────────────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys

    phase_id_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    conn = connect(get_db_path("."))
    ctx = get_spec_context(conn, phase_id_arg)
    conn.close()
    print(json.dumps(ctx, indent=2, default=str))
