"""Generate Claude Code command wrappers from Meridian skill definitions.

Scans skills/*/SKILL.md, extracts metadata, and writes thin .md wrappers
to ~/.claude/commands/meridian/ for slash command routing.

Usage:
    uv run python scripts/generate_commands.py            # Install commands
    uv run python scripts/generate_commands.py --uninstall # Remove generated commands
    uv run python scripts/generate_commands.py --fix-symlink # Repair skills symlink
"""

from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

REPO_ROOT = Path("/Users/mattjaikaran/dev/meridian")
COMMANDS_DIR = Path.home() / ".claude" / "commands" / "meridian"
SYMLINK_PATH = Path.home() / ".claude" / "skills" / "meridian"
GENERATED_MARKER = "<!-- meridian:generated -->"


def discover_skills(repo_root: Path) -> list[dict]:
    """Scan skills/ directory and return metadata for each skill."""
    skills = []
    skills_dir = repo_root / "skills"
    if not skills_dir.exists():
        return skills
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_dir.is_dir() and skill_md.exists():
            metadata = extract_metadata(skill_md)
            metadata["name"] = skill_dir.name
            skills.append(metadata)
    return skills


def extract_metadata(skill_md: Path) -> dict:
    """Extract description and argument hints from a SKILL.md file."""
    content = skill_md.read_text()
    lines = content.splitlines()

    # Title line: # /meridian:<name> — <description>
    description = ""
    if lines and lines[0].startswith("# "):
        match = re.search(r"[—–-]\s*(.+)$", lines[0])
        if match:
            description = match.group(1).strip()

    # Arguments section
    arguments: list[str] = []
    in_args = False
    for line in lines:
        if line.strip().startswith("## Arguments"):
            in_args = True
            continue
        if in_args and line.strip().startswith("## "):
            break
        if in_args and line.strip().startswith("- "):
            arguments.append(line.strip()[2:])

    # Build argument-hint from parsed arguments
    arg_hint = ""
    if arguments:
        hints = []
        for arg in arguments:
            match = re.match(r"`([^`]+)`", arg)
            if match:
                hints.append(match.group(1))
        if hints:
            arg_hint = " ".join(hints)

    return {"description": description, "arguments": arguments, "argument_hint": arg_hint}


def generate_wrapper(skill: dict) -> str:
    """Produce the .md command wrapper content for a skill."""
    name = skill["name"]
    description = skill["description"]
    arg_hint = skill.get("argument_hint", "")

    frontmatter_lines = [
        "---",
        f"name: meridian:{name}",
        f"description: {description}",
    ]
    if arg_hint:
        frontmatter_lines.append(f'argument-hint: "{arg_hint}"')
    frontmatter_lines.append("---")

    parts = [
        GENERATED_MARKER,
        "\n".join(frontmatter_lines),
        "",
        f"{description}.",
        "",
        "## Procedure",
        "",
        f"@/Users/mattjaikaran/.claude/skills/meridian/skills/{name}/SKILL.md",
    ]
    return "\n".join(parts) + "\n"


def is_generated(filepath: Path) -> bool:
    """Check if a command file was created by this generator."""
    try:
        first_line = filepath.read_text().splitlines()[0]
        return first_line.strip() == GENERATED_MARKER
    except (IndexError, OSError):
        return False


def write_commands(skills: list[dict], commands_dir: Path) -> tuple[int, int]:
    """Write command wrapper files. Returns (created, skipped) counts."""
    commands_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    skipped = 0
    for skill in skills:
        filepath = commands_dir / f"{skill['name']}.md"
        if filepath.exists() and not is_generated(filepath):
            skipped += 1
            continue
        filepath.write_text(generate_wrapper(skill))
        created += 1
    return created, skipped


def cleanup_orphans(commands_dir: Path, valid_names: set[str]) -> list[str]:
    """Remove generated command files that no longer have a matching skill."""
    removed = []
    if not commands_dir.exists():
        return removed
    for md_file in commands_dir.glob("*.md"):
        if is_generated(md_file) and md_file.stem not in valid_names:
            md_file.unlink()
            removed.append(md_file.name)
    return removed


def verify_symlink(symlink_path: Path, expected_target: Path) -> bool:
    """Check if symlink exists and points to the expected target."""
    if not symlink_path.is_symlink():
        return False
    return symlink_path.resolve() == expected_target.resolve()


def fix_symlink(symlink_path: Path, target: Path) -> None:
    """Create or repair the skills symlink."""
    symlink_path.parent.mkdir(parents=True, exist_ok=True)
    if symlink_path.is_symlink() or symlink_path.exists():
        symlink_path.unlink()
    symlink_path.symlink_to(target)


def uninstall(commands_dir: Path) -> list[str]:
    """Remove only generated command files. Returns list of removed filenames."""
    removed = []
    if not commands_dir.exists():
        return removed
    for md_file in commands_dir.glob("*.md"):
        if is_generated(md_file):
            md_file.unlink()
            removed.append(md_file.name)
    return removed


def update_root_skill(repo_root: Path, skills: list[dict]) -> None:
    """Regenerate root SKILL.md without Commands section."""
    skill_list = "\n".join(f"- {s['name']} -- {s['description']}" for s in skills)

    content = textwrap.dedent(f"""\
        # Meridian -- Unified Workflow Engine

        Meridian is a SQLite-backed state machine for managing complex development workflows with deterministic resume, fresh-context subagents, and engineering discipline protocols.

        ## Available Skills

        {skill_list}

        ## Architecture

        State is stored in `.meridian/state.db` (SQLite) in each project directory. The state machine enforces valid transitions and computes the next action deterministically.

        ### Hierarchy
        ```
        Project -> Milestone -> Phase -> Plan
        ```

        ### Phase Lifecycle
        ```
        planned -> context_gathered -> planned_out -> executing -> verifying -> reviewing -> complete
                                                                                 |
                                                                               blocked
        ```

        ### Plan Lifecycle
        ```
        pending -> executing -> complete
                             -> failed -> pending (retry)
                             -> paused -> executing
        ```

        ## Scripts (Python, stdlib only)
        - `scripts/db.py` -- Schema init + migrations (v2: priority column)
        - `scripts/state.py` -- CRUD + transitions + next-action + auto-advancement + priority
        - `scripts/resume.py` -- Deterministic resume prompt generator
        - `scripts/export.py` -- SQLite -> JSON export for Nero
        - `scripts/dispatch.py` -- Nero HTTP dispatch client (push only)
        - `scripts/sync.py` -- Bidirectional Nero sync (pull status + push state)
        - `scripts/metrics.py` -- PM metrics: velocity, cycle times, stalls, forecasts, progress
        - `scripts/axis_sync.py` -- Axis PM ticket sync
        - `scripts/context_window.py` -- Token estimation + checkpoint triggers
        - `scripts/generate_commands.py` -- Generate Claude Code command wrappers from skills

        ## References
        - `references/state-machine.md` -- State transitions + rules + auto-advancement + priority
        - `references/discipline-protocols.md` -- TDD, debugging, verification, review
        - `references/nero-integration.md` -- Dispatch + bidirectional sync protocol
        - `references/axis-integration.md` -- PM sync protocol
    """)

    (repo_root / "SKILL.md").write_text(content)


def main() -> None:
    """CLI entry point for the command generator."""
    parser = argparse.ArgumentParser(
        description="Generate Claude Code command wrappers from Meridian skills."
    )
    parser.add_argument(
        "--uninstall", action="store_true",
        help="Remove generated command files",
    )
    parser.add_argument(
        "--fix-symlink", action="store_true",
        help="Create or repair the skills symlink",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="With --uninstall, also remove the symlink",
    )
    args = parser.parse_args()

    if args.fix_symlink:
        fix_symlink(SYMLINK_PATH, REPO_ROOT)
        print(f"Symlink fixed: {SYMLINK_PATH} -> {REPO_ROOT}")
        return

    if args.uninstall:
        removed = uninstall(COMMANDS_DIR)
        if removed:
            print(f"Removed: {', '.join(removed)}")
        else:
            print("No generated files to remove.")
        if args.all and SYMLINK_PATH.is_symlink():
            SYMLINK_PATH.unlink()
            print(f"Removed symlink: {SYMLINK_PATH}")
        return

    # Default: install
    skills = discover_skills(REPO_ROOT)
    if not skills:
        print("No skills found.")
        return

    # Write command wrappers
    created, skipped = write_commands(skills, COMMANDS_DIR)

    # Clean up orphans
    valid_names = {s["name"] for s in skills}
    removed = cleanup_orphans(COMMANDS_DIR, valid_names)

    # Verify symlink
    if not verify_symlink(SYMLINK_PATH, REPO_ROOT):
        print(f"WARNING: Symlink missing or wrong: {SYMLINK_PATH}")
        print("  Run with --fix-symlink to repair.")

    # Update root SKILL.md
    update_root_skill(REPO_ROOT, skills)

    # Summary
    created_names = [s["name"] + ".md" for s in skills]
    print(f"Created: {', '.join(created_names)}")
    if skipped:
        print(f"Skipped: {skipped} custom files")
    if removed:
        print(f"Removed: {', '.join(removed)} (orphans)")
    print(f"Root SKILL.md updated.")


if __name__ == "__main__":
    main()
