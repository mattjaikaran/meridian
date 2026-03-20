#!/usr/bin/env python3
"""Meridian backlog/seed management — park ideas with trigger conditions."""

import re
from datetime import UTC, datetime
from pathlib import Path

# Backlog storage location
BACKLOG_FILENAME = "backlog.md"

# Valid trigger types
VALID_TRIGGER_TYPES = {"after_phase", "after_milestone", "manual"}


def _backlog_path(project_dir: Path) -> Path:
    """Get the path to the backlog file."""
    return project_dir / ".meridian" / BACKLOG_FILENAME


def _now_str() -> str:
    """Return current UTC time as a formatted string."""
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M")


def _next_seed_id(content: str) -> str:
    """Compute the next seed ID from existing content.

    Seeds are formatted as [SEED-001], [SEED-002], etc.
    """
    ids = re.findall(r"\[SEED-(\d+)\]", content)
    if not ids:
        return "SEED-001"
    max_id = max(int(i) for i in ids)
    return f"SEED-{max_id + 1:03d}"


def _parse_trigger(trigger_str: str) -> dict:
    """Parse a trigger string into type and value.

    Formats:
        'after_phase:auth' -> {'type': 'after_phase', 'value': 'auth'}
        'after_milestone:v2.0' -> {'type': 'after_milestone', 'value': 'v2.0'}
        'manual' -> {'type': 'manual', 'value': ''}

    Raises:
        ValueError: If trigger type is invalid.
    """
    if ":" in trigger_str:
        trigger_type, value = trigger_str.split(":", 1)
    else:
        trigger_type = trigger_str
        value = ""

    trigger_type = trigger_type.strip()
    value = value.strip()

    if trigger_type not in VALID_TRIGGER_TYPES:
        raise ValueError(
            f"Invalid trigger type '{trigger_type}'. "
            f"Valid types: {', '.join(sorted(VALID_TRIGGER_TYPES))}"
        )

    return {"type": trigger_type, "value": value}


def plant_seed(
    project_dir: Path,
    idea: str,
    trigger: str = "manual",
) -> dict:
    """Plant a new seed (idea) in the backlog.

    Args:
        project_dir: Project root directory.
        idea: The idea description.
        trigger: Trigger condition string (e.g., 'after_phase:auth', 'manual').

    Returns:
        Dict with id, idea, trigger, timestamp, status, and file path.

    Raises:
        ValueError: If trigger type is invalid.
    """
    trigger_info = _parse_trigger(trigger)

    backlog_file = _backlog_path(project_dir)
    backlog_file.parent.mkdir(parents=True, exist_ok=True)

    if backlog_file.exists():
        content = backlog_file.read_text(encoding="utf-8")
    else:
        content = "## Backlog Seeds\n\n"

    seed_id = _next_seed_id(content)
    timestamp = _now_str()

    # Build the seed entry
    trigger_str = trigger_info["type"]
    if trigger_info["value"]:
        trigger_str += f":{trigger_info['value']}"

    entry = (
        f"### [{seed_id}] {idea}\n"
        f"- **Status:** active\n"
        f"- **Trigger:** {trigger_str}\n"
        f"- **Created:** {timestamp}\n"
        f"\n"
    )

    if not content.endswith("\n"):
        content += "\n"
    content += entry

    backlog_file.write_text(content, encoding="utf-8")

    return {
        "id": seed_id,
        "idea": idea,
        "trigger": trigger_info,
        "timestamp": timestamp,
        "status": "active",
        "file": str(backlog_file),
    }


def list_seeds(project_dir: Path) -> list[dict]:
    """List all seeds from the backlog.

    Returns:
        List of dicts with id, idea, status, trigger, created.
    """
    backlog_file = _backlog_path(project_dir)
    if not backlog_file.exists():
        return []

    content = backlog_file.read_text(encoding="utf-8")
    seeds: list[dict] = []

    # Parse seed entries
    pattern = re.compile(
        r"### \[(SEED-\d+)\] (.+?)\n"
        r"- \*\*Status:\*\* (\w+)\n"
        r"- \*\*Trigger:\*\* (.+?)\n"
        r"- \*\*Created:\*\* (.+?)\n",
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        seed_id = match.group(1)
        idea = match.group(2).strip()
        status = match.group(3).strip()
        trigger_raw = match.group(4).strip()
        created = match.group(5).strip()

        trigger_info = _parse_trigger(trigger_raw)

        seeds.append({
            "id": seed_id,
            "idea": idea,
            "status": status,
            "trigger": trigger_info,
            "created": created,
        })

    return seeds


def _update_seed_status(project_dir: Path, seed_id: str, new_status: str) -> dict:
    """Update a seed's status in the backlog file.

    Args:
        project_dir: Project root directory.
        seed_id: The seed ID (e.g., 'SEED-001').
        new_status: New status string.

    Returns:
        Dict with seed info.

    Raises:
        ValueError: If seed not found.
    """
    backlog_file = _backlog_path(project_dir)
    if not backlog_file.exists():
        raise ValueError(f"Backlog file not found: {backlog_file}")

    content = backlog_file.read_text(encoding="utf-8")

    # Find the seed entry and update status
    pattern = re.compile(
        rf"(### \[{re.escape(seed_id)}\] (.+?)\n)"
        rf"- \*\*Status:\*\* (\w+)\n",
        re.MULTILINE,
    )

    match = pattern.search(content)
    if not match:
        raise ValueError(f"Seed {seed_id} not found")

    old_status = match.group(3)
    idea = match.group(2).strip()

    old_text = match.group(0)
    new_text = old_text.replace(
        f"- **Status:** {old_status}",
        f"- **Status:** {new_status}",
    )

    content = content.replace(old_text, new_text)
    backlog_file.write_text(content, encoding="utf-8")

    return {
        "id": seed_id,
        "idea": idea,
        "old_status": old_status,
        "new_status": new_status,
    }


def promote_seed(project_dir: Path, seed_id: str) -> dict:
    """Promote a seed — mark it as promoted for inclusion in planning.

    Args:
        project_dir: Project root directory.
        seed_id: The seed ID to promote.

    Returns:
        Dict with seed info.

    Raises:
        ValueError: If seed not found or already promoted/dismissed.
    """
    seeds = list_seeds(project_dir)
    seed = next((s for s in seeds if s["id"] == seed_id), None)
    if seed is None:
        raise ValueError(f"Seed {seed_id} not found")
    if seed["status"] != "active":
        raise ValueError(f"Seed {seed_id} has status '{seed['status']}', can only promote active seeds")

    return _update_seed_status(project_dir, seed_id, "promoted")


def dismiss_seed(project_dir: Path, seed_id: str) -> dict:
    """Dismiss a seed — archive it as not needed.

    Args:
        project_dir: Project root directory.
        seed_id: The seed ID to dismiss.

    Returns:
        Dict with seed info.

    Raises:
        ValueError: If seed not found or already dismissed/promoted.
    """
    seeds = list_seeds(project_dir)
    seed = next((s for s in seeds if s["id"] == seed_id), None)
    if seed is None:
        raise ValueError(f"Seed {seed_id} not found")
    if seed["status"] != "active":
        raise ValueError(f"Seed {seed_id} has status '{seed['status']}', can only dismiss active seeds")

    return _update_seed_status(project_dir, seed_id, "dismissed")


def check_triggers(project_dir: Path, completed_phases: list[str] | None = None, completed_milestones: list[str] | None = None) -> list[dict]:
    """Check which seeds have their trigger conditions met.

    Args:
        project_dir: Project root directory.
        completed_phases: List of completed phase names.
        completed_milestones: List of completed milestone names.

    Returns:
        List of seeds whose triggers are satisfied.
    """
    completed_phases = completed_phases or []
    completed_milestones = completed_milestones or []

    seeds = list_seeds(project_dir)
    triggered: list[dict] = []

    for seed in seeds:
        if seed["status"] != "active":
            continue

        trigger = seed["trigger"]
        if trigger["type"] == "after_phase" and trigger["value"] in completed_phases:
            triggered.append(seed)
        elif trigger["type"] == "after_milestone" and trigger["value"] in completed_milestones:
            triggered.append(seed)
        # 'manual' triggers never auto-surface

    return triggered
