#!/usr/bin/env python3
"""Tests for Meridian fast task execution."""

import pytest

from scripts.fast import (
    COMPLEXITY_THRESHOLD,
    complete_fast_task,
    estimate_complexity,
    execute_fast_task,
)
from scripts.state import create_project


class TestEstimateComplexity:
    def test_trivial_task(self):
        result = estimate_complexity("fix typo in README")
        assert result["is_trivial"] is True
        assert result["score"] < COMPLEXITY_THRESHOLD

    def test_complex_keyword_refactor(self):
        result = estimate_complexity("refactor the entire auth module")
        assert result["is_trivial"] is False
        assert any("refactor" in r for r in result["reasons"])

    def test_complex_keyword_architect(self):
        result = estimate_complexity("architect a new plugin system")
        assert result["is_trivial"] is False
        assert result["score"] >= COMPLEXITY_THRESHOLD

    def test_many_file_references(self):
        result = estimate_complexity("update state.py, db.py, and router.py with new schema")
        assert result["score"] >= 2
        assert any("files" in r.lower() for r in result["reasons"])

    def test_long_description(self):
        long_desc = " ".join(["word"] * 60)
        result = estimate_complexity(long_desc)
        assert any("words" in r.lower() for r in result["reasons"])

    def test_empty_description(self):
        result = estimate_complexity("")
        assert result["is_trivial"] is True
        assert result["score"] == 0

    def test_moderate_description(self):
        desc = " ".join(["update"] * 30)
        result = estimate_complexity(desc)
        assert any("Moderate" in r for r in result["reasons"])

    def test_returns_expected_keys(self):
        result = estimate_complexity("some task")
        assert "score" in result
        assert "reasons" in result
        assert "is_trivial" in result


class TestExecuteFastTask:
    def test_trivial_task_executes(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(db, "fix typo in config")
        assert result["status"] == "executing"
        assert result["task_id"] is not None
        assert "complexity" in result

    def test_complex_task_warns(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(db, "refactor the entire database layer and architect new schema")
        assert result["status"] == "too_complex"
        assert "suggested_command" in result

    def test_complex_task_force(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(
            db, "refactor the entire database layer", force=True
        )
        assert result["status"] == "executing"

    def test_logs_event(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(db, "fix a bug")
        events = db.execute(
            "SELECT * FROM state_event WHERE entity_type = 'quick_task' AND old_status = 'created'"
        ).fetchall()
        assert len(events) >= 1
        assert events[0]["entity_id"] == str(result["task_id"])


class TestCompleteFastTask:
    def test_complete_task(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(db, "fix typo")
        task = complete_fast_task(db, result["task_id"], commit_sha="abc123")
        assert task["status"] == "complete"
        assert task["commit_sha"] == "abc123"

    def test_complete_logs_event(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = execute_fast_task(db, "fix typo")
        complete_fast_task(db, result["task_id"])
        events = db.execute(
            "SELECT * FROM state_event WHERE entity_type = 'quick_task' AND new_status = 'complete'"
        ).fetchall()
        assert len(events) == 1
