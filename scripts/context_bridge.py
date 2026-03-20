#!/usr/bin/env python3
"""Context bridge — import external project context into Meridian.

Supports matt-stack context dumps and generic markdown/JSON context files.
"""

import json
import sqlite3
from pathlib import Path


def import_context_file(
    conn: sqlite3.Connection,
    file_path: str | Path,
    phase_id: int | None = None,
) -> dict:
    """Import a context file (markdown or JSON) into Meridian.

    If phase_id is provided, stores as phase context_doc.
    Otherwise stores as project-level context in settings.

    Returns:
        {"imported": True, "format": str, "size": int, "target": str}
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Context file not found: {file_path}")

    content = file_path.read_text()
    fmt = _detect_format(file_path, content)

    if fmt == "json":
        # Parse JSON and convert to markdown for storage
        try:
            data = json.loads(content)
            content = _json_to_markdown(data)
        except json.JSONDecodeError:
            pass  # Fall through to raw text

    if phase_id is not None:
        conn.execute(
            "UPDATE phase SET context_doc = ? WHERE id = ?",
            (content, phase_id),
        )
        conn.commit()
        target = f"phase:{phase_id}"
    else:
        from scripts.state import set_setting
        set_setting(conn, "imported_context", content)
        target = "project"

    return {
        "imported": True,
        "format": fmt,
        "size": len(content),
        "target": target,
    }


def import_matt_stack_context(
    conn: sqlite3.Connection,
    project_dir: str | Path,
) -> dict:
    """Try to import context from a matt-stack project.

    Looks for matt-stack context output in common locations.
    Returns import result or indication that no context was found.
    """
    project_dir = Path(project_dir)

    # Check common matt-stack context locations
    candidates = [
        project_dir / ".matt-stack" / "context.md",
        project_dir / ".matt-stack" / "context.json",
        project_dir / "context.md",
    ]

    for candidate in candidates:
        if candidate.exists():
            result = import_context_file(conn, candidate)
            result["source"] = "matt-stack"
            result["path"] = str(candidate)
            return result

    return {"imported": False, "source": "matt-stack", "reason": "No matt-stack context found"}


def extract_project_context(project_dir: str | Path) -> dict:
    """Extract project context from common files (CLAUDE.md, package.json, pyproject.toml).

    Returns structured context dict that can be used for context gathering.
    """
    project_dir = Path(project_dir)
    context: dict = {
        "project_dir": str(project_dir),
        "files_found": [],
        "stack": [],
        "commands": {},
    }

    # Check CLAUDE.md
    claude_md = project_dir / "CLAUDE.md"
    if claude_md.exists():
        context["files_found"].append("CLAUDE.md")
        content = claude_md.read_text()
        context["claude_md"] = content[:2000]  # First 2k chars

    # Check pyproject.toml
    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        context["files_found"].append("pyproject.toml")
        context["stack"].append("python")
        content = pyproject.read_text()
        # Extract project name
        for line in content.split("\n"):
            if line.strip().startswith("name"):
                context["project_name"] = line.split("=")[-1].strip().strip('"')
                break

    # Check package.json
    pkg_json = project_dir / "package.json"
    if pkg_json.exists():
        context["files_found"].append("package.json")
        context["stack"].append("javascript")
        try:
            data = json.loads(pkg_json.read_text())
            context["project_name"] = context.get("project_name") or data.get("name", "")
            if "scripts" in data:
                context["commands"] = {
                    k: v for k, v in data["scripts"].items()
                    if k in ("test", "dev", "build", "lint", "start")
                }
        except json.JSONDecodeError:
            pass

    # Check Makefile
    makefile = project_dir / "Makefile"
    if makefile.exists():
        context["files_found"].append("Makefile")

    # Check docker-compose
    for dc in ("docker-compose.yml", "docker-compose.yaml", "compose.yml"):
        if (project_dir / dc).exists():
            context["files_found"].append(dc)
            context["stack"].append("docker")
            break

    return context


def format_context_for_prompt(context: dict) -> str:
    """Format extracted context as markdown for inclusion in prompts."""
    lines = ["## Project Context", ""]

    if context.get("project_name"):
        lines.append(f"**Project:** {context['project_name']}")

    if context.get("stack"):
        lines.append(f"**Stack:** {', '.join(set(context['stack']))}")

    if context.get("files_found"):
        lines.append(f"**Config files:** {', '.join(context['files_found'])}")

    if context.get("commands"):
        lines.append("")
        lines.append("**Commands:**")
        for cmd, script in context["commands"].items():
            lines.append(f"- `{cmd}`: `{script}`")

    if context.get("claude_md"):
        lines.append("")
        lines.append("**CLAUDE.md (excerpt):**")
        lines.append(f"```\n{context['claude_md'][:500]}\n```")

    lines.append("")
    return "\n".join(lines)


def _detect_format(file_path: Path, content: str) -> str:
    """Detect the format of a context file."""
    if file_path.suffix == ".json":
        return "json"
    if file_path.suffix in (".md", ".markdown"):
        return "markdown"
    # Try to parse as JSON
    try:
        json.loads(content)
        return "json"
    except (json.JSONDecodeError, ValueError):
        return "text"


def _json_to_markdown(data: dict) -> str:
    """Convert a JSON context dict to readable markdown."""
    lines = ["## Imported Context", ""]

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f"**{key}:** {value}")
            elif isinstance(value, list):
                lines.append(f"**{key}:**")
                for item in value:
                    lines.append(f"- {item}")
            elif isinstance(value, dict):
                lines.append(f"**{key}:**")
                for k, v in value.items():
                    lines.append(f"- {k}: {v}")
            lines.append("")
    else:
        lines.append(str(data))

    return "\n".join(lines)
