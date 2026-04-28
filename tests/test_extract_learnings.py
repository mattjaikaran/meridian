#!/usr/bin/env python3
"""Tests for structured learning extraction (scripts/extract_learnings.py)."""

import json
from pathlib import Path

import pytest

from scripts.extract_learnings import (
    _dedup,
    _extract_matches,
    _extract_section_bullets,
    _extract_yaml_list,
    _YAML_DECISION_RE,
    _YAML_PATTERNS_RE,
    check_extraction_pending,
    extract_from_phase_dir,
    find_phases_without_learnings,
    save_extracted_to_db,
    write_learnings_md,
    _DECISION_RES,
    _PATTERN_RES,
)
from scripts.state import create_project


@pytest.fixture
def pdb(db):
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── Utility helpers ────────────────────────────────────────────────────────────


class TestDedup:
    def test_removes_duplicates_by_prefix(self):
        items = ["Do not mock the database", "Do not mock the database again", "Use real fixtures"]
        result = _dedup(items)
        assert len(result) == 2

    def test_enforces_min_len(self):
        items = ["short", "this is long enough to count"]
        result = _dedup(items, min_len=20)
        assert result == ["this is long enough to count"]

    def test_caps_at_limit(self):
        items = [f"Learning number {i} is important" for i in range(20)]
        result = _dedup(items, cap=5)
        assert len(result) == 5


class TestExtractYamlList:
    def test_extracts_key_decisions(self):
        content = "key-decisions:\n  - \"Use open_project for all DB access\"\n  - \"Retry on busy\"\n"
        result = _extract_yaml_list(content, _YAML_DECISION_RE)
        assert "Use open_project for all DB access" in result
        assert "Retry on busy" in result

    def test_extracts_patterns(self):
        content = "patterns-established:\n  - \"Always use context managers\"\n"
        result = _extract_yaml_list(content, _YAML_PATTERNS_RE)
        assert "Always use context managers" in result

    def test_returns_empty_on_no_match(self):
        content = "no-relevant-keys:\n  - something\n"
        assert _extract_yaml_list(content, _YAML_DECISION_RE) == []


class TestExtractSectionBullets:
    def test_extracts_bullets_after_header(self):
        content = "## Decisions Made\n\n- Kept connect() alias\n- Use WAL mode\n"
        result = _extract_section_bullets(content, "Decisions Made")
        assert "Kept connect() alias" in result
        assert "Use WAL mode" in result

    def test_returns_empty_when_section_missing(self):
        content = "## Other Section\n- bullet\n"
        assert _extract_section_bullets(content, "Decisions Made") == []

    def test_handles_multiple_level_headers(self):
        content = "### Decisions Made\n- Use open_project context manager\n- Retry on busy writes\n"
        result = _extract_section_bullets(content, "Decisions Made")
        assert "Use open_project context manager" in result


# ── extract_from_phase_dir ─────────────────────────────────────────────────────


class TestExtractFromPhaseDir:
    def test_empty_dir_returns_empty_lists(self, tmp_path):
        result = extract_from_phase_dir(tmp_path)
        assert result["decisions"] == []
        assert result["patterns"] == []
        assert result["surprises"] == []
        assert result["failures"] == []
        assert result["artifacts_read"] == []

    def test_reads_yaml_frontmatter_decisions(self, tmp_path):
        plan = tmp_path / "01-01-PLAN.md"
        plan.write_text(
            "key-decisions:\n"
            '  - "Use open_project for all DB interactions"\n'
            '  - "Retry on database locked errors"\n'
        )
        result = extract_from_phase_dir(tmp_path)
        assert any("open_project" in d for d in result["decisions"])
        assert "01-01-PLAN.md" in result["artifacts_read"]

    def test_reads_summary_patterns(self, tmp_path):
        summary = tmp_path / "01-01-SUMMARY.md"
        summary.write_text(
            "patterns-established:\n"
            '  - "Always use WAL mode for concurrent access"\n'
        )
        result = extract_from_phase_dir(tmp_path)
        assert any("WAL" in p for p in result["patterns"])

    def test_reads_decisions_prose_section(self, tmp_path):
        md = tmp_path / "01-01-SUMMARY.md"
        md.write_text(
            "## Decisions Made\n\n"
            "- Kept backward-compatible alias to avoid breaking imports\n"
            "- Used shared fixtures for test isolation\n"
        )
        result = extract_from_phase_dir(tmp_path)
        assert any("backward-compatible" in d for d in result["decisions"])

    def test_reads_multiple_artifacts(self, tmp_path):
        (tmp_path / "01-01-PLAN.md").write_text(
            'key-decisions:\n  - "Decision from plan"\n'
        )
        (tmp_path / "01-01-SUMMARY.md").write_text(
            'patterns-established:\n  - "Pattern from summary"\n'
        )
        result = extract_from_phase_dir(tmp_path)
        assert len(result["artifacts_read"]) == 2

    def test_deduplicates_across_artifacts(self, tmp_path):
        identical = "Use open_project for all DB access, always"
        (tmp_path / "01-01-PLAN.md").write_text(f'key-decisions:\n  - "{identical}"\n')
        (tmp_path / "01-01-SUMMARY.md").write_text(f'key-decisions:\n  - "{identical}"\n')
        result = extract_from_phase_dir(tmp_path)
        assert result["decisions"].count(identical) == 1


# ── write_learnings_md ─────────────────────────────────────────────────────────


class TestWriteLearningsMd:
    def test_creates_file(self, tmp_path):
        extraction = {
            "decisions": ["Kept backward-compatible alias for connect()"],
            "patterns": ["Use open_project context manager everywhere"],
            "surprises": ["Renaming connect broke 5 existing imports"],
            "failures": [],
            "artifacts_read": ["01-01-PLAN.md"],
        }
        out = write_learnings_md(tmp_path, extraction)
        assert out.exists()
        assert out.name == "LEARNINGS.md"

    def test_content_includes_sections(self, tmp_path):
        extraction = {
            "decisions": ["Decision A"],
            "patterns": ["Pattern B"],
            "surprises": ["Surprise C"],
            "failures": [],
            "artifacts_read": ["PLAN.md"],
        }
        out = write_learnings_md(tmp_path, extraction)
        content = out.read_text()
        assert "## Decisions" in content
        assert "## Patterns" in content
        assert "## Surprises" in content
        assert "Decision A" in content
        assert "Pattern B" in content

    def test_empty_section_shows_none_detected(self, tmp_path):
        extraction = {
            "decisions": [],
            "patterns": [],
            "surprises": [],
            "failures": [],
            "artifacts_read": [],
        }
        out = write_learnings_md(tmp_path, extraction)
        assert "_None detected_" in out.read_text()

    def test_overwrites_existing(self, tmp_path):
        extraction = {"decisions": ["First decision from old extraction"], "patterns": [], "surprises": [], "failures": [], "artifacts_read": []}
        write_learnings_md(tmp_path, extraction)
        extraction["decisions"] = ["Second decision overwrites previous"]
        out = write_learnings_md(tmp_path, extraction)
        content = out.read_text()
        assert "Second decision overwrites previous" in content
        assert "First decision from old extraction" not in content


# ── save_extracted_to_db ───────────────────────────────────────────────────────


class TestSaveExtractedToDb:
    def test_saves_all_categories(self, pdb):
        extraction = {
            "decisions": ["Decision: use open_project for all DB access"],
            "patterns": ["Pattern: always retry on locked writes"],
            "surprises": ["Surprise: connect alias breaks on rename"],
            "failures": [],
        }
        saved = save_extracted_to_db(pdb, extraction)
        assert len(saved) == 3
        categories = {r["category"] for r in saved}
        assert "decision" in categories
        assert "pattern" in categories
        assert "surprise" in categories

    def test_sets_source_execution(self, pdb):
        extraction = {
            "decisions": ["Decision: always use WAL mode for SQLite"],
            "patterns": [],
            "surprises": [],
            "failures": [],
        }
        saved = save_extracted_to_db(pdb, extraction)
        assert saved[0]["source"] == "execution"

    def test_skips_duplicates(self, pdb):
        extraction = {
            "decisions": ["Always use open_project context manager for DB access"],
            "patterns": [],
            "surprises": [],
            "failures": [],
        }
        save_extracted_to_db(pdb, extraction)
        second = save_extracted_to_db(pdb, extraction)
        assert second == []

    def test_auto_creates_stub_project(self, db):
        # db fixture has no project record — ensure_project should handle it
        extraction = {
            "decisions": ["Use context managers for resource cleanup"],
            "patterns": [],
            "surprises": [],
            "failures": [],
        }
        saved = save_extracted_to_db(db, extraction, project_id="auto-stub")
        assert len(saved) == 1

    def test_returns_empty_on_no_items(self, pdb):
        extraction = {"decisions": [], "patterns": [], "surprises": [], "failures": []}
        assert save_extracted_to_db(pdb, extraction) == []


# ── find_phases_without_learnings ─────────────────────────────────────────────


class TestFindPhasesWithoutLearnings:
    def test_returns_empty_when_no_planning_dir(self, tmp_path):
        result = find_phases_without_learnings(tmp_path)
        assert result == []

    def test_returns_dirs_without_learnings(self, tmp_path):
        phases = tmp_path / ".planning" / "phases"
        phase1 = phases / "01-setup"
        phase2 = phases / "02-impl"
        phase1.mkdir(parents=True)
        phase2.mkdir(parents=True)
        (phase1 / "01-01-PLAN.md").write_text("some artifact")
        (phase2 / "02-01-PLAN.md").write_text("some artifact")

        result = find_phases_without_learnings(tmp_path)
        assert len(result) == 2

    def test_excludes_dirs_with_learnings(self, tmp_path):
        phases = tmp_path / ".planning" / "phases"
        phase1 = phases / "01-setup"
        phase1.mkdir(parents=True)
        (phase1 / "01-01-PLAN.md").write_text("artifact")
        (phase1 / "LEARNINGS.md").write_text("already extracted")

        result = find_phases_without_learnings(tmp_path)
        assert result == []

    def test_excludes_empty_dirs(self, tmp_path):
        phases = tmp_path / ".planning" / "phases"
        (phases / "empty-phase").mkdir(parents=True)
        result = find_phases_without_learnings(tmp_path)
        assert result == []


# ── check_extraction_pending ───────────────────────────────────────────────────


class TestCheckExtractionPending:
    def test_no_planning_dir(self, tmp_path):
        status = check_extraction_pending(tmp_path)
        assert status == {"total_phases": 0, "extracted": 0, "pending": []}

    def test_counts_pending_correctly(self, tmp_path):
        phases = tmp_path / ".planning" / "phases"
        for name in ["01-setup", "02-build", "03-test"]:
            d = phases / name
            d.mkdir(parents=True)
            (d / "01-01-PLAN.md").write_text("artifact")  # matches *-PLAN.md glob
        (phases / "01-setup" / "LEARNINGS.md").write_text("extracted")

        status = check_extraction_pending(tmp_path)
        assert status["total_phases"] == 3
        assert status["extracted"] == 1
        assert len(status["pending"]) == 2
