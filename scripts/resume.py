#!/usr/bin/env python3
"""Deterministic resume prompt generator.

Queries SQLite, produces identical prompt for identical state.
"""

import json
import subprocess
import textwrap
from pathlib import Path

from scripts.db import connect, get_db_path
from scripts.state import (
    compute_next_action,
    get_latest_checkpoint,
    get_project,
    list_decisions,
    list_milestones,
    list_phases,
    list_plans,
)


def _get_git_log(repo_path: str, count: int = 10) -> str:
    """Get recent git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", f"-{count}"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        return result.stdout.strip() or "(no commits)"
    except Exception:
        return "(git unavailable)"


def _get_git_branch(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _get_git_sha(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def generate_resume_prompt(
    project_dir: str | Path | None = None,
    project_id: str = "default",
) -> str:
    """Generate a deterministic resume prompt from SQLite state.

    Same state = same prompt. No LLM-written prose. Every field is a discrete DB query.
    """
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)

    db_path = get_db_path(project_dir)
    if not db_path.exists():
        return "# Meridian Resume\n\nProject not initialized. Run `/meridian:init`."

    conn = connect(db_path)

    try:
        try:
            project = get_project(conn, project_id)
        except Exception:
            project = None
        if not project:
            return "# Meridian Resume\n\nProject not initialized. Run `/meridian:init`."

        # Find active milestone
        milestones = list_milestones(conn, project_id)
        active_milestone = next((m for m in milestones if m["status"] == "active"), None)

        if not active_milestone:
            return textwrap.dedent(f"""\
                # Meridian Resume — {project["name"]}

                ## Position
                No active milestone. Create one with `/meridian:plan`.

                ## Project
                - Path: {project["repo_path"]}
                - Tech: {project.get("tech_stack", "not set")}
            """)

        # Get phases
        phases = list_phases(conn, active_milestone["id"])
        current_phase = next((p for p in phases if p["status"] not in ("complete",)), None)

        # Get plans for current phase
        plans = []
        completed_plans = []
        pending_plans = []
        if current_phase:
            plans = list_plans(conn, current_phase["id"])
            completed_plans = [p for p in plans if p["status"] == "complete"]
            pending_plans = [p for p in plans if p["status"] in ("pending", "paused", "failed")]

        # Get decisions
        recent_decisions = list_decisions(conn, project_id, limit=10)

        # Get checkpoint
        checkpoint = get_latest_checkpoint(conn, project_id)

        # Compute next action
        next_action = compute_next_action(conn, project_id)

        # Git state
        repo_path = str(project_dir)
        git_branch = _get_git_branch(repo_path)
        git_sha = _get_git_sha(repo_path)
        git_log = _get_git_log(repo_path)

        # Build prompt
        sections = []

        # Header
        sections.append(f"# Meridian Resume — {project['name']}")
        sections.append("")

        # Position
        sections.append("## Position")
        sections.append(f"- Milestone: {active_milestone['name']} ({active_milestone['status']})")
        if current_phase:
            phase_seq = current_phase["sequence"]
            phase_name = current_phase["name"]
            phase_status = current_phase["status"]
            sections.append(f"- Phase {phase_seq}: {phase_name} ({phase_status})")
            if plans:
                executing = [p for p in plans if p["status"] == "executing"]
                if executing:
                    sections.append(f"- Current plan: {executing[0]['name']} (executing)")
                elif pending_plans:
                    sections.append(f"- Next plan: {pending_plans[0]['name']} (pending)")
        sections.append("")

        # Phase progress overview
        sections.append("## Phase Overview")
        for p in phases:
            marker = "→" if current_phase and p["id"] == current_phase["id"] else " "
            phase_plans = list_plans(conn, p["id"])
            plan_count = len(phase_plans)
            complete_count = len([pl for pl in phase_plans if pl["status"] == "complete"])
            sections.append(
                f"{marker} Phase {p['sequence']}: {p['name']}"
                f" [{p['status']}] ({complete_count}/{plan_count} plans)"
            )
        sections.append("")

        # Current phase detail
        if current_phase:
            sections.append(f"## Current Phase: {current_phase['name']}")
            if current_phase.get("description"):
                sections.append(current_phase["description"])
            sections.append("")

            # Acceptance criteria
            if current_phase.get("acceptance_criteria"):
                sections.append("## Acceptance Criteria")
                try:
                    criteria = json.loads(current_phase["acceptance_criteria"])
                    for c in criteria:
                        sections.append(f"- [ ] {c}")
                except (json.JSONDecodeError, TypeError):
                    sections.append(f"- {current_phase['acceptance_criteria']}")
                sections.append("")

            # Completed plans
            if completed_plans:
                sections.append("## Completed in This Phase")
                for p in completed_plans:
                    sha = f" (commit: {p['commit_sha'][:8]})" if p.get("commit_sha") else ""
                    sections.append(f"- {p['name']}{sha}")
                sections.append("")

            # Remaining plans
            if pending_plans:
                sections.append("## Remaining Plans")
                for p in pending_plans:
                    status_note = f" **[{p['status']}]**" if p["status"] != "pending" else ""
                    error = f" — Error: {p['error_message']}" if p.get("error_message") else ""
                    sections.append(f"- Wave {p['wave']}: {p['name']}{status_note}{error}")
                    if p.get("description"):
                        # First 200 chars of description
                        desc = p["description"][:200]
                        if len(p["description"]) > 200:
                            desc += "..."
                        sections.append(f"  > {desc}")
                sections.append("")

        # Decisions
        if recent_decisions:
            sections.append("## Key Decisions (Recent)")
            for d in recent_decisions[:5]:
                sections.append(f"- [{d['category']}] {d['summary']}")
            sections.append("")

        # Blockers
        if checkpoint and checkpoint.get("blockers"):
            try:
                blockers = json.loads(checkpoint["blockers"])
                if blockers:
                    sections.append("## Blockers")
                    for b in blockers:
                        sections.append(f"- {b}")
                    sections.append("")
            except (json.JSONDecodeError, TypeError):
                pass

        # Git state
        sections.append("## Git State")
        sections.append(f"Branch: {git_branch}, SHA: {git_sha}")
        sections.append("Recent commits:")
        for line in git_log.split("\n")[:5]:
            sections.append(f"  {line}")
        sections.append("")

        # Next action
        sections.append("## Next Action")
        sections.append(f"→ {next_action['message']}")
        if next_action.get("action") == "execute_plan":
            sections.append(f"  Plan: {next_action.get('plan_name', 'unknown')}")
            sections.append(f"  Wave: {next_action.get('wave', '?')}")

        return "\n".join(sections)

    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    print(generate_resume_prompt(project_dir))
