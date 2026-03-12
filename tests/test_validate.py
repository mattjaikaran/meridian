#!/usr/bin/env python3
"""Tests for git state validation."""

import sqlite3
import subprocess

import pytest

from scripts.db import init_schema
from scripts.state import (
    create_milestone,
    create_phase,
    create_plan,
    create_project,
    list_phases,
    transition_milestone,
    transition_plan,
)
from scripts.validate import validate_state


@pytest.fixture
def git_db(tmp_path):
    """Create a git repo + in-memory DB with completed plans."""
    # Init git repo
    subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp_path), capture_output=True)
    # Create a commit
    (tmp_path / "file.txt").write_text("hello")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(tmp_path), capture_output=True, text=True
    ).stdout.strip()

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)

    create_project(conn, name="Test", repo_path=str(tmp_path))
    create_milestone(conn, "v1.0", "V1")
    transition_milestone(conn, "v1.0", "active")
    phase = create_phase(conn, "v1.0", "Phase 1")

    yield conn, tmp_path, sha, phase
    conn.close()


class TestValidateState:
    def test_valid_sha(self, git_db):
        conn, tmp_path, sha, phase = git_db
        p = create_plan(conn, phase["id"], "Plan 1", "Do it")
        transition_plan(conn, p["id"], "executing")
        transition_plan(conn, p["id"], "complete", commit_sha=sha)
        result = validate_state(conn, str(tmp_path))
        assert p["id"] in result["valid"]
        assert result["missing"] == []

    def test_missing_sha(self, git_db):
        conn, tmp_path, sha, phase = git_db
        p = create_plan(conn, phase["id"], "Plan 1", "Do it")
        transition_plan(conn, p["id"], "executing")
        transition_plan(conn, p["id"], "complete", commit_sha="deadbeefdeadbeef")
        result = validate_state(conn, str(tmp_path))
        assert p["id"] in result["missing"]

    def test_no_sha_plans_skipped(self, git_db):
        conn, tmp_path, sha, phase = git_db
        p = create_plan(conn, phase["id"], "Plan 1", "Do it")
        transition_plan(conn, p["id"], "executing")
        transition_plan(conn, p["id"], "complete")
        result = validate_state(conn, str(tmp_path))
        assert result["valid"] == []
        assert result["missing"] == []
