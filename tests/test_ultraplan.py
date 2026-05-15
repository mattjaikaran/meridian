"""Tests for scripts/ultraplan.py — availability check, cloud plan, CLI surface."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from scripts.cli import main
from scripts.state import create_project, set_setting
from scripts.ultraplan import check_ultraplan_availability, run_cloud_plan


# ── Helpers ───────────────────────────────────────────────────────────────────


def _argv(tmp_path, *args, json_flag: bool = False):
    base = ["meridian", "--project-dir", str(tmp_path)]
    if json_flag:
        base.append("--json")
    return base + list(args)


# ── check_ultraplan_availability ─────────────────────────────────────────────


class TestCheckUltraplanAvailability:
    def test_returns_local_when_not_enabled(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()

        result = check_ultraplan_availability(tmp_path)
        assert result["available"] is False
        assert result["mode"] == "local"
        assert "ultraplan_enabled" in result["reason"]

    def test_returns_local_when_no_endpoint(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        conn.close()

        result = check_ultraplan_availability(tmp_path)
        assert result["available"] is False
        assert result["mode"] == "local"
        assert "endpoint" in result["reason"]

    def test_returns_local_on_unreachable_endpoint(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://localhost:19999")
        conn.close()

        result = check_ultraplan_availability(tmp_path)
        assert result["available"] is False
        assert result["mode"] == "local"
        assert "unreachable" in result["reason"].lower() or "error" in result["reason"].lower()

    def test_returns_cloud_when_healthy(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.close()

        import urllib.request
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = check_ultraplan_availability(tmp_path)

        assert result["available"] is True
        assert result["mode"] == "cloud"

    def test_returns_local_on_unhealthy_response(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.close()

        import urllib.request
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "degraded"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = check_ultraplan_availability(tmp_path)

        assert result["available"] is False
        assert "unhealthy" in result["reason"].lower() or "degraded" in result["reason"].lower()

    def test_cc_version_below_minimum_returns_local(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.close()

        with patch("scripts.ultraplan._detect_cc_version", return_value="1.0.0"):
            result = check_ultraplan_availability(tmp_path)

        assert result["available"] is False
        assert result["mode"] == "local"
        assert "1.0.0" in result["reason"]


# ── run_cloud_plan ────────────────────────────────────────────────────────────


class TestRunCloudPlan:
    def test_returns_failed_when_no_endpoint(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()

        result = run_cloud_plan(tmp_path, goal="build something")
        assert result["status"] == "failed"
        assert "endpoint" in result["error"].lower()
        assert result["plans"] == []

    def test_returns_failed_when_no_active_phase(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.close()

        result = run_cloud_plan(tmp_path, goal="build something")
        assert result["status"] == "failed"
        assert "No phase" in result["error"] or "phase" in result["error"].lower()

    def test_returns_success_on_valid_response(self, file_db):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.execute(
            "INSERT INTO milestone (id, project_id, name, status, created_at) VALUES ('M1', 'default', 'v1', 'active', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO phase (milestone_id, sequence, name, status, created_at) VALUES ('M1', 1, 'Build X', 'executing', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        import urllib.request
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"plans": ["plan-A", "plan-B"], "artifact_paths": ["/tmp/plan.md"]}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.object(urllib.request, "urlopen", return_value=mock_resp):
            result = run_cloud_plan(tmp_path, goal="build X")

        assert result["status"] == "success"
        assert len(result["plans"]) == 2
        assert result["error"] is None

    def test_returns_failed_on_url_error(self, file_db):
        import urllib.error

        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.execute(
            "INSERT INTO milestone (id, project_id, name, status, created_at) VALUES ('M1', 'default', 'v1', 'active', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO phase (milestone_id, sequence, name, status, created_at) VALUES ('M1', 1, 'Build X', 'executing', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            result = run_cloud_plan(tmp_path, goal="build X")

        assert result["status"] == "failed"
        assert result["plans"] == []


# ── CLI: ultraplan subcommand ─────────────────────────────────────────────────


class TestUltraplanCLI:
    def test_dry_run_local_mode(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "--dry-run"))
        main()
        captured = capsys.readouterr()
        assert "LOCAL" in captured.out or "local" in captured.out

    def test_dry_run_json(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "--dry-run", json_flag=True))
        main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "available" in data
        assert "mode" in data

    def test_local_flag_skips_cloud_check(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "--local", "--dry-run"))
        main()
        captured = capsys.readouterr()
        assert "LOCAL" in captured.out or "--local" in captured.out or "local" in captured.out.lower()

    def test_cloud_flag_fails_when_unavailable(self, file_db, monkeypatch):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "--cloud"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_no_db_exits_nonzero(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "--dry-run"))
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code != 0

    def test_local_mode_prints_fallback_message(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        conn.commit()
        conn.close()
        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "build something", "--local"))
        main()
        captured = capsys.readouterr()
        assert "local" in captured.out.lower() or "plan" in captured.out.lower()

    def test_cloud_mode_prints_success(self, file_db, monkeypatch, capsys):
        conn, tmp_path = file_db
        create_project(conn, name="TestProject", repo_path=str(tmp_path))
        set_setting(conn, "ultraplan_enabled", "true")
        set_setting(conn, "ultraplan_endpoint", "http://cloud.test")
        conn.execute(
            "INSERT INTO milestone (id, project_id, name, status, created_at) VALUES ('M1', 'default', 'v1', 'active', '2026-01-01')"
        )
        conn.execute(
            "INSERT INTO phase (milestone_id, sequence, name, status, created_at) VALUES ('M1', 1, 'Build X', 'executing', '2026-01-01')"
        )
        conn.commit()
        conn.close()

        import urllib.request
        health_resp = MagicMock()
        health_resp.read.return_value = json.dumps({"status": "ok"}).encode()
        health_resp.__enter__ = lambda s: s
        health_resp.__exit__ = MagicMock(return_value=False)

        plan_resp = MagicMock()
        plan_resp.read.return_value = json.dumps({"plans": ["p1"], "artifact_paths": []}).encode()
        plan_resp.__enter__ = lambda s: s
        plan_resp.__exit__ = MagicMock(return_value=False)

        responses = [health_resp, plan_resp]

        def fake_urlopen(req, timeout=None):
            return responses.pop(0)

        monkeypatch.setattr("sys.argv", _argv(tmp_path, "ultraplan", "build X"))
        with patch.object(urllib.request, "urlopen", side_effect=fake_urlopen):
            main()

        captured = capsys.readouterr()
        assert "CLOUD" in captured.out or "cloud" in captured.out.lower()
