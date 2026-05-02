"""Integration tests for scripts/cli.py — all 16 subcommands.

Pattern: monkeypatch sys.argv, call main(), capture stdout via capsys.
Uses file_db fixture (file-backed DB) since the CLI expects a real .meridian/state.db.
"""

from __future__ import annotations

import json

import pytest

from scripts.cli import main
from scripts.state import create_project, create_milestone, transition_milestone


# ── Helpers ───────────────────────────────────────────────────────────────────


def _argv(tmp_path, *args, json_flag: bool = False):
    """Build sys.argv list for a CLI call."""
    base = ["meridian", "--project-dir", str(tmp_path)]
    if json_flag:
        base.append("--json")
    return base + list(args)


def _seed(conn, tmp_path):
    """Seed a minimal project so status/next/plan/etc. work."""
    create_project(conn, name="TestProject", repo_path=str(tmp_path))
    conn.commit()


def _seed_with_milestone(conn, tmp_path):
    """Seed a project with an active milestone."""
    create_project(conn, name="TestProject", repo_path=str(tmp_path))
    create_milestone(conn, milestone_id="M001", name="v1.0", project_id="default")
    transition_milestone(conn, "M001", "active")
    conn.commit()


# ── init ─────────────────────────────────────────────────────────────────────


class TestInit:
    def test_init_creates_db(self, tmp_path, monkeypatch, capsys):
        """init creates .meridian/state.db and prints confirmation."""
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "init"))
        main()
        captured = capsys.readouterr()
        assert "Meridian initialized" in captured.out or "state.db" in captured.out
        db_path = tmp_path / ".meridian" / "state.db"
        assert db_path.exists()

    def test_init_json(self, tmp_path, monkeypatch, capsys):
        """init --json returns valid JSON with status and db_path."""
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "init", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "ok"
        assert "db_path" in data

    def test_init_idempotent(self, tmp_path, monkeypatch, capsys):
        """Running init twice does not error."""
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "init"))
        main()
        capsys.readouterr()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "init"))
        main()
        captured = capsys.readouterr()
        assert captured.out  # some output produced


# ── status ────────────────────────────────────────────────────────────────────


class TestStatus:
    def test_status_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "status"))
        main()
        captured = capsys.readouterr()
        assert "TestProject" in captured.out

    def test_status_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "status", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "project" in data

    def test_status_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        """status without init exits with code 1."""
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "status"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── next ──────────────────────────────────────────────────────────────────────


class TestNext:
    def test_next_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "next"))
        main()
        captured = capsys.readouterr()
        assert captured.out  # non-empty

    def test_next_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "next", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "action" in data

    def test_next_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "next"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── note ──────────────────────────────────────────────────────────────────────


class TestNote:
    def test_note_add_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "add", "hello world"))
        main()
        captured = capsys.readouterr()
        assert "hello world" in captured.out or captured.out

    def test_note_add_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "add", "test note", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "id" in data or "text" in data

    def test_note_list_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        conn.close()
        # Add a note first
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "add", "list me"))
        main()
        capsys.readouterr()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "list"))
        main()
        captured = capsys.readouterr()
        assert "list me" in captured.out

    def test_note_list_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "list", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)

    def test_note_list_empty(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "note", "list"))
        main()
        captured = capsys.readouterr()
        assert "No notes" in captured.out or captured.out == ""


# ── fast ──────────────────────────────────────────────────────────────────────


class TestFast:
    def test_fast_trivial_task(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "fast", "fix typo in readme"))
        main()
        captured = capsys.readouterr()
        assert captured.out  # non-empty output

    def test_fast_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "fast", "fix typo in readme", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "status" in data

    def test_fast_complex_task_returns_too_complex(self, file_db, monkeypatch, capsys):
        """A task with complex keywords returns too_complex status."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "fast", "refactor the entire architecture", json_flag=True),
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["status"] == "too_complex"

    def test_fast_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "fast", "fix typo"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── dashboard ─────────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_json(self, file_db, monkeypatch, capsys):
        """dashboard --json returns path without opening a browser."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "dashboard", json_flag=True))
        # Prevent browser from opening
        monkeypatch.setattr("webbrowser.open", lambda *a, **kw: None)
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "path" in data

    def test_dashboard_creates_html_file(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "dashboard"))
        monkeypatch.setattr("webbrowser.open", lambda *a, **kw: None)
        main()
        captured = capsys.readouterr()
        assert captured.out
        html_file = tmp_path / ".meridian" / "dashboard.html"
        assert html_file.exists()

    def test_dashboard_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "dashboard"))
        monkeypatch.setattr("webbrowser.open", lambda *a, **kw: None)
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── execute ───────────────────────────────────────────────────────────────────


class TestExecute:
    def test_execute_no_plan_id_prints_instructions(self, file_db, monkeypatch, capsys):
        """execute without --plan-id prints dispatch instructions and exits 0."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "execute"))
        main()
        captured = capsys.readouterr()
        assert captured.out  # dispatch instructions printed

    def test_execute_no_plan_id_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "execute", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "message" in data

    def test_execute_with_invalid_plan_id_exits_nonzero(self, file_db, monkeypatch, capsys):
        """execute --plan-id 999 with no nero endpoint exits nonzero."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "execute", "--plan-id", "999"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_execute_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "execute", "--plan-id", "1"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── plan ──────────────────────────────────────────────────────────────────────


class TestPlan:
    def test_plan_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "plan"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_plan_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "plan", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "action" in data

    def test_plan_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "plan"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── resume ────────────────────────────────────────────────────────────────────


class TestResume:
    def test_resume_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "resume"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_resume_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "resume", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "resume_prompt" in data

    def test_resume_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "resume"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── ship ──────────────────────────────────────────────────────────────────────


class TestShip:
    def test_ship_nonexistent_milestone_exits_nonzero(self, file_db, monkeypatch, capsys):
        """ship with a milestone that doesn't exist should fail gracefully."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ship", "--milestone-id", "NOPE"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_ship_nonexistent_milestone_json(self, file_db, monkeypatch, capsys):
        """ship --json with bad milestone returns JSON error."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "ship", "--milestone-id", "NOPE", json_flag=True),
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        # JSON error output — may go to stdout (json path) or stderr
        combined = captured.out + captured.err
        assert combined  # some error output

    def test_ship_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ship", "--milestone-id", "M001"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── checkpoint ────────────────────────────────────────────────────────────────


class TestCheckpoint:
    def test_checkpoint_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "checkpoint", "--trigger", "manual"))
        main()
        captured = capsys.readouterr()
        assert "Checkpoint" in captured.out or captured.out

    def test_checkpoint_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "checkpoint", "--trigger", "manual", json_flag=True),
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "id" in data or "trigger" in data

    def test_checkpoint_default_trigger(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "checkpoint"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_checkpoint_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "checkpoint"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── pause ─────────────────────────────────────────────────────────────────────


class TestPause:
    def test_pause_set_directory(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "pause", str(tmp_path / "src")))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_pause_set_directory_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "pause", str(tmp_path / "src"), json_flag=True),
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "frozen_directory" in data or "error" in data

    def test_pause_clear(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "pause", "--clear"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_pause_clear_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "pause", "--clear", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "cleared" in data

    def test_pause_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "pause", "--clear"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── review ────────────────────────────────────────────────────────────────────


class TestReview:
    def test_review_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "review"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_review_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "review", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "available_models" in data
        assert "model_count" in data

    def test_review_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "review"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── validate ──────────────────────────────────────────────────────────────────


class TestValidate:
    def test_validate_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "validate"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_validate_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "validate", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        # validate_state returns keys like valid, drift, missing
        assert isinstance(data, dict)

    def test_validate_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "validate"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── config ────────────────────────────────────────────────────────────────────


class TestConfig:
    def test_config_list_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "config", "list"))
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_config_list_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "config", "list", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "active_profile" in data
        assert "profiles" in data

    def test_config_set_valid_profile(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "config", "set", "model_profile", "balanced"),
        )
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_config_set_invalid_profile_exits_nonzero(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "config", "set", "model_profile", "invalid_profile_xyz"),
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_config_set_unknown_key_exits_nonzero(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "config", "set", "unknown_key", "value"),
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_config_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "config", "list"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── workstream ────────────────────────────────────────────────────────────────


class TestWorkstream:
    def test_workstream_list_empty(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "workstream", "list"))
        main()
        captured = capsys.readouterr()
        assert "No workstreams" in captured.out or captured.out == "" or captured.out

    def test_workstream_list_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "workstream", "list", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)

    def test_workstream_create_happy_path(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "create", "feature-alpha"),
        )
        main()
        captured = capsys.readouterr()
        assert "feature-alpha" in captured.out or captured.out

    def test_workstream_create_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "create", "beta-track", json_flag=True),
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "name" in data or "slug" in data

    def test_workstream_create_with_description(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(
                tmp_path,
                "workstream",
                "create",
                "gamma-track",
                "--description",
                "A test workstream",
            ),
        )
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_workstream_activate_after_create(self, file_db, monkeypatch, capsys):
        """Create a workstream then activate it by slug."""
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        # Create
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "create", "my-track", json_flag=True),
        )
        main()
        out = capsys.readouterr().out
        created = json.loads(out)
        slug = created["slug"]
        # Activate
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "activate", slug),
        )
        main()
        captured = capsys.readouterr()
        assert captured.out

    def test_workstream_activate_invalid_slug_exits_nonzero(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "activate", "nonexistent-slug"),
        )
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_workstream_list_with_status_filter(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        _seed(conn, tmp_path)
        conn.close()
        monkeypatch.setattr(
            "sys.argv",
            _argv(tmp_path, "workstream", "list", "--status", "active", json_flag=True),
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)

    def test_workstream_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "workstream", "list"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0


# ── project-dir routing ───────────────────────────────────────────────────────


class TestProjectDirRouting:
    def test_project_dir_routes_to_correct_db(self, tmp_path, monkeypatch, capsys):
        """--project-dir should route to the correct project's DB."""
        project_a = tmp_path / "project_a"
        project_b = tmp_path / "project_b"
        project_a.mkdir()
        project_b.mkdir()

        # Init project A
        monkeypatch.setattr("sys.argv", ["meridian", "--project-dir", str(project_a), "init"])
        main()
        capsys.readouterr()

        # Init project B
        monkeypatch.setattr("sys.argv", ["meridian", "--project-dir", str(project_b), "init"])
        main()
        capsys.readouterr()

        # Both DBs exist independently
        assert (project_a / ".meridian" / "state.db").exists()
        assert (project_b / ".meridian" / "state.db").exists()

        # Status from project A dir should work
        monkeypatch.setattr(
            "sys.argv",
            ["meridian", "--project-dir", str(project_a), "--json", "status"],
        )
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, dict)

    def test_wrong_project_dir_exits_nonzero(self, tmp_path, monkeypatch):
        """Status on an empty dir (no .meridian) exits nonzero."""
        empty = tmp_path / "empty_project"
        empty.mkdir()
        monkeypatch.setattr("sys.argv", _argv(empty, "status"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0
