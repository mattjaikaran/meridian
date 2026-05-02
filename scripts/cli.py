"""Meridian CLI — top-level entry point for the `meridian` command.

Provides status, next, init, note, fast, and dashboard subcommands.

Usage:
    meridian [--project-dir DIR] [--json] status
    meridian [--project-dir DIR] [--json] next
    meridian [--project-dir DIR] [--json] init
    meridian [--project-dir DIR] [--json] note add "text"
    meridian [--project-dir DIR] [--json] note list
    meridian [--project-dir DIR] [--json] note promote <id>
    meridian [--project-dir DIR] [--json] fast "implement X"
    meridian [--project-dir DIR] [--json] dashboard
"""

from __future__ import annotations

import argparse
import json
import sys
import webbrowser
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


def cmd_init(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    from scripts.db import init as db_init

    try:
        db_path = db_init(project_dir)
    except Exception as exc:
        print(f"Error initializing Meridian: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"status": "ok", "db_path": str(db_path)}, indent=2))
    else:
        print(f"Meridian initialized at {db_path}")


def cmd_note(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    from scripts.notes import append_note, list_notes, promote_note

    subcmd = args.note_command

    if subcmd == "add":
        try:
            result = append_note(project_dir, args.text)
        except Exception as exc:
            print(f"Error adding note: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            print(f"[{result['id']}] {result['timestamp']} — {result['text']}")

    elif subcmd == "list":
        try:
            notes = list_notes(project_dir)
        except Exception as exc:
            print(f"Error listing notes: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(notes, default=str, indent=2))
        else:
            if not notes:
                print("No notes found.")
            else:
                for n in notes:
                    promoted = " [PROMOTED]" if n.get("promoted") else ""
                    print(f"[{n['id']}] {n['timestamp']} — {n['text']}{promoted}")

    elif subcmd == "promote":
        _check_db(project_dir)
        try:
            with _load_conn(project_dir) as conn:
                result = promote_note(project_dir, args.note_id, conn)
        except Exception as exc:
            print(f"Error promoting note: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            task = result.get("task", {})
            print(f"Note {args.note_id} promoted to task {task.get('id', '?')}: {task.get('description', '')}")

    else:
        print(f"Unknown note subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


def cmd_fast(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.fast import execute_fast_task

    try:
        with _load_conn(project_dir) as conn:
            result = execute_fast_task(
                conn,
                description=args.description,
                force=args.force,
            )
    except Exception as exc:
        print(f"Error executing fast task: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        status = result.get("status", "unknown")
        if status == "too_complex":
            print(f"Task too complex (score: {result['complexity']['score']})")
            print(f"  {result['message']}")
            print(f"  Suggested: {result.get('suggested_command', '')}")
        else:
            task = result.get("task", {})
            print(f"Fast task created: [{task.get('id', '?')}] {args.description}")
            complexity = result.get("complexity", {})
            if complexity:
                print(f"  Complexity score: {complexity.get('score', '?')}")


def cmd_dashboard(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.html_dashboard import generate_dashboard_data, render_html

    try:
        with _load_conn(project_dir) as conn:
            data = generate_dashboard_data(conn)
        html = render_html(data)
    except Exception as exc:
        print(f"Error generating dashboard: {exc}", file=sys.stderr)
        sys.exit(1)

    dashboard_path = project_dir / ".meridian" / "dashboard.html"
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(html, encoding="utf-8")

    if args.json:
        print(json.dumps({"path": str(dashboard_path)}, indent=2))
    else:
        print(f"Dashboard written to {dashboard_path}")
        webbrowser.open(dashboard_path.as_uri())


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

    # init
    init_p = subparsers.add_parser(
        "init",
        help="Initialize Meridian in a project directory (creates .meridian/state.db)",
    )
    init_p.set_defaults(func=cmd_init)

    # note
    note_p = subparsers.add_parser(
        "note",
        help="Capture, list, or promote notes",
    )
    note_subs = note_p.add_subparsers(dest="note_command", metavar="SUBCOMMAND")
    note_subs.required = True

    note_add_p = note_subs.add_parser("add", help="Append a new note")
    note_add_p.add_argument("text", help="Note text")

    note_subs.add_parser("list", help="List all notes")

    note_promote_p = note_subs.add_parser("promote", help="Promote a note to a task")
    note_promote_p.add_argument("note_id", help="Note ID (e.g. N001)")

    note_p.set_defaults(func=cmd_note)

    # fast
    fast_p = subparsers.add_parser(
        "fast",
        help="Execute a fast/trivial task inline",
    )
    fast_p.add_argument("description", help="Task description")
    fast_p.add_argument(
        "--force",
        action="store_true",
        help="Skip complexity warning and execute even if non-trivial",
    )
    fast_p.set_defaults(func=cmd_fast)

    # dashboard
    dashboard_p = subparsers.add_parser(
        "dashboard",
        help="Generate an HTML dashboard and open it in the browser",
    )
    dashboard_p.set_defaults(func=cmd_dashboard)

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
