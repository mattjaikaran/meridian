#!/usr/bin/env python3
"""Tests for Meridian UI phase module."""

import json
from pathlib import Path

import pytest

from scripts.ui_phase import (
    check_ui_artifact,
    get_ui_context,
    get_ui_metadata,
    is_ui_complete,
    mark_ui_complete,
    ui_gate,
    write_ui_spec_md,
)
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_milestone,
)


# ── Context Retrieval Tests ───────────────────────────────────────────────────


class TestGetUiContext:
    def test_returns_error_when_no_phases(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        result = get_ui_context(db)
        assert "error" in result

    def test_finds_pending_phase(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Dashboard UI", description="Build dashboard")
        result = get_ui_context(db)
        assert "error" not in result
        assert result["phase_name"] == "Dashboard UI"
        assert result["description"] == "Build dashboard"

    def test_finds_phase_by_id(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Settings Page", description="User settings")
        row = db.execute("SELECT id FROM phase WHERE name='Settings Page'").fetchone()
        result = get_ui_context(db, phase_id=row["id"])
        assert "error" not in result
        assert result["phase_id"] == row["id"]

    def test_returns_error_for_missing_phase_id(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        result = get_ui_context(db, phase_id=9999)
        assert "error" in result

    def test_returns_phase_dir_slug(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="Auth Login", sequence=5)
        result = get_ui_context(db)
        assert "phase_dir" in result
        assert "slug" in result
        assert "auth-login" in result["slug"]

    def test_includes_tech_stack(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        db.execute(
            "UPDATE project SET tech_stack = 'React TypeScript' WHERE id = 'default'"
        )
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI", description="Build UI")
        result = get_ui_context(db)
        assert result["tech_stack"] == "React TypeScript"

    def test_returns_acceptance_criteria_list(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(
            db,
            milestone_id="v1.0",
            name="Form UI",
            acceptance_criteria=["Form submits", "Validation shows"],
        )
        result = get_ui_context(db)
        assert isinstance(result["acceptance_criteria"], list)


# ── Artifact Check Tests ──────────────────────────────────────────────────────


class TestCheckUiArtifact:
    def test_returns_false_when_missing(self, tmp_path):
        assert check_ui_artifact(tmp_path) is False

    def test_returns_false_when_empty(self, tmp_path):
        (tmp_path / "UI_SPEC.md").write_text("small")
        assert check_ui_artifact(tmp_path) is False

    def test_returns_true_when_present(self, tmp_path):
        content = "# UI Spec\n\n" + "x" * 200
        (tmp_path / "UI_SPEC.md").write_text(content)
        assert check_ui_artifact(tmp_path) is True


# ── Artifact Writing Tests ────────────────────────────────────────────────────


class TestWriteUiSpecMd:
    def test_creates_file(self, tmp_path):
        path = write_ui_spec_md(
            tmp_path,
            phase_name="Dashboard",
            phase_id=1,
            design="Design tokens: blue-500, gray-900",
            components="Button, Card, Table",
            ux="Focus management: trap in modal",
        )
        assert path.exists()
        assert path.name == "UI_SPEC.md"

    def test_contains_all_sections(self, tmp_path):
        content_design = "Tailwind CSS with shadcn/ui"
        content_components = "Button variant='primary'"
        content_ux = "Tab order: nav, main, footer"
        path = write_ui_spec_md(
            tmp_path,
            phase_name="Settings",
            phase_id=2,
            design=content_design,
            components=content_components,
            ux=content_ux,
        )
        text = path.read_text()
        assert "Design System" in text
        assert "Component Contracts" in text
        assert "UX" in text
        assert content_design in text
        assert content_components in text
        assert content_ux in text

    def test_includes_phase_id_and_name(self, tmp_path):
        path = write_ui_spec_md(
            tmp_path,
            phase_name="Auth Flow",
            phase_id=42,
            design="d",
            components="c",
            ux="u",
        )
        text = path.read_text()
        assert "42" in text
        assert "Auth Flow" in text

    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "phases" / "42-auth-flow"
        path = write_ui_spec_md(
            nested,
            phase_name="Auth Flow",
            phase_id=42,
            design="d",
            components="c",
            ux="u",
        )
        assert path.exists()

    def test_handles_empty_ux(self, tmp_path):
        path = write_ui_spec_md(
            tmp_path,
            phase_name="Quick UI",
            phase_id=3,
            design="tokens",
            components="Button",
            ux="",
        )
        assert path.exists()
        text = path.read_text()
        assert "Component Contracts" in text


# ── Completion Marker Tests ───────────────────────────────────────────────────


class TestMarkUiComplete:
    def test_marks_phase_complete(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI Phase")
        row = db.execute("SELECT id FROM phase LIMIT 1").fetchone()
        phase_id = row["id"]

        assert is_ui_complete(db, phase_id) is False
        mark_ui_complete(db, phase_id)
        assert is_ui_complete(db, phase_id) is True

    def test_preserves_existing_notes(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI Phase")
        row = db.execute("SELECT id FROM phase LIMIT 1").fetchone()
        phase_id = row["id"]

        # Pre-populate notes with existing data
        db.execute(
            "UPDATE phase SET notes = ? WHERE id = ?",
            (json.dumps({"research_complete": True}), phase_id),
        )
        mark_ui_complete(db, phase_id)

        notes_row = db.execute("SELECT notes FROM phase WHERE id=?", (phase_id,)).fetchone()
        notes = json.loads(notes_row["notes"])
        assert notes["research_complete"] is True
        assert notes["ui_spec_complete"] is True

    def test_idempotent(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI Phase")
        row = db.execute("SELECT id FROM phase LIMIT 1").fetchone()
        phase_id = row["id"]

        mark_ui_complete(db, phase_id)
        mark_ui_complete(db, phase_id)
        assert is_ui_complete(db, phase_id) is True


class TestGetUiMetadata:
    def test_returns_none_when_not_complete(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI Phase")
        row = db.execute("SELECT id FROM phase LIMIT 1").fetchone()
        assert get_ui_metadata(db, row["id"]) is None

    def test_returns_metadata_when_complete(self, db):
        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="V1", project_id="default")
        transition_milestone(db, "v1.0", "active")
        create_phase(db, milestone_id="v1.0", name="UI Phase")
        row = db.execute("SELECT id FROM phase LIMIT 1").fetchone()
        phase_id = row["id"]

        mark_ui_complete(db, phase_id)
        meta = get_ui_metadata(db, phase_id)
        assert meta is not None
        assert "ui_spec_date" in meta


# ── Gate Tests ────────────────────────────────────────────────────────────────


class TestUiGate:
    def test_passes_when_artifact_exists(self, tmp_path):
        content = "# UI Spec\n\n" + "x" * 200
        (tmp_path / "UI_SPEC.md").write_text(content)
        result = ui_gate(tmp_path)
        assert result["passed"] is True
        assert result["warning"] is None
        assert result["ui_spec_path"] is not None

    def test_fails_when_artifact_missing(self, tmp_path):
        result = ui_gate(tmp_path)
        assert result["passed"] is False
        assert result["warning"] is not None
        assert "UI_SPEC.md" in result["warning"]
        assert result["ui_spec_path"] is None

    def test_gate_message_mentions_skip_flag(self, tmp_path):
        result = ui_gate(tmp_path)
        assert "--skip-ui" in result["warning"]

    def test_returns_absolute_path_when_passed(self, tmp_path):
        content = "# UI Spec\n\n" + "x" * 200
        (tmp_path / "UI_SPEC.md").write_text(content)
        result = ui_gate(tmp_path)
        assert result["ui_spec_path"].endswith("UI_SPEC.md")
