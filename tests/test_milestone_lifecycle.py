#!/usr/bin/env python3
"""Tests for Meridian milestone lifecycle."""

import pytest

from scripts.milestone_lifecycle import (
    archive_milestone,
    audit_milestone,
    complete_milestone,
    generate_milestone_summary,
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


def _complete_phase(db, ms_id, name="Phase", plans=1):
    """Helper to create a fully complete phase with plans."""
    p = create_phase(db, ms_id, name, f"desc for {name}")
    transition_phase(db, p["id"], "context_gathered")
    transition_phase(db, p["id"], "planned_out")
    transition_phase(db, p["id"], "executing")
    for i in range(plans):
        plan = create_plan(db, p["id"], f"Plan {i+1}", f"task {i+1}")
        transition_plan(db, plan["id"], "executing")
        transition_plan(db, plan["id"], "complete")
    transition_phase(db, p["id"], "verifying")
    transition_phase(db, p["id"], "reviewing")
    transition_phase(db, p["id"], "complete")
    return p


def _ms(db):
    create_project(db, name="Test", repo_path="/tmp/test")
    ms = create_milestone(db, "v1", "V1", project_id="default")
    transition_milestone(db, ms["id"], "active")
    return ms


class TestAuditMilestone:
    def test_ready_milestone(self, db):
        ms = _ms(db)
        _complete_phase(db, ms["id"], "Phase A", 2)
        _complete_phase(db, ms["id"], "Phase B", 1)

        result = audit_milestone(db, ms["id"])
        assert result["ready"] is True
        assert result["issues"] == []
        assert result["stats"]["total_phases"] == 2
        assert result["stats"]["complete_plans"] == 3

    def test_incomplete_phase(self, db):
        ms = _ms(db)
        _complete_phase(db, ms["id"], "Done")
        create_phase(db, ms["id"], "Not Done", "desc")

        result = audit_milestone(db, ms["id"])
        assert result["ready"] is False
        assert len(result["issues"]) >= 1

    def test_failed_plan(self, db):
        ms = _ms(db)
        p = create_phase(db, ms["id"], "Broken", "desc")
        transition_phase(db, p["id"], "context_gathered")
        transition_phase(db, p["id"], "planned_out")
        transition_phase(db, p["id"], "executing")
        plan = create_plan(db, p["id"], "Bad Plan", "fails")
        transition_plan(db, plan["id"], "executing")
        transition_plan(db, plan["id"], "failed", error_message="broke")

        result = audit_milestone(db, ms["id"])
        assert result["ready"] is False
        assert result["stats"]["failed_plans"] == 1

    def test_nonexistent(self, db):
        _ms(db)
        with pytest.raises(ValueError):
            audit_milestone(db, "bogus")


class TestCompleteMilestone:
    def test_complete_ready(self, db):
        ms = _ms(db)
        _complete_phase(db, ms["id"], "Done", 2)

        result = complete_milestone(db, ms["id"])
        assert result["status"] == "complete"
        assert result["summary"]["phases_count"] == 1
        assert result["summary"]["plans_count"] == 2
        assert "milestone/v1" in result["git_tag"]

    def test_reject_incomplete(self, db):
        ms = _ms(db)
        create_phase(db, ms["id"], "Not Done", "desc")

        with pytest.raises(ValueError, match="not ready"):
            complete_milestone(db, ms["id"])


class TestArchiveMilestone:
    def test_archive_complete(self, db):
        ms = _ms(db)
        _complete_phase(db, ms["id"], "Done")
        complete_milestone(db, ms["id"])

        result = archive_milestone(db, ms["id"])
        assert result["status"] == "archived"


class TestGenerateMilestoneSummary:
    def test_summary_structure(self, db):
        ms = _ms(db)
        _complete_phase(db, ms["id"], "Phase A", 2)

        summary = generate_milestone_summary(db, ms["id"])
        assert "# Milestone:" in summary
        assert "Phase A" in summary
        assert "## Phases" in summary
        assert "## Summary Statistics" in summary

    def test_nonexistent(self, db):
        _ms(db)
        with pytest.raises(ValueError):
            generate_milestone_summary(db, "bogus")
