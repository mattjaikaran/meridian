"""Meridian CLI — top-level entry point for the `meridian` command.

Provides status and next subcommands backed by scripts/state.py.

Usage:
    meridian [--project-dir DIR] [--json] status
    meridian [--project-dir DIR] [--json] next
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load_conn(project_dir: str | Path | None):
    """Return an open_project context manager for the given directory."""
    from scripts.db import open_project
    return open_project(project_dir)


def _check_db(project_dir: Path) -> None:
    """Exit with a clear message if the DB file does not exist yet."""
    db_path = project_dir / ".meridian" / "state.db"
    if not db_path.exists():
        print(
            f"Error: no Meridian database found at {db_path}\n"
            "Run `meridian init` (or /meridian:init) inside your project first.",
            file=sys.stderr,
        )
        sys.exit(1)


# ── Human-readable formatters ─────────────────────────────────────────────────


def _fmt_status(data: dict) -> str:
    """Render get_status() dict as human-readable text."""
    if "error" in data:
        return f"Error: {data['error']}"

    lines: list[str] = []
    project = data.get("project") or {}
    lines.append(f"Project: {project.get('name', 'unknown')}  ({project.get('id', '')})")

    active_ms = data.get("active_milestone")
    milestones = data.get("milestones") or []
    lines.append(f"Milestones: {len(milestones)} total")
    if active_ms:
        lines.append(f"  Active: [{active_ms['status']}] {active_ms['name']}")

    active_ws = data.get("active_workstream")
    if active_ws:
        lines.append(f"Workstream: {active_ws.get('name', '')}  ({active_ws.get('slug', '')})")

    current_phase = data.get("current_phase")
    phases = data.get("phases") or []
    if phases:
        lines.append(f"Phases: {len(phases)}")
    if current_phase:
        lines.append(f"  Current: [{current_phase['status']}] {current_phase['name']}")

    plans = data.get("plans") or []
    if plans:
        pending = [p for p in plans if p["status"] == "pending"]
        executing = [p for p in plans if p["status"] == "executing"]
        complete = [p for p in plans if p["status"] == "complete"]
        lines.append(
            f"Plans: {len(plans)} total  "
            f"({len(executing)} executing, {len(pending)} pending, {len(complete)} complete)"
        )

    next_action = data.get("next_action") or {}
    if next_action:
        lines.append(f"Next action: [{next_action.get('action', '?')}] {next_action.get('message', '')}")

    latest_ckpt = data.get("latest_checkpoint")
    if latest_ckpt:
        lines.append(f"Latest checkpoint: {latest_ckpt.get('created_at', '')} — {latest_ckpt.get('summary', '')[:80]}")

    recent = data.get("recent_decisions") or []
    if recent:
        lines.append(f"Recent decisions ({len(recent)}):")
        for d in recent[:3]:
            lines.append(f"  • {d.get('summary', '')[:80]}")

    return "\n".join(lines)


def _fmt_next(data: dict) -> str:
    """Render compute_next_action() dict as human-readable text."""
    action = data.get("action", "unknown")
    message = data.get("message", "")
    lines = [f"Action: {action}", f"  {message}"]
    for key in ("milestone_id", "phase_id", "plan_id"):
        if key in data:
            lines.append(f"  {key}: {data[key]}")
    return "\n".join(lines)


# ── Subcommand handlers ───────────────────────────────────────────────────────


def cmd_status(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.state import get_status

    try:
        with _load_conn(project_dir) as conn:
            data = get_status(conn)
    except Exception as exc:
        print(f"Error reading status: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # sqlite3.Row objects are not JSON-serialisable; normalise to plain dicts.
        print(json.dumps(data, default=str, indent=2))
    else:
        print(_fmt_status(data))


def cmd_next(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.state import compute_next_action

    try:
        with _load_conn(project_dir) as conn:
            data = compute_next_action(conn)
    except Exception as exc:
        print(f"Error computing next action: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(data, default=str, indent=2))
    else:
        print(_fmt_next(data))


# ── Argument parser ───────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meridian",
        description="Meridian workflow engine — inspect and advance project state.",
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        metavar="DIR",
        help="Path to the project root (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable text",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # status
    status_p = subparsers.add_parser(
        "status",
        help="Show full project status (milestone, phase, plans, next action)",
    )
    status_p.set_defaults(func=cmd_status)

    # next
    next_p = subparsers.add_parser(
        "next",
        help="Show the next recommended action for the current project state",
    )
    next_p.set_defaults(func=cmd_next)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
