#!/usr/bin/env python3
"""Tests for Meridian spec phase module."""

import json
from pathlib import Path

import pytest

from scripts.spec_phase import (
    DIMENSIONS,
    GATE_THRESHOLD,
    check_spec_artifact,
    compute_ambiguity,
    format_scores,
    gate_passed,
    get_spec_context,
    get_spec_metadata,
    initial_scores_from_context,
    is_spec_complete,
    mark_spec_complete,
    spec_gate,
    write_spec_md,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_milestone,
)


# ── Ambiguity Model Tests ─────────────────────────────────────────────────────


class TestComputeAmbiguity:
    def test_perfect_clarity(self):
        scores = {dim: 1.0 for dim in DIMENSIONS}
        assert compute_ambiguity(scores) == 0.0

    def test_perfect_ambiguity(self):
        scores = {dim: 0.0 for dim in DIMENSIONS}
        assert compute_ambiguity(scores) == 1.0

    def test_weighted_correctly(self):
        # 0.35*goal + 0.25*boundary + 0.20*constraint + 0.20*acceptance
        scores = {
            "goal_clarity": 1.0,
            "boundary_clarity": 0.0,
            "constraint_clarity": 0.0,
            "acceptance_criteria": 0.0,
        }
        expected = round(1.0 - 0.35, 4)
        assert compute_ambiguity(scores) == expected

    def test_gate_threshold_boundary(self):
        # At exactly 0.20 ambiguity (80% weighted clarity)
        scores = {
            "goal_clarity": 0.80,
            "boundary_clarity": 0.80,
            "constraint_clarity": 0.80,
            "acceptance_criteria": 0.80,
        }
        ambiguity = compute_ambiguity(scores)
        assert ambiguity <= GATE_THRESHOLD


class TestGatePassed:
    def test_passes_when_all_clear(self):
        scores = {
            "goal_clarity": 0.90,
            "boundary_clarity": 0.85,
            "constraint_clarity": 0.80,
            "acceptance_criteria": 0.85,
        }
        passed, failing = gate_passed(scores)
        assert passed is True
        assert failing == []

    def test_fails_when_ambiguity_high(self):
        scores = {
            "goal_clarity": 0.50,
            "boundary_clarity": 0.50,
            "constraint_clarity": 0.50,
            "acceptance_criteria": 0.50,
        }
        passed, failing = gate_passed(scores)
        assert passed is False

    def test_fails_when_dimension_below_minimum(self):
        scores = {
            "goal_clarity": 0.90,
            "boundary_clarity": 0.50,  # below 0.70
            "constraint_clarity": 0.80,
            "acceptance_criteria": 0.85,
        }
        passed, failing = gate_passed(scores)
        assert passed is False
        assert "boundary_clarity" in failing

    def test_reports_all_failing_dimensions(self):
        scores = {
            "goal_clarity": 0.50,  # below 0.75
            "boundary_clarity": 0.50,  # below 0.70
            "constraint_clarity": 0.50,  # below 0.65
            "acceptance_criteria": 0.50,  # below 0.70
        }
        passed, failing = gate_passed(scores)
        assert len(failing) == 4


class TestFormatScores:
    def test_returns_string(self):
        scores = {dim: 0.80 for dim in DIMENSIONS}
        result = format_scores(scores)
        assert isinstance(result, str)
        assert "Goal Clarity" in result
        assert "Ambiguity" in result

    def test_shows_pass_when_gate_passed(self):
        scores = {
            "goal_clarity": 0.90,
            "boundary_clarity": 0.85,
            "constraint_clarity": 0.80,
            "acceptance_criteria": 0.85,
        }
        result = format_scores(scores)
        assert "PASS" in result

    def test_shows_fail_when_gate_not_passed(self):
        scores = {dim: 0.30 for dim in DIMENSIONS}
        result = format_scores(scores)
        assert "FAIL" in result


class TestInitialScoresFromContext:
    def test_returns_all_dimensions(self):
        scores = initial_scores_from_context("Test Phase", "Some description", [])
        assert set(scores.keys()) == set(DIMENSIONS.keys())

    def test_more_criteria_raises_acceptance_score(self):
        few = initial_scores_from_context("Test", "Desc", ["crit1"])
        many = initial_scores_from_context("Test", "Desc", ["c1", "c2", "c3", "c4", "c5"])
        assert many["acceptance_criteria"] >= few["acceptance_criteria"]

    def test_longer_description_raises_goal_score(self):
        short = initial_scores_from_context("Test", "Short", [])
        long_desc = "This is a much longer description " * 10
        long = initial_scores_from_context("Test", long_desc, [])
        assert long["goal_clarity"] >= short["goal_clarity"]

    def test_scores_capped_at_reasonable_values(self):
        scores = initial_scores_from_context("Test", "x" * 1000, ["c"] * 20)
        for score in scores.values():
            assert 0.0 <= score <= 1.0


# ── Context Retrieval Tests ───────────────────────────────────────────────────


class TestGetSpecContext:
    def test_returns_error_when_no_phases(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        result = get_spec_context(db)
        assert "error" in result

    def test_finds_pending_phase(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Auth System", description="Build auth")
        result = get_spec_context(db)
        assert "error" not in result
        assert result["phase_name"] == "Auth System"
        assert result["description"] == "Build auth"

    def test_finds_phase_by_id(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Phase One", description="First")
        row = db.execute("SELECT id FROM phase WHERE name='Phase One'").fetchone()
        result = get_spec_context(db, phase_id=row["id"])
        assert "error" not in result
        assert result["phase_id"] == row["id"]

    def test_returns_initial_scores(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Phase One", description="Build stuff")
        result = get_spec_context(db)
        assert "initial_scores" in result
        assert "initial_ambiguity" in result
        assert isinstance(result["initial_ambiguity"], float)

    def test_returns_error_for_missing_phase_id(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        result = get_spec_context(db, phase_id=9999)
        assert "error" in result

    def test_includes_phase_dir(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="My Phase", description="Desc")
        result = get_spec_context(db)
        assert "phase_dir" in result
        assert ".planning/phases/" in result["phase_dir"]


# ── Artifact Tests ────────────────────────────────────────────────────────────


class TestCheckSpecArtifact:
    def test_returns_false_when_missing(self, tmp_path):
        assert check_spec_artifact(tmp_path) is False

    def test_returns_false_when_empty(self, tmp_path):
        (tmp_path / "SPEC.md").write_text("")
        assert check_spec_artifact(tmp_path) is False

    def test_returns_true_when_exists(self, tmp_path):
        (tmp_path / "SPEC.md").write_text("# Spec\n" + "x" * 200)
        assert check_spec_artifact(tmp_path) is True


class TestWriteSpecMd:
    def test_creates_spec_md(self, tmp_path):
        scores = {
            "goal_clarity": 0.90,
            "boundary_clarity": 0.85,
            "constraint_clarity": 0.80,
            "acceptance_criteria": 0.85,
        }
        path = write_spec_md(
            phase_dir=tmp_path,
            phase_name="Auth System",
            phase_id=3,
            goal="Build a complete authentication system.",
            requirements=["Users can log in via API", "Sessions expire after 1 hour"],
            in_scope=["Login endpoint", "Session management"],
            out_of_scope=["OAuth integration", "2FA"],
            acceptance_criteria=["POST /login returns 200 on valid credentials"],
            constraints=["Must work with PostgreSQL"],
            final_scores=scores,
        )
        assert path.exists()
        assert path.name == "SPEC.md"
        content = path.read_text()
        assert "Auth System" in content
        assert "Phase 3" in content
        assert "REQ-01" in content
        assert "REQ-02" in content
        assert "In Scope" in content
        assert "Out of Scope" in content
        assert "Ambiguity Report" in content

    def test_creates_directory(self, tmp_path):
        nested = tmp_path / "phases" / "03-auth"
        scores = {dim: 0.90 for dim in DIMENSIONS}
        path = write_spec_md(
            phase_dir=nested,
            phase_name="Auth",
            phase_id=3,
            goal="Build auth.",
            requirements=["Users can log in"],
            in_scope=["Login"],
            out_of_scope=["OAuth"],
            acceptance_criteria=["Login works"],
            constraints=[],
            final_scores=scores,
        )
        assert path.exists()
        assert nested.exists()

    def test_flags_unresolved_dimensions(self, tmp_path):
        scores = {dim: 0.90 for dim in DIMENSIONS}
        scores["boundary_clarity"] = 0.50  # below minimum
        path = write_spec_md(
            phase_dir=tmp_path,
            phase_name="Test",
            phase_id=1,
            goal="Do the thing.",
            requirements=["Thing is done"],
            in_scope=["Thing"],
            out_of_scope=["Other thing"],
            acceptance_criteria=["Thing passes test"],
            constraints=[],
            final_scores=scores,
            unresolved_dimensions=["boundary_clarity"],
        )
        content = path.read_text()
        assert "Below minimum" in content

    def test_ambiguity_score_in_output(self, tmp_path):
        scores = {dim: 0.90 for dim in DIMENSIONS}
        path = write_spec_md(
            phase_dir=tmp_path,
            phase_name="Test",
            phase_id=1,
            goal="Test goal.",
            requirements=["Req one"],
            in_scope=["Scope"],
            out_of_scope=["Out"],
            acceptance_criteria=["AC one"],
            constraints=[],
            final_scores=scores,
        )
        content = path.read_text()
        assert "Ambiguity Score" in content


# ── DB Completion Tests ───────────────────────────────────────────────────────


class TestMarkSpecComplete:
    def test_marks_complete(self, seeded_db):
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        mark_spec_complete(seeded_db, phase_id, 0.15, 5)
        assert is_spec_complete(seeded_db, phase_id) is True

    def test_stores_metadata(self, seeded_db):
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        mark_spec_complete(seeded_db, phase_id, 0.12, 7)
        meta = get_spec_metadata(seeded_db, phase_id)
        assert meta is not None
        assert meta["spec_ambiguity"] == 0.12
        assert meta["spec_requirement_count"] == 7

    def test_is_spec_complete_false_when_not_marked(self, seeded_db):
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        assert is_spec_complete(seeded_db, phase_id) is False

    def test_get_spec_metadata_none_when_not_marked(self, seeded_db):
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        assert get_spec_metadata(seeded_db, phase_id) is None

    def test_preserves_existing_notes(self, seeded_db):
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        existing = {"research_complete": True, "research_date": "2026-01-01"}
        seeded_db.execute(
            "UPDATE phase SET notes = ? WHERE id = ?",
            (json.dumps(existing), phase_id),
        )
        seeded_db.commit()
        mark_spec_complete(seeded_db, phase_id, 0.10, 3)
        notes = json.loads(
            seeded_db.execute("SELECT notes FROM phase WHERE id=?", (phase_id,)).fetchone()["notes"]
        )
        assert notes.get("research_complete") is True
        assert notes.get("spec_complete") is True


# ── Gate Tests ────────────────────────────────────────────────────────────────


class TestSpecGate:
    def test_passes_when_spec_exists(self, tmp_path):
        (tmp_path / "SPEC.md").write_text("# Spec\n" + "x" * 200)
        result = spec_gate(tmp_path)
        assert result["passed"] is True
        assert result["spec_path"] is not None
        assert result["warning"] is None

    def test_fails_when_spec_missing(self, tmp_path):
        result = spec_gate(tmp_path)
        assert result["passed"] is False
        assert result["warning"] is not None
        assert "spec-phase" in result["warning"]

    def test_includes_requirement_count_from_db(self, tmp_path, seeded_db):
        (tmp_path / "SPEC.md").write_text("# Spec\n" + "x" * 200)
        phase_id = seeded_db.execute("SELECT id FROM phase LIMIT 1").fetchone()["id"]
        mark_spec_complete(seeded_db, phase_id, 0.10, 6)
        result = spec_gate(tmp_path, conn=seeded_db, phase_id=phase_id)
        assert result["passed"] is True
        assert result["requirement_count"] == 6
