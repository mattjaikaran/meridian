#!/usr/bin/env python3
"""Tests for Meridian bidirectional Nero sync."""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.db import init_schema
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
    get_dispatch_summary,
    pull_dispatch_status,
    push_state_to_nero,
    sync_all,
)


@pytest.fixture
def db():
    """In-memory DB with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db):
    """DB with project (nero_endpoint set), active milestone, phases, plans."""
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

        with patch("scripts.sync._nero_rpc", return_value=None):
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

    def test_nero_unreachable(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        create_plan(seeded_db, phase["id"], "Plan 1", "Do it")

        with patch("scripts.sync._nero_rpc", return_value=None):
            result = push_state_to_nero(seeded_db)

        assert result["status"] == "error"


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
