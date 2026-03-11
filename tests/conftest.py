"""Shared test fixtures for Meridian test suite."""

import sqlite3

import pytest

from scripts.db import init_schema
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    transition_milestone,
)


@pytest.fixture
def db():
    """Create an in-memory database with schema initialized."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(db):
    """DB with a project, active milestone, and 2 phases."""
    create_project(db, name="Test Project", repo_path="/tmp/test", project_id="default")
    create_milestone(db, milestone_id="v1.0", name="Version 1.0", project_id="default")
    transition_milestone(db, "v1.0", "active")
    create_phase(db, milestone_id="v1.0", name="Foundation", description="Build the base")
    create_phase(db, milestone_id="v1.0", name="Features", description="Add features")
    return db


@pytest.fixture
def file_db(tmp_path):
    """Create a file-backed database and return (conn, tmp_path)."""
    db_path = tmp_path / ".meridian" / "state.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn, tmp_path
    conn.close()
