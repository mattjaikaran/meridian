#!/usr/bin/env python3
"""Tests for Meridian state management."""

import pytest

from scripts.db import StateTransitionError
from scripts.state import (
    add_priority,
    check_auto_advance,
    compute_next_action,
    create_checkpoint,
    create_decision,
    create_milestone,
    create_nero_dispatch,
    create_phase,
    create_plan,
    create_project,
    create_quick_task,
    get_latest_checkpoint,
    get_project,
    get_status,
    list_decisions,
    list_milestones,
    list_phases,
    list_plans,
    safe_update,
    transition_milestone,
    transition_phase,
    transition_plan,
    transition_quick_task,
    update_nero_dispatch,
    update_phase,
    update_project,
)


# ── Project Tests ─────────────────────────────────────────────────────────────


class TestProject:
    def test_create_and_get(self, db):
        p = create_project(db, name="My App", repo_path="/dev/myapp")
        assert p["name"] == "My App"
        assert p["repo_path"] == "/dev/myapp"
        assert p["id"] == "default"

        fetched = get_project(db)
        assert fetched["name"] == "My App"

    def test_create_with_tech_stack(self, db):
        p = create_project(db, name="App", repo_path="/dev/app", tech_stack=["python", "react"])
        assert p["tech_stack"] == '["python", "react"]'

    def test_update(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        updated = update_project(
            db, "default", name="Updated App", repo_url="https://github.com/test"
        )
        assert updated["name"] == "Updated App"
        assert updated["repo_url"] == "https://github.com/test"


# ── Milestone Tests ───────────────────────────────────────────────────────────


class TestMilestone:
    def test_create_and_list(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "Version 1.0")
        create_milestone(db, "v2.0", "Version 2.0")
        milestones = list_milestones(db)
        assert len(milestones) == 2
        assert milestones[0]["id"] == "v1.0"

    def test_valid_transitions(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        m = transition_milestone(db, "v1.0", "active")
        assert m["status"] == "active"
        m = transition_milestone(db, "v1.0", "complete")
        assert m["status"] == "complete"
        assert m["completed_at"] is not None

    def test_invalid_transition(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        with pytest.raises(StateTransitionError, match="Invalid transition"):
            transition_milestone(db, "v1.0", "complete")  # can't skip active


# ── Phase Tests ───────────────────────────────────────────────────────────────


class TestPhase:
    def test_create_auto_sequence(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        p1 = create_phase(db, "v1.0", "Phase 1")
        p2 = create_phase(db, "v1.0", "Phase 2")
        assert p1["sequence"] == 1
        assert p2["sequence"] == 2

    def test_list_ordered(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        create_phase(db, "v1.0", "B Phase", sequence=2)
        create_phase(db, "v1.0", "A Phase", sequence=1)
        phases = list_phases(db, "v1.0")
        assert phases[0]["name"] == "A Phase"
        assert phases[1]["name"] == "B Phase"

    def test_valid_transitions(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        p = create_phase(db, "v1.0", "Phase 1")
        pid = p["id"]

        p = transition_phase(db, pid, "context_gathered")
        assert p["status"] == "context_gathered"
        p = transition_phase(db, pid, "planned_out")
        assert p["status"] == "planned_out"
        p = transition_phase(db, pid, "executing")
        assert p["status"] == "executing"
        assert p["started_at"] is not None
        p = transition_phase(db, pid, "verifying")
        assert p["status"] == "verifying"
        p = transition_phase(db, pid, "reviewing")
        assert p["status"] == "reviewing"
        p = transition_phase(db, pid, "complete")
        assert p["status"] == "complete"
        assert p["completed_at"] is not None

    def test_invalid_transition(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        p = create_phase(db, "v1.0", "Phase 1")
        with pytest.raises(StateTransitionError, match="Invalid phase transition"):
            transition_phase(db, p["id"], "executing")  # can't skip context_gathered

    def test_block_and_unblock(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        p = create_phase(db, "v1.0", "Phase 1")
        pid = p["id"]
        p = transition_phase(db, pid, "blocked")
        assert p["status"] == "blocked"
        p = transition_phase(db, pid, "planned")
        assert p["status"] == "planned"

    def test_update_phase(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        p = create_phase(db, "v1.0", "Phase 1")
        updated = update_phase(db, p["id"], acceptance_criteria=["tests pass", "docs written"])
        assert '"tests pass"' in updated["acceptance_criteria"]


# ── Plan Tests ────────────────────────────────────────────────────────────────


class TestPlan:
    def test_create_auto_sequence(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p1 = create_plan(seeded_db, phase["id"], "Plan A", "Do A")
        p2 = create_plan(seeded_db, phase["id"], "Plan B", "Do B")
        assert p1["sequence"] == 1
        assert p2["sequence"] == 2

    def test_wave_assignment(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        create_plan(seeded_db, phase["id"], "P1", "Do 1", wave=1)
        create_plan(seeded_db, phase["id"], "P2", "Do 2", wave=1)
        create_plan(seeded_db, phase["id"], "P3", "Do 3", wave=2)

        plans = list_plans(seeded_db, phase["id"])
        assert len(plans) == 3
        assert plans[0]["wave"] == 1
        assert plans[2]["wave"] == 2

    def test_valid_transitions(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Plan", "Do it")

        p = transition_plan(seeded_db, p["id"], "executing")
        assert p["status"] == "executing"
        assert p["started_at"] is not None

        p = transition_plan(seeded_db, p["id"], "complete", commit_sha="abc123")
        assert p["status"] == "complete"
        assert p["commit_sha"] == "abc123"
        assert p["completed_at"] is not None

    def test_failure_and_retry(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Plan", "Do it")

        p = transition_plan(seeded_db, p["id"], "executing")
        p = transition_plan(seeded_db, p["id"], "failed", error_message="tests broke")
        assert p["status"] == "failed"
        assert p["error_message"] == "tests broke"

        # Can retry
        p = transition_plan(seeded_db, p["id"], "executing")
        assert p["status"] == "executing"

    def test_invalid_transition(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        p = create_plan(seeded_db, phase["id"], "Plan", "Do it")
        with pytest.raises(StateTransitionError, match="Invalid plan transition"):
            transition_plan(seeded_db, p["id"], "complete")  # can't skip executing


# ── Checkpoint Tests ──────────────────────────────────────────────────────────


class TestCheckpoint:
    def test_create_and_get_latest(self, seeded_db):
        create_checkpoint(seeded_db, trigger="manual", notes="First save")
        cp2 = create_checkpoint(seeded_db, trigger="plan_complete", notes="After plan 1")
        latest = get_latest_checkpoint(seeded_db)
        assert latest["id"] == cp2["id"]
        assert latest["notes"] == "After plan 1"

    def test_with_decisions(self, seeded_db):
        decisions = [{"summary": "Use SQLite", "category": "architecture"}]
        cp = create_checkpoint(seeded_db, trigger="manual", decisions=decisions)
        assert '"Use SQLite"' in cp["decisions"]


# ── Decision Tests ────────────────────────────────────────────────────────────


class TestDecision:
    def test_create_and_list(self, seeded_db):
        create_decision(seeded_db, "Use SQLite for state", category="architecture")
        create_decision(seeded_db, "TDD required for all plans", category="approach")
        decisions = list_decisions(seeded_db)
        assert len(decisions) == 2

    def test_filter_by_phase(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        create_decision(seeded_db, "Phase-specific", phase_id=phase["id"])
        create_decision(seeded_db, "Global decision")
        phase_decisions = list_decisions(seeded_db, phase_id=phase["id"])
        assert len(phase_decisions) == 1
        assert phase_decisions[0]["summary"] == "Phase-specific"


# ── Quick Task Tests ──────────────────────────────────────────────────────────


class TestQuickTask:
    def test_lifecycle(self, seeded_db):
        qt = create_quick_task(seeded_db, "Fix typo in README")
        assert qt["status"] == "pending"

        qt = transition_quick_task(seeded_db, qt["id"], "executing")
        assert qt["status"] == "executing"

        qt = transition_quick_task(seeded_db, qt["id"], "complete", commit_sha="def456")
        assert qt["status"] == "complete"
        assert qt["commit_sha"] == "def456"


# ── Next Action Tests ─────────────────────────────────────────────────────────


class TestNextAction:
    def test_no_milestones(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        action = compute_next_action(db)
        assert action["action"] == "create_milestone"

    def test_planned_milestone(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        action = compute_next_action(db)
        assert action["action"] == "activate_milestone"

    def test_active_milestone_no_phases(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        create_milestone(db, "v1.0", "V1")
        transition_milestone(db, "v1.0", "active")
        action = compute_next_action(db)
        assert action["action"] == "create_phases"

    def test_phase_needs_context(self, seeded_db):
        action = compute_next_action(seeded_db)
        assert action["action"] == "gather_context"

    def test_phase_needs_plans(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        action = compute_next_action(seeded_db)
        assert action["action"] == "create_plans"

    def test_phase_ready_to_execute(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        action = compute_next_action(seeded_db)
        assert action["action"] == "execute"

    def test_executing_with_pending_plan(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        create_plan(seeded_db, phase["id"], "Plan 1", "Do thing 1")
        action = compute_next_action(seeded_db)
        assert action["action"] == "execute_plan"
        assert action["plan_name"] == "Plan 1"

    def test_all_plans_complete_triggers_verify(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        p = create_plan(seeded_db, phase["id"], "Plan 1", "Do thing")
        transition_plan(seeded_db, p["id"], "executing")
        transition_plan(seeded_db, p["id"], "complete")
        action = compute_next_action(seeded_db)
        assert action["action"] == "verify_phase"

    def test_all_phases_complete(self, seeded_db):
        phases = list_phases(seeded_db, "v1.0")
        for phase in phases:
            pid = phase["id"]
            transition_phase(seeded_db, pid, "context_gathered")
            transition_phase(seeded_db, pid, "planned_out")
            transition_phase(seeded_db, pid, "executing")
            transition_phase(seeded_db, pid, "verifying")
            transition_phase(seeded_db, pid, "reviewing")
            transition_phase(seeded_db, pid, "complete")
        action = compute_next_action(seeded_db)
        assert action["action"] == "complete_milestone"


# ── Status Tests ──────────────────────────────────────────────────────────────


class TestStatus:
    def test_uninitalized(self, db):
        status = get_status(db)
        assert "error" in status

    def test_full_status(self, seeded_db):
        status = get_status(seeded_db)
        assert status["project"]["name"] == "Test Project"
        assert status["active_milestone"]["id"] == "v1.0"
        assert len(status["phases"]) == 2
        assert status["next_action"]["action"] == "gather_context"


# ── safe_update Tests ────────────────────────────────────────────────────────


class TestSafeUpdate:
    def test_valid_update(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        safe_update(seeded_db, "phase", phase["id"], {"status": "context_gathered"})
        seeded_db.commit()
        row = seeded_db.execute(
            "SELECT status FROM phase WHERE id = ?", (phase["id"],)
        ).fetchone()
        assert row["status"] == "context_gathered"

    def test_rejects_invalid_column(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        with pytest.raises(ValueError, match="Invalid columns for phase"):
            safe_update(seeded_db, "phase", phase["id"], {"hacker": "drop"})

    def test_rejects_unknown_table(self, db):
        with pytest.raises(ValueError, match="Unknown table"):
            safe_update(db, "nonexistent", 1, {"col": "val"})

    def test_empty_updates_noop(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        # Should return without executing SQL (no error, no change)
        safe_update(seeded_db, "phase", phase["id"], {})

    def test_multiple_columns(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        # Transition to executing first so started_at/completed_at are allowed
        safe_update(
            seeded_db,
            "phase",
            phase["id"],
            {"status": "context_gathered", "description": "updated desc"},
        )
        seeded_db.commit()
        row = seeded_db.execute(
            "SELECT status, description FROM phase WHERE id = ?", (phase["id"],)
        ).fetchone()
        assert row["status"] == "context_gathered"
        assert row["description"] == "updated desc"


# ── add_priority Tests ───────────────────────────────────────────────────────


class TestAddPriority:
    def test_valid_phase_priority(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        result = add_priority(seeded_db, "phase", phase["id"], "high")
        assert result["priority"] == "high"

    def test_valid_plan_priority(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        plan = create_plan(seeded_db, phase["id"], "Test Plan", "desc")
        result = add_priority(seeded_db, "plan", plan["id"], "critical")
        assert result["priority"] == "critical"

    def test_invalid_entity_type(self, seeded_db):
        with pytest.raises(ValueError, match="Invalid entity_type"):
            add_priority(seeded_db, "milestone", 1, "high")

    def test_invalid_priority(self, seeded_db):
        phase = list_phases(seeded_db, "v1.0")[0]
        with pytest.raises(ValueError, match="Invalid priority"):
            add_priority(seeded_db, "phase", phase["id"], "urgent")


# ── Auto-Advance Tests ──────────────────────────────────────────────────────


class TestAutoAdvance:
    """Tests for check_auto_advance edge cases."""

    def test_returns_none_when_phase_not_found(self, seeded_db):
        """Returns action='none' for a non-existent phase_id."""
        result = check_auto_advance(seeded_db, phase_id=9999)
        assert result["action"] == "none"
        assert "not found" in result["message"]

    def test_returns_none_when_phase_not_executing(self, seeded_db):
        """Returns action='none' when phase status is 'planned' (not executing)."""
        phase = list_phases(seeded_db, "v1.0")[0]
        result = check_auto_advance(seeded_db, phase_id=phase["id"])
        assert result["action"] == "none"
        assert "not in executing state" in result["message"]

    def test_returns_none_when_no_plans_exist(self, seeded_db):
        """Returns action='none' when phase has no plans."""
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        result = check_auto_advance(seeded_db, phase_id=phase["id"])
        assert result["action"] == "none"
        assert "No plans" in result["message"]

    def test_returns_none_when_plans_still_pending(self, seeded_db):
        """Returns action='none' with count when plans still pending."""
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        create_plan(seeded_db, phase["id"], "Plan A", "Do A")
        create_plan(seeded_db, phase["id"], "Plan B", "Do B")
        # Leave both pending
        result = check_auto_advance(seeded_db, phase_id=phase["id"])
        assert result["action"] == "none"
        assert "2 plan(s) still pending" in result["message"]

    def test_phase_to_verifying_when_all_plans_complete(self, seeded_db):
        """Transitions phase to verifying when all plans are complete."""
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        p1 = create_plan(seeded_db, phase["id"], "Plan A", "Do A")
        p2 = create_plan(seeded_db, phase["id"], "Plan B", "Do B")
        transition_plan(seeded_db, p1["id"], "executing")
        transition_plan(seeded_db, p1["id"], "complete")
        transition_plan(seeded_db, p2["id"], "executing")
        transition_plan(seeded_db, p2["id"], "complete")

        result = check_auto_advance(seeded_db, phase_id=phase["id"])
        assert result["action"] == "phase_to_verifying"
        # Verify phase actually transitioned
        from scripts.state import get_phase
        updated_phase = get_phase(seeded_db, phase["id"])
        assert updated_phase["status"] == "verifying"

    def test_phase_to_verifying_with_mix_of_complete_and_skipped(self, seeded_db):
        """Transitions to verifying when plans are mix of complete and skipped."""
        phase = list_phases(seeded_db, "v1.0")[0]
        transition_phase(seeded_db, phase["id"], "context_gathered")
        transition_phase(seeded_db, phase["id"], "planned_out")
        transition_phase(seeded_db, phase["id"], "executing")
        p1 = create_plan(seeded_db, phase["id"], "Plan A", "Do A")
        p2 = create_plan(seeded_db, phase["id"], "Plan B", "Do B")
        transition_plan(seeded_db, p1["id"], "executing")
        transition_plan(seeded_db, p1["id"], "complete")
        transition_plan(seeded_db, p2["id"], "skipped")

        result = check_auto_advance(seeded_db, phase_id=phase["id"])
        assert result["action"] == "phase_to_verifying"

    def test_milestone_ready_when_all_phases_complete(self, seeded_db):
        """Sets milestone_ready=True when current phase is the only non-complete one.

        Note: This captures the CURRENT (potentially buggy) behavior where
        milestone_ready is True even though the current phase just moved to
        'verifying' (not 'complete'). Plan 04 will address this.
        """
        phases = list_phases(seeded_db, "v1.0")
        # Complete phase 2 fully
        p2 = phases[1]
        transition_phase(seeded_db, p2["id"], "context_gathered")
        transition_phase(seeded_db, p2["id"], "planned_out")
        transition_phase(seeded_db, p2["id"], "executing")
        transition_phase(seeded_db, p2["id"], "verifying")
        transition_phase(seeded_db, p2["id"], "reviewing")
        transition_phase(seeded_db, p2["id"], "complete")

        # Phase 1 in executing with all plans complete
        p1 = phases[0]
        transition_phase(seeded_db, p1["id"], "context_gathered")
        transition_phase(seeded_db, p1["id"], "planned_out")
        transition_phase(seeded_db, p1["id"], "executing")
        plan = create_plan(seeded_db, p1["id"], "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")
        transition_plan(seeded_db, plan["id"], "complete")

        result = check_auto_advance(seeded_db, phase_id=p1["id"])
        assert result["action"] == "phase_to_verifying"
        # Current behavior: milestone_ready is True because the only other
        # incomplete phase is the current one (which just moved to verifying)
        assert result.get("milestone_ready") is True

    def test_milestone_not_ready_when_other_phases_incomplete(self, seeded_db):
        """milestone_ready is NOT set when other phases are still incomplete."""
        phases = list_phases(seeded_db, "v1.0")
        # Phase 2 still in planned state (not complete)

        # Phase 1 in executing with all plans complete
        p1 = phases[0]
        transition_phase(seeded_db, p1["id"], "context_gathered")
        transition_phase(seeded_db, p1["id"], "planned_out")
        transition_phase(seeded_db, p1["id"], "executing")
        plan = create_plan(seeded_db, p1["id"], "Plan 1", "Do it")
        transition_plan(seeded_db, plan["id"], "executing")
        transition_plan(seeded_db, plan["id"], "complete")

        result = check_auto_advance(seeded_db, phase_id=p1["id"])
        assert result["action"] == "phase_to_verifying"
        assert result.get("milestone_ready") is None


# ── Nero Dispatch Tests ─────────────────────────────────────────────────────


class TestNeroDispatch:
    """Tests for update_nero_dispatch buggy truthiness check."""

    def test_update_with_empty_string_status_not_updated(self, seeded_db):
        """Passing status='' does NOT update status due to truthiness check.

        This documents the current buggy behavior (QUAL-04). The `if status:`
        check in update_nero_dispatch treats '' as falsy, so the status field
        is not included in the update dict.
        """
        phase = list_phases(seeded_db, "v1.0")[0]
        plan = create_plan(seeded_db, phase["id"], "Plan 1", "Do it")
        dispatch = create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"]
        )
        assert dispatch["status"] == "dispatched"

        # Call with status="" -- should NOT update due to truthiness bug
        updated = update_nero_dispatch(seeded_db, dispatch["id"], status="")
        assert updated["status"] == "dispatched"  # unchanged

    def test_update_with_valid_status(self, seeded_db):
        """Passing a valid non-empty status updates correctly."""
        phase = list_phases(seeded_db, "v1.0")[0]
        plan = create_plan(seeded_db, phase["id"], "Plan 1", "Do it")
        dispatch = create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"]
        )

        updated = update_nero_dispatch(seeded_db, dispatch["id"], status="running")
        assert updated["status"] == "running"

    def test_update_with_pr_url(self, seeded_db):
        """Passing pr_url updates the dispatch record."""
        phase = list_phases(seeded_db, "v1.0")[0]
        plan = create_plan(seeded_db, phase["id"], "Plan 1", "Do it")
        dispatch = create_nero_dispatch(
            seeded_db, dispatch_type="plan", plan_id=plan["id"]
        )

        updated = update_nero_dispatch(
            seeded_db, dispatch["id"], pr_url="https://github.com/test/pr/1"
        )
        assert updated["pr_url"] == "https://github.com/test/pr/1"
