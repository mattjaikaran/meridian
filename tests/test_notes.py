#!/usr/bin/env python3
"""Tests for Meridian note capture."""

import pytest

from scripts.notes import (
    _next_note_id,
    append_note,
    list_notes,
    promote_note,
)
from scripts.state import create_project


# ── Helper Tests ─────────────────────────────────────────────────────────────


class TestNextNoteId:
    def test_empty_content(self):
        assert _next_note_id("") == "N001"

    def test_single_note(self):
        assert _next_note_id("- [N001] 2026-03-20 10:00 — test") == "N002"

    def test_multiple_notes(self):
        content = "- [N001] test\n- [N003] test\n- [N002] test"
        assert _next_note_id(content) == "N004"


# ── Append Tests ─────────────────────────────────────────────────────────────


class TestAppendNote:
    def test_append_to_new_file(self, tmp_path):
        result = append_note(tmp_path, "Test note")
        assert result["id"] == "N001"
        assert result["text"] == "Test note"
        notes_file = tmp_path / ".meridian" / "notes.md"
        assert notes_file.exists()
        content = notes_file.read_text()
        assert "[N001]" in content
        assert "Test note" in content

    def test_append_multiple(self, tmp_path):
        append_note(tmp_path, "First note")
        result = append_note(tmp_path, "Second note")
        assert result["id"] == "N002"
        notes = list_notes(tmp_path)
        assert len(notes) == 2

    def test_preserves_existing_content(self, tmp_path):
        append_note(tmp_path, "First")
        append_note(tmp_path, "Second")
        notes = list_notes(tmp_path)
        assert notes[0]["text"] == "First"
        assert notes[1]["text"] == "Second"

    def test_creates_meridian_dir(self, tmp_path):
        append_note(tmp_path, "test")
        assert (tmp_path / ".meridian").is_dir()


# ── List Tests ───────────────────────────────────────────────────────────────


class TestListNotes:
    def test_empty_dir(self, tmp_path):
        assert list_notes(tmp_path) == []

    def test_lists_all_notes(self, tmp_path):
        append_note(tmp_path, "Alpha")
        append_note(tmp_path, "Beta")
        append_note(tmp_path, "Gamma")
        notes = list_notes(tmp_path)
        assert len(notes) == 3
        assert notes[0]["id"] == "N001"
        assert notes[2]["id"] == "N003"

    def test_returns_expected_keys(self, tmp_path):
        append_note(tmp_path, "Test")
        notes = list_notes(tmp_path)
        note = notes[0]
        assert "id" in note
        assert "timestamp" in note
        assert "text" in note
        assert "promoted" in note
        assert note["promoted"] is False


# ── Promote Tests ────────────────────────────────────────────────────────────


class TestPromoteNote:
    def test_promote_creates_task(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        append_note(tmp_path, "Consider batch mode for executor")
        result = promote_note(tmp_path, "N001", db)
        assert result["task_id"] is not None
        assert "batch mode" in result["text"]

    def test_promote_marks_note(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        append_note(tmp_path, "Test idea")
        promote_note(tmp_path, "N001", db)
        notes = list_notes(tmp_path)
        assert notes[0]["promoted"] is True

    def test_promote_invalid_id(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        append_note(tmp_path, "Test")
        with pytest.raises(ValueError, match="not found"):
            promote_note(tmp_path, "N999", db)

    def test_promote_already_promoted(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        append_note(tmp_path, "Test")
        promote_note(tmp_path, "N001", db)
        with pytest.raises(ValueError, match="already promoted"):
            promote_note(tmp_path, "N001", db)

    def test_promote_no_notes_file(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        with pytest.raises(ValueError, match="not found"):
            promote_note(tmp_path, "N001", db)
