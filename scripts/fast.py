#!/usr/bin/env python3
"""Meridian fast task execution — complexity check, inline execution, atomic commit."""

import logging
import re
import sqlite3
from datetime import UTC, datetime

from scripts.db import retry_on_busy
from scripts.state import _log_event, create_quick_task, transition_quick_task

logger = logging.getLogger(__name__)

# Keywords that suggest a task is too complex for /meridian:fast
COMPLEX_KEYWORDS: list[str] = [
    "refactor",
    "architect",
    "redesign",
    "migrate",
    "rewrite",
    "overhaul",
    "restructure",
    "multi-file",
    "across files",
    "breaking change",
]

# Threshold: if estimated complexity >= this, warn user
COMPLEXITY_THRESHOLD: int = 3


def estimate_complexity(description: str) -> dict:
    """Estimate task complexity from a freeform description.

    Returns a dict with:
        - score: int (0 = trivial, higher = more complex)
        - reasons: list[str] explaining why
        - is_trivial: bool (True if score < COMPLEXITY_THRESHOLD)
    """
    score = 0
    reasons: list[str] = []
    desc_lower = description.lower()

    # Check for complex keywords
    for keyword in COMPLEX_KEYWORDS:
        if keyword in desc_lower:
            score += 3
            reasons.append(f"Contains complex keyword: '{keyword}'")

    # Check for mention of multiple files
    file_refs = re.findall(r'\b[\w/]+\.\w{1,5}\b', description)
    if len(file_refs) >= 3:
        score += 2
        reasons.append(f"References {len(file_refs)} files")
    elif len(file_refs) >= 1:
        # Some file references but not many — slight bump
        score += 1

    # Check for long descriptions (likely complex)
    word_count = len(description.split())
    if word_count > 50:
        score += 2
        reasons.append(f"Long description ({word_count} words)")
    elif word_count > 25:
        score += 1
        reasons.append(f"Moderate description ({word_count} words)")

    if not reasons:
        reasons.append("Looks trivial")

    return {
        "score": score,
        "reasons": reasons,
        "is_trivial": score < COMPLEXITY_THRESHOLD,
    }


@retry_on_busy()
def execute_fast_task(
    conn: sqlite3.Connection,
    description: str,
    project_id: str = "default",
    force: bool = False,
) -> dict:
    """Execute a fast task inline. Creates a quick_task record and logs events.

    Args:
        conn: Database connection.
        description: Freeform task description.
        project_id: Project identifier.
        force: If True, skip complexity warning for borderline tasks.

    Returns:
        Dict with task info, complexity estimate, and suggested_command if too complex.
    """
    complexity = estimate_complexity(description)

    if not complexity["is_trivial"] and not force:
        return {
            "status": "too_complex",
            "complexity": complexity,
            "description": description,
            "suggested_command": "/meridian:quick" if complexity["score"] < 5 else "/meridian:plan",
            "message": (
                f"Task looks non-trivial (complexity score: {complexity['score']}). "
                f"Reasons: {', '.join(complexity['reasons'])}. "
                f"Use {'/meridian:quick' if complexity['score'] < 5 else '/meridian:plan'} instead, "
                "or pass force=True to proceed anyway."
            ),
        }

    # Create the quick task record
    task = create_quick_task(conn, description, project_id)
    task_id = task["id"]

    # Transition to executing
    transition_quick_task(conn, task_id, "executing")

    # Log the event (use quick_task entity_type to match DB constraint)
    _log_event(
        conn,
        "quick_task",
        task_id,
        "created",
        "executing",
        metadata={"source": "fast", "description": description, "complexity": complexity["score"]},
    )
    conn.commit()

    return {
        "status": "executing",
        "task_id": task_id,
        "description": description,
        "complexity": complexity,
        "message": f"Fast task #{task_id} is executing: {description}",
    }


def complete_fast_task(
    conn: sqlite3.Connection,
    task_id: int,
    commit_sha: str | None = None,
) -> dict:
    """Mark a fast task as complete.

    Args:
        conn: Database connection.
        task_id: The quick_task ID.
        commit_sha: Optional git commit SHA.

    Returns:
        The updated task record.
    """
    # transition_quick_task already logs the state_event and commits
    task = transition_quick_task(conn, task_id, "complete", commit_sha=commit_sha)
    return task
