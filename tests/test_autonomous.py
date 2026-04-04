#!/usr/bin/env python3
"""Tests for Meridian autonomous mode."""

import pytest

from scripts.autonomous import (
    get_autonomous_step,
    plan_autonomous_run,
    validate_autonomous_range,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_milestone,
    transition_phase,
)


def _ms(db):
    create_project(db, name="Test", repo_path="/tmp/test")
    ms = create_milestone(db, "v1", "V1", project_id="default")
    transition_milestone(db, ms["id"], "active")
    return ms


class TestValidateAutonomousRange:
    def test_valid_range(self, db):
        ms = _ms(db)
        p1 = create_phase(db, ms["id"], "A", "desc")
        p2 = create_phase(db, ms["id"], "B", "desc")
        result = validate_autonomous_range(db, ms["id"], None, None, None)
        assert result["valid"] is True
        assert len(result["phases"]) == 2

    def test_only_phase(self, db):
        ms = _ms(db)
        p1 = create_phase(db, ms["id"], "A", "desc")
        p2 = create_phase(db, ms["id"], "B", "desc")
        result = validate_autonomous_range(db, ms["id"], None, None, p1["id"])
        assert result["valid"] is True
        assert len(result["phases"]) == 1

    def test_invalid_milestone(self, db):
        _ms(db)
        result = validate_autonomous_range(db, "bogus", None, None, None)
        assert result["valid"] is False

    def test_invalid_only_phase(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "A", "desc")
        result = validate_autonomous_range(db, ms["id"], None, None, 999)
        assert result["valid"] is False

    def test_empty_milestone(self, db):
        ms = _ms(db)
        result = validate_autonomous_range(db, ms["id"], None, None, None)
        assert result["valid"] is False


class TestGetAutonomousStep:
    def test_planned_returns_discuss(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "A", "desc")
        result = get_autonomous_step(db, p["id"])
        assert result["step"] == "discuss"

    def test_context_gathered_returns_plan(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "A", "desc")
        transition_phase(db, p["id"], "context_gathered")
        result = get_autonomous_step(db, p["id"])
        assert result["step"] == "plan"

    def test_planned_out_returns_execute(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "A", "desc")
        transition_phase(db, p["id"], "context_gathered")
        transition_phase(db, p["id"], "planned_out")
        result = get_autonomous_step(db, p["id"])
        assert result["step"] == "execute"

    def test_phase_not_found(self, db):
        _ms(db)
        with pytest.raises(ValueError):
            get_autonomous_step(db, 999)


class TestPlanAutonomousRun:
    def test_skips_complete_phases(self, db):
        ms = _ms(db)
        p1 = create_phase(db, ms["id"], "Done", "desc")
        # Walk through full lifecycle
        transition_phase(db, p1["id"], "context_gathered")
        transition_phase(db, p1["id"], "planned_out")
        transition_phase(db, p1["id"], "executing")
        transition_phase(db, p1["id"], "verifying")
        transition_phase(db, p1["id"], "reviewing")
        transition_phase(db, p1["id"], "complete")
        p2 = create_phase(db, ms["id"], "Todo", "desc")

        result = plan_autonomous_run(db, ms["id"])
        assert result["skipped"] == 1
        assert len(result["phases"]) == 1
        assert result["phases"][0]["phase_name"] == "Todo"

    def test_all_complete(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "Done", "desc")
        transition_phase(db, p["id"], "context_gathered")
        transition_phase(db, p["id"], "planned_out")
        transition_phase(db, p["id"], "executing")
        transition_phase(db, p["id"], "verifying")
        transition_phase(db, p["id"], "reviewing")
        transition_phase(db, p["id"], "complete")

        result = plan_autonomous_run(db, ms["id"])
        assert len(result["phases"]) == 0
        assert "complete" in result["message"].lower()

    def test_invalid_milestone(self, db):
        _ms(db)
        result = plan_autonomous_run(db, "bogus")
        assert len(result["phases"]) == 0
