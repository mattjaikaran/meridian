"""Tests for the Meridian workstream system (Phase 43)."""

import pytest

from scripts.db import open_project
from scripts.state import create_project
from scripts.workstreams import (
    assign_milestone,
    complete_workstream,
    create_workstream,
    get_active_workstream,
    get_all_workstreams_progress,
    get_workstream,
    get_workstream_progress,
    list_workstreams,
    pause_workstream,
    resume_workstream,
    switch_workstream,
)


@pytest.fixture
def conn():
    with open_project(":memory:") as c:
        create_project(c, name="Test Project", repo_path="/tmp/test")
        yield c


# ── Create ────────────────────────────────────────────────────────────────────


class TestCreateWorkstream:
    def test_basic_create(self, conn):
        ws = create_workstream(conn, "Backend Refactor")
        assert ws["name"] == "Backend Refactor"
        assert ws["slug"] == "backend-refactor"
        assert ws["status"] == "active"
        assert ws["description"] == ""

    def test_custom_slug(self, conn):
        ws = create_workstream(conn, "My Track", slug="my-track")
        assert ws["slug"] == "my-track"

    def test_with_description(self, conn):
        ws = create_workstream(conn, "Auth", description="OAuth2 implementation")
        assert ws["description"] == "OAuth2 implementation"

    def test_duplicate_slug_raises(self, conn):
        create_workstream(conn, "Duplicate", slug="dup")
        with pytest.raises(Exception):
            create_workstream(conn, "Another", slug="dup")

    def test_get_returns_none_for_missing(self, conn):
        assert get_workstream(conn, "nonexistent") is None


# ── List ──────────────────────────────────────────────────────────────────────


class TestListWorkstreams:
    def test_list_all(self, conn):
        create_workstream(conn, "Alpha")
        create_workstream(conn, "Beta")
        result = list_workstreams(conn)
        assert len(result) == 2

    def test_filter_by_status(self, conn):
        ws = create_workstream(conn, "Active One")
        create_workstream(conn, "To Pause")
        pause_workstream(conn, "to-pause")

        active = list_workstreams(conn, status="active")
        paused = list_workstreams(conn, status="paused")
        assert len(active) == 1
        assert active[0]["slug"] == "active-one"
        assert len(paused) == 1

    def test_invalid_status_raises(self, conn):
        with pytest.raises(ValueError, match="Invalid status"):
            list_workstreams(conn, status="unknown")


# ── Pause / Resume ────────────────────────────────────────────────────────────


class TestPauseResume:
    def test_pause_active(self, conn):
        create_workstream(conn, "Track A")
        ws = pause_workstream(conn, "track-a")
        assert ws["status"] == "paused"

    def test_pause_non_active_raises(self, conn):
        create_workstream(conn, "Track B")
        pause_workstream(conn, "track-b")
        with pytest.raises(ValueError, match="not active"):
            pause_workstream(conn, "track-b")

    def test_resume_paused(self, conn):
        create_workstream(conn, "Track C")
        pause_workstream(conn, "track-c")
        ws = resume_workstream(conn, "track-c")
        assert ws["status"] == "active"

    def test_resume_non_paused_raises(self, conn):
        create_workstream(conn, "Track D")
        with pytest.raises(ValueError, match="not paused"):
            resume_workstream(conn, "track-d")

    def test_pause_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            pause_workstream(conn, "ghost")

    def test_resume_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            resume_workstream(conn, "ghost")


# ── Complete ──────────────────────────────────────────────────────────────────


class TestCompleteWorkstream:
    def test_complete_active(self, conn):
        create_workstream(conn, "Done Track")
        ws = complete_workstream(conn, "done-track")
        assert ws["status"] == "complete"
        assert ws["completed_at"] is not None

    def test_complete_already_complete_raises(self, conn):
        create_workstream(conn, "Already Done")
        complete_workstream(conn, "already-done")
        with pytest.raises(ValueError, match="already"):
            complete_workstream(conn, "already-done")

    def test_complete_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            complete_workstream(conn, "ghost")


# ── Session switching ─────────────────────────────────────────────────────────


class TestSwitch:
    def test_switch_sets_active(self, conn):
        create_workstream(conn, "WS1")
        switch_workstream(conn, "ws1")
        active = get_active_workstream(conn)
        assert active is not None
        assert active["slug"] == "ws1"

    def test_switch_pauses_previous(self, conn):
        create_workstream(conn, "WS A")
        create_workstream(conn, "WS B")
        switch_workstream(conn, "ws-a")
        switch_workstream(conn, "ws-b")
        ws_a = get_workstream(conn, "ws-a")
        assert ws_a["status"] == "paused"
        active = get_active_workstream(conn)
        assert active["slug"] == "ws-b"
        assert active["status"] == "active"

    def test_switch_resumes_paused(self, conn):
        create_workstream(conn, "WS X")
        create_workstream(conn, "WS Y")
        switch_workstream(conn, "ws-x")
        switch_workstream(conn, "ws-y")
        # ws-x is now paused; switch back
        switch_workstream(conn, "ws-x")
        ws_x = get_workstream(conn, "ws-x")
        assert ws_x["status"] == "active"

    def test_switch_to_same_is_noop(self, conn):
        create_workstream(conn, "Solo")
        switch_workstream(conn, "solo")
        switch_workstream(conn, "solo")
        ws = get_workstream(conn, "solo")
        assert ws["status"] == "active"

    def test_switch_to_complete_raises(self, conn):
        create_workstream(conn, "Finished")
        complete_workstream(conn, "finished")
        with pytest.raises(ValueError, match="complete"):
            switch_workstream(conn, "finished")

    def test_no_active_returns_none(self, conn):
        assert get_active_workstream(conn) is None

    def test_switch_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            switch_workstream(conn, "ghost")


# ── Progress ──────────────────────────────────────────────────────────────────


class TestProgress:
    def test_progress_empty_milestones(self, conn):
        create_workstream(conn, "Empty WS")
        prog = get_workstream_progress(conn, "empty-ws")
        assert prog["total_phases"] == 0
        assert prog["overall_pct"] == 0
        assert prog["milestones"] == []

    def test_progress_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="not found"):
            get_workstream_progress(conn, "ghost")

    def test_all_workstreams_progress(self, conn):
        create_workstream(conn, "Track 1")
        create_workstream(conn, "Track 2")
        results = get_all_workstreams_progress(conn)
        assert len(results) == 2
        slugs = {r["workstream"]["slug"] for r in results}
        assert slugs == {"track-1", "track-2"}

    def test_assign_milestone_sets_fk(self, conn):
        create_workstream(conn, "WS Assign")
        conn.execute(
            "INSERT INTO milestone (id, project_id, name) VALUES ('m1', 'default', 'Milestone One')"
        )
        assign_milestone(conn, "m1", "ws-assign")
        row = conn.execute("SELECT workstream_id FROM milestone WHERE id = 'm1'").fetchone()
        ws = get_workstream(conn, "ws-assign")
        assert row["workstream_id"] == ws["id"]

    def test_assign_not_found_raises(self, conn):
        conn.execute(
            "INSERT INTO milestone (id, project_id, name) VALUES ('m2', 'default', 'M2')"
        )
        with pytest.raises(ValueError, match="not found"):
            assign_milestone(conn, "m2", "ghost")
