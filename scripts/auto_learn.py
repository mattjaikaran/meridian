#!/usr/bin/env python3
"""Auto-capture learnings from execution events (failures, review rejections)."""

import sqlite3

from scripts.learnings import add_learning, find_similar


def suggest_learning_from_failure(
    conn: sqlite3.Connection,
    plan_id: int,
    error_message: str,
    fix_description: str = "",
    project_id: str = "default",
) -> dict:
    """Generate a learning suggestion from a plan failure + fix cycle.

    Returns:
        {"suggested_rule": str, "duplicate": dict|None, "auto_saved": bool}
    """
    # Get plan context
    plan = conn.execute(
        "SELECT name, description FROM plan WHERE id = ?", (plan_id,)
    ).fetchone()

    plan_name = plan["name"] if plan else "unknown plan"

    # Build the learning rule from the failure context
    parts = [f"When working on '{plan_name}':"]
    if error_message:
        # Extract the key lesson from the error
        parts.append(f"Watch out for: {_summarize_error(error_message)}")
    if fix_description:
        parts.append(f"Fix: {fix_description}")

    suggested_rule = " ".join(parts)

    # Check for duplicates
    duplicate = find_similar(conn, suggested_rule, project_id=project_id)

    return {
        "suggested_rule": suggested_rule,
        "duplicate": duplicate,
        "auto_saved": False,
    }


def suggest_learning_from_review(
    conn: sqlite3.Connection,
    phase_id: int,
    review_feedback: str,
    project_id: str = "default",
) -> dict:
    """Generate a learning suggestion from a review rejection.

    Returns:
        {"suggested_rule": str, "duplicate": dict|None, "auto_saved": bool}
    """
    phase = conn.execute(
        "SELECT name FROM phase WHERE id = ?", (phase_id,)
    ).fetchone()

    phase_name = phase["name"] if phase else "unknown phase"

    # Extract actionable pattern from review feedback
    suggested_rule = _extract_review_pattern(review_feedback, phase_name)

    duplicate = find_similar(conn, suggested_rule, project_id=project_id)

    return {
        "suggested_rule": suggested_rule,
        "duplicate": duplicate,
        "auto_saved": False,
    }


def save_suggested_learning(
    conn: sqlite3.Connection,
    rule: str,
    source: str,
    phase_id: int | None = None,
    project_id: str = "default",
) -> dict:
    """Save a suggested learning after user confirmation."""
    return add_learning(
        conn, rule, scope="project", source=source, phase_id=phase_id, project_id=project_id
    )


def check_phase_for_retro_prompt(
    conn: sqlite3.Connection,
    project_id: str = "default",
    phase_interval: int = 3,
) -> dict:
    """Check if we should prompt for a retrospective.

    Returns:
        {"should_prompt": bool, "reason": str, "phases_since_last": int}
    """
    # Count completed phases since last retro decision
    last_retro = conn.execute(
        """SELECT created_at FROM decision
           WHERE project_id = ? AND summary LIKE 'Retro:%'
           ORDER BY created_at DESC LIMIT 1""",
        (project_id,),
    ).fetchone()

    if last_retro:
        completed_since = conn.execute(
            """SELECT COUNT(*) as cnt FROM phase ph
               JOIN milestone m ON ph.milestone_id = m.id
               WHERE m.project_id = ? AND ph.status = 'complete'
                 AND ph.completed_at > ?""",
            (project_id, last_retro["created_at"]),
        ).fetchone()
        count = completed_since["cnt"]
    else:
        count = conn.execute(
            """SELECT COUNT(*) as cnt FROM phase ph
               JOIN milestone m ON ph.milestone_id = m.id
               WHERE m.project_id = ? AND ph.status = 'complete'""",
            (project_id,),
        ).fetchone()["cnt"]

    should_prompt = count >= phase_interval
    reason = (
        f"{count} phases completed since last retro"
        if should_prompt
        else f"Only {count} phases since last retro (threshold: {phase_interval})"
    )

    return {
        "should_prompt": should_prompt,
        "reason": reason,
        "phases_since_last": count,
    }


def _summarize_error(error_message: str) -> str:
    """Extract the key part of an error message for a learning rule."""
    # Take first meaningful line, strip stack trace noise
    lines = error_message.strip().split("\n")
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith("at ") and not line.startswith("File "):
            return line[:200]
    return lines[0][:200] if lines else "unknown error"


def _extract_review_pattern(feedback: str, phase_name: str) -> str:
    """Extract an actionable pattern from review feedback."""
    # Take the first substantive sentence from feedback
    feedback = feedback.strip()
    if not feedback:
        return f"Review rejected for '{phase_name}' — check review feedback"

    # First 200 chars of feedback as the rule
    summary = feedback[:200].rstrip(".")
    return f"In code like '{phase_name}': {summary}"
