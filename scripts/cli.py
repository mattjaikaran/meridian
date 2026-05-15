"""Meridian CLI — top-level entry point for the `meridian` command.

Provides status, next, init, note, fast, dashboard, execute, plan,
resume, ship, checkpoint, pause, workstream, and ultraplan subcommands.

Usage:
    meridian [--project-dir DIR] [--json] status [--all-workstreams]
    meridian [--project-dir DIR] [--json] next
    meridian [--project-dir DIR] [--json] init
    meridian [--project-dir DIR] [--json] note add "text"
    meridian [--project-dir DIR] [--json] note list
    meridian [--project-dir DIR] [--json] note promote <id>
    meridian [--project-dir DIR] [--json] fast "implement X"
    meridian [--project-dir DIR] [--json] dashboard
    meridian [--project-dir DIR] [--json] execute [--plan-id N]
    meridian [--project-dir DIR] [--json] plan
    meridian [--project-dir DIR] [--json] resume
    meridian [--project-dir DIR] [--json] ship --milestone-id ID
    meridian [--project-dir DIR] [--json] checkpoint [--trigger TEXT]
    meridian [--project-dir DIR] [--json] pause <directory>
    meridian [--project-dir DIR] [--json] pause --clear
    meridian [--project-dir DIR] [--json] review
    meridian [--project-dir DIR] [--json] validate
    meridian [--project-dir DIR] [--json] config list
    meridian [--project-dir DIR] [--json] config set <key> <value>
    meridian [--project-dir DIR] [--json] workstream list [--status STATUS]
    meridian [--project-dir DIR] [--json] workstream create <name> [--description TEXT]
    meridian [--project-dir DIR] [--json] workstream activate <slug>
    meridian [--project-dir DIR] [--json] workstream switch <slug>
    meridian [--project-dir DIR] [--json] workstream status <slug>
    meridian [--project-dir DIR] [--json] workstream progress
    meridian [--project-dir DIR] [--json] workstream complete <slug>
    meridian [--project-dir DIR] [--json] workstream resume <slug>
    meridian [--project-dir DIR] [--json] workstream assign <milestone-id> <workstream-slug>
    meridian [--project-dir DIR] [--json] ultraplan [<goal>] [--phase N] [--deep] [--local] [--cloud] [--dry-run]
    meridian [--project-dir DIR] [--json] stats
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
            if getattr(args, "all_workstreams", False):
                from scripts.workstreams import get_all_workstreams_progress, get_active_workstream
                data["workstreams"] = get_all_workstreams_progress(conn)
                data["active_workstream"] = get_active_workstream(conn)
    except Exception as exc:
        print(f"Error reading status: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        # sqlite3.Row objects are not JSON-serialisable; normalise to plain dicts.
        print(json.dumps(data, default=str, indent=2))
    elif getattr(args, "all_workstreams", False):
        print(_fmt_status(data))
        workstreams = data.get("workstreams", [])
        active_ws = data.get("active_workstream")
        active_slug = active_ws["slug"] if active_ws else None
        print("\n## Workstream Portfolio\n")
        if not workstreams:
            print("No workstreams found.")
        else:
            print(f"{'Workstream':<20} {'Status':<10} {'Milestones':<12} {'Phases':<10} {'Progress'}")
            print("-" * 65)
            for entry in workstreams:
                ws = entry["workstream"]
                star = " ★" if ws["slug"] == active_slug else ""
                ms_count = len(entry.get("milestones", []))
                total = entry.get("total_phases", 0)
                done = entry.get("complete_phases", 0)
                pct = entry.get("overall_pct", 0)
                print(f"  {ws['slug']:<18} {ws['status']:<10} {ms_count:<12} {done}/{total:<8} {pct}%{star}")
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


def _suggest_rtk_exclusions() -> str | None:
    """Return a setup hint when RTK is installed but scripts/*.py is not excluded.

    Returns a message string, or None if RTK is not installed.
    """
    import shutil
    import tomllib

    if not shutil.which("rtk"):
        return None

    config_paths = [
        Path.home() / "Library" / "Application Support" / "rtk" / "config.toml",
        Path.home() / ".config" / "rtk" / "config.toml",
    ]
    config_path = next((p for p in config_paths if p.exists()), None)

    if config_path is not None:
        try:
            with open(config_path, "rb") as f:
                cfg = tomllib.load(f)
            ignore_files = cfg.get("filters", {}).get("ignore_files", [])
            if "scripts/*.py" in ignore_files:
                return None  # already configured
        except Exception:
            pass

    return (
        "RTK detected. Add 'scripts/*.py' to [filters] ignore_files in your RTK config "
        "to prevent internal Meridian scripts from flooding grep/find output. "
        "Run: rtk config"
    )


def cmd_init(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    from scripts.db import init as db_init

    try:
        db_path = db_init(project_dir)
    except Exception as exc:
        print(f"Error initializing Meridian: {exc}", file=sys.stderr)
        sys.exit(1)

    rtk_msg = _suggest_rtk_exclusions()

    if args.json:
        payload: dict = {"status": "ok", "db_path": str(db_path)}
        if rtk_msg:
            payload["rtk"] = rtk_msg
        print(json.dumps(payload, indent=2))
    else:
        print(f"Meridian initialized at {db_path}")
        if rtk_msg:
            print(f"  {rtk_msg}")


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
            print(f"[{result.get('id', '?')}] {result.get('timestamp', '')} — {result.get('text', '')}")

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
        opened = webbrowser.open(dashboard_path.as_uri())
        if not opened:
            print(f"Could not open browser — view file at: {dashboard_path}", file=sys.stderr)


def cmd_execute(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.dispatch import dispatch_plan

    plan_id: int | None = getattr(args, "plan_id", None)

    if plan_id is None:
        msg = (
            "execute dispatches the next pending plan to Nero for autonomous execution.\n"
            "Provide --plan-id N to dispatch a specific plan, or run `meridian next` to\n"
            "see which plan is up next."
        )
        if args.json:
            print(json.dumps({"message": msg}, indent=2))
        else:
            print(msg)
        return

    try:
        result = dispatch_plan(project_dir=project_dir, plan_id=plan_id)
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error dispatching plan: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        status = result.get("status", "unknown")
        print(f"Plan {plan_id} dispatched — status: {status}")
        if result.get("nero_response"):
            print(f"  Nero: {result['nero_response']}")


def cmd_plan(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.state import compute_next_action

    try:
        with _load_conn(project_dir) as conn:
            data = compute_next_action(conn)
    except Exception as exc:
        print(f"Error reading plan state: {exc}", file=sys.stderr)
        sys.exit(1)

    hint = (
        "Tip: use the /meridian:plan skill in Claude Code to create or update plans "
        "with AI assistance."
    )

    if args.json:
        data["_hint"] = hint
        print(json.dumps(data, default=str, indent=2))
    else:
        print(_fmt_next(data))
        print()
        print(hint)


def cmd_resume(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.resume import generate_resume_prompt

    try:
        prompt_text = generate_resume_prompt(project_dir=project_dir)
    except Exception as exc:
        print(f"Error generating resume prompt: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps({"resume_prompt": prompt_text}, indent=2))
    else:
        print(prompt_text)


def cmd_ship(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.milestone_lifecycle import complete_milestone

    milestone_id: str = args.milestone_id

    try:
        with _load_conn(project_dir) as conn:
            result = complete_milestone(
                conn,
                milestone_id,
                repo_path=project_dir,
                planning_dir=project_dir / ".meridian",
            )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc), "milestone_id": milestone_id}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error completing milestone: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        status = result.get("status", "unknown")
        tag = result.get("git_tag", "")
        print(f"Milestone {milestone_id} shipped — status: {status}")
        if tag:
            print(f"  Git tag: {tag}")
        if result.get("summary_path"):
            print(f"  Summary: {result['summary_path']}")


def cmd_checkpoint(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.state import create_checkpoint

    trigger: str = getattr(args, "trigger", None) or "manual"

    try:
        with _load_conn(project_dir) as conn:
            result = create_checkpoint(conn, trigger=trigger, repo_path=str(project_dir))
    except Exception as exc:
        print(f"Error creating checkpoint: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        ckpt_id = result.get("id", "?")
        created_at = result.get("created_at", "")
        print(f"Checkpoint created: [{ckpt_id}] trigger={trigger}  {created_at}")


def cmd_pause(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.freeze import clear_freeze, set_freeze

    clear: bool = getattr(args, "clear", False)
    directory: str | None = getattr(args, "directory", None)

    if not clear and not directory:
        print("Error: provide a DIRECTORY to lock or --clear to remove the lock.", file=sys.stderr)
        sys.exit(1)
    if clear and directory:
        print("Error: DIRECTORY and --clear are mutually exclusive.", file=sys.stderr)
        sys.exit(1)

    try:
        with _load_conn(project_dir) as conn:
            if clear:
                cleared = clear_freeze(conn)
                if args.json:
                    print(json.dumps({"cleared": cleared}, indent=2))
                else:
                    if cleared:
                        print("Edit lock cleared.")
                    else:
                        print("No active edit lock to clear.")
            else:
                result = set_freeze(conn, directory)
                if args.json:
                    print(json.dumps(result, default=str, indent=2))
                else:
                    print(f"Edit lock set: {result['frozen_directory']}")
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error setting pause/freeze: {exc}", file=sys.stderr)
        sys.exit(1)


# ── Review / Validate / Config / Workstream handlers ─────────────────────────


def cmd_review(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.cross_review import detect_models

    try:
        available_models = detect_models()
    except Exception as exc:
        print(f"Error detecting review models: {exc}", file=sys.stderr)
        sys.exit(1)

    result = {
        "project_dir": str(project_dir),
        "available_models": available_models,
        "model_count": len(available_models),
    }

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        if not available_models:
            print("No external review models found.")
            print("Install one of: codex, gemini, aider — then re-run `meridian review`.")
        else:
            print(f"Available review models ({len(available_models)}):")
            for m in available_models:
                print(f"  • {m['name']} ({m['id']})  binary: {m['binary']}")


def cmd_validate(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.validate import validate_state

    try:
        with _load_conn(project_dir) as conn:
            result = validate_state(conn, repo_path=str(project_dir))
    except Exception as exc:
        print(f"Error validating state: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(result, default=str, indent=2))
    else:
        valid = result.get("valid", [])
        drift = result.get("drift", [])
        missing = result.get("missing", [])
        print("Validation results:")
        print(f"  Valid   : {len(valid)} plans (commit SHA found in git)")
        if drift:
            print(f"  Drift   : {len(drift)} plans (content differs)")
        print(f"  Missing : {len(missing)} plans (commit SHA not in git)")
        if missing:
            print(f"  Missing plan IDs: {', '.join(str(i) for i in missing)}")
        if not missing and not drift:
            print("All tracked plans are consistent with git.")


def cmd_config(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.model_profiles import (
        PROFILES,
        VALID_PROFILES,
        format_profile_display,
        get_profile_table,
        set_active_profile,
    )

    subcmd = args.config_command

    if subcmd == "list":
        try:
            with _load_conn(project_dir) as conn:
                data = get_profile_table(conn)
        except Exception as exc:
            print(f"Error listing config: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            payload = {
                "active_profile": data["profile"],
                "profiles": {k: dict(v) for k, v in PROFILES.items()},
                "valid_profiles": sorted(VALID_PROFILES),
            }
            print(json.dumps(payload, default=str, indent=2))
        else:
            print(format_profile_display(data))
            print()
            print(f"Available profiles: {', '.join(sorted(PROFILES.keys()))}")

    elif subcmd == "set":
        key = args.key
        value = args.value
        if key == "model_profile":
            try:
                with _load_conn(project_dir) as conn:
                    result = set_active_profile(conn, value)
            except ValueError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            except Exception as exc:
                print(f"Error setting config: {exc}", file=sys.stderr)
                sys.exit(1)
            if args.json:
                print(json.dumps(result, default=str, indent=2))
            else:
                print(f"Set model_profile → {result['profile']}")
        else:
            print(
                f"Unknown config key: {key!r}\nSupported keys: model_profile",
                file=sys.stderr,
            )
            sys.exit(1)

    elif subcmd == "rtk":
        import shutil
        from scripts.state import get_setting, list_settings, set_setting

        rtk_sub = args.rtk_action
        rtk_installed = bool(shutil.which("rtk"))

        if rtk_sub == "status":
            with _load_conn(project_dir) as conn:
                enabled = get_setting(conn, "rtk_enabled", default="true")
            status_dict = {
                "rtk_installed": rtk_installed,
                "rtk_enabled": enabled == "true",
                "rtk_path": shutil.which("rtk"),
            }
            if args.json:
                print(json.dumps(status_dict, indent=2))
            else:
                installed_str = f"yes ({shutil.which('rtk')})" if rtk_installed else "no"
                print(f"RTK installed : {installed_str}")
                print(f"RTK enabled   : {enabled}")
                if not rtk_installed:
                    print("\nInstall: cargo install rtk  OR  brew install reachingforthejack/rtk/rtk")
                    print("Setup  : rtk init -g --auto-patch")

        elif rtk_sub == "enable":
            with _load_conn(project_dir) as conn:
                set_setting(conn, "rtk_enabled", "true")
            if args.json:
                print(json.dumps({"rtk_enabled": True}))
            else:
                print("RTK enabled for this project.")
                if not rtk_installed:
                    print("Warning: rtk binary not found on PATH.")

        elif rtk_sub == "disable":
            with _load_conn(project_dir) as conn:
                set_setting(conn, "rtk_enabled", "false")
            if args.json:
                print(json.dumps({"rtk_enabled": False}))
            else:
                print("RTK disabled for this project.")

        else:
            print(f"Unknown rtk action: {rtk_sub}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"Unknown config subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


def cmd_workstream(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.workstreams import (
        assign_milestone,
        complete_workstream,
        create_workstream,
        get_all_workstreams_progress,
        get_workstream_progress,
        list_workstreams,
        resume_workstream,
        switch_workstream,
    )

    subcmd = args.workstream_command

    if subcmd == "list":
        status_filter = getattr(args, "status", None)
        try:
            with _load_conn(project_dir) as conn:
                workstreams = list_workstreams(conn, status=status_filter)
        except Exception as exc:
            print(f"Error listing workstreams: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(workstreams, default=str, indent=2))
        else:
            if not workstreams:
                print("No workstreams found.")
            else:
                print(f"Workstreams ({len(workstreams)}):")
                for ws in workstreams:
                    desc = f"  {ws.get('description', '')[:60]}" if ws.get("description") else ""
                    print(f"  [{ws['status']}] {ws['name']}  (slug: {ws['slug']}, id: {ws['id']}){desc}")

    elif subcmd == "create":
        name = args.name
        description = getattr(args, "description", "") or ""
        try:
            with _load_conn(project_dir) as conn:
                ws = create_workstream(conn, name=name, description=description)
        except Exception as exc:
            print(f"Error creating workstream: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ws, default=str, indent=2))
        else:
            print(f"Created workstream: [{ws['status']}] {ws['name']}  (slug: {ws['slug']}, id: {ws['id']})")

    elif subcmd in ("activate", "switch"):
        slug = args.slug
        try:
            with _load_conn(project_dir) as conn:
                ws = switch_workstream(conn, slug=slug)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error activating workstream: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ws, default=str, indent=2))
        else:
            print(f"Activated workstream: [{ws['status']}] {ws['name']}  (slug: {ws['slug']})")

    elif subcmd == "status":
        slug = args.slug
        try:
            with _load_conn(project_dir) as conn:
                progress = get_workstream_progress(conn, slug=slug)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error fetching workstream status: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(progress, default=str, indent=2))
        else:
            ws = progress["workstream"]
            print(f"Workstream: {ws['slug']}")
            print(f"Name: {ws['name']}")
            print(f"Status: {ws['status']}")
            print(f"Progress: {progress['overall_pct']}% ({progress['complete_phases']}/{progress['total_phases']} phases)")
            milestones = progress.get("milestones", [])
            if milestones:
                print("\nMilestones:")
                for ms in milestones:
                    print(f"  [{ms['status']}] {ms['name']}  {ms['phase_done']}/{ms['phase_count']} phases ({ms['pct']}%)")

    elif subcmd == "progress":
        try:
            with _load_conn(project_dir) as conn:
                all_progress = get_all_workstreams_progress(conn)
        except Exception as exc:
            print(f"Error fetching workstream progress: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(all_progress, default=str, indent=2))
        else:
            if not all_progress:
                print("No workstreams found.")
            else:
                print("## Portfolio Progress\n")
                print(f"{'Workstream':<20} {'Status':<10} {'Milestones':<12} {'Phases':<10} {'Progress'}")
                print("-" * 65)
                for entry in all_progress:
                    ws = entry["workstream"]
                    ms_count = len(entry.get("milestones", []))
                    total = entry.get("total_phases", 0)
                    done = entry.get("complete_phases", 0)
                    pct = entry.get("overall_pct", 0)
                    print(f"  {ws['slug']:<18} {ws['status']:<10} {ms_count:<12} {done}/{total:<8} {pct}%")

    elif subcmd == "complete":
        slug = args.slug
        try:
            with _load_conn(project_dir) as conn:
                ws = complete_workstream(conn, slug=slug)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error completing workstream: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ws, default=str, indent=2))
        else:
            print(f"Completed workstream: [{ws['status']}] {ws['name']}  (slug: {ws['slug']})")

    elif subcmd == "resume":
        slug = args.slug
        try:
            with _load_conn(project_dir) as conn:
                ws = resume_workstream(conn, slug=slug)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error resuming workstream: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps(ws, default=str, indent=2))
        else:
            print(f"Resumed workstream: [{ws['status']}] {ws['name']}  (slug: {ws['slug']})")

    elif subcmd == "assign":
        milestone_id = args.milestone_id
        workstream_slug = args.workstream_slug
        try:
            with _load_conn(project_dir) as conn:
                assign_milestone(conn, milestone_id=milestone_id, workstream_slug=workstream_slug)
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        except Exception as exc:
            print(f"Error assigning milestone: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"status": "ok", "milestone_id": milestone_id, "workstream_slug": workstream_slug}))
        else:
            print(f"Assigned milestone {milestone_id} to workstream {workstream_slug}")

    else:
        print(f"Unknown workstream subcommand: {subcmd}", file=sys.stderr)
        sys.exit(1)


def cmd_stats(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.db import open_project
    from scripts.stats import compute_stats, format_stats

    with open_project(project_dir) as conn:
        data = compute_stats(conn, project_dir)

    if args.json:
        print(json.dumps(data, default=str, indent=2))
    else:
        print(format_stats(data))


def cmd_ultraplan(args: argparse.Namespace) -> None:
    project_dir = Path(args.project_dir).resolve()
    _check_db(project_dir)
    from scripts.ultraplan import check_ultraplan_availability, run_cloud_plan

    force_local = getattr(args, "local", False)
    force_cloud = getattr(args, "cloud", False)
    dry_run = getattr(args, "dry_run", False)
    phase_id = getattr(args, "phase", None)
    goal = getattr(args, "goal", "") or ""

    # Step 1: Check availability (skip if --local)
    if force_local:
        availability = {"available": False, "mode": "local", "version": None, "reason": "--local flag set"}
    else:
        try:
            availability = check_ultraplan_availability(project_dir)
        except Exception as exc:
            print(f"Error checking ultraplan availability: {exc}", file=sys.stderr)
            sys.exit(1)

    if dry_run:
        if args.json:
            print(json.dumps(availability, indent=2))
        else:
            mode = availability.get("mode", "local").upper()
            reason = availability.get("reason", "")
            print(f"## Ultraplan — {mode} Mode (dry-run)\n\n{reason}")
        return

    # Step 2: Enforce --cloud flag
    if force_cloud and not availability.get("available"):
        reason = availability.get("reason", "cloud unavailable")
        print(f"Error: --cloud required but cloud backend unavailable: {reason}", file=sys.stderr)
        sys.exit(1)

    mode = "cloud" if availability.get("available") else "local"

    if not args.json:
        if mode == "cloud":
            print("## Ultraplan — CLOUD Mode\n\nOffloading plan generation to Claude Code cloud backend.")
        else:
            reason = availability.get("reason", "")
            print(f"## Ultraplan — LOCAL Mode (fallback)\n\nCloud backend unavailable: {reason}\nRunning local planning pipeline.")

    # Step 3: Execute
    if mode == "cloud":
        try:
            result = run_cloud_plan(project_dir, phase_id=phase_id, goal=goal)
        except Exception as exc:
            print(f"Error running cloud plan: {exc}", file=sys.stderr)
            sys.exit(1)
        if result.get("status") == "failed" and not force_cloud:
            # Fall back to local
            mode = "local"
            if not args.json:
                print(f"\nCloud plan failed: {result.get('error')} — falling back to local planning.")
        elif result.get("status") == "failed":
            print(f"Error: cloud plan failed: {result.get('error')}", file=sys.stderr)
            sys.exit(1)
        else:
            if args.json:
                print(json.dumps(result, default=str, indent=2))
            else:
                plans = result.get("plans", [])
                paths = result.get("artifact_paths", [])
                print(f"\n## Ultraplan Complete\n\nMode: CLOUD\nPlans generated: {len(plans)}")
                if paths:
                    print("Artifacts: " + ", ".join(str(p) for p in paths))
                print("\nNext: /meridian:execute")
            return

    if mode == "local":
        if not args.json:
            print("\nInvoke /meridian:plan to run the local planning pipeline.")
        if args.json:
            print(json.dumps({"mode": "local", "message": "Run /meridian:plan to continue."}))


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
    status_p.add_argument(
        "--all-workstreams",
        dest="all_workstreams",
        action="store_true",
        help="Include workstream portfolio in output",
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

    # execute
    execute_p = subparsers.add_parser(
        "execute",
        help="Dispatch a plan to Nero for autonomous execution",
    )
    execute_p.add_argument(
        "--plan-id",
        type=int,
        default=None,
        metavar="N",
        help="Plan ID to dispatch (omit to see dispatch instructions)",
    )
    execute_p.set_defaults(func=cmd_execute)

    # plan
    plan_p = subparsers.add_parser(
        "plan",
        help="Show current plan status (use /meridian:plan skill for AI-assisted creation)",
    )
    plan_p.set_defaults(func=cmd_plan)

    # resume
    resume_p = subparsers.add_parser(
        "resume",
        help="Generate a deterministic resume prompt from current project state",
    )
    resume_p.set_defaults(func=cmd_resume)

    # ship
    ship_p = subparsers.add_parser(
        "ship",
        help="Complete (ship) a milestone after all phases pass validation",
    )
    ship_p.add_argument(
        "--milestone-id",
        required=True,
        metavar="ID",
        help="Milestone ID to ship (e.g. M001)",
    )
    ship_p.set_defaults(func=cmd_ship)

    # checkpoint
    checkpoint_p = subparsers.add_parser(
        "checkpoint",
        help="Create a manual checkpoint capturing current project state",
    )
    checkpoint_p.add_argument(
        "--trigger",
        default="manual",
        metavar="TEXT",
        help="Checkpoint trigger label (default: manual)",
    )
    checkpoint_p.set_defaults(func=cmd_checkpoint)

    # pause
    pause_p = subparsers.add_parser(
        "pause",
        help="Set or clear an edit-scope lock (freeze) on a directory",
    )
    pause_p.add_argument(
        "directory",
        nargs="?",
        default=None,
        metavar="DIRECTORY",
        help="Directory path to lock edits to",
    )
    pause_p.add_argument(
        "--clear",
        action="store_true",
        help="Remove the active edit-scope lock",
    )
    pause_p.set_defaults(func=cmd_pause)

    # review
    review_p = subparsers.add_parser(
        "review",
        help="Show available cross-model review tools (codex, gemini, aider)",
    )
    review_p.set_defaults(func=cmd_review)

    # validate
    validate_p = subparsers.add_parser(
        "validate",
        help="Validate DB state against git (check plan commit SHAs)",
    )
    validate_p.set_defaults(func=cmd_validate)

    # config
    config_p = subparsers.add_parser(
        "config",
        help="View or update project configuration (model profiles, settings)",
    )
    config_subs = config_p.add_subparsers(dest="config_command", metavar="SUBCOMMAND")
    config_subs.required = True

    config_subs.add_parser("list", help="List current config / active model profile")

    config_set_p = config_subs.add_parser("set", help="Set a config key (e.g. model_profile)")
    config_set_p.add_argument("key", choices=["model_profile"], help="Config key to set")
    config_set_p.add_argument("value", help="Config value (e.g. balanced, quality, budget)")

    config_rtk_p = config_subs.add_parser("rtk", help="RTK token-optimization settings")
    config_rtk_p.add_argument(
        "rtk_action",
        choices=["status", "enable", "disable"],
        help="status: show RTK state | enable/disable: toggle RTK for this project",
    )

    config_p.set_defaults(func=cmd_config)

    # workstream
    ws_p = subparsers.add_parser(
        "workstream",
        help="Manage workstreams (multi-track parallel milestone management)",
    )
    ws_subs = ws_p.add_subparsers(dest="workstream_command", metavar="SUBCOMMAND")
    ws_subs.required = True

    ws_list_p = ws_subs.add_parser("list", help="List workstreams")
    ws_list_p.add_argument(
        "--status",
        default=None,
        metavar="STATUS",
        help="Filter by status: active, paused, complete, archived",
    )

    ws_create_p = ws_subs.add_parser("create", help="Create a new workstream")
    ws_create_p.add_argument("name", help="Workstream name")
    ws_create_p.add_argument(
        "--description",
        default="",
        metavar="TEXT",
        help="Optional description",
    )

    ws_activate_p = ws_subs.add_parser("activate", help="Activate (switch to) a workstream")
    ws_activate_p.add_argument("slug", help="Workstream slug to activate")

    ws_switch_p = ws_subs.add_parser("switch", help="Switch to a workstream (alias for activate)")
    ws_switch_p.add_argument("slug", help="Workstream slug to switch to")

    ws_status_p = ws_subs.add_parser("status", help="Show a workstream's details and milestone progress")
    ws_status_p.add_argument("slug", help="Workstream slug")

    ws_subs.add_parser("progress", help="Show progress across all workstreams")

    ws_complete_p = ws_subs.add_parser("complete", help="Mark a workstream as complete")
    ws_complete_p.add_argument("slug", help="Workstream slug")

    ws_resume_p = ws_subs.add_parser("resume", help="Re-activate a paused workstream")
    ws_resume_p.add_argument("slug", help="Workstream slug")

    ws_assign_p = ws_subs.add_parser("assign", help="Assign a milestone to a workstream")
    ws_assign_p.add_argument("milestone_id", help="Milestone ID (e.g. M001)")
    ws_assign_p.add_argument("workstream_slug", help="Workstream slug")

    ws_p.set_defaults(func=cmd_workstream)

    # stats
    stats_p = subparsers.add_parser(
        "stats",
        help="Show project statistics (phases, plans, git, tests, velocity)",
    )
    stats_p.set_defaults(func=cmd_stats)

    # ultraplan
    ultraplan_p = subparsers.add_parser(
        "ultraplan",
        help="Cloud-accelerated planning with local fallback (Phase 39)",
    )
    ultraplan_p.add_argument(
        "goal",
        nargs="?",
        default="",
        help="Planning goal (same as /meridian:plan)",
    )
    ultraplan_p.add_argument(
        "--phase",
        type=int,
        default=None,
        metavar="N",
        help="Plan a specific phase by ID",
    )
    ultraplan_p.add_argument(
        "--deep",
        action="store_true",
        help="Force deep discovery questions before planning",
    )
    ultraplan_p.add_argument(
        "--local",
        action="store_true",
        help="Skip cloud check and run local planning directly",
    )
    ultraplan_p.add_argument(
        "--cloud",
        action="store_true",
        help="Require cloud backend; fail if unavailable",
    )
    ultraplan_p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Check cloud availability and print mode; do not plan",
    )
    ultraplan_p.set_defaults(func=cmd_ultraplan)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
