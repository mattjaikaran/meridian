#!/usr/bin/env python3
"""Tests for scripts/stats.py — project statistics engine."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.stats import (
    _bar,
    _phase_plan_counts,
    _milestone_summary,
    _test_count,
    _timeline,
    compute_stats,
    format_stats,
)
from scripts.state import (
    create_phase,
    create_plan,
    list_phases,
    transition_phase,
    transition_plan,
)


# ── _bar ─────────────────────────────────────────────────────────────────────


class TestBar:
    def test_empty(self):
        assert _bar(0, 0) == "[░░░░░░░░░░]"

    def test_full(self):
        assert _bar(10, 10) == "[██████████]"

    def test_half(self):
        result = _bar(5, 10)
        assert result == "[█████░░░░░]"

    def test_partial(self):
        result = _bar(3, 10)
        assert "[" in result and "]" in result


# ── _phase_plan_counts ────────────────────────────────────────────────────────


class TestPhasePlanCounts:
    def test_empty_db(self, seeded_db):
        result = _phase_plan_counts(seeded_db, "default")
        assert result["total_phases"] == 2
        assert result["done_phases"] == 0
        assert result["total_plans"] == 0
        assert result["plan_pct"] == 0

    def test_with_completed_phase(self, seeded_db):
        phases = list_phases(seeded_db, "v1.0")
        p = create_plan(seeded_db, phases[0]["id"], "Plan A", "Do A")
        transition_plan(seeded_db, p["id"], "executing")
        transition_plan(seeded_db, p["id"], "complete", commit_sha="abc")
        ph_id = phases[0]["id"]
        for st in ("context_gathered", "planned_out", "executing", "verifying", "reviewing", "complete"):
            transition_phase(seeded_db, ph_id, st)

        result = _phase_plan_counts(seeded_db, "default")
        assert result["done_phases"] == 1
        assert result["done_plans"] == 1
        assert result["phase_pct"] == 50
        assert result["plan_pct"] == 100

    def test_pct_zero_when_no_plans(self, seeded_db):
        result = _phase_plan_counts(seeded_db, "default")
        assert result["plan_pct"] == 0

    def test_skipped_plans_count_as_done(self, seeded_db):
        phases = list_phases(seeded_db, "v1.0")
        p = create_plan(seeded_db, phases[0]["id"], "Plan skip", "Skip me")
        transition_plan(seeded_db, p["id"], "skipped")

        result = _phase_plan_counts(seeded_db, "default")
        assert result["done_plans"] == 1


# ── _milestone_summary ───────────────────────────────────────────────────────


class TestMilestoneSummary:
    def test_returns_list(self, seeded_db):
        result = _milestone_summary(seeded_db, "default")
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["milestone_id"] == "v1.0"

    def test_phase_count(self, seeded_db):
        result = _milestone_summary(seeded_db, "default")
        assert result[0]["phase_count"] == 2

    def test_done_phases(self, seeded_db):
        phases = list_phases(seeded_db, "v1.0")
        ph_id = phases[0]["id"]
        for st in ("context_gathered", "planned_out", "executing", "verifying", "reviewing", "complete"):
            transition_phase(seeded_db, ph_id, st)

        result = _milestone_summary(seeded_db, "default")
        assert result[0]["done_phases"] == 1


# ── _test_count ───────────────────────────────────────────────────────────────


class TestTestCount:
    def test_no_tests_dir(self, tmp_path):
        result = _test_count(tmp_path)
        assert result["test_files"] == 0
        assert result["test_functions"] == 0

    def test_counts_test_files(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_foo.py").write_text(
            "def test_alpha():\n    pass\n\ndef test_beta():\n    pass\n"
        )
        (tests_dir / "test_bar.py").write_text("def test_gamma():\n    pass\n")

        result = _test_count(tmp_path)
        assert result["test_files"] == 2
        assert result["test_functions"] == 3

    def test_ignores_non_test_files(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "helpers.py").write_text("def helper(): pass\n")

        result = _test_count(tmp_path)
        assert result["test_files"] == 0


# ── _timeline ─────────────────────────────────────────────────────────────────


class TestTimeline:
    def test_none_input(self):
        result = _timeline(None)
        assert result["project_age_days"] is None
        assert result["started"] is None

    def test_valid_date(self):
        result = _timeline("2020-01-01")
        assert result["started"] == "2020-01-01"
        assert isinstance(result["project_age_days"], int)
        assert result["project_age_days"] > 0

    def test_invalid_date(self):
        result = _timeline("not-a-date")
        assert result["started"] == "not-a-date"
        assert result["project_age_days"] is None


# ── compute_stats ─────────────────────────────────────────────────────────────


class TestComputeStats:
    def test_returns_expected_keys(self, seeded_db, tmp_path):
        result = compute_stats(seeded_db, tmp_path)
        assert "phases" in result
        assert "milestones" in result
        assert "git" in result
        assert "tests" in result
        assert "velocity" in result
        assert "timeline" in result

    def test_no_git_repo(self, seeded_db, tmp_path):
        result = compute_stats(seeded_db, tmp_path)
        # Should not raise even if git is not available in tmp_path
        assert result["git"]["commit_count"] == 0

    def test_phases_structure(self, seeded_db, tmp_path):
        counts = compute_stats(seeded_db, tmp_path)["phases"]
        assert counts["total_phases"] == 2
        assert counts["done_phases"] == 0


# ── format_stats ──────────────────────────────────────────────────────────────


class TestFormatStats:
    def _minimal_data(self):
        return {
            "phases": {
                "total_phases": 4,
                "done_phases": 2,
                "phase_pct": 50,
                "total_plans": 10,
                "done_plans": 7,
                "plan_pct": 70,
            },
            "milestones": [
                {
                    "milestone_id": "v1.0",
                    "name": "Version 1.0",
                    "status": "complete",
                    "phase_count": 4,
                    "done_phases": 4,
                }
            ],
            "git": {
                "commit_count": 42,
                "first_commit_date": "2024-01-01",
                "last_commit_date": "2024-06-01",
                "total_insertions": 5000,
                "total_deletions": 1200,
                "files_tracked": 38,
            },
            "tests": {"test_files": 12, "test_functions": 150},
            "velocity": {"velocity": 0.71, "completed_count": 5, "window_days": 7},
            "timeline": {"project_age_days": 180, "started": "2024-01-01"},
        }

    def test_header_present(self):
        out = format_stats(self._minimal_data())
        assert "## Project Statistics" in out

    def test_phase_bar_present(self):
        out = format_stats(self._minimal_data())
        assert "Phases" in out
        assert "2/4" in out

    def test_plan_bar_present(self):
        out = format_stats(self._minimal_data())
        assert "7/10" in out

    def test_git_section(self):
        out = format_stats(self._minimal_data())
        assert "42" in out  # commit count
        assert "+5000" in out

    def test_test_section(self):
        out = format_stats(self._minimal_data())
        assert "150" in out

    def test_velocity_section(self):
        out = format_stats(self._minimal_data())
        assert "0.71" in out

    def test_timeline_section(self):
        out = format_stats(self._minimal_data())
        assert "180 days" in out

    def test_no_git_data(self):
        data = self._minimal_data()
        data["git"]["commit_count"] = 0
        out = format_stats(data)
        # Git section should be absent when no commits
        assert "Commits" not in out

    def test_no_test_data(self):
        data = self._minimal_data()
        data["tests"]["test_files"] = 0
        out = format_stats(data)
        assert "Test files" not in out
