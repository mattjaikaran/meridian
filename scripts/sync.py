#!/usr/bin/env python3
"""Bidirectional Nero sync — pull dispatch status and push state for scheduling."""

import json
import logging
import sqlite3
import urllib.request

from scripts.db import NeroUnreachableError, open_project, retry_on_http_error
from scripts.state import (
    get_plan,
    get_project,
    list_phases,
    list_plans,
    transition_plan,
    update_nero_dispatch,
)

logger = logging.getLogger(__name__)


@retry_on_http_error(max_retries=3, base_delay=1.0)
def _nero_rpc(endpoint: str, method: str, params: dict, timeout: int = 10) -> dict:
    """Make an RPC call to Nero. Returns response dict.

    Retries on transient HTTP/network errors. Raises NeroUnreachableError
    after exhausting retries.
    """
    url = f"{endpoint.rstrip('/')}/rpc"
    payload = {"method": method, "params": params}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def pull_dispatch_status(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> list[dict]:
    """Poll all active nero_dispatch records and update local state.

    When Nero reports completion, auto-transition the associated plan.
    When Nero reports failure, mark the plan as failed.

    Returns list of updates applied.
    """
    project = get_project(conn, project_id)
    if not project or not project.get("nero_endpoint"):
        return [{"status": "skipped", "message": "No nero_endpoint configured"}]

    endpoint = project["nero_endpoint"]

    # Get all in-progress dispatches
    rows = conn.execute(
        """
        SELECT * FROM nero_dispatch
        WHERE status IN ('dispatched', 'accepted', 'running')
        ORDER BY dispatched_at
        """
    ).fetchall()

    updates = []
    for row in rows:
        dispatch = dict(row)
        if not dispatch.get("nero_task_id"):
            continue

        try:
            result = _nero_rpc(endpoint, "get_task_status", {"task_id": dispatch["nero_task_id"]})
        except NeroUnreachableError:
            updates.append(
                {
                    "dispatch_id": dispatch["id"],
                    "status": "unreachable",
                    "message": "Could not reach Nero",
                }
            )
            continue

        new_status = result.get("status")
        pr_url = result.get("pr_url")

        if not new_status or new_status == dispatch["status"]:
            continue

        # Update dispatch record
        update_nero_dispatch(conn, dispatch["id"], status=new_status, pr_url=pr_url)

        update_record = {
            "dispatch_id": dispatch["id"],
            "old_status": dispatch["status"],
            "new_status": new_status,
            "pr_url": pr_url,
        }

        # Auto-transition associated plan
        if dispatch.get("plan_id"):
            plan = get_plan(conn, dispatch["plan_id"])
            if plan and plan["status"] == "executing":
                if new_status == "completed":
                    commit_sha = result.get("commit_sha")
                    transition_plan(conn, plan["id"], "complete", commit_sha=commit_sha)
                    update_record["plan_transitioned"] = "complete"
                elif new_status in ("failed", "rejected"):
                    error_msg = result.get("error", f"Nero dispatch {new_status}")
                    transition_plan(conn, plan["id"], "failed", error_message=error_msg)
                    update_record["plan_transitioned"] = "failed"

        updates.append(update_record)

    return updates


def push_state_to_nero(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> dict:
    """Export current state in Nero's AI-Agent-Ready ticket format.

    Pushes active work items so Nero's PM agent can schedule and prioritize.

    Returns {status, tickets_pushed} or error.
    """
    project = get_project(conn, project_id)
    if not project or not project.get("nero_endpoint"):
        return {"status": "skipped", "message": "No nero_endpoint configured"}

    endpoint = project["nero_endpoint"]

    # Build ticket list from active milestone
    milestone = conn.execute(
        "SELECT * FROM milestone WHERE project_id = ? AND status = 'active' LIMIT 1",
        (project_id,),
    ).fetchone()

    if not milestone:
        return {"status": "skipped", "message": "No active milestone"}

    phases = list_phases(conn, milestone["id"])
    tickets = []

    for phase in phases:
        if phase["status"] == "complete":
            continue

        plans = list_plans(conn, phase["id"])
        pending_plans = [p for p in plans if p["status"] in ("pending", "failed")]

        for plan in pending_plans:
            ticket = {
                "type": "implement",
                "project": project["name"],
                "milestone": milestone["name"],
                "phase": phase["name"],
                "plan_id": plan["id"],
                "name": plan["name"],
                "description": plan["description"],
                "priority": plan.get("priority") or phase.get("priority") or "medium",
                "wave": plan["wave"],
                "tdd_required": bool(plan.get("tdd_required")),
                "files_to_create": (
                    json.loads(plan["files_to_create"]) if plan.get("files_to_create") else []
                ),
                "files_to_modify": (
                    json.loads(plan["files_to_modify"]) if plan.get("files_to_modify") else []
                ),
                "test_command": plan.get("test_command"),
                "context": phase.get("context_doc"),
            }
            tickets.append(ticket)

    if not tickets:
        return {"status": "ok", "tickets_pushed": 0, "message": "No pending work to push"}

    result = _nero_rpc(
        endpoint,
        "sync_tickets",
        {"project": project["name"], "tickets": tickets},
        timeout=30,
    )

    return {
        "status": "ok",
        "tickets_pushed": len(tickets),
        "nero_response": result,
    }


def sync_all(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> dict:
    """Full bidirectional sync: pull status updates, then push current state.

    Returns {pull_results, push_result}.
    """
    pull_results = pull_dispatch_status(conn, project_id)
    push_result = push_state_to_nero(conn, project_id)

    return {
        "pull_results": pull_results,
        "push_result": push_result,
    }


def get_dispatch_summary(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> list[dict]:
    """Get a summary of all dispatches for the active milestone.

    Returns list of dispatch records with plan names and phase context.
    """
    milestone = conn.execute(
        "SELECT id FROM milestone WHERE project_id = ? AND status = 'active' LIMIT 1",
        (project_id,),
    ).fetchone()

    if not milestone:
        return []

    rows = conn.execute(
        """
        SELECT nd.*, p.name as plan_name, ph.name as phase_name
        FROM nero_dispatch nd
        LEFT JOIN plan p ON nd.plan_id = p.id
        LEFT JOIN phase ph ON nd.phase_id = ph.id
        WHERE ph.milestone_id = ?
        ORDER BY nd.dispatched_at DESC
        """,
        (milestone["id"],),
    ).fetchall()

    return [dict(r) for r in rows]


if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    with open_project(project_dir) as conn:
        result = sync_all(conn)
        print(json.dumps(result, indent=2, default=str))
