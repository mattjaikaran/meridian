#!/usr/bin/env python3
"""Execution learning system — capture, deduplicate, and inject learned patterns."""

import re
import sqlite3
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


# -- CRUD ---------------------------------------------------------------------


def add_learning(
    conn: sqlite3.Connection,
    rule: str,
    scope: str = "project",
    source: str = "manual",
    phase_id: int | None = None,
    project_id: str = "default",
) -> dict:
    """Store a new learning rule after dedup check.

    Returns the created learning as a dict.
    Raises ValueError if scope/source is invalid or rule is empty.
    """
    rule = rule.strip()
    if not rule:
        raise ValueError("Learning rule cannot be empty")
    if scope not in ("global", "project", "phase"):
        raise ValueError(f"Invalid scope: {scope}")
    if source not in ("manual", "execution", "review", "debug"):
        raise ValueError(f"Invalid source: {source}")

    cur = conn.execute(
        """INSERT INTO learning (project_id, scope, phase_id, rule, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (project_id, scope, phase_id, rule, source, _now_iso()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM learning WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_learning(conn: sqlite3.Connection, learning_id: int) -> dict | None:
    """Get a single learning by ID."""
    row = conn.execute("SELECT * FROM learning WHERE id = ?", (learning_id,)).fetchone()
    return dict(row) if row else None


def list_learnings(
    conn: sqlite3.Connection,
    project_id: str = "default",
    scope: str | None = None,
    source: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List learnings with optional filters."""
    query = "SELECT * FROM learning WHERE project_id = ?"
    params: list = [project_id]

    if scope is not None:
        query += " AND scope = ?"
        params.append(scope)
    if source is not None:
        query += " AND source = ?"
        params.append(source)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def delete_learning(conn: sqlite3.Connection, learning_id: int) -> bool:
    """Delete a learning by ID. Returns True if deleted."""
    cur = conn.execute("DELETE FROM learning WHERE id = ?", (learning_id,))
    conn.commit()
    return cur.rowcount > 0


def increment_applied(conn: sqlite3.Connection, learning_id: int) -> None:
    """Increment the applied_count for a learning."""
    conn.execute(
        "UPDATE learning SET applied_count = applied_count + 1 WHERE id = ?",
        (learning_id,),
    )
    conn.commit()


# -- Deduplication -------------------------------------------------------------


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase words, stripping punctuation."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard_similarity(a: str, b: str) -> float:
    """Compute Jaccard similarity between two strings (word-level)."""
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def find_similar(
    conn: sqlite3.Connection,
    new_rule: str,
    project_id: str = "default",
    threshold: float = 0.7,
) -> dict | None:
    """Find the most similar existing learning above threshold.

    Returns the matching learning dict, or None if no match.
    """
    existing = list_learnings(conn, project_id=project_id, limit=200)
    best_match: dict | None = None
    best_score = 0.0

    for learning in existing:
        score = jaccard_similarity(new_rule, learning["rule"])
        if score >= threshold and score > best_score:
            best_score = score
            best_match = learning

    if best_match is not None:
        best_match["similarity"] = best_score
    return best_match


# -- Prompt injection ----------------------------------------------------------


def get_learnings_for_prompt(
    conn: sqlite3.Connection,
    project_id: str = "default",
    phase_id: int | None = None,
    limit: int = 20,
) -> str:
    """Format learnings as a markdown section for subagent prompt injection.

    Includes global + project learnings, plus phase-specific if phase_id provided.
    Increments applied_count for each included learning.

    Returns empty string if no learnings exist.
    """
    query = """
        SELECT * FROM learning
        WHERE project_id = ?
          AND (scope IN ('global', 'project')
               OR (scope = 'phase' AND phase_id = ?))
        ORDER BY applied_count ASC, created_at DESC
        LIMIT ?
    """
    rows = conn.execute(query, (project_id, phase_id, limit)).fetchall()

    if not rows:
        return ""

    lines = ["## Learnings from Prior Execution", ""]
    for row in rows:
        learning = dict(row)
        scope_tag = f"[{learning['scope']}]"
        source_tag = f"({learning['source']})"
        lines.append(f"- {scope_tag} {source_tag} {learning['rule']}")
        increment_applied(conn, learning["id"])

    lines.append("")
    return "\n".join(lines)


# -- Pruning -------------------------------------------------------------------


def prune_stale(
    conn: sqlite3.Connection,
    project_id: str = "default",
    min_applied: int = 0,
    older_than_days: int = 90,
) -> int:
    """Remove learnings that have never been applied and are older than threshold.

    Returns count of pruned learnings.
    """
    cur = conn.execute(
        """DELETE FROM learning
           WHERE project_id = ?
             AND applied_count <= ?
             AND created_at < datetime('now', ? || ' days')""",
        (project_id, min_applied, f"-{older_than_days}"),
    )
    conn.commit()
    return cur.rowcount
