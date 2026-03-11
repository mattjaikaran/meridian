#!/usr/bin/env python3
"""Tests for Meridian resume prompt generator."""

import sqlite3

import pytest

from scripts.db import init_schema
from scripts.resume import generate_resume_prompt
from scripts.state import (
    create_decision,
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    transition_milestone,
    transition_phase,
    transition_plan,
)


@pytest.fixture
def db(tmp_path):
    """Create a temporary database and return (conn, project_dir).

    Note: This fixture overrides the shared conftest db fixture because
    test_resume needs file-backed DB with project_dir for generate_resume_prompt.
    """
    db_path = tmp_path / ".meridian" / "state.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    return conn, tmp_path


class TestResumePrompt:
    def test_no_project(self, tmp_path):
        # No .meridian directory at all — should return init message
        prompt = generate_resume_prompt(tmp_path)
        assert "not initialized" in prompt.lower() or "init" in prompt.lower()

    def test_empty_db(self, db):
        # DB exists with schema but no project record
        conn, project_dir = db
        conn.close()
        prompt = generate_resume_prompt(project_dir)
        assert "not initialized" in prompt.lower() or "init" in prompt.lower()

    def test_no_milestone(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        conn.close()
        prompt = generate_resume_prompt(project_dir)
        assert "TestApp" in prompt
        assert "No active milestone" in prompt

    def test_with_active_milestone(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "Version 1.0", description="First release")
        transition_milestone(conn, "v1.0", "active")
        create_phase(
            conn,
            "v1.0",
            "Foundation",
            description="Build the base",
            acceptance_criteria=["Tests pass", "Schema created"],
        )
        conn.close()

        prompt = generate_resume_prompt(project_dir)
        assert "TestApp" in prompt
        assert "Version 1.0" in prompt
        assert "Foundation" in prompt
        assert "Tests pass" in prompt

    def test_with_plans_and_progress(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "Version 1.0")
        transition_milestone(conn, "v1.0", "active")
        phase = create_phase(conn, "v1.0", "Foundation")
        transition_phase(conn, phase["id"], "context_gathered")
        transition_phase(conn, phase["id"], "planned_out")
        transition_phase(conn, phase["id"], "executing")

        p1 = create_plan(conn, phase["id"], "Setup DB", "Create schema", wave=1)
        create_plan(conn, phase["id"], "Add models", "Create models", wave=1)
        create_plan(conn, phase["id"], "Add API", "Create endpoints", wave=2)

        transition_plan(conn, p1["id"], "executing")
        transition_plan(conn, p1["id"], "complete", commit_sha="abc123def")
        conn.close()

        prompt = generate_resume_prompt(project_dir)
        assert "Setup DB" in prompt
        assert "abc123de" in prompt  # truncated SHA
        assert "Add API" in prompt
        assert "Wave 2" in prompt

    def test_with_decisions(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "V1")
        transition_milestone(conn, "v1.0", "active")
        create_phase(conn, "v1.0", "Foundation")
        create_decision(conn, "Use SQLite for state", category="architecture")
        conn.close()

        prompt = generate_resume_prompt(project_dir)
        assert "Use SQLite" in prompt
        assert "architecture" in prompt

    def test_deterministic(self, db):
        """Same state = same prompt (excluding git state which may change)."""
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "V1")
        transition_milestone(conn, "v1.0", "active")
        create_phase(conn, "v1.0", "Foundation")
        conn.close()

        prompt1 = generate_resume_prompt(project_dir)
        prompt2 = generate_resume_prompt(project_dir)
        assert prompt1 == prompt2

    def test_next_action_included(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "V1")
        transition_milestone(conn, "v1.0", "active")
        create_phase(conn, "v1.0", "Foundation")
        conn.close()

        prompt = generate_resume_prompt(project_dir)
        assert "Next Action" in prompt
        assert "→" in prompt

    def test_failed_plan_shows_error(self, db):
        conn, project_dir = db
        create_project(conn, name="TestApp", repo_path=str(project_dir))
        create_milestone(conn, "v1.0", "V1")
        transition_milestone(conn, "v1.0", "active")
        phase = create_phase(conn, "v1.0", "Foundation")
        transition_phase(conn, phase["id"], "context_gathered")
        transition_phase(conn, phase["id"], "planned_out")
        transition_phase(conn, phase["id"], "executing")
        p = create_plan(conn, phase["id"], "Broken Plan", "This will fail")
        transition_plan(conn, p["id"], "executing")
        transition_plan(conn, p["id"], "failed", error_message="ImportError: no module named foo")
        conn.close()

        prompt = generate_resume_prompt(project_dir)
        assert "failed" in prompt.lower()
        assert "ImportError" in prompt
