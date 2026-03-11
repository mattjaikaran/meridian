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
