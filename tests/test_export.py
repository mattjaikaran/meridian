#!/usr/bin/env python3
"""Tests for Meridian export module."""

import json
from contextlib import contextmanager
from unittest.mock import patch

import pytest

from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
)


@contextmanager
def _mock_open_project(conn):
    """Wrap a test connection as a context manager for open_project patches."""
    yield conn


def _seed_export_db(db):
    """Seed DB with project, milestone, phases, and plans for export tests."""
    create_project(
        db, name="Export Project", repo_path="/tmp/export", project_id="default"
    )
    create_milestone(db, milestone_id="v1.0", name="Version 1.0", project_id="default")
    transition_milestone(db, "v1.0", "active")
    phase1 = create_phase(
        db, milestone_id="v1.0", name="Foundation", description="Build the base"
    )
    phase2 = create_phase(
        db, milestone_id="v1.0", name="Features", description="Add features"
    )
    create_plan(db, phase_id=phase1["id"], name="Setup DB", description="Create schema")
    create_plan(db, phase_id=phase2["id"], name="Add Auth", description="Auth system")
    return phase1, phase2


class TestExportState:
    def test_raises_when_project_not_initialized(self, db, tmp_path):
        """export_state raises ValueError when no project in DB."""
        from scripts.export import export_state

        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            with pytest.raises(ValueError, match="Project not initialized"):
                export_state(project_dir=tmp_path)

    def test_writes_json_file(self, db, tmp_path):
        """export_state writes JSON file to .meridian/meridian-state.json."""
        from scripts.export import export_state

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        expected = tmp_path / ".meridian" / "meridian-state.json"
        assert result_path == expected
        assert expected.exists()

    def test_json_contains_required_keys(self, db, tmp_path):
        """export_state JSON contains version, project, milestones keys."""
        from scripts.export import export_state

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        data = json.loads(result_path.read_text())
        assert data["version"] == 1
        assert "project" in data
        assert data["project"]["name"] == "Export Project"
        assert "milestones" in data

    def test_milestones_contain_nested_phases_with_plans(self, db, tmp_path):
        """export_state milestones contain nested phases with nested plans."""
        from scripts.export import export_state

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        data = json.loads(result_path.read_text())
        milestones = data["milestones"]
        assert len(milestones) == 1
        assert milestones[0]["name"] == "Version 1.0"

        phases = milestones[0]["phases"]
        assert len(phases) == 2
        assert phases[0]["name"] == "Foundation"
        assert phases[1]["name"] == "Features"

        # Each phase has plans
        assert len(phases[0]["plans"]) == 1
        assert phases[0]["plans"][0]["name"] == "Setup DB"
        assert len(phases[1]["plans"]) == 1
        assert phases[1]["plans"][0]["name"] == "Add Auth"

    def test_includes_decisions_and_checkpoints(self, db, tmp_path):
        """export_state includes decisions and checkpoints keys."""
        from scripts.export import export_state

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        data = json.loads(result_path.read_text())
        assert "decisions" in data
        assert "checkpoints" in data
        # Both should be lists (possibly empty)
        assert isinstance(data["decisions"], list)
        assert isinstance(data["checkpoints"], list)


class TestExportStatusSummary:
    def test_returns_string_containing_project_name(self, db):
        """export_status_summary returns string containing project name."""
        from scripts.export import export_status_summary

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result = export_status_summary(project_dir="/tmp/test")

        assert isinstance(result, str)
        assert "Export Project" in result

    def test_includes_phase_table_with_status(self, db):
        """export_status_summary includes phase table with status."""
        from scripts.export import export_status_summary

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result = export_status_summary(project_dir="/tmp/test")

        assert "Foundation" in result
        assert "Features" in result
        # Should contain table markers
        assert "|" in result

    def test_returns_error_string_when_project_missing(self, db):
        """export_status_summary returns error string when project missing."""
        from scripts.export import export_status_summary

        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result = export_status_summary(project_dir="/tmp/test")

        assert isinstance(result, str)
        assert "not initialized" in result.lower() or "error" in result.lower()


class TestExportAsTemplate:
    def test_correct_structure(self, db):
        from scripts.export import export_as_template
        _seed_export_db(db)
        template = export_as_template(db, "v1.0")
        assert template["name"] == "Version 1.0"
        assert len(template["phases"]) == 2
        assert template["phases"][0]["name"] == "Foundation"
        assert len(template["phases"][0]["plans"]) == 1
        assert template["phases"][0]["plans"][0]["name"] == "Setup DB"

    def test_runtime_data_stripped(self, db):
        from scripts.export import export_as_template
        _seed_export_db(db)
        template = export_as_template(db, "v1.0")
        # No IDs, status, timestamps
        phase = template["phases"][0]
        assert "id" not in phase
        assert "status" not in phase
        plan = phase["plans"][0]
        assert "id" not in plan
        assert "status" not in plan
        assert "commit_sha" not in plan

    def test_round_trip(self, db):
        """Template can be used to create new milestone."""
        from scripts.export import export_as_template
        from scripts.state import create_milestone, create_phase, create_plan
        _seed_export_db(db)
        template = export_as_template(db, "v1.0")
        # Apply template to new milestone
        create_milestone(db, "v2.0", template["name"] + " v2")
        for phase_data in template["phases"]:
            phase = create_phase(db, "v2.0", phase_data["name"], phase_data.get("description"))
            for plan_data in phase_data["plans"]:
                create_plan(db, phase["id"], plan_data["name"], plan_data["description"],
                           wave=plan_data.get("wave", 1),
                           tdd_required=plan_data.get("tdd_required", True))
        from scripts.state import list_phases, list_plans
        phases = list_phases(db, "v2.0")
        assert len(phases) == 2
        plans = list_plans(db, phases[0]["id"])
        assert len(plans) == 1


class TestExportStateEdgeCases:
    """Edge cases for export_state."""

    def test_empty_database_no_milestones(self, db, tmp_path):
        """export_state with project but no milestones produces valid JSON."""
        from scripts.export import export_state

        create_project(db, name="Empty Project", repo_path="/tmp/empty", project_id="default")
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        data = json.loads(result_path.read_text())
        assert data["version"] == 1
        assert data["project"]["name"] == "Empty Project"
        assert data["milestones"] == []
        assert data["decisions"] == []
        assert data["checkpoints"] == []

    def test_milestone_with_no_phases(self, db, tmp_path):
        """export_state handles milestones that have no phases."""
        from scripts.export import export_state

        create_project(db, name="Bare Project", repo_path="/tmp/bare", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="Bare Milestone", project_id="default")
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        data = json.loads(result_path.read_text())
        assert len(data["milestones"]) == 1
        assert data["milestones"][0]["phases"] == []

    def test_special_characters_in_names(self, db, tmp_path):
        """export_state handles special characters in project/phase/plan names."""
        from scripts.export import export_state

        create_project(
            db, name='Project "Alpha" & <Beta>', repo_path="/tmp/special", project_id="default"
        )
        create_milestone(db, milestone_id="v1.0", name="Milestone: 100% done!", project_id="default")
        transition_milestone(db, "v1.0", "active")
        phase = create_phase(db, milestone_id="v1.0", name="Phase\twith\ttabs", description="desc with\nnewlines")
        create_plan(db, phase_id=phase["id"], name="Plan 'quoted'", description="emoji: \u2728")

        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        # Should produce valid JSON despite special characters
        data = json.loads(result_path.read_text())
        assert data["project"]["name"] == 'Project "Alpha" & <Beta>'
        assert data["milestones"][0]["phases"][0]["name"] == "Phase\twith\ttabs"
        assert data["milestones"][0]["phases"][0]["plans"][0]["name"] == "Plan 'quoted'"

    def test_file_io_error_permission_denied(self, db, tmp_path):
        """export_state raises error when output path is not writable."""
        from scripts.export import export_state

        create_project(db, name="Test", repo_path="/tmp/test", project_id="default")

        # Use a path that will fail on write
        bad_path = tmp_path / "readonly"
        bad_path.mkdir()
        meridian_dir = bad_path / ".meridian"
        meridian_dir.mkdir()
        # Make the directory read-only so file creation fails
        import os
        os.chmod(str(meridian_dir), 0o444)

        try:
            with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
                with pytest.raises(PermissionError):
                    export_state(project_dir=bad_path)
        finally:
            # Restore permissions for cleanup
            os.chmod(str(meridian_dir), 0o755)

    def test_round_trip_json_structure(self, db, tmp_path):
        """Export produces valid JSON that can be parsed and re-serialized identically."""
        from scripts.export import export_state

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result_path = export_state(project_dir=tmp_path)

        # Parse and re-serialize
        data = json.loads(result_path.read_text())
        reserialized = json.dumps(data, indent=2, default=str)
        reparsed = json.loads(reserialized)

        # Should be structurally identical
        assert data == reparsed
        assert data["version"] == 1
        assert isinstance(data["milestones"], list)
        assert isinstance(data["decisions"], list)
        assert isinstance(data["checkpoints"], list)

        # Verify nested structure integrity
        for ms in data["milestones"]:
            assert "name" in ms
            assert "phases" in ms
            for phase in ms["phases"]:
                assert "name" in phase
                assert "plans" in phase


class TestExportStatusSummaryEdgeCases:
    """Edge cases for export_status_summary."""

    def test_summary_with_no_phases(self, db):
        """export_status_summary handles project with no phases."""
        from scripts.export import export_status_summary

        create_project(db, name="Empty", repo_path="/tmp/empty", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="Empty MS", project_id="default")
        transition_milestone(db, "v1.0", "active")

        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result = export_status_summary(project_dir="/tmp/test")

        assert isinstance(result, str)
        assert "Empty" in result

    def test_summary_includes_next_action(self, db):
        """export_status_summary always includes a next action."""
        from scripts.export import export_status_summary

        _seed_export_db(db)
        with patch("scripts.export.open_project", return_value=_mock_open_project(db)):
            result = export_status_summary(project_dir="/tmp/test")

        assert "Next Action" in result


class TestExportAsTemplateEdgeCases:
    """Edge cases for export_as_template."""

    def test_raises_for_nonexistent_milestone(self, db):
        """export_as_template raises ValueError for missing milestone."""
        from scripts.export import export_as_template

        _seed_export_db(db)
        with pytest.raises(ValueError, match="not found"):
            export_as_template(db, "v99.0")

    def test_template_with_empty_phases(self, db):
        """export_as_template handles milestone with phases but no plans."""
        from scripts.export import export_as_template

        create_project(db, name="Test", repo_path="/tmp", project_id="default")
        create_milestone(db, milestone_id="v1.0", name="Empty", project_id="default")
        create_phase(db, milestone_id="v1.0", name="Phase A", description="No plans")

        template = export_as_template(db, "v1.0")
        assert len(template["phases"]) == 1
        assert template["phases"][0]["plans"] == []
