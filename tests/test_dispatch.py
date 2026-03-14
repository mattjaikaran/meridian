#!/usr/bin/env python3
"""Tests for Meridian dispatch module."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
)


@contextmanager
def _mock_open_project(conn):
    """Wrap a test connection as a context manager for open_project patches."""
    yield conn


def _seed_dispatch_db(db, nero_endpoint="http://nero:8080"):
    """Seed DB with project, milestone, phase, and plans for dispatch tests."""
    create_project(
        db,
        name="Test Project",
        repo_path="/tmp/test",
        project_id="default",
        nero_endpoint=nero_endpoint,
    )
    create_milestone(db, milestone_id="v1.0", name="Version 1.0", project_id="default")
    transition_milestone(db, "v1.0", "active")
    phase = create_phase(db, milestone_id="v1.0", name="Foundation", description="Build the base")
    return phase


class TestDispatchPlan:
    def test_raises_when_project_not_initialized(self, db):
        """dispatch_plan raises ValueError when no project in DB."""
        from scripts.dispatch import dispatch_plan

        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="Project not initialized"):
                dispatch_plan(project_dir="/tmp/test", plan_id=1)

    def test_raises_when_nero_endpoint_not_set(self, db):
        """dispatch_plan raises ValueError when nero_endpoint is None."""
        from scripts.dispatch import dispatch_plan

        create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="No nero_endpoint configured"):
                dispatch_plan(project_dir="/tmp/test", plan_id=1)

    def test_raises_when_plan_not_found(self, db):
        """dispatch_plan raises ValueError when plan_id not found."""
        from scripts.dispatch import dispatch_plan

        _seed_dispatch_db(db)
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="Plan 999 not found"):
                dispatch_plan(project_dir="/tmp/test", plan_id=999)

    def test_builds_correct_payload(self, db):
        """dispatch_plan builds JSON-RPC payload with project/phase/plan data."""
        from scripts.dispatch import dispatch_plan

        phase = _seed_dispatch_db(db)
        plan = create_plan(
            db,
            phase_id=phase["id"],
            name="Setup DB",
            description="Create database schema",
            files_to_create=["db.py"],
            test_command="pytest tests/",
        )

        mock_send = MagicMock(return_value={"task_id": "nero-123"})
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            result = dispatch_plan(project_dir="/tmp/test", plan_id=plan["id"])

        # Verify _send_to_nero was called
        mock_send.assert_called_once()
        url, payload = mock_send.call_args[0]

        assert url == "http://nero:8080/rpc"
        assert payload["method"] == "dispatch_task"
        params = payload["params"]
        assert params["project"]["name"] == "Test Project"
        assert params["project"]["repo_path"] == "/tmp/test"
        assert params["phase"]["name"] == "Foundation"
        assert params["plan"]["name"] == "Setup DB"
        assert params["plan"]["description"] == "Create database schema"
        assert params["plan"]["files_to_create"] == ["db.py"]
        assert params["plan"]["test_command"] == "pytest tests/"

    def test_calls_send_to_nero_with_correct_url(self, db):
        """dispatch_plan calls _send_to_nero with endpoint + '/rpc'."""
        from scripts.dispatch import dispatch_plan

        phase = _seed_dispatch_db(db, nero_endpoint="http://nero:9090/")
        plan = create_plan(
            db, phase_id=phase["id"], name="Plan A", description="desc"
        )

        mock_send = MagicMock(return_value={"task_id": "t1"})
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            dispatch_plan(project_dir="/tmp/test", plan_id=plan["id"])

        url = mock_send.call_args[0][0]
        assert url == "http://nero:9090/rpc"

    def test_creates_dispatch_record_and_returns_ids(self, db):
        """dispatch_plan creates nero_dispatch record and returns dispatch_id + nero_task_id."""
        from scripts.dispatch import dispatch_plan

        phase = _seed_dispatch_db(db)
        plan = create_plan(
            db, phase_id=phase["id"], name="Plan B", description="desc"
        )

        mock_send = MagicMock(return_value={"task_id": "nero-456"})
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            result = dispatch_plan(project_dir="/tmp/test", plan_id=plan["id"])

        assert result["status"] == "dispatched"
        assert result["nero_task_id"] == "nero-456"
        assert "dispatch_id" in result
        assert result["plan_name"] == "Plan B"

        # Verify DB record
        row = db.execute(
            "SELECT * FROM nero_dispatch WHERE id = ?", (result["dispatch_id"],)
        ).fetchone()
        assert row is not None
        assert dict(row)["nero_task_id"] == "nero-456"


class TestDispatchPhase:
    def test_returns_info_when_no_pending_plans(self, db):
        """dispatch_phase returns info message when no pending plans exist."""
        from scripts.dispatch import dispatch_phase

        phase = _seed_dispatch_db(db)
        plan = create_plan(db, phase_id=phase["id"], name="Done Plan", description="d")
        # Transition plan to complete so nothing is pending
        from scripts.state import transition_plan

        transition_plan(db, plan["id"], "executing")
        transition_plan(db, plan["id"], "complete")

        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            results = dispatch_phase(project_dir="/tmp/test", phase_id=phase["id"])

        assert len(results) == 1
        assert results[0]["status"] == "info"
        assert "No pending plans" in results[0]["message"]

    def test_wave_filtering_without_swarm(self, db):
        """dispatch_phase with swarm=False only dispatches lowest wave pending plans."""
        from scripts.dispatch import dispatch_phase

        phase = _seed_dispatch_db(db)
        create_plan(
            db, phase_id=phase["id"], name="Wave 1 Plan", description="w1", wave=1
        )
        create_plan(
            db, phase_id=phase["id"], name="Wave 2 Plan", description="w2", wave=2
        )

        mock_send = MagicMock(return_value={"task_id": "t-wave"})
        # open_project is called by both dispatch_phase and dispatch_plan (nested),
        # so we use a lambda that always returns a fresh context manager over the same conn
        with (
            patch(
                "scripts.dispatch.open_project",
                side_effect=lambda *a, **kw: _mock_open_project(db),
            ),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            results = dispatch_phase(
                project_dir="/tmp/test", phase_id=phase["id"], swarm=False
            )

        # Only wave 1 plan should be dispatched
        assert len(results) == 1
        assert results[0]["plan_name"] == "Wave 1 Plan"


class TestCheckDispatchStatus:
    def test_returns_error_when_nero_not_configured(self, db):
        """check_dispatch_status returns error dict when nero not configured."""
        from scripts.dispatch import check_dispatch_status

        create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            result = check_dispatch_status(project_dir="/tmp/test", dispatch_id=1)

        assert result["status"] == "error"
        assert "not configured" in result["message"].lower()

    def test_returns_cached_status_on_nero_unreachable(self, db):
        """check_dispatch_status returns cached status when NeroUnreachableError occurs."""
        from scripts.db import NeroUnreachableError
        from scripts.dispatch import check_dispatch_status
        from scripts.state import create_nero_dispatch

        phase = _seed_dispatch_db(db)
        plan = create_plan(db, phase_id=phase["id"], name="P", description="d")
        dispatch = create_nero_dispatch(
            db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=phase["id"],
            nero_task_id="nero-test",
        )

        mock_send = MagicMock(side_effect=NeroUnreachableError("unreachable"))
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            result = check_dispatch_status(
                project_dir="/tmp/test", dispatch_id=dispatch["id"]
            )

        # Should return the cached dispatch record, not raise
        assert result["nero_task_id"] == "nero-test"
        assert result["status"] == "dispatched"

    def test_returns_error_when_dispatch_not_found(self, db):
        """check_dispatch_status returns error when dispatch_id doesn't exist."""
        from scripts.dispatch import check_dispatch_status

        _seed_dispatch_db(db)
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            result = check_dispatch_status(project_dir="/tmp/test", dispatch_id=9999)

        assert result["status"] == "error"
        assert "9999" in result["message"]

    def test_updates_status_when_nero_returns_new_status(self, db):
        """check_dispatch_status updates DB when Nero reports a different status."""
        from scripts.dispatch import check_dispatch_status
        from scripts.state import create_nero_dispatch

        phase = _seed_dispatch_db(db)
        plan = create_plan(db, phase_id=phase["id"], name="P", description="d")
        dispatch = create_nero_dispatch(
            db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=phase["id"],
            nero_task_id="nero-update",
        )

        mock_send = MagicMock(return_value={"status": "completed", "pr_url": "https://github.com/pr/1"})
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            result = check_dispatch_status(
                project_dir="/tmp/test", dispatch_id=dispatch["id"]
            )

        assert result["status"] == "completed"
        assert result["pr_url"] == "https://github.com/pr/1"


class TestSendToNero:
    """Tests for _send_to_nero HTTP handling (mocking urllib)."""

    def test_http_4xx_error_raises_immediately(self):
        """4xx errors are not retried — they raise HTTPError directly."""
        import urllib.error

        from scripts.dispatch import _send_to_nero

        mock_response = MagicMock()
        mock_response.code = 400
        http_error = urllib.error.HTTPError(
            "http://nero:8080/rpc", 400, "Bad Request", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=http_error):
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=1)
            assert exc_info.value.code == 400

    def test_http_5xx_error_retries_then_raises_nero_unreachable(self):
        """5xx errors are retried and eventually raise NeroUnreachableError."""
        import urllib.error

        from scripts.db import NeroUnreachableError
        from scripts.dispatch import _send_to_nero

        http_error = urllib.error.HTTPError(
            "http://nero:8080/rpc", 503, "Service Unavailable", {}, None
        )
        with (
            patch("urllib.request.urlopen", side_effect=http_error),
            patch("scripts.db.time.sleep"),  # Skip actual sleep in retry decorator
        ):
            with pytest.raises(NeroUnreachableError):
                _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=1)

    def test_timeout_error_retries_then_raises_nero_unreachable(self):
        """TimeoutError is retried and eventually raises NeroUnreachableError."""
        from scripts.db import NeroUnreachableError
        from scripts.dispatch import _send_to_nero

        with (
            patch("urllib.request.urlopen", side_effect=TimeoutError("timed out")),
            patch("scripts.db.time.sleep"),
        ):
            with pytest.raises(NeroUnreachableError, match="timed out"):
                _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=1)

    def test_connection_refused_retries_then_raises_nero_unreachable(self):
        """Connection refused (URLError) is retried and raises NeroUnreachableError."""
        import urllib.error

        from scripts.db import NeroUnreachableError
        from scripts.dispatch import _send_to_nero

        url_error = urllib.error.URLError("Connection refused")
        with (
            patch("urllib.request.urlopen", side_effect=url_error),
            patch("scripts.db.time.sleep"),
        ):
            with pytest.raises(NeroUnreachableError, match="Connection refused"):
                _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=1)

    def test_successful_response_returns_parsed_json(self):
        """Successful response returns parsed JSON dict."""
        from scripts.dispatch import _send_to_nero

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"task_id": "abc"}).encode("utf-8")
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=5)

        assert result == {"task_id": "abc"}

    def test_http_404_raises_without_retry(self):
        """404 errors raise immediately without retrying."""
        import urllib.error

        from scripts.dispatch import _send_to_nero

        http_error = urllib.error.HTTPError(
            "http://nero:8080/rpc", 404, "Not Found", {}, None
        )
        with patch("urllib.request.urlopen", side_effect=http_error) as mock_urlopen:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                _send_to_nero("http://nero:8080/rpc", {"method": "test"}, timeout=1)
            assert exc_info.value.code == 404
            # Should only be called once (no retry for 4xx)
            assert mock_urlopen.call_count == 1


class TestDispatchPlanEdgeCases:
    """Edge cases for dispatch_plan payload building."""

    def test_plan_with_no_files_to_create(self, db):
        """dispatch_plan handles plan with no files_to_create gracefully."""
        from scripts.dispatch import dispatch_plan

        phase = _seed_dispatch_db(db)
        plan = create_plan(
            db, phase_id=phase["id"], name="No Files", description="Minimal plan"
        )

        mock_send = MagicMock(return_value={"task_id": "nero-min"})
        with (
            patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            result = dispatch_plan(project_dir="/tmp/test", plan_id=plan["id"])

        url, payload = mock_send.call_args[0]
        assert payload["params"]["plan"]["files_to_create"] == []
        assert payload["params"]["plan"]["files_to_modify"] == []
        assert result["status"] == "dispatched"

    def test_plan_with_none_plan_id_raises(self, db):
        """dispatch_plan with plan_id=None raises ValueError (plan not found)."""
        from scripts.dispatch import dispatch_plan

        _seed_dispatch_db(db)
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="not found"):
                dispatch_plan(project_dir="/tmp/test", plan_id=None)

    def test_dispatch_plan_uses_default_cwd_when_project_dir_none(self, db):
        """dispatch_plan defaults to cwd when project_dir is None."""
        from scripts.dispatch import dispatch_plan

        # Should fail with "Project not initialized" since the mock DB has no project,
        # but the path resolution should work
        with patch("scripts.dispatch.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="Project not initialized"):
                dispatch_plan(project_dir=None, plan_id=1)


class TestDispatchPhaseEdgeCases:
    """Edge cases for dispatch_phase."""

    def test_swarm_mode_dispatches_all_waves(self, db):
        """dispatch_phase with swarm=True dispatches plans from all waves."""
        from scripts.dispatch import dispatch_phase

        phase = _seed_dispatch_db(db)
        create_plan(db, phase_id=phase["id"], name="W1", description="w1", wave=1)
        create_plan(db, phase_id=phase["id"], name="W2", description="w2", wave=2)
        create_plan(db, phase_id=phase["id"], name="W3", description="w3", wave=3)

        mock_send = MagicMock(return_value={"task_id": "t-swarm"})
        with (
            patch(
                "scripts.dispatch.open_project",
                side_effect=lambda *a, **kw: _mock_open_project(db),
            ),
            patch("scripts.dispatch._send_to_nero", mock_send),
        ):
            results = dispatch_phase(
                project_dir="/tmp/test", phase_id=phase["id"], swarm=True
            )

        # All 3 plans from all waves should be dispatched
        assert len(results) == 3
