#!/usr/bin/env python3
"""Nero HTTP dispatch client — sends plans to Mac Mini for autonomous execution."""

import json
import urllib.error
import urllib.request
from pathlib import Path

from scripts.db import open_project
from scripts.state import (
    create_nero_dispatch,
    get_phase,
    get_plan,
    get_project,
    list_plans,
    update_nero_dispatch,
)


def dispatch_plan(
    project_dir: str | Path | None = None,
    plan_id: int | None = None,
    project_id: str = "default",
) -> dict:
    """Dispatch a single plan to Nero for autonomous execution."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn, project_id)
        if not project:
            raise ValueError("Project not initialized")
        if not project.get("nero_endpoint"):
            raise ValueError("No nero_endpoint configured. Set it with /meridian:init.")

        plan = get_plan(conn, plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        phase = get_phase(conn, plan["phase_id"])

        # Build dispatch payload
        payload = {
            "method": "dispatch_task",
            "params": {
                "type": "implement",
                "project": {
                    "name": project["name"],
                    "repo_path": project["repo_path"],
                    "repo_url": project.get("repo_url"),
                    "tech_stack": (
                        json.loads(project["tech_stack"]) if project.get("tech_stack") else []
                    ),
                },
                "phase": {
                    "name": phase["name"],
                    "description": phase.get("description"),
                },
                "plan": {
                    "name": plan["name"],
                    "description": plan["description"],
                    "files_to_create": (
                        json.loads(plan["files_to_create"]) if plan.get("files_to_create") else []
                    ),
                    "files_to_modify": (
                        json.loads(plan["files_to_modify"]) if plan.get("files_to_modify") else []
                    ),
                    "test_command": plan.get("test_command"),
                    "tdd_required": bool(plan.get("tdd_required")),
                },
                "context": phase.get("context_doc"),
            },
        }

        # Send to Nero
        endpoint = project["nero_endpoint"].rstrip("/")
        url = f"{endpoint}/rpc"

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            return {
                "status": "error",
                "message": f"Failed to connect to Nero at {url}: {e}",
            }

        # Record dispatch
        nero_task_id = result.get("task_id")
        dispatch = create_nero_dispatch(
            conn,
            dispatch_type="plan",
            plan_id=plan_id,
            phase_id=plan["phase_id"],
            nero_task_id=nero_task_id,
        )

        return {
            "status": "dispatched",
            "dispatch_id": dispatch["id"],
            "nero_task_id": nero_task_id,
            "plan_name": plan["name"],
        }


def dispatch_phase(
    project_dir: str | Path | None = None,
    phase_id: int | None = None,
    project_id: str = "default",
    swarm: bool = False,
) -> list[dict]:
    """Dispatch all pending plans in a phase to Nero.

    If swarm=True, dispatch all at once (parallel PRs).
    If swarm=False, dispatch one at a time respecting wave order.
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        plans = list_plans(conn, phase_id)
        pending = [p for p in plans if p["status"] == "pending"]

        if not pending:
            return [{"status": "info", "message": "No pending plans to dispatch"}]

        if not swarm:
            # Only dispatch wave 1 pending plans (or lowest wave with pending)
            min_wave = min(p["wave"] for p in pending)
            pending = [p for p in pending if p["wave"] == min_wave]

        results = []
        for plan in pending:
            result = dispatch_plan(project_dir, plan["id"], project_id)
            results.append(result)

        return results


def check_dispatch_status(
    project_dir: str | Path | None = None,
    dispatch_id: int | None = None,
    project_id: str = "default",
) -> dict:
    """Check the status of a Nero dispatch."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    with open_project(project_dir) as conn:
        project = get_project(conn, project_id)
        if not project or not project.get("nero_endpoint"):
            return {"status": "error", "message": "Nero not configured"}

        row = conn.execute("SELECT * FROM nero_dispatch WHERE id = ?", (dispatch_id,)).fetchone()
        if not row:
            return {"status": "error", "message": f"Dispatch {dispatch_id} not found"}

        dispatch = dict(row)

        # Check with Nero if still in progress
        if dispatch["status"] in ("dispatched", "accepted", "running"):
            endpoint = project["nero_endpoint"].rstrip("/")
            url = f"{endpoint}/rpc"
            payload = {
                "method": "get_task_status",
                "params": {"task_id": dispatch["nero_task_id"]},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    new_status = result.get("status")
                    pr_url = result.get("pr_url")
                    if new_status and new_status != dispatch["status"]:
                        dispatch = update_nero_dispatch(
                            conn, dispatch_id, status=new_status, pr_url=pr_url
                        )
            except urllib.error.URLError:
                pass  # Can't reach Nero, return cached status

        return dispatch
