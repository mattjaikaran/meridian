#!/usr/bin/env python3
"""Meridian next-action workflow advancement — detect state and suggest next step."""

import sqlite3

from scripts.state import compute_next_action, get_project

# Maps compute_next_action() action types to user-facing commands and messages
ACTION_MAP: dict[str, dict] = {
    "create_milestone": {
        "command": "/meridian:init",
        "label": "Initialize project",
        "description": "No project or milestones found. Run /meridian:init to get started.",
        "destructive": False,
    },
    "activate_milestone": {
        "command": "/meridian:plan",
        "label": "Activate milestone",
        "description": "A milestone is planned but not active. Activate it to begin work.",
        "destructive": False,
    },
    "create_phases": {
        "command": "/meridian:plan",
        "label": "Create phases",
        "description": "Milestone is active but has no phases. Run /meridian:plan to create them.",
        "destructive": False,
    },
    "gather_context": {
        "command": "/meridian:plan",
        "label": "Gather context",
        "description": "Phase needs context gathering before planning.",
        "destructive": False,
    },
    "create_plans": {
        "command": "/meridian:plan",
        "label": "Create plans",
        "description": "Phase has context, needs execution plans.",
        "destructive": False,
    },
    "execute": {
        "command": "/meridian:execute",
        "label": "Start execution",
        "description": "Phase is planned out and ready to execute.",
        "destructive": False,
    },
    "execute_plan": {
        "command": "/meridian:execute",
        "label": "Execute plan",
        "description": "Continue executing the current plan.",
        "destructive": False,
    },
    "verify_phase": {
        "command": "/meridian:execute",
        "label": "Run verification",
        "description": "Phase execution complete. Run verification step.",
        "destructive": False,
    },
    "review_phase": {
        "command": "/meridian:review",
        "label": "Review phase",
        "description": "Phase verified. Run two-stage review.",
        "destructive": False,
    },
    "complete_phase": {
        "command": "/meridian:execute",
        "label": "Complete phase",
        "description": "Phase reviewed. Mark complete if review passed.",
        "destructive": False,
    },
    "complete_milestone": {
        "command": "/meridian:ship",
        "label": "Complete milestone",
        "description": "All phases complete. Close the milestone.",
        "destructive": True,
    },
    "unblock_phase": {
        "command": "/meridian:status",
        "label": "Unblock phase",
        "description": "A phase is blocked. Review and resolve the blocker.",
        "destructive": False,
    },
}


def determine_next_step(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> dict:
    """Determine the next workflow step based on current state.

    Wraps compute_next_action() with a user-facing layer that maps
    internal actions to /meridian:* commands.

    Args:
        conn: Database connection.
        project_id: Project identifier.

    Returns:
        Dict with action, command, label, description, context, destructive.
    """
    # Check if project exists
    project = get_project(conn, project_id)
    if not project:
        return {
            "action": "no_project",
            "command": "/meridian:init",
            "label": "Initialize project",
            "description": "No project initialized. Run /meridian:init to get started.",
            "context": {},
            "destructive": False,
        }

    # Get the raw next action from state.py
    raw_action = compute_next_action(conn, project_id)
    action_type = raw_action.get("action", "unknown")

    # Look up the mapping
    mapping = ACTION_MAP.get(action_type)

    if mapping:
        result = {
            "action": action_type,
            "command": mapping["command"],
            "label": mapping["label"],
            "description": mapping["description"],
            "context": raw_action,
            "destructive": mapping["destructive"],
        }

        # Enrich with specific context
        if "phase_name" in raw_action:
            result["description"] = (
                f"{mapping['description']} (Phase: {raw_action['phase_name']})"
            )
        if "plan_name" in raw_action:
            result["description"] += f" Plan: {raw_action['plan_name']}"

        return result

    # Fallback for unknown/idle states
    return {
        "action": action_type,
        "command": "/meridian:note",
        "label": "All caught up",
        "description": (
            f"Current state: {raw_action.get('message', 'unknown')}. "
            "Use /meridian:note to capture ideas."
        ),
        "context": raw_action,
        "destructive": False,
    }


def format_next_action(step: dict) -> str:
    """Format a next-step dict into a human-readable string.

    Args:
        step: Dict from determine_next_step().

    Returns:
        Formatted multi-line string.
    """
    lines: list[str] = []
    lines.append(f"## Next: {step['label']}")
    lines.append("")
    lines.append(f"**Command:** `{step['command']}`")
    lines.append(f"**Action:** {step['description']}")

    if step["destructive"]:
        lines.append("")
        lines.append("**Warning:** This is a destructive action. Confirm before proceeding.")

    # Add context details if available
    context = step.get("context", {})
    if context.get("phase_id"):
        lines.append(f"**Phase ID:** {context['phase_id']}")
    if context.get("milestone_id"):
        lines.append(f"**Milestone:** {context['milestone_id']}")
    if context.get("plan_name"):
        lines.append(f"**Plan:** {context['plan_name']}")
    if context.get("wave"):
        lines.append(f"**Wave:** {context['wave']}")

    return "\n".join(lines)
