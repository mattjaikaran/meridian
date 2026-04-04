#!/usr/bin/env python3
"""Tests for Meridian gap closure module."""

import pytest

from scripts.gap_closure import (
    execute_gaps_only,
    find_gaps,
    find_gaps_in_milestone,
    prepare_gap_execution,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
    transition_phase,
    transition_plan,
)


def _setup_phase_with_plans(db, milestone_id, phase_name="Test Phase", plan_count=3, wave=1):
    """Helper to create a phase with plans."""
    phase = create_phase(db, milestone_id, phase_name, f"Description for {phase_name}")
    transition_phase(db, phase["id"], "context_gathered")
    transition_phase(db, phase["id"], "planned_out")
    transition_phase(db, phase["id"], "executing")
    plans = []
    for i in range(plan_count):
        plan = create_plan(
            db,
            phase["id"],
            f"Plan {i + 1}",
            f"Do thing {i + 1}",
            wave=wave,
        )
        plans.append(plan)
    return phase, plans


class TestFindGaps:
    def test_no_gaps(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        for p in plans:
            transition_plan(db, p["id"], "executing")
            transition_plan(db, p["id"], "complete")

        gaps = find_gaps(db, phase["id"])
        assert len(gaps) == 0

    def test_finds_failed_plans(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        transition_plan(db, plans[0]["id"], "executing")
        transition_plan(db, plans[0]["id"], "failed", error_message="broke")

        gaps = find_gaps(db, phase["id"])
        assert len(gaps) == 1
        assert gaps[0]["status"] == "failed"

    def test_finds_skipped_plans(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        transition_plan(db, plans[1]["id"], "skipped")

        gaps = find_gaps(db, phase["id"])
        assert len(gaps) == 1
        assert gaps[0]["status"] == "skipped"

    def test_mixed_statuses(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        # One complete, one failed, one skipped
        transition_plan(db, plans[0]["id"], "executing")
        transition_plan(db, plans[0]["id"], "complete")
        transition_plan(db, plans[1]["id"], "executing")
        transition_plan(db, plans[1]["id"], "failed", error_message="err")
        transition_plan(db, plans[2]["id"], "skipped")

        gaps = find_gaps(db, phase["id"])
        assert len(gaps) == 2


class TestFindGapsInMilestone:
    def test_groups_by_phase(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")

        phase1, plans1 = _setup_phase_with_plans(db, ms["id"], "Phase A", 2)
        phase2, plans2 = _setup_phase_with_plans(db, ms["id"], "Phase B", 2)

        transition_plan(db, plans1[0]["id"], "executing")
        transition_plan(db, plans1[0]["id"], "failed", error_message="err")
        transition_plan(db, plans2[0]["id"], "executing")
        transition_plan(db, plans2[0]["id"], "failed", error_message="err")

        result = find_gaps_in_milestone(db, ms["id"])
        assert len(result) == 2
        assert result[0]["phase"]["name"] == "Phase A"
        assert len(result[0]["gaps"]) == 1

    def test_skips_phases_with_no_gaps(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")

        phase1, plans1 = _setup_phase_with_plans(db, ms["id"], "Clean Phase", 2)
        phase2, plans2 = _setup_phase_with_plans(db, ms["id"], "Broken Phase", 2)

        for p in plans1:
            transition_plan(db, p["id"], "executing")
            transition_plan(db, p["id"], "complete")

        transition_plan(db, plans2[0]["id"], "executing")
        transition_plan(db, plans2[0]["id"], "failed", error_message="err")

        result = find_gaps_in_milestone(db, ms["id"])
        assert len(result) == 1
        assert result[0]["phase"]["name"] == "Broken Phase"


class TestPrepareGapExecution:
    def test_no_gaps_returns_empty(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        for p in plans:
            transition_plan(db, p["id"], "executing")
            transition_plan(db, p["id"], "complete")

        result = prepare_gap_execution(db, phase["id"])
        assert result["reset_count"] == 0
        assert result["plans"] == []

    def test_resets_failed_to_pending(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        transition_plan(db, plans[0]["id"], "executing")
        transition_plan(db, plans[0]["id"], "failed", error_message="err")

        result = prepare_gap_execution(db, phase["id"])
        assert result["reset_count"] == 1
        assert 1 in result["waves"]

    def test_respects_wave_ordering(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Multi Wave", "desc")
        transition_phase(db, phase["id"], "context_gathered")
        transition_phase(db, phase["id"], "planned_out")
        transition_phase(db, phase["id"], "executing")

        # Wave 1: one failed
        p1 = create_plan(db, phase["id"], "W1 Plan", "d", wave=1)
        transition_plan(db, p1["id"], "executing")
        transition_plan(db, p1["id"], "failed", error_message="err")

        # Wave 2: one failed — should still be reset since wave 1 has resettable plans
        p2 = create_plan(db, phase["id"], "W2 Plan", "d", wave=2)
        transition_plan(db, p2["id"], "executing")
        transition_plan(db, p2["id"], "failed", error_message="err")

        result = prepare_gap_execution(db, phase["id"])
        assert result["reset_count"] == 2
        assert sorted(result["waves"]) == [1, 2]

    def test_skipped_wave_blocks_higher(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase = create_phase(db, ms["id"], "Blocked", "desc")
        transition_phase(db, phase["id"], "context_gathered")
        transition_phase(db, phase["id"], "planned_out")
        transition_phase(db, phase["id"], "executing")

        # Wave 1: skipped (not resettable)
        p1 = create_plan(db, phase["id"], "W1 Skip", "d", wave=1)
        transition_plan(db, p1["id"], "skipped")

        # Wave 2: failed
        p2 = create_plan(db, phase["id"], "W2 Fail", "d", wave=2)
        transition_plan(db, p2["id"], "executing")
        transition_plan(db, p2["id"], "failed", error_message="err")

        result = prepare_gap_execution(db, phase["id"])
        # Wave 1 has only skipped plans, so wave 2 is blocked
        assert result["reset_count"] == 0


class TestExecuteGapsOnly:
    def test_no_gaps(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        for p in plans:
            transition_plan(db, p["id"], "executing")
            transition_plan(db, p["id"], "complete")

        result = execute_gaps_only(db, phase["id"])
        assert result["has_gaps"] is False
        assert result["gap_count"] == 0

    def test_with_gaps(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        transition_plan(db, plans[0]["id"], "executing")
        transition_plan(db, plans[0]["id"], "failed", error_message="err")

        result = execute_gaps_only(db, phase["id"])
        assert result["has_gaps"] is True
        assert result["gap_count"] == 1
        assert len(result["plans_to_retry"]) >= 1

    def test_logs_event(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        ms = create_milestone(db, "v1", "Version 1", project_id="default")
        transition_milestone(db, ms["id"], "active")
        phase, plans = _setup_phase_with_plans(db, ms["id"])

        transition_plan(db, plans[0]["id"], "executing")
        transition_plan(db, plans[0]["id"], "failed", error_message="err")

        execute_gaps_only(db, phase["id"])

        events = db.execute(
            "SELECT * FROM state_event WHERE new_status = 'gap_closure'"
        ).fetchall()
        assert len(events) == 1
