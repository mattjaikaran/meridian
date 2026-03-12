#!/usr/bin/env python3
"""Tests for Meridian bidirectional Nero sync."""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from scripts.db import NeroUnreachableError
from scripts.state import (
    create_milestone,
    create_nero_dispatch,
    create_phase,
    create_plan,
    create_project,
    get_plan,
    list_phases,
    transition_milestone,
    transition_phase,
    transition_plan,
)
from scripts.sync import (
    _nero_rpc,
    get_dispatch_summary,
    handle_webhook,
    pull_dispatch_status,
    push_state_to_nero,
    sync_all,
)


@pytest.fixture
def seeded_db(db):
    """DB with project (nero_endpoint set), active milestone, phases, plans.

    Overrides the shared conftest seeded_db because sync tests need nero_endpoint.
    """
    create_project(
        db,
        name="Test App",
        repo_path="/tmp/test",
        nero_endpoint="http://localhost:7655",
    )
    create_milestone(db, "v1.0", "Version 1.0")
    transition_milestone(db, "v1.0", "active")
    create_phase(db, "v1.0", "Foundation", description="Build base")
    create_phase(db, "v1.0", "Features", description="Add features")
    return db


# ── _nero_rpc Retry Tests ────────────────────────────────────────────────────


class TestNeroRpcRetry:
    """Tests for _nero_rpc retry behavior with @retry_on_http_error."""

    def test_nero_rpc_retries_on_url_error(self):
        """_nero_rpc retries on URLError, eventually succeeds."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise urllib.error.URLError("Connection refused")
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=side_effect):
            with patch("time.sleep"):  # Skip actual delays
                result = _nero_rpc("http://localhost:7655", "test_method", {"key": "val"})

        assert result == {"status": "ok"}
        assert call_count == 3

    def test_nero_rpc_raises_nero_unreachable(self):
        """_nero_rpc raises NeroUnreachableError after exhausting retries (not None)."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            with patch("time.sleep"):
                with pytest.raises(NeroUnreachableError):
                    _nero_rpc("http://localhost:7655", "test_method", {})


# ── Pull Dispatch Status Tests ───────────────────────────────────────────────


class TestPullDispatchStatus:
    def test_no_nero_endpoint(self, db):
        create_project(db, name="App", repo_path="/tmp")
        result = pull_dispatch_status(db)
        assert result[0]["status"] == "skipped"

    def test_no_active_dispatches(self, seeded_db):
        result = pull_dispatch_status(seeded_db)
        assert result == []

    def test_pull_completed_dispatch(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")

        create_nero_dispatch(
            seeded_db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=pid,
            nero_task_id="nero-123",
        )

        # Mock Nero returning completed status
        mock_response = {
            "status": "completed",
            "pr_url": "https://github.com/pr/1",
            "commit_sha": "abc123",
        }

        with patch("scripts.sync._nero_rpc", return_value=mock_response):
            results = pull_dispatch_status(seeded_db)

        assert len(results) == 1
        assert results[0]["new_status"] == "completed"
        assert results[0]["plan_transitioned"] == "complete"

        # Verify plan was actually transitioned
        updated_plan = get_plan(seeded_db, plan["id"])
        assert updated_plan["status"] == "complete"

    def test_pull_failed_dispatch(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")

        create_nero_dispatch(
            seeded_db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=pid,
            nero_task_id="nero-456",
        )

        mock_response = {"status": "failed", "error": "Tests failed"}

        with patch("scripts.sync._nero_rpc", return_value=mock_response):
            results = pull_dispatch_status(seeded_db)

        assert results[0]["plan_transitioned"] == "failed"
        updated_plan = get_plan(seeded_db, plan["id"])
        assert updated_plan["status"] == "failed"
        assert "failed" in updated_plan["error_message"]

    def test_pull_unreachable_nero(self, seeded_db):
        """pull_dispatch_status catches NeroUnreachableError per-dispatch and continues."""
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")

        create_nero_dispatch(
            seeded_db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=pid,
            nero_task_id="nero-789",
        )

        with patch("scripts.sync._nero_rpc", side_effect=NeroUnreachableError("unreachable")):
            results = pull_dispatch_status(seeded_db)

        assert results[0]["status"] == "unreachable"
        # Plan should not be transitioned
        updated_plan = get_plan(seeded_db, plan["id"])
        assert updated_plan["status"] == "executing"

    def test_same_status_no_update(self, seeded_db):
        """If Nero returns same status, no update should happen."""
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")

        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")

        create_nero_dispatch(
            seeded_db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=pid,
            nero_task_id="nero-same",
        )

        # Return same status as current ("dispatched")
        mock_response = {"status": "dispatched"}

        with patch("scripts.sync._nero_rpc", return_value=mock_response):
            results = pull_dispatch_status(seeded_db)

        # No updates since status didn't change
        assert results == []


# ── Push State Tests ─────────────────────────────────────────────────────────


class TestPushState:
    def test_no_nero_endpoint(self, db):
        create_project(db, name="App", repo_path="/tmp")
        result = push_state_to_nero(db)
        assert result["status"] == "skipped"

    def test_no_active_milestone(self, db):
        create_project(db, name="App", repo_path="/tmp", nero_endpoint="http://localhost:7655")
        result = push_state_to_nero(db)
        assert result["status"] == "skipped"

    def test_push_pending_plans(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        create_plan(seeded_db, phase["id"], "Plan 1", "Do thing 1")
        create_plan(seeded_db, phase["id"], "Plan 2", "Do thing 2")

        mock_response = {"status": "ok", "received": 2}

        with patch("scripts.sync._nero_rpc", return_value=mock_response):
            result = push_state_to_nero(seeded_db)

        assert result["status"] == "ok"
        assert result["tickets_pushed"] == 2

    def test_skip_completed_plans(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p1 = create_plan(seeded_db, phase["id"], "Done plan", "Already done")
        transition_plan(seeded_db, p1["id"], "executing")
        transition_plan(seeded_db, p1["id"], "complete")

        create_plan(seeded_db, phase["id"], "Pending plan", "Not started")

        mock_response = {"status": "ok"}

        with patch("scripts.sync._nero_rpc", return_value=mock_response):
            result = push_state_to_nero(seeded_db)

        assert result["tickets_pushed"] == 1

    def test_no_pending_work(self, seeded_db):
        # No plans at all
        result = push_state_to_nero(seeded_db)
        assert result["tickets_pushed"] == 0

    def test_push_state_raises_on_failure(self, seeded_db):
        """push_state_to_nero lets NeroUnreachableError propagate."""
        phase = list_phases(seeded_db, "v1.0")[0]
        create_plan(seeded_db, phase["id"], "Plan 1", "Do it")

        with patch("scripts.sync._nero_rpc", side_effect=NeroUnreachableError("unreachable")):
            with pytest.raises(NeroUnreachableError):
                push_state_to_nero(seeded_db)


# ── Sync All Tests ───────────────────────────────────────────────────────────


class TestSyncAll:
    def test_full_sync(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        create_plan(seeded_db, phase["id"], "Plan 1", "Do it")

        with patch("scripts.sync._nero_rpc", return_value={"status": "ok"}):
            result = sync_all(seeded_db)

        assert "pull_results" in result
        assert "push_result" in result


# ── Dispatch Summary Tests ───────────────────────────────────────────────────


class TestDispatchSummary:
    def test_no_dispatches(self, seeded_db):
        summary = get_dispatch_summary(seeded_db)
        assert summary == []

    def test_with_dispatches(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")

        create_nero_dispatch(
            seeded_db,
            dispatch_type="plan",
            plan_id=plan["id"],
            phase_id=pid,
            nero_task_id="nero-summary",
        )

        summary = get_dispatch_summary(seeded_db)
        assert len(summary) == 1
        assert summary[0]["plan_name"] == "Plan 1"
        assert summary[0]["phase_name"] == "Foundation"


class TestWebhookHandler:
    def test_completed_webhook_transitions_plan(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")
        create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"],
            phase_id=pid, nero_task_id="nero-wh-1",
        )
        result = handle_webhook(seeded_db, {
            "event_type": "task.completed",
            "task_id": "nero-wh-1",
            "commit_sha": "abc123",
            "pr_url": "https://github.com/pr/1",
        })
        assert result["status"] == "ok"
        assert result["plan_transitioned"] == "complete"
        updated = get_plan(seeded_db, plan["id"])
        assert updated["status"] == "complete"

    def test_failed_webhook(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")
        create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"],
            phase_id=pid, nero_task_id="nero-wh-2",
        )
        result = handle_webhook(seeded_db, {
            "event_type": "task.failed",
            "task_id": "nero-wh-2",
            "error": "Build failed",
        })
        assert result["plan_transitioned"] == "failed"

    def test_unknown_task_id(self, seeded_db):
        result = handle_webhook(seeded_db, {
            "event_type": "task.completed",
            "task_id": "nonexistent",
        })
        assert result["status"] == "error"
        assert "Unknown" in result["message"]

    def test_event_logged(self, seeded_db):
        from scripts.state import list_events
        phase = list_phases(seeded_db, "v1.0")[0]
        pid = phase["id"]
        transition_phase(seeded_db, pid, "context_gathered")
        transition_phase(seeded_db, pid, "planned_out")
        transition_phase(seeded_db, pid, "executing")
        plan = create_plan(seeded_db, pid, "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")
        create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"],
            phase_id=pid, nero_task_id="nero-wh-3",
        )
        handle_webhook(seeded_db, {
            "event_type": "task.completed",
            "task_id": "nero-wh-3",
        })
        events = list_events(seeded_db, entity_type="nero_dispatch")
        assert len(events) >= 1
