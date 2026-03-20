#!/usr/bin/env python3
"""Tests for Meridian session handoff (create and consume HANDOFF.json)."""

import json
import sqlite3

import pytest

from scripts.db import init_schema
from scripts.handoff import (
    HANDOFF_FILENAME,
    consume_handoff,
    create_handoff,
    format_handoff_section,
)
from scripts.state import (
    create_checkpoint,
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
def project_dir(tmp_path):
    """Create a temporary project with DB initialized."""
    db_path = tmp_path / ".meridian" / "state.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)

    create_project(conn, name="TestApp", repo_path=str(tmp_path))
    create_milestone(conn, "v1.0", "Version 1.0")
    transition_milestone(conn, "v1.0", "active")
    phase = create_phase(conn, "v1.0", "Foundation")
    transition_phase(conn, phase["id"], "context_gathered")
    transition_phase(conn, phase["id"], "planned_out")
    transition_phase(conn, phase["id"], "executing")

    p1 = create_plan(conn, phase["id"], "Setup DB", "Create schema", wave=1)
    transition_plan(conn, p1["id"], "executing")

    create_decision(conn, "Use SQLite", category="architecture")

    conn.close()
    return tmp_path


class TestCreateHandoff:
    def test_creates_file(self, project_dir):
        handoff = create_handoff(project_dir)
        handoff_path = project_dir / ".meridian" / HANDOFF_FILENAME
        assert handoff_path.exists()
        assert isinstance(handoff, dict)

    def test_contains_required_fields(self, project_dir):
        handoff = create_handoff(project_dir)
        assert "created_at" in handoff
        assert "active_phase" in handoff
        assert "active_plan" in handoff
        assert "blockers" in handoff
        assert "decisions_made" in handoff
        assert "files_modified" in handoff
        assert "next_action" in handoff
        assert "user_notes" in handoff

    def test_captures_active_phase(self, project_dir):
        handoff = create_handoff(project_dir)
        assert handoff["active_phase"] is not None
        assert handoff["active_phase"]["name"] == "Foundation"
        assert handoff["active_phase"]["status"] == "executing"

    def test_captures_active_plan(self, project_dir):
        handoff = create_handoff(project_dir)
        assert handoff["active_plan"] is not None
        assert handoff["active_plan"]["name"] == "Setup DB"

    def test_captures_decisions(self, project_dir):
        handoff = create_handoff(project_dir)
        assert len(handoff["decisions_made"]) >= 1
        assert handoff["decisions_made"][0]["summary"] == "Use SQLite"

    def test_captures_user_notes(self, project_dir):
        handoff = create_handoff(project_dir, user_notes="Was debugging import issue")
        assert handoff["user_notes"] == "Was debugging import issue"

    def test_captures_next_action(self, project_dir):
        handoff = create_handoff(project_dir)
        assert handoff["next_action"] is not None

    def test_no_db_graceful(self, tmp_path):
        """If no DB exists, still create handoff with minimal info."""
        handoff = create_handoff(tmp_path)
        assert handoff["active_phase"] is None
        assert handoff["active_plan"] is None
        assert handoff["created_at"] is not None

    def test_json_roundtrip(self, project_dir):
        """HANDOFF.json can be read back as valid JSON."""
        create_handoff(project_dir)
        handoff_path = project_dir / ".meridian" / HANDOFF_FILENAME
        data = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert data["active_phase"]["name"] == "Foundation"


class TestConsumeHandoff:
    def test_consumes_and_deletes(self, project_dir):
        create_handoff(project_dir)
        handoff_path = project_dir / ".meridian" / HANDOFF_FILENAME
        assert handoff_path.exists()

        data = consume_handoff(project_dir)
        assert data is not None
        assert data["active_phase"]["name"] == "Foundation"
        assert not handoff_path.exists()  # deleted after consumption

    def test_missing_file_returns_none(self, tmp_path):
        """Missing HANDOFF.json gracefully returns None."""
        result = consume_handoff(tmp_path)
        assert result is None

    def test_corrupt_file_returns_none(self, tmp_path):
        """Corrupt JSON gracefully returns None."""
        handoff_path = tmp_path / ".meridian" / HANDOFF_FILENAME
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text("NOT VALID JSON {{{", encoding="utf-8")
        result = consume_handoff(tmp_path)
        assert result is None

    def test_double_consume(self, project_dir):
        """Second consume returns None (file already deleted)."""
        create_handoff(project_dir)
        first = consume_handoff(project_dir)
        assert first is not None
        second = consume_handoff(project_dir)
        assert second is None


class TestFormatHandoffSection:
    def test_basic_format(self):
        handoff = {
            "created_at": "2026-03-20T10:00:00Z",
            "active_phase": {"name": "Foundation", "status": "executing"},
            "active_plan": {"name": "Setup DB", "wave": 1},
            "blockers": ["Need API key"],
            "decisions_made": [{"category": "architecture", "summary": "Use SQLite"}],
            "files_modified": ["scripts/db.py"],
            "next_action": "Execute plan: Setup DB",
            "user_notes": "Debugging import",
        }
        result = format_handoff_section(handoff)
        assert "Session Handoff" in result
        assert "Foundation" in result
        assert "Setup DB" in result
        assert "Need API key" in result
        assert "Use SQLite" in result
        assert "scripts/db.py" in result
        assert "Debugging import" in result

    def test_empty_handoff(self):
        handoff = {
            "created_at": "2026-03-20T10:00:00Z",
            "active_phase": None,
            "active_plan": None,
            "blockers": [],
            "decisions_made": [],
            "files_modified": [],
            "next_action": None,
            "user_notes": None,
        }
        result = format_handoff_section(handoff)
        assert "Session Handoff" in result
