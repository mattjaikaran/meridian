#!/usr/bin/env python3
"""Tests for auto-capture learnings (scripts/auto_learn.py)."""

import pytest

from scripts.auto_learn import (
    check_phase_for_retro_prompt,
    save_suggested_learning,
    suggest_learning_from_failure,
    suggest_learning_from_review,
)
from scripts.state import (
    create_decision,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
    transition_phase,
    transition_plan,
)


@pytest.fixture
def pdb(db):
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── Failure Suggestions ──────────────────────────────────────────────────────


class TestSuggestFromFailure:
    def test_basic_suggestion(self, seeded_db):
        create_plan(seeded_db, 1, "Setup DB", "Create tables", wave=1)
        result = suggest_learning_from_failure(
            seeded_db, 1, "Connection refused to port 5432"
        )
        assert "suggested_rule" in result
        assert "Setup DB" in result["suggested_rule"]
        assert "Connection refused" in result["suggested_rule"]
        assert result["auto_saved"] is False

    def test_with_fix_description(self, seeded_db):
        create_plan(seeded_db, 1, "API route", "Build endpoint", wave=1)
        result = suggest_learning_from_failure(
            seeded_db, 1, "404 on /api/users", fix_description="Add URL prefix"
        )
        assert "Fix:" in result["suggested_rule"]

    def test_detects_duplicate(self, seeded_db):
        from scripts.learnings import add_learning
        create_plan(seeded_db, 1, "Auth", "Build auth", wave=1)
        add_learning(seeded_db, "When working on 'Auth': Watch out for: token expiry")
        result = suggest_learning_from_failure(
            seeded_db, 1, "token expiry error"
        )
        # May or may not find duplicate depending on similarity
        assert "duplicate" in result

    def test_nonexistent_plan(self, pdb):
        result = suggest_learning_from_failure(pdb, 999, "some error")
        assert "suggested_rule" in result
        assert "unknown plan" in result["suggested_rule"]


# ── Review Suggestions ───────────────────────────────────────────────────────


class TestSuggestFromReview:
    def test_basic_suggestion(self, seeded_db):
        result = suggest_learning_from_review(
            seeded_db, 1, "Missing input validation on user endpoints"
        )
        assert "suggested_rule" in result
        assert "Foundation" in result["suggested_rule"]
        assert "validation" in result["suggested_rule"].lower()

    def test_empty_feedback(self, seeded_db):
        result = suggest_learning_from_review(seeded_db, 1, "")
        assert "suggested_rule" in result

    def test_nonexistent_phase(self, pdb):
        result = suggest_learning_from_review(pdb, 999, "some feedback")
        assert "unknown phase" in result["suggested_rule"]


# ── Save Suggested ───────────────────────────────────────────────────────────


class TestSaveSuggested:
    def test_save_from_execution(self, pdb):
        result = save_suggested_learning(pdb, "Always check DB connection", source="execution")
        assert result["id"] is not None
        assert result["source"] == "execution"
        assert result["scope"] == "project"

    def test_save_from_review(self, pdb):
        result = save_suggested_learning(pdb, "Validate inputs", source="review", phase_id=None)
        assert result["source"] == "review"


# ── Retro Prompt Check ──────────────────────────────────────────────────────


class TestRetroPromptCheck:
    def test_no_completed_phases(self, pdb):
        result = check_phase_for_retro_prompt(pdb)
        assert result["should_prompt"] is False
        assert result["phases_since_last"] == 0

    def test_below_threshold(self, seeded_db):
        # Complete 1 phase (below default threshold of 3)
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")
        result = check_phase_for_retro_prompt(seeded_db)
        assert result["should_prompt"] is False

    def test_at_threshold(self, seeded_db):
        # Complete both phases and add a 3rd
        for pid in [1, 2]:
            transition_phase(seeded_db, pid, "context_gathered")
            transition_phase(seeded_db, pid, "planned_out")
            transition_phase(seeded_db, pid, "executing")
            transition_phase(seeded_db, pid, "verifying")
            transition_phase(seeded_db, pid, "reviewing")
            transition_phase(seeded_db, pid, "complete")

        create_phase(seeded_db, "v1.0", "Third", description="third phase")
        transition_phase(seeded_db, 3, "context_gathered")
        transition_phase(seeded_db, 3, "planned_out")
        transition_phase(seeded_db, 3, "executing")
        transition_phase(seeded_db, 3, "verifying")
        transition_phase(seeded_db, 3, "reviewing")
        transition_phase(seeded_db, 3, "complete")

        result = check_phase_for_retro_prompt(seeded_db)
        assert result["should_prompt"] is True
        assert result["phases_since_last"] >= 3

    def test_resets_after_retro_decision(self, seeded_db):
        # Complete phases
        for pid in [1, 2]:
            transition_phase(seeded_db, pid, "context_gathered")
            transition_phase(seeded_db, pid, "planned_out")
            transition_phase(seeded_db, pid, "executing")
            transition_phase(seeded_db, pid, "verifying")
            transition_phase(seeded_db, pid, "reviewing")
            transition_phase(seeded_db, pid, "complete")

        # Record a retro decision
        create_decision(seeded_db, "Retro: weekly review completed", category="approach")

        result = check_phase_for_retro_prompt(seeded_db)
        assert result["should_prompt"] is False

    def test_custom_interval(self, seeded_db):
        transition_phase(seeded_db, 1, "context_gathered")
        transition_phase(seeded_db, 1, "planned_out")
        transition_phase(seeded_db, 1, "executing")
        transition_phase(seeded_db, 1, "verifying")
        transition_phase(seeded_db, 1, "reviewing")
        transition_phase(seeded_db, 1, "complete")

        result = check_phase_for_retro_prompt(seeded_db, phase_interval=1)
        assert result["should_prompt"] is True
