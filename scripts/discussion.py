#!/usr/bin/env python3
"""Meridian discussion audit trail — capture reasoning behind decisions."""

import re
from datetime import UTC, datetime
from pathlib import Path

# Discussion log location
DISCUSSION_LOG_FILENAME = "DISCUSSION-LOG.md"


def _log_path(project_dir: Path) -> Path:
    """Get the path to the discussion log file."""
    return project_dir / ".meridian" / DISCUSSION_LOG_FILENAME


def _now_str() -> str:
    """Return current UTC date as a formatted string."""
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _next_disc_id(content: str) -> str:
    """Compute the next discussion ID from existing content.

    Discussions are formatted as [DISC-001], [DISC-002], etc.
    """
    ids = re.findall(r"\[DISC-(\d+)\]", content)
    if not ids:
        return "DISC-001"
    max_id = max(int(i) for i in ids)
    return f"DISC-{max_id + 1:03d}"


def log_discussion(
    project_dir: Path,
    topic: str,
    options: list[dict],
    decision: str,
    rationale: str,
    decision_id: str,
) -> dict:
    """Log a discussion entry to the append-only discussion log.

    Args:
        project_dir: Project root directory.
        topic: The topic discussed.
        options: List of dicts with 'name' and 'description' keys.
        decision: Which option was chosen.
        rationale: Why this decision was made.
        decision_id: The decision ID this discussion produced (e.g., 'DEC-005').

    Returns:
        Dict with disc_id, topic, decision_id, timestamp, and file path.
    """
    log_file = _log_path(project_dir)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    if log_file.exists():
        content = log_file.read_text(encoding="utf-8")
    else:
        content = "# Discussion Log\n\n"

    disc_id = _next_disc_id(content)
    timestamp = _now_str()

    # Build options text
    options_lines = []
    for i, opt in enumerate(options, 1):
        name = opt.get("name", f"Option {i}")
        desc = opt.get("description", "")
        if desc:
            options_lines.append(f"{i}. {name} — {desc}")
        else:
            options_lines.append(f"{i}. {name}")

    entry = (
        f"## [{disc_id}] {timestamp} — {topic}\n"
        f"\n"
        f"**Topic:** {topic}\n"
        f"**Options considered:**\n"
    )
    for line in options_lines:
        entry += f"{line}\n"
    entry += (
        f"\n"
        f"**Decision:** {decision}\n"
        f"**Rationale:** {rationale}\n"
        f"**Decision ID:** {decision_id}\n"
        f"\n"
    )

    if not content.endswith("\n"):
        content += "\n"
    content += entry

    log_file.write_text(content, encoding="utf-8")

    return {
        "disc_id": disc_id,
        "topic": topic,
        "decision_id": decision_id,
        "timestamp": timestamp,
        "file": str(log_file),
    }


def load_discussion_log(project_dir: Path) -> list[dict]:
    """Load all discussion entries from the log.

    Returns:
        List of dicts with disc_id, timestamp, topic, options,
        decision, rationale, decision_id.
    """
    log_file = _log_path(project_dir)
    if not log_file.exists():
        return []

    content = log_file.read_text(encoding="utf-8")
    entries: list[dict] = []

    # Split by entry headers
    pattern = re.compile(
        r"## \[(DISC-\d+)\] (\d{4}-\d{2}-\d{2}) — (.+?)\n"
        r"\n"
        r"\*\*Topic:\*\* (.+?)\n"
        r"\*\*Options considered:\*\*\n"
        r"((?:\d+\..+?\n)+)"
        r"\n"
        r"\*\*Decision:\*\* (.+?)\n"
        r"\*\*Rationale:\*\* (.+?)\n"
        r"\*\*Decision ID:\*\* (.+?)\n",
        re.MULTILINE,
    )

    for match in pattern.finditer(content):
        disc_id = match.group(1)
        timestamp = match.group(2)
        topic = match.group(3).strip()
        options_block = match.group(5)
        decision = match.group(6).strip()
        rationale = match.group(7).strip()
        decision_id = match.group(8).strip()

        # Parse options
        options: list[dict] = []
        for opt_match in re.finditer(r"\d+\. (.+?)(?:\n|$)", options_block):
            opt_text = opt_match.group(1).strip()
            if " — " in opt_text:
                name, desc = opt_text.split(" — ", 1)
                options.append({"name": name.strip(), "description": desc.strip()})
            else:
                options.append({"name": opt_text, "description": ""})

        entries.append({
            "disc_id": disc_id,
            "timestamp": timestamp,
            "topic": topic,
            "options": options,
            "decision": decision,
            "rationale": rationale,
            "decision_id": decision_id,
        })

    return entries


def get_discussions_for_decision(project_dir: Path, decision_id: str) -> list[dict]:
    """Get all discussion entries linked to a specific decision ID.

    Args:
        project_dir: Project root directory.
        decision_id: The decision ID to search for.

    Returns:
        List of discussion entries matching the decision_id.
    """
    entries = load_discussion_log(project_dir)
    return [e for e in entries if e["decision_id"] == decision_id]
