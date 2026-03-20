#!/usr/bin/env python3
"""Tests for Meridian next-action workflow advancement."""

import pytest

from scripts.next_action import (
    determine_next_step,
    format_next_action,
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


# ── No Project ───────────────────────────────────────────────────────────────


class TestNoProject:
    def test_no_project(self, db):
        result = determine_next_step(db)
        assert result["action"] == "no_project"
        assert result["command"] == "/meridian:init"
        assert result["destructive"] is False


# ── Milestone States ─────────────────────────────────────────────────────────


class TestMilestoneStates:
    def test_no_milestones(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = determine_next_step(db)
        assert result["action"] == "create_milestone"
        assert "/meridian:init" in result["command"]

    def test_planned_milestone(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        create_milestone(db, "v1.0", "Version 1.0")
        result = determine_next_step(db)
        assert result["action"] == "activate_milestone"
        assert "/meridian:plan" in result["command"]

    def test_active_milestone_no_phases(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        create_milestone(db, "v1.0", "Version 1.0")
        transition_milestone(db, "v1.0", "active")
        result = determine_next_step(db)
        assert result["action"] == "create_phases"
        assert "/meridian:plan" in result["command"]


# ── Phase States ─────────────────────────────────────────────────────────────


class TestPhaseStates:
    def test_planned_phase(self, seeded_db):
        result = determine_next_step(seeded_db)
        assert result["action"] == "gather_context"
        assert "/meridian:plan" in result["command"]

    def test_context_gathered_phase(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        result = determine_next_step(seeded_db)
        assert result["action"] == "create_plans"

    def test_planned_out_phase(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        result = determine_next_step(seeded_db)
        assert result["action"] == "execute"
        assert "/meridian:execute" in result["command"]

    def test_executing_phase(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        # Create a plan so execute_plan logic kicks in
        create_plan(seeded_db, 1, "Plan A", "Do stuff", wave=1)
        result = determine_next_step(seeded_db)
        assert result["action"] == "execute_plan"
        assert "/meridian:execute" in result["command"]

    def test_verifying_phase(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        result = determine_next_step(seeded_db)
        assert result["action"] == "review_phase"

    def test_reviewing_phase(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        result = determine_next_step(seeded_db)
        assert result["action"] == "complete_phase"


# ── Complete Milestone ───────────────────────────────────────────────────────


class TestCompleteMilestone:
    def test_all_phases_complete(self, seeded_db):
        # Complete both phases
        for phase_id in (1, 2):
            transition_phase(seeded_db, phase_id, "context_gathered")
            transition_phase(seeded_db, phase_id, "planned_out")
            transition_phase(seeded_db, phase_id, "executing")
            transition_phase(seeded_db, phase_id, "verifying")
            transition_phase(seeded_db, phase_id, "reviewing")
            transition_phase(seeded_db, phase_id, "complete")
        result = determine_next_step(seeded_db)
        assert result["action"] == "complete_milestone"
        assert result["destructive"] is True


# ── Format Output ────────────────────────────────────────────────────────────


class TestFormatNextAction:
    def test_basic_format(self):
        step = {
            "action": "execute",
            "command": "/meridian:execute",
            "label": "Start execution",
            "description": "Phase is ready to execute.",
            "context": {"phase_id": 1},
            "destructive": False,
        }
        output = format_next_action(step)
        assert "## Next: Start execution" in output
        assert "/meridian:execute" in output
        assert "Phase is ready to execute." in output

    def test_destructive_warning(self):
        step = {
            "action": "complete_milestone",
            "command": "/meridian:ship",
            "label": "Complete milestone",
            "description": "All phases complete.",
            "context": {"milestone_id": "v1.0"},
            "destructive": True,
        }
        output = format_next_action(step)
        assert "Warning" in output
        assert "destructive" in output.lower()

    def test_includes_context(self):
        step = {
            "action": "execute_plan",
            "command": "/meridian:execute",
            "label": "Execute plan",
            "description": "Continue executing.",
            "context": {"phase_id": 1, "plan_name": "Plan A", "wave": 1},
            "destructive": False,
        }
        output = format_next_action(step)
        assert "Plan A" in output
        assert "**Wave:** 1" in output

    def test_no_project_format(self):
        step = determine_next_step.__wrapped__(None) if hasattr(determine_next_step, '__wrapped__') else None
        # Just test with a manually constructed step
        step = {
            "action": "no_project",
            "command": "/meridian:init",
            "label": "Initialize project",
            "description": "No project initialized.",
            "context": {},
            "destructive": False,
        }
        output = format_next_action(step)
        assert "/meridian:init" in output
