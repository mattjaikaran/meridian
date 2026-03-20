#!/usr/bin/env python3
"""Tests for Meridian debug knowledge base."""

import pytest

from scripts.debug_kb import (
    DebugEntry,
    KB_FILENAME,
    append_debug_entry,
    load_kb,
    search_kb,
)


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory with .meridian/."""
    (tmp_path / ".meridian").mkdir()
    return tmp_path


class TestAppendDebugEntry:
    def test_creates_kb_file(self, project_dir):
        entry = append_debug_entry(
            project_dir,
            title="VALIDATION.md mismatch",
            symptom="Nyquist engine couldn't find any VALIDATION.md files",
            root_cause="Hardcoded VALIDATION.md but real files use NN-VALIDATION.md prefix",
            fix="Added _find_validation_md() glob helper",
            files=["scripts/nyquist.py", "tests/test_nyquist.py"],
        )
        assert entry is not None
        assert entry.entry_id == "DBG-001"
        assert entry.title == "VALIDATION.md mismatch"
        kb_path = project_dir / ".meridian" / KB_FILENAME
        assert kb_path.exists()

    def test_sequential_ids(self, project_dir):
        e1 = append_debug_entry(
            project_dir, "First", "symptom1", "cause1", "fix1",
        )
        e2 = append_debug_entry(
            project_dir, "Second", "symptom2", "cause2", "fix2",
        )
        assert e1.entry_id == "DBG-001"
        assert e2.entry_id == "DBG-002"

    def test_dedup_skips_same_root_cause(self, project_dir):
        e1 = append_debug_entry(
            project_dir, "First", "symptom1", "Hardcoded path", "fix1",
        )
        e2 = append_debug_entry(
            project_dir, "Duplicate", "symptom2", "Hardcoded path", "fix2",
        )
        assert e1 is not None
        assert e2 is None  # duplicate detected

    def test_dedup_case_insensitive(self, project_dir):
        e1 = append_debug_entry(
            project_dir, "First", "symptom1", "Missing import", "fix1",
        )
        e2 = append_debug_entry(
            project_dir, "Second", "symptom2", "missing import", "fix2",
        )
        assert e1 is not None
        assert e2 is None  # same root cause, different case

    def test_creates_meridian_dir(self, tmp_path):
        """Creates .meridian/ if it doesn't exist."""
        entry = append_debug_entry(
            tmp_path, "Title", "symptom", "cause", "fix",
        )
        assert entry is not None
        assert (tmp_path / ".meridian" / KB_FILENAME).exists()

    def test_entry_contains_files(self, project_dir):
        entry = append_debug_entry(
            project_dir, "Title", "symptom", "cause", "fix",
            files=["a.py", "b.py"],
        )
        assert entry.files == ["a.py", "b.py"]


class TestLoadKb:
    def test_empty_kb(self, tmp_path):
        entries = load_kb(tmp_path)
        assert entries == []

    def test_load_single_entry(self, project_dir):
        append_debug_entry(
            project_dir, "Test Entry", "Some symptom", "Some cause", "Some fix",
            files=["test.py"],
        )
        entries = load_kb(project_dir)
        assert len(entries) == 1
        assert entries[0].entry_id == "DBG-001"
        assert entries[0].symptom == "Some symptom"
        assert entries[0].root_cause == "Some cause"
        assert entries[0].fix == "Some fix"
        assert entries[0].files == ["test.py"]

    def test_load_multiple_entries(self, project_dir):
        append_debug_entry(project_dir, "First", "s1", "c1", "f1")
        append_debug_entry(project_dir, "Second", "s2", "c2", "f2")
        append_debug_entry(project_dir, "Third", "s3", "c3", "f3")
        entries = load_kb(project_dir)
        assert len(entries) == 3
        assert entries[0].entry_id == "DBG-001"
        assert entries[2].entry_id == "DBG-003"

    def test_roundtrip_preserves_data(self, project_dir):
        append_debug_entry(
            project_dir,
            title="Import failure",
            symptom="ModuleNotFoundError on startup",
            root_cause="Missing __init__.py in scripts/",
            fix="Added scripts/__init__.py",
            files=["scripts/__init__.py"],
        )
        entries = load_kb(project_dir)
        e = entries[0]
        assert e.title == "Import failure"
        assert e.symptom == "ModuleNotFoundError on startup"
        assert e.root_cause == "Missing __init__.py in scripts/"
        assert e.fix == "Added scripts/__init__.py"


class TestSearchKb:
    def test_search_by_symptom(self, project_dir):
        append_debug_entry(project_dir, "Import bug", "ModuleNotFoundError", "Missing init", "Added init")
        append_debug_entry(project_dir, "Schema bug", "Table not found", "Missing migration", "Added migration")
        results = search_kb(project_dir, "ModuleNotFoundError")
        assert len(results) == 1
        assert results[0].title == "Import bug"

    def test_search_by_root_cause(self, project_dir):
        append_debug_entry(project_dir, "Bug A", "symptom A", "Hardcoded path issue", "fix A")
        append_debug_entry(project_dir, "Bug B", "symptom B", "Missing dependency", "fix B")
        results = search_kb(project_dir, "hardcoded path")
        assert len(results) == 1
        assert results[0].title == "Bug A"

    def test_search_empty_kb(self, tmp_path):
        results = search_kb(tmp_path, "anything")
        assert results == []

    def test_search_no_matches(self, project_dir):
        append_debug_entry(project_dir, "Bug", "symptom", "cause", "fix")
        results = search_kb(project_dir, "zzzznotfound")
        assert results == []

    def test_search_ranks_by_relevance(self, project_dir):
        append_debug_entry(
            project_dir, "Import everywhere",
            "import error in module", "import path wrong", "fixed import",
        )
        append_debug_entry(
            project_dir, "Schema thing",
            "table missing", "schema not applied", "ran migration",
        )
        # "import" appears multiple times in the first entry
        results = search_kb(project_dir, "import error")
        assert len(results) >= 1
        assert results[0].title == "Import everywhere"

    def test_search_empty_query(self, project_dir):
        append_debug_entry(project_dir, "Bug", "symptom", "cause", "fix")
        results = search_kb(project_dir, "")
        assert results == []
