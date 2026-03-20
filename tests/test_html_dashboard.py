#!/usr/bin/env python3
"""Tests for HTML dashboard generator (scripts/html_dashboard.py)."""

import pytest

from scripts.html_dashboard import generate_dashboard_data, render_html, write_dashboard
from scripts.state import (
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
    transition_plan,
)


@pytest.fixture
def pdb(db):
    create_project(db, name="Test Project", repo_path="/tmp/test", project_id="default")
    return db


class TestGenerateDashboardData:
    def test_empty_project(self, pdb):
        data = generate_dashboard_data(pdb)
        assert "generated_at" in data
        assert "velocity" in data
        assert "stalls" in data
        assert "streak" in data
        assert "learnings_count" in data
        assert "decisions_count" in data

    def test_with_milestone(self, seeded_db):
        data = generate_dashboard_data(seeded_db)
        assert data["milestone"] is not None

    def test_with_plans(self, seeded_db):
        create_plan(seeded_db, 1, "Plan A", "desc", wave=1)
        transition_plan(seeded_db, 1, "executing")
        transition_plan(seeded_db, 1, "complete")
        data = generate_dashboard_data(seeded_db)
        assert data["velocity"]["completed_count"] >= 1


class TestRenderHtml:
    def test_renders_valid_html(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "<!DOCTYPE html>" in html
        assert "Meridian Dashboard" in html
        assert "</html>" in html

    def test_includes_project_name(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "Test Project" in html

    def test_includes_health_indicator(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert any(h in html for h in ["ON TRACK", "AT RISK", "STALLED"])

    def test_includes_velocity(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "plans/day" in html

    def test_includes_phase_table(self, seeded_db):
        data = generate_dashboard_data(seeded_db)
        html = render_html(data)
        assert "Foundation" in html
        assert "Features" in html

    def test_includes_next_action(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "Next Action" in html

    def test_no_phases_message(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "No phases yet" in html

    def test_dark_theme(self, pdb):
        data = generate_dashboard_data(pdb)
        html = render_html(data)
        assert "#0f172a" in html  # Dark background


class TestWriteDashboard:
    def test_writes_file(self, pdb, tmp_path):
        output = tmp_path / "dashboard.html"
        result = write_dashboard(pdb, str(output))
        assert output.exists()
        content = output.read_text()
        assert "<!DOCTYPE html>" in content

    def test_returns_path(self, pdb, tmp_path):
        output = tmp_path / "dashboard.html"
        result = write_dashboard(pdb, str(output))
        assert result == str(output)
