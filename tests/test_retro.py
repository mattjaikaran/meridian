#!/usr/bin/env python3
"""Tests for structured retrospective (scripts/retro.py)."""

import pytest

from scripts.retro import (
    compute_failure_rate,
    compute_shipping_streak,
    format_retro,
    generate_retro,
    get_period_decisions,
    get_period_learnings,
    get_period_phases,
    get_review_rejections,
)
from scripts.state import (
    create_decision,
    create_phase,
    create_plan,
    create_project,
    create_review,
    transition_milestone,
    transition_phase,
    transition_plan,
)
from scripts.learnings import add_learning


@pytest.fixture
def pdb(db):
    """DB with project."""
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── Shipping Streak Tests ────────────────────────────────────────────────────


class TestShippingStreak:
    def test_empty_db(self, pdb):
        assert compute_shipping_streak(pdb) == 0

    def test_all_complete(self, seeded_db):
        # Complete both phases
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")

        transition_phase(seeded_db, 2, "context_gathered")
        transition_phase(seeded_db, 2, "planned_out")
        transition_phase(seeded_db, 2, "executing")
        transition_phase(seeded_db, 2, "verifying")
        transition_phase(seeded_db, 2, "reviewing")
        transition_phase(seeded_db, 2, "complete")

        assert compute_shipping_streak(seeded_db) == 2

    def test_streak_broken_by_non_complete(self, seeded_db):
        # Phase 1 complete, phase 2 still executing
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")

        transition_phase(seeded_db, 2, "context_gathered")
        transition_phase(seeded_db, 2, "planned_out")
        transition_phase(seeded_db, 2, "executing")

        # Streak is broken by phase 2 being in executing state
        streak = compute_shipping_streak(seeded_db)
        # Phase 1 is complete, phase 2 is executing
        # Ordering is by completed_at DESC, so complete phases come first
        assert streak >= 1

    def test_no_complete_phases(self, seeded_db):
        # Both phases still planned
        assert compute_shipping_streak(seeded_db) == 0


# ── Failure Rate Tests ───────────────────────────────────────────────────────


class TestFailureRate:
    def test_no_plans(self, pdb):
        result = compute_failure_rate(pdb)
        assert result["total"] == 0
        assert result["rate"] == 0.0

    def test_no_failures(self, seeded_db):
        # Create and complete a plan
        create_plan(seeded_db, 1, "Plan 1", "desc", wave=1)
        transition_plan(seeded_db, 1, "executing")
        transition_plan(seeded_db, 1, "complete")
        result = compute_failure_rate(seeded_db)
        assert result["total"] == 1
        assert result["failed"] == 0
        assert result["rate"] == 0.0

    def test_some_failures(self, seeded_db):
        create_plan(seeded_db, 1, "Plan 1", "desc", wave=1)
        create_plan(seeded_db, 1, "Plan 2", "desc", wave=1)
        transition_plan(seeded_db, 1, "executing")
        transition_plan(seeded_db, 1, "complete")
        transition_plan(seeded_db, 2, "executing")
        transition_plan(seeded_db, 2, "failed")
        result = compute_failure_rate(seeded_db)
        assert result["total"] == 2
        assert result["failed"] == 1
        assert result["rate"] == 50.0


# ── Period Queries ───────────────────────────────────────────────────────────


class TestPeriodPhases:
    def test_empty(self, pdb):
        assert get_period_phases(pdb) == []

    def test_returns_completed_phases(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")
        phases = get_period_phases(seeded_db)
        assert len(phases) == 1
        assert phases[0]["name"] == "Foundation"


class TestPeriodDecisions:
    def test_empty(self, pdb):
        assert get_period_decisions(pdb) == []

    def test_returns_recent_decisions(self, seeded_db):
        create_decision(seeded_db, "Chose PostgreSQL", category="architecture")
        decisions = get_period_decisions(seeded_db)
        assert len(decisions) == 1
        assert "PostgreSQL" in decisions[0]["summary"]


class TestPeriodLearnings:
    def test_empty(self, pdb):
        assert get_period_learnings(pdb) == []

    def test_returns_recent_learnings(self, pdb):
        add_learning(pdb, "Always run tests")
        learnings = get_period_learnings(pdb)
        assert len(learnings) == 1
        assert learnings[0]["rule"] == "Always run tests"


class TestReviewRejections:
    def test_empty(self, pdb):
        result = get_review_rejections(pdb)
        assert result["total"] == 0

    def test_with_reviews(self, seeded_db):
        create_review(seeded_db, phase_id=1, stage=1, result="pass", feedback="ok")
        create_review(seeded_db, phase_id=1, stage=2, result="fail", feedback="issues")
        result = get_review_rejections(seeded_db)
        assert result["total"] == 2
        assert result["failed"] == 1
        assert result["rate"] == 50.0


# ── Full Retro Tests ─────────────────────────────────────────────────────────


class TestGenerateRetro:
    def test_empty_project(self, pdb):
        retro = generate_retro(pdb)
        assert retro["period"]["days"] == 7
        assert retro["shipped"] == []
        assert retro["streak"] == 0

    def test_full_retro_structure(self, seeded_db):
        # Create some activity
        create_plan(seeded_db, 1, "Plan A", "desc", wave=1)
        transition_plan(seeded_db, 1, "executing")
        transition_plan(seeded_db, 1, "complete")
        create_decision(seeded_db, "Used FastAPI", category="tooling")
        add_learning(seeded_db, "Always check types")

        retro = generate_retro(seeded_db)
        assert "period" in retro
        assert "shipped" in retro
        assert "streak" in retro
        assert "velocity" in retro
        assert "cycle_times" in retro
        assert "failures" in retro
        assert "stalls" in retro
        assert "review_rejections" in retro
        assert "decisions" in retro
        assert "learnings" in retro

    def test_custom_window(self, pdb):
        retro = generate_retro(pdb, since_days=30)
        assert retro["period"]["days"] == 30


# ── Format Tests ─────────────────────────────────────────────────────────────


class TestFormatRetro:
    def test_empty_retro(self, pdb):
        retro = generate_retro(pdb)
        output = format_retro(retro)
        assert "## Retrospective" in output
        assert "No phases completed" in output
        assert "smooth sailing" in output

    def test_with_data(self, seeded_db):
        # Complete a phase with plans
        create_plan(seeded_db, 1, "Plan A", "desc", wave=1)
        transition_plan(seeded_db, 1, "executing")
        transition_plan(seeded_db, 1, "complete")
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")

        create_decision(seeded_db, "Picked SQLite", category="architecture")
        add_learning(seeded_db, "Test before commit")

        retro = generate_retro(seeded_db)
        output = format_retro(retro)
        assert "Foundation" in output
        assert "Plans/day" in output
        assert "Picked SQLite" in output
        assert "1 new learnings" in output
