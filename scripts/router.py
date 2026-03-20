#!/usr/bin/env python3
"""Meridian freeform text router — maps natural language to /meridian:* commands."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Default skills directory relative to project root
SKILLS_DIR = Path(__file__).parent.parent / "skills"


def load_command_registry(skills_dir: Path | None = None) -> list[dict]:
    """Load command registry from skills/*/SKILL.md metadata.

    Each SKILL.md is expected to have:
    - Line 1: `# /meridian:<name> — <description>`
    - A `## Keywords` section with comma-separated keywords

    Returns:
        List of dicts with name, description, keywords, path.
    """
    if skills_dir is None:
        skills_dir = SKILLS_DIR

    registry: list[dict] = []

    if not skills_dir.is_dir():
        return registry

    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue

        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError:
            continue

        entry = _parse_skill_md(content, skill_dir.name)
        if entry:
            registry.append(entry)

    return registry


def _parse_skill_md(content: str, dir_name: str) -> dict | None:
    """Parse a SKILL.md file to extract name, description, and keywords."""
    lines = content.strip().split("\n")
    if not lines:
        return None

    # Parse header: # /meridian:<name> — <description>
    header_match = re.match(r"^#\s+/meridian:(\S+)\s*[—–-]\s*(.+)$", lines[0])
    if not header_match:
        return None

    name = header_match.group(1)
    description = header_match.group(2).strip()

    # Parse keywords section
    keywords: list[str] = []
    in_keywords = False
    for line in lines[1:]:
        if line.strip().lower().startswith("## keywords"):
            in_keywords = True
            continue
        if in_keywords:
            if line.startswith("##"):
                break
            kw_line = line.strip().strip("-").strip()
            if kw_line:
                keywords.extend(
                    k.strip().lower() for k in kw_line.split(",") if k.strip()
                )
            break  # Only read the first line after ## Keywords

    return {
        "name": name,
        "description": description,
        "keywords": keywords,
        "dir_name": dir_name,
    }


def route_freeform(
    text: str,
    registry: list[dict] | None = None,
    skills_dir: Path | None = None,
) -> dict:
    """Route freeform text to the best matching /meridian:* command.

    Args:
        text: Freeform user input.
        registry: Pre-loaded command registry. If None, loads from skills_dir.
        skills_dir: Path to skills directory. Defaults to project skills/.

    Returns:
        Dict with:
        - match: "exact" | "confident" | "ambiguous" | "none"
        - command: str (best match command name, if any)
        - candidates: list[dict] (top matches with scores)
        - message: str (human-readable explanation)
    """
    if registry is None:
        registry = load_command_registry(skills_dir)

    if not registry:
        return {
            "match": "none",
            "command": None,
            "candidates": [],
            "message": "No commands registered. Run /meridian:help.",
        }

    text_lower = text.lower().strip()
    words = set(re.findall(r"\w+", text_lower))

    # Score each command
    scored: list[dict] = []
    for cmd in registry:
        score = _score_command(text_lower, words, cmd)
        if score > 0:
            scored.append({
                "name": cmd["name"],
                "description": cmd["description"],
                "score": score,
            })

    # Sort by score descending
    scored.sort(key=lambda x: x["score"], reverse=True)

    if not scored:
        return {
            "match": "none",
            "command": None,
            "candidates": [],
            "message": f"No matching command for: '{text}'. Try /meridian:help.",
        }

    top = scored[0]

    # Exact match: command name appears in text
    if top["name"] in text_lower:
        return {
            "match": "exact",
            "command": top["name"],
            "candidates": scored[:3],
            "message": f"Matched /meridian:{top['name']} — {top['description']}",
        }

    # High confidence: score well above second place
    if len(scored) == 1 or top["score"] >= scored[1]["score"] * 1.5:
        return {
            "match": "confident",
            "command": top["name"],
            "candidates": scored[:3],
            "message": f"Best match: /meridian:{top['name']} — {top['description']}",
        }

    # Ambiguous: multiple close matches
    return {
        "match": "ambiguous",
        "command": None,
        "candidates": scored[:3],
        "message": (
            "Ambiguous input. Top matches:\n"
            + "\n".join(
                f"  {i+1}. /meridian:{c['name']} — {c['description']} (score: {c['score']})"
                for i, c in enumerate(scored[:3])
            )
        ),
    }


def _score_command(text_lower: str, words: set[str], cmd: dict) -> float:
    """Score how well a command matches the input text."""
    score = 0.0

    # Exact command name in text
    if cmd["name"] in text_lower:
        score += 10.0

    # Keyword overlap
    for kw in cmd["keywords"]:
        kw_words = set(kw.split())
        overlap = words & kw_words
        if overlap:
            score += 3.0 * len(overlap) / len(kw_words)

    # Description word overlap
    desc_words = set(re.findall(r"\w+", cmd["description"].lower()))
    # Remove common words
    stopwords = {"a", "an", "the", "to", "for", "in", "of", "and", "or", "with", "is", "it"}
    desc_words -= stopwords
    words_clean = words - stopwords
    overlap = words_clean & desc_words
    if overlap:
        score += 1.0 * len(overlap)

    return score
