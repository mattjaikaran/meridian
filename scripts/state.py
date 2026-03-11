#!/usr/bin/env python3
"""Meridian state management — CRUD, transitions, and next-action computation."""

import json
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from scripts.db import StateTransitionError

# Valid state transitions
PHASE_TRANSITIONS = {
    "planned": ["context_gathered", "blocked"],
    "context_gathered": ["planned_out", "blocked"],
    "planned_out": ["executing", "blocked"],
    "executing": ["verifying", "blocked", "planned_out"],
    "verifying": ["reviewing", "executing", "blocked"],
    "reviewing": ["complete", "executing", "blocked"],
    "complete": ["archived"],
    "blocked": ["planned", "context_gathered", "planned_out", "executing"],
}

PLAN_TRANSITIONS = {
    "pending": ["executing", "skipped"],
    "executing": ["complete", "failed", "paused"],
    "paused": ["executing", "skipped"],
    "failed": ["pending", "executing", "skipped"],
    "complete": [],
    "skipped": [],
}

MILESTONE_TRANSITIONS = {
    "planned": ["active"],
    "active": ["complete", "archived"],
    "complete": ["archived"],
    "archived": [],
}

ALLOWED_COLUMNS = {
    "project": {"name", "repo_path", "repo_url", "tech_stack", "nero_endpoint",
                "axis_project_id", "updated_at"},
    "milestone": {"status", "completed_at"},
    "phase": {"name", "description", "context_doc", "acceptance_criteria",
              "axis_ticket_id", "status", "started_at", "completed_at", "priority"},
    "plan": {"name", "description", "wave", "tdd_required", "files_to_create",
             "files_to_modify", "test_command", "executor_type", "status",
             "started_at", "completed_at", "commit_sha", "error_message", "priority"},
    "quick_task": {"status", "completed_at", "commit_sha"},
    "nero_dispatch": {"status", "pr_url", "completed_at"},
}

_PRIORITY_SQL = {
    "phase": "UPDATE phase SET priority = ? WHERE id = ?",
    "plan": "UPDATE plan SET priority = ? WHERE id = ?",
}


def safe_update(conn, table: str, row_id, updates: dict, id_column: str = "id") -> None:
    """Update a row with column allowlist validation.

    Raises ValueError for unknown tables or invalid columns.
    """
    allowed = ALLOWED_COLUMNS.get(table)
    if allowed is None:
        raise ValueError(f"Unknown table: {table}")
    invalid = set(updates.keys()) - allowed
    if invalid:
        raise ValueError(f"Invalid columns for {table}: {invalid}")
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [row_id]
    conn.execute(f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?", values)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows: list[sqlite3.Row]) -> list[dict]:
    return [dict(r) for r in rows]


# ── Project CRUD ──────────────────────────────────────────────────────────────


def create_project(
    conn: sqlite3.Connection,
    name: str,
    repo_path: str,
    project_id: str = "default",
    repo_url: str | None = None,
    tech_stack: list[str] | None = None,
    nero_endpoint: str | None = None,
    axis_project_id: str | None = None,
) -> dict:
    conn.execute(
        """INSERT INTO project
        (id, name, repo_path, repo_url, tech_stack, nero_endpoint, axis_project_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            name,
            repo_path,
            repo_url,
            json.dumps(tech_stack) if tech_stack else None,
            nero_endpoint,
            axis_project_id,
        ),
    )
    conn.commit()
    return get_project(conn, project_id)


def get_project(conn: sqlite3.Connection, project_id: str = "default") -> dict | None:
    row = conn.execute("SELECT * FROM project WHERE id = ?", (project_id,)).fetchone()
    return _row_to_dict(row)


def update_project(conn: sqlite3.Connection, project_id: str, **kwargs) -> dict | None:
    allowed = {"name", "repo_path", "repo_url", "tech_stack", "nero_endpoint", "axis_project_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_project(conn, project_id)
    if "tech_stack" in updates and isinstance(updates["tech_stack"], list):
        updates["tech_stack"] = json.dumps(updates["tech_stack"])
    updates["updated_at"] = _now()
    safe_update(conn, "project", project_id, updates)
    conn.commit()
    return get_project(conn, project_id)


# ── Milestone CRUD ────────────────────────────────────────────────────────────


def create_milestone(
    conn: sqlite3.Connection,
    milestone_id: str,
    name: str,
    description: str | None = None,
    project_id: str = "default",
) -> dict:
    conn.execute(
        "INSERT INTO milestone (id, project_id, name, description) VALUES (?, ?, ?, ?)",
        (milestone_id, project_id, name, description),
    )
    conn.commit()
    return get_milestone(conn, milestone_id)


def get_milestone(conn: sqlite3.Connection, milestone_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM milestone WHERE id = ?", (milestone_id,)).fetchone()
    return _row_to_dict(row)


def list_milestones(conn: sqlite3.Connection, project_id: str = "default") -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM milestone WHERE project_id = ? ORDER BY created_at", (project_id,)
    ).fetchall()
    return _rows_to_list(rows)


def transition_milestone(conn: sqlite3.Connection, milestone_id: str, new_status: str) -> dict:
    current = get_milestone(conn, milestone_id)
    if not current:
        raise ValueError(f"Milestone {milestone_id} not found")
    if new_status not in MILESTONE_TRANSITIONS.get(current["status"], []):
        raise StateTransitionError(
            f"Invalid transition: {current['status']} → {new_status}. "
            f"Valid: {MILESTONE_TRANSITIONS[current['status']]}"
        )
    updates = {"status": new_status}
    if new_status == "complete":
        updates["completed_at"] = _now()
    safe_update(conn, "milestone", milestone_id, updates)
    conn.commit()
    return get_milestone(conn, milestone_id)


# ── Phase CRUD ────────────────────────────────────────────────────────────────


def create_phase(
    conn: sqlite3.Connection,
    milestone_id: str,
    name: str,
    description: str | None = None,
    acceptance_criteria: list[str] | None = None,
    axis_ticket_id: str | None = None,
    sequence: int | None = None,
) -> dict:
    if sequence is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM phase WHERE milestone_id = ?",
            (milestone_id,),
        ).fetchone()
        sequence = row["next_seq"]
    conn.execute(
        """INSERT INTO phase
        (milestone_id, sequence, name, description, acceptance_criteria, axis_ticket_id)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            milestone_id,
            sequence,
            name,
            description,
            json.dumps(acceptance_criteria) if acceptance_criteria else None,
            axis_ticket_id,
        ),
    )
    conn.commit()
    return get_phase(conn, conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_phase(conn: sqlite3.Connection, phase_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM phase WHERE id = ?", (phase_id,)).fetchone()
    return _row_to_dict(row)


def list_phases(conn: sqlite3.Connection, milestone_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM phase WHERE milestone_id = ? ORDER BY sequence", (milestone_id,)
    ).fetchall()
    return _rows_to_list(rows)


def transition_phase(conn: sqlite3.Connection, phase_id: int, new_status: str) -> dict:
    current = get_phase(conn, phase_id)
    if not current:
        raise ValueError(f"Phase {phase_id} not found")
    if new_status not in PHASE_TRANSITIONS.get(current["status"], []):
        raise StateTransitionError(
            f"Invalid phase transition: {current['status']} → {new_status}. "
            f"Valid: {PHASE_TRANSITIONS[current['status']]}"
        )
    updates = {"status": new_status}
    if new_status == "executing" and not current["started_at"]:
        updates["started_at"] = _now()
    if new_status == "complete":
        updates["completed_at"] = _now()
    safe_update(conn, "phase", phase_id, updates)
    conn.commit()
    return get_phase(conn, phase_id)


def update_phase(conn: sqlite3.Connection, phase_id: int, **kwargs) -> dict | None:
    allowed = {"name", "description", "context_doc", "acceptance_criteria", "axis_ticket_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_phase(conn, phase_id)
    if "acceptance_criteria" in updates and isinstance(updates["acceptance_criteria"], list):
        updates["acceptance_criteria"] = json.dumps(updates["acceptance_criteria"])
    safe_update(conn, "phase", phase_id, updates)
    conn.commit()
    return get_phase(conn, phase_id)


# ── Plan CRUD ─────────────────────────────────────────────────────────────────


def create_plan(
    conn: sqlite3.Connection,
    phase_id: int,
    name: str,
    description: str,
    wave: int = 1,
    tdd_required: bool = True,
    files_to_create: list[str] | None = None,
    files_to_modify: list[str] | None = None,
    test_command: str | None = None,
    executor_type: str = "subagent",
    sequence: int | None = None,
) -> dict:
    if sequence is None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM plan WHERE phase_id = ?",
            (phase_id,),
        ).fetchone()
        sequence = row["next_seq"]
    conn.execute(
        """INSERT INTO plan (phase_id, sequence, name, description, wave, tdd_required,
        files_to_create, files_to_modify, test_command, executor_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            phase_id,
            sequence,
            name,
            description,
            wave,
            1 if tdd_required else 0,
            json.dumps(files_to_create) if files_to_create else None,
            json.dumps(files_to_modify) if files_to_modify else None,
            test_command,
            executor_type,
        ),
    )
    conn.commit()
    return get_plan(conn, conn.execute("SELECT last_insert_rowid()").fetchone()[0])


def get_plan(conn: sqlite3.Connection, plan_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM plan WHERE id = ?", (plan_id,)).fetchone()
    return _row_to_dict(row)


def list_plans(conn: sqlite3.Connection, phase_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM plan WHERE phase_id = ? ORDER BY wave, sequence", (phase_id,)
    ).fetchall()
    return _rows_to_list(rows)


def get_plans_by_wave(conn: sqlite3.Connection, phase_id: int, wave: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM plan WHERE phase_id = ? AND wave = ? ORDER BY sequence",
        (phase_id, wave),
    ).fetchall()
    return _rows_to_list(rows)


def transition_plan(
    conn: sqlite3.Connection,
    plan_id: int,
    new_status: str,
    commit_sha: str | None = None,
    error_message: str | None = None,
) -> dict:
    current = get_plan(conn, plan_id)
    if not current:
        raise ValueError(f"Plan {plan_id} not found")
    if new_status not in PLAN_TRANSITIONS.get(current["status"], []):
        raise StateTransitionError(
            f"Invalid plan transition: {current['status']} → {new_status}. "
            f"Valid: {PLAN_TRANSITIONS[current['status']]}"
        )
    updates = {"status": new_status}
    if new_status == "executing" and not current["started_at"]:
        updates["started_at"] = _now()
    if new_status == "complete":
        updates["completed_at"] = _now()
    if commit_sha:
        updates["commit_sha"] = commit_sha
    if error_message:
        updates["error_message"] = error_message
    safe_update(conn, "plan", plan_id, updates)
    conn.commit()
    return get_plan(conn, plan_id)


def update_plan(conn: sqlite3.Connection, plan_id: int, **kwargs) -> dict | None:
    allowed = {
        "name",
        "description",
        "wave",
        "tdd_required",
        "files_to_create",
        "files_to_modify",
        "test_command",
        "executor_type",
    }
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_plan(conn, plan_id)
    for field in ("files_to_create", "files_to_modify"):
        if field in updates and isinstance(updates[field], list):
            updates[field] = json.dumps(updates[field])
    if "tdd_required" in updates and isinstance(updates["tdd_required"], bool):
        updates["tdd_required"] = 1 if updates["tdd_required"] else 0
    safe_update(conn, "plan", plan_id, updates)
    conn.commit()
    return get_plan(conn, plan_id)


# ── Checkpoint CRUD ───────────────────────────────────────────────────────────


def create_checkpoint(
    conn: sqlite3.Connection,
    trigger: str,
    project_id: str = "default",
    milestone_id: str | None = None,
    phase_id: int | None = None,
    plan_id: int | None = None,
    plan_status: str | None = None,
    decisions: list[dict] | None = None,
    blockers: list[str] | None = None,
    notes: str | None = None,
    estimated_tokens_used: int | None = None,
    repo_path: str | None = None,
) -> dict:
    git_branch, git_sha, git_dirty = _get_git_state(repo_path)
    conn.execute(
        """INSERT INTO checkpoint
        (project_id, trigger, milestone_id, phase_id, plan_id,
        plan_status, decisions, blockers, notes,
        git_branch, git_sha, git_dirty, estimated_tokens_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            project_id,
            trigger,
            milestone_id,
            phase_id,
            plan_id,
            plan_status,
            json.dumps(decisions) if decisions else None,
            json.dumps(blockers) if blockers else None,
            notes,
            git_branch,
            git_sha,
            1 if git_dirty else 0,
            estimated_tokens_used,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM checkpoint WHERE id = last_insert_rowid()").fetchone()
    return _row_to_dict(row)


def get_latest_checkpoint(conn: sqlite3.Connection, project_id: str = "default") -> dict | None:
    row = conn.execute(
        "SELECT * FROM checkpoint WHERE project_id = ? ORDER BY id DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    return _row_to_dict(row)


def list_checkpoints(
    conn: sqlite3.Connection, project_id: str = "default", limit: int = 10
) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM checkpoint WHERE project_id = ? ORDER BY id DESC LIMIT ?",
        (project_id, limit),
    ).fetchall()
    return _rows_to_list(rows)


# ── Decision CRUD ─────────────────────────────────────────────────────────────


def create_decision(
    conn: sqlite3.Connection,
    summary: str,
    category: str = "approach",
    rationale: str | None = None,
    project_id: str = "default",
    phase_id: int | None = None,
) -> dict:
    conn.execute(
        "INSERT INTO decision (project_id, phase_id, category, summary, rationale)"
        " VALUES (?, ?, ?, ?, ?)",
        (project_id, phase_id, category, summary, rationale),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM decision WHERE id = last_insert_rowid()").fetchone()
    return _row_to_dict(row)


def list_decisions(
    conn: sqlite3.Connection,
    project_id: str = "default",
    phase_id: int | None = None,
    limit: int = 20,
) -> list[dict]:
    if phase_id:
        rows = conn.execute(
            "SELECT * FROM decision WHERE project_id = ? AND phase_id = ? ORDER BY id DESC LIMIT ?",
            (project_id, phase_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decision WHERE project_id = ? ORDER BY id DESC LIMIT ?",
            (project_id, limit),
        ).fetchall()
    return _rows_to_list(rows)


# ── Quick Task CRUD ───────────────────────────────────────────────────────────


def create_quick_task(
    conn: sqlite3.Connection,
    description: str,
    project_id: str = "default",
) -> dict:
    conn.execute(
        "INSERT INTO quick_task (project_id, description) VALUES (?, ?)",
        (project_id, description),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM quick_task WHERE id = last_insert_rowid()").fetchone()
    return _row_to_dict(row)


def transition_quick_task(
    conn: sqlite3.Connection,
    task_id: int,
    new_status: str,
    commit_sha: str | None = None,
) -> dict:
    valid = {"pending": ["executing"], "executing": ["complete", "failed"]}
    current = conn.execute("SELECT * FROM quick_task WHERE id = ?", (task_id,)).fetchone()
    if not current:
        raise ValueError(f"Quick task {task_id} not found")
    if new_status not in valid.get(current["status"], []):
        raise StateTransitionError(f"Invalid quick task transition: {current['status']} → {new_status}")
    updates = {"status": new_status}
    if new_status == "complete":
        updates["completed_at"] = _now()
    if commit_sha:
        updates["commit_sha"] = commit_sha
    safe_update(conn, "quick_task", task_id, updates)
    conn.commit()
    row = conn.execute("SELECT * FROM quick_task WHERE id = ?", (task_id,)).fetchone()
    return _row_to_dict(row)


# ── Nero Dispatch CRUD ────────────────────────────────────────────────────────


def create_nero_dispatch(
    conn: sqlite3.Connection,
    dispatch_type: str,
    plan_id: int | None = None,
    phase_id: int | None = None,
    nero_task_id: str | None = None,
) -> dict:
    conn.execute(
        "INSERT INTO nero_dispatch"
        " (plan_id, phase_id, dispatch_type, nero_task_id)"
        " VALUES (?, ?, ?, ?)",
        (plan_id, phase_id, dispatch_type, nero_task_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM nero_dispatch WHERE id = last_insert_rowid()").fetchone()
    return _row_to_dict(row)


def update_nero_dispatch(
    conn: sqlite3.Connection,
    dispatch_id: int,
    status: str | None = None,
    pr_url: str | None = None,
) -> dict:
    updates = {}
    if status is not None:
        updates["status"] = status
    if pr_url is not None:
        updates["pr_url"] = pr_url
    if status in ("completed", "failed"):
        updates["completed_at"] = _now()
    if updates:
        safe_update(conn, "nero_dispatch", dispatch_id, updates)
        conn.commit()
    row = conn.execute("SELECT * FROM nero_dispatch WHERE id = ?", (dispatch_id,)).fetchone()
    return _row_to_dict(row)


VALID_PRIORITIES = ("critical", "high", "medium", "low")


# ── Auto-Advancement ─────────────────────────────────────────────────────────


def check_auto_advance(conn: sqlite3.Connection, phase_id: int) -> dict:
    """Check if post-action auto-advancement should trigger.

    Call after plan completion. Returns {action, message} describing what was done.

    Logic:
    - All plans complete/skipped → auto-transition phase to 'verifying'
    - All phases in milestone complete → flag milestone for completion
    """
    phase = get_phase(conn, phase_id)
    if not phase:
        return {"action": "none", "message": f"Phase {phase_id} not found"}

    # Only auto-advance from executing state
    if phase["status"] != "executing":
        return {"action": "none", "message": f"Phase not in executing state ({phase['status']})"}

    plans = list_plans(conn, phase_id)
    if not plans:
        return {"action": "none", "message": "No plans in phase"}

    # Check if all plans are terminal (complete or skipped)
    non_terminal = [p for p in plans if p["status"] not in ("complete", "skipped")]
    if non_terminal:
        remaining = len(non_terminal)
        return {
            "action": "none",
            "message": f"{remaining} plan(s) still pending/executing",
        }

    # All plans done → advance phase to verifying
    transition_phase(conn, phase_id, "verifying")
    result = {
        "action": "phase_to_verifying",
        "message": f"All plans complete — phase '{phase['name']}' auto-advanced to verifying",
        "phase_id": phase_id,
    }

    # Check if all phases in milestone are complete (after this one finishes review)
    milestone_id = phase["milestone_id"]
    # Re-fetch after transition so current phase shows "verifying" status
    all_phases = list_phases(conn, milestone_id)
    incomplete = [p for p in all_phases if p["status"] != "complete"]
    if not incomplete:
        result["milestone_ready"] = True
        result["message"] += " — milestone may be ready for completion after review"

    return result


def add_priority(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: int,
    priority: str,
) -> dict:
    """Set priority on a phase or plan.

    Args:
        entity_type: 'phase' or 'plan'
        entity_id: ID of the entity
        priority: 'critical', 'high', 'medium', or 'low'

    Returns the updated entity dict.
    """
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority '{priority}'. Valid: {VALID_PRIORITIES}")
    sql = _PRIORITY_SQL.get(entity_type)
    if sql is None:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'phase' or 'plan'.")

    conn.execute(sql, (priority, entity_id))
    conn.commit()

    if entity_type == "phase":
        return get_phase(conn, entity_id)
    return get_plan(conn, entity_id)


# ── Next Action Computation ───────────────────────────────────────────────────


def compute_next_action(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Compute the next action based on current state. Returns action type + context."""

    # Find active milestone
    milestone = conn.execute(
        "SELECT * FROM milestone WHERE project_id = ? AND status = 'active'"
        " ORDER BY created_at LIMIT 1",
        (project_id,),
    ).fetchone()

    if not milestone:
        # Check for planned milestones
        planned = conn.execute(
            "SELECT * FROM milestone WHERE project_id = ? AND status = 'planned'"
            " ORDER BY created_at LIMIT 1",
            (project_id,),
        ).fetchone()
        if planned:
            return {
                "action": "activate_milestone",
                "message": (
                    f"Milestone '{planned['name']}' is planned but not active."
                    " Activate it to begin."
                ),
                "milestone_id": planned["id"],
            }
        return {
            "action": "create_milestone",
            "message": "No milestones exist. Create one with /meridian:plan.",
        }

    # Find current phase (first non-complete phase in sequence order)
    phase = conn.execute(
        """SELECT * FROM phase WHERE milestone_id = ? AND status NOT IN ('complete', 'blocked')
        ORDER BY sequence LIMIT 1""",
        (milestone["id"],),
    ).fetchone()

    if not phase:
        # Check if all phases are complete
        incomplete = conn.execute(
            "SELECT COUNT(*) as cnt FROM phase WHERE milestone_id = ? AND status != 'complete'",
            (milestone["id"],),
        ).fetchone()
        if incomplete["cnt"] == 0:
            phases_exist = conn.execute(
                "SELECT COUNT(*) as cnt FROM phase WHERE milestone_id = ?",
                (milestone["id"],),
            ).fetchone()
            if phases_exist["cnt"] > 0:
                return {
                    "action": "complete_milestone",
                    "message": f"All phases in milestone '{milestone['name']}' are complete.",
                    "milestone_id": milestone["id"],
                }
        # Check for blocked phases
        blocked = conn.execute(
            "SELECT * FROM phase WHERE milestone_id = ? AND status = 'blocked'"
            " ORDER BY sequence LIMIT 1",
            (milestone["id"],),
        ).fetchone()
        if blocked:
            return {
                "action": "unblock_phase",
                "message": f"Phase {blocked['sequence']}: '{blocked['name']}' is blocked.",
                "phase_id": blocked["id"],
            }
        return {
            "action": "create_phases",
            "message": f"Milestone '{milestone['name']}' has no phases. Run /meridian:plan.",
            "milestone_id": milestone["id"],
        }

    phase = dict(phase)

    # Route based on phase status
    if phase["status"] == "planned":
        return {
            "action": "gather_context",
            "message": f"Phase {phase['sequence']}: '{phase['name']}' needs context gathering.",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
        }

    if phase["status"] == "context_gathered":
        return {
            "action": "create_plans",
            "message": f"Phase {phase['sequence']}: '{phase['name']}' has context, needs plans.",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
        }

    if phase["status"] == "planned_out":
        return {
            "action": "execute",
            "message": f"Phase {phase['sequence']}: '{phase['name']}' is ready to execute.",
            "phase_id": phase["id"],
            "phase_name": phase["name"],
        }

    if phase["status"] == "executing":
        # Find next pending plan
        plan = conn.execute(
            "SELECT * FROM plan WHERE phase_id = ? AND status = 'pending'"
            " ORDER BY wave, sequence LIMIT 1",
            (phase["id"],),
        ).fetchone()

        if plan:
            # Check if earlier wave plans are still running
            earlier_running = conn.execute(
                """SELECT COUNT(*) as cnt FROM plan
                WHERE phase_id = ? AND wave < ? AND status IN ('executing', 'paused')""",
                (phase["id"], plan["wave"]),
            ).fetchone()
            if earlier_running["cnt"] > 0:
                return {
                    "action": "wait_for_wave",
                    "message": (
                        f"Wave {plan['wave'] - 1} plans still executing. Wait for completion."
                    ),
                    "phase_id": phase["id"],
                }
            return {
                "action": "execute_plan",
                "message": f"Execute plan: '{plan['name']}' (wave {plan['wave']}).",
                "phase_id": phase["id"],
                "plan_id": plan["id"],
                "plan_name": plan["name"],
                "wave": plan["wave"],
            }

        # Check for failed plans
        failed = conn.execute(
            "SELECT * FROM plan WHERE phase_id = ? AND status = 'failed' ORDER BY sequence LIMIT 1",
            (phase["id"],),
        ).fetchone()
        if failed:
            return {
                "action": "fix_failed_plan",
                "message": (
                    f"Plan '{failed['name']}' failed: {failed['error_message'] or 'unknown error'}"
                ),
                "phase_id": phase["id"],
                "plan_id": failed["id"],
            }

        # All plans complete or skipped — move to verifying
        return {
            "action": "verify_phase",
            "message": (
                f"All plans in phase '{phase['name']}' are done. Verify acceptance criteria."
            ),
            "phase_id": phase["id"],
        }

    if phase["status"] == "verifying":
        return {
            "action": "review_phase",
            "message": f"Phase '{phase['name']}' verified. Run two-stage review.",
            "phase_id": phase["id"],
        }

    if phase["status"] == "reviewing":
        return {
            "action": "complete_phase",
            "message": f"Phase '{phase['name']}' reviewed. Mark complete if review passed.",
            "phase_id": phase["id"],
        }

    return {
        "action": "unknown",
        "message": f"Phase '{phase['name']}' is in unexpected state: {phase['status']}",
        "phase_id": phase["id"],
    }


# ── Status Summary ────────────────────────────────────────────────────────────


def get_status(conn: sqlite3.Connection, project_id: str = "default") -> dict:
    """Get a full status summary for the project."""
    project = get_project(conn, project_id)
    if not project:
        return {"error": "Project not initialized. Run /meridian:init."}

    milestones = list_milestones(conn, project_id)
    active_milestone = next((m for m in milestones if m["status"] == "active"), None)

    phases = []
    current_phase = None
    if active_milestone:
        phases = list_phases(conn, active_milestone["id"])
        current_phase = next(
            (p for p in phases if p["status"] not in ("complete", "blocked")), None
        )

    plans = []
    if current_phase:
        plans = list_plans(conn, current_phase["id"])

    next_action = compute_next_action(conn, project_id)
    latest_checkpoint = get_latest_checkpoint(conn, project_id)
    recent_decisions = list_decisions(conn, project_id, limit=5)

    return {
        "project": project,
        "milestones": milestones,
        "active_milestone": active_milestone,
        "phases": phases,
        "current_phase": current_phase,
        "plans": plans,
        "next_action": next_action,
        "latest_checkpoint": latest_checkpoint,
        "recent_decisions": recent_decisions,
    }


# ── Git Helpers ───────────────────────────────────────────────────────────────


def _get_git_state(repo_path: str | None = None) -> tuple[str | None, str | None, bool]:
    """Get current git branch, SHA, and dirty state."""
    cwd = repo_path or str(Path.cwd())
    try:
        branch = (
            subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=cwd,
            ).stdout.strip()
            or None
        )
        sha = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=cwd
            ).stdout.strip()
            or None
        )
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=cwd
            ).stdout.strip()
        )
        return branch, sha, dirty
    except Exception:
        return None, None, False
