#!/usr/bin/env python3
"""Model profile management — map agent types to model tiers per profile."""

import logging
import sqlite3

from scripts.db import retry_on_busy
from scripts.state import get_setting, set_setting

logger = logging.getLogger(__name__)

AGENT_TYPES: list[str] = [
    "planner",
    "executor",
    "reviewer",
    "researcher",
    "verifier",
    "debugger",
    "mapper",
    "synthesizer",
]

PROFILES: dict[str, dict[str, str]] = {
    "quality": {
        "planner": "opus",
        "executor": "opus",
        "reviewer": "sonnet",
        "researcher": "opus",
        "verifier": "sonnet",
        "debugger": "opus",
        "mapper": "sonnet",
        "synthesizer": "sonnet",
    },
    "balanced": {
        "planner": "opus",
        "executor": "sonnet",
        "reviewer": "sonnet",
        "researcher": "sonnet",
        "verifier": "sonnet",
        "debugger": "sonnet",
        "mapper": "haiku",
        "synthesizer": "sonnet",
    },
    "budget": {
        "planner": "sonnet",
        "executor": "sonnet",
        "reviewer": "haiku",
        "researcher": "haiku",
        "verifier": "haiku",
        "debugger": "sonnet",
        "mapper": "haiku",
        "synthesizer": "haiku",
    },
}

VALID_PROFILES: set[str] = {*PROFILES, "inherit"}


def get_active_profile(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> str:
    """Read the active model profile from settings."""
    profile = get_setting(conn, "model_profile", default="balanced", project_id=project_id)
    if profile not in VALID_PROFILES:
        logger.warning(
            "Unknown profile %r in settings, falling back to balanced",
            profile,
        )
        return "balanced"
    return profile


@retry_on_busy()
def set_active_profile(
    conn: sqlite3.Connection,
    profile: str,
    project_id: str = "default",
) -> dict:
    """Persist a new active profile and return the resulting mapping."""
    if profile not in VALID_PROFILES:
        msg = f"Invalid profile {profile!r}. Must be one of: {', '.join(sorted(VALID_PROFILES))}"
        raise ValueError(msg)
    set_setting(conn, "model_profile", profile, project_id=project_id)
    agents = PROFILES.get(profile, {})
    logger.info("Set model profile to %r for project %s", profile, project_id)
    return {"profile": profile, "agents": agents}


def resolve_model(
    conn: sqlite3.Connection,
    agent_type: str,
    project_id: str = "default",
) -> str:
    """Resolve the model name for a given agent type under the active profile."""
    profile = get_active_profile(conn, project_id=project_id)
    if profile == "inherit":
        return "inherit"
    mapping = PROFILES.get(profile, PROFILES["balanced"])
    model = mapping.get(agent_type, "sonnet")
    if agent_type not in AGENT_TYPES:
        logger.warning("Unrecognized agent type %r, defaulting to sonnet", agent_type)
    return model


def get_profile_table(
    conn: sqlite3.Connection,
    project_id: str = "default",
) -> dict:
    """Return the full agent-to-model mapping for the active profile."""
    profile = get_active_profile(conn, project_id=project_id)
    agents = PROFILES.get(profile, {})
    return {"profile": profile, "agents": agents}


def format_profile_display(profile_data: dict) -> str:
    """Format a profile mapping as a markdown table."""
    name = profile_data.get("profile", "unknown")
    agents: dict[str, str] = profile_data.get("agents", {})
    lines = [
        f"**Profile: {name}**",
        "",
        "| Agent | Model |",
        "|-------|-------|",
    ]
    for agent in AGENT_TYPES:
        model = agents.get(agent, "—")
        lines.append(f"| {agent} | {model} |")
    return "\n".join(lines)
