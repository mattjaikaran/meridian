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
