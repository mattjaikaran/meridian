#!/usr/bin/env python3
"""Tests for execution learning system (scripts/learnings.py)."""

import pytest

from scripts.learnings import (
    add_learning,
    delete_learning,
    find_similar,
    get_learning,
    get_learnings_for_prompt,
    increment_applied,
    jaccard_similarity,
    list_learnings,
    prune_stale,
)
from scripts.state import create_project


@pytest.fixture
def pdb(db):
    """DB fixture with a default project (needed for FK on learning table)."""
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── CRUD Tests ────────────────────────────────────────────────────────────────


class TestAddLearning:
    def test_add_basic(self, pdb):
        result = add_learning(pdb, "Always run migrations before seeding")
        assert result["id"] is not None
        assert result["rule"] == "Always run migrations before seeding"
        assert result["scope"] == "project"
        assert result["source"] == "manual"
        assert result["applied_count"] == 0

    def test_add_with_scope_and_source(self, pdb):
        result = add_learning(pdb, "Use UTC everywhere", scope="global", source="review")
        assert result["scope"] == "global"
        assert result["source"] == "review"

    def test_add_with_phase(self, seeded_db):
        result = add_learning(seeded_db, "Phase-specific rule", scope="phase",
                              source="execution", phase_id=1)
        assert result["phase_id"] == 1
        assert result["scope"] == "phase"

    def test_add_empty_rule_raises(self, pdb):
        with pytest.raises(ValueError, match="empty"):
            add_learning(pdb, "")

    def test_add_whitespace_only_raises(self, pdb):
        with pytest.raises(ValueError, match="empty"):
            add_learning(pdb, "   ")

    def test_add_invalid_scope_raises(self, pdb):
        with pytest.raises(ValueError, match="Invalid scope"):
            add_learning(pdb, "some rule", scope="invalid")

    def test_add_invalid_source_raises(self, pdb):
        with pytest.raises(ValueError, match="Invalid source"):
            add_learning(pdb, "some rule", source="invalid")

    def test_add_strips_whitespace(self, pdb):
        result = add_learning(pdb, "  rule with spaces  ")
        assert result["rule"] == "rule with spaces"


class TestGetLearning:
    def test_get_existing(self, pdb):
        created = add_learning(pdb, "test rule")
        fetched = get_learning(pdb, created["id"])
        assert fetched is not None
        assert fetched["rule"] == "test rule"

    def test_get_nonexistent(self, pdb):
        assert get_learning(pdb, 999) is None


class TestListLearnings:
    def test_list_empty(self, pdb):
        assert list_learnings(pdb) == []

    def test_list_all(self, pdb):
        add_learning(pdb, "rule 1")
        add_learning(pdb, "rule 2")
        add_learning(pdb, "rule 3")
        result = list_learnings(pdb)
        assert len(result) == 3

    def test_list_filter_by_scope(self, pdb):
        add_learning(pdb, "global rule", scope="global")
        add_learning(pdb, "project rule", scope="project")
        result = list_learnings(pdb, scope="global")
        assert len(result) == 1
        assert result[0]["scope"] == "global"

    def test_list_filter_by_source(self, pdb):
        add_learning(pdb, "manual rule", source="manual")
        add_learning(pdb, "review rule", source="review")
        result = list_learnings(pdb, source="review")
        assert len(result) == 1
        assert result[0]["source"] == "review"

    def test_list_respects_limit(self, pdb):
        for i in range(10):
            add_learning(pdb, f"rule {i}")
        result = list_learnings(pdb, limit=3)
        assert len(result) == 3

    def test_list_ordered_by_created_desc(self, pdb):
        add_learning(pdb, "first")
        add_learning(pdb, "second")
        add_learning(pdb, "third")
        result = list_learnings(pdb)
        assert result[0]["rule"] == "third"
        assert result[2]["rule"] == "first"


class TestDeleteLearning:
    def test_delete_existing(self, pdb):
        created = add_learning(pdb, "to delete")
        assert delete_learning(pdb, created["id"]) is True
        assert get_learning(pdb, created["id"]) is None

    def test_delete_nonexistent(self, pdb):
        assert delete_learning(pdb, 999) is False


class TestIncrementApplied:
    def test_increment(self, pdb):
        created = add_learning(pdb, "test rule")
        assert created["applied_count"] == 0
        increment_applied(pdb, created["id"])
        updated = get_learning(pdb, created["id"])
        assert updated["applied_count"] == 1

    def test_increment_multiple(self, pdb):
        created = add_learning(pdb, "test rule")
        for _ in range(5):
            increment_applied(pdb, created["id"])
        updated = get_learning(pdb, created["id"])
        assert updated["applied_count"] == 5


# ── Deduplication Tests ───────────────────────────────────────────────────────


class TestJaccardSimilarity:
    def test_identical(self):
        assert jaccard_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert jaccard_similarity("hello world", "foo bar") == 0.0

    def test_partial_overlap(self):
        score = jaccard_similarity("always run migrations", "always run tests")
        assert 0.3 < score < 0.7

    def test_empty_string(self):
        assert jaccard_similarity("", "hello") == 0.0
        assert jaccard_similarity("hello", "") == 0.0
        assert jaccard_similarity("", "") == 0.0

    def test_case_insensitive(self):
        assert jaccard_similarity("Hello World", "hello world") == 1.0

    def test_ignores_punctuation(self):
        assert jaccard_similarity("hello, world!", "hello world") == 1.0


class TestFindSimilar:
    def test_finds_similar(self, pdb):
        add_learning(pdb, "always run database migrations before seeding test data")
        match = find_similar(pdb, "always run database migrations before seeding the data")
        assert match is not None
        assert match["similarity"] >= 0.7

    def test_no_match_below_threshold(self, pdb):
        add_learning(pdb, "use UTC for all timestamps")
        match = find_similar(pdb, "always run migrations before seeding")
        assert match is None

    def test_returns_best_match(self, pdb):
        add_learning(pdb, "run tests first")
        add_learning(pdb, "always run tests before committing code")
        match = find_similar(pdb, "always run tests before committing changes")
        assert match is not None
        assert "always run tests" in match["rule"]

    def test_empty_db(self, pdb):
        assert find_similar(pdb, "any rule") is None

    def test_custom_threshold(self, pdb):
        add_learning(pdb, "run tests before committing")
        # With low threshold, even weak matches should be found
        match = find_similar(pdb, "run linter before committing", threshold=0.3)
        assert match is not None


# ── Prompt Injection Tests ────────────────────────────────────────────────────


class TestGetLearningsForPrompt:
    def test_empty_returns_empty_string(self, pdb):
        assert get_learnings_for_prompt(pdb) == ""

    def test_basic_format(self, pdb):
        add_learning(pdb, "Always validate input", scope="project", source="manual")
        prompt = get_learnings_for_prompt(pdb)
        assert "## Learnings from Prior Execution" in prompt
        assert "[project]" in prompt
        assert "(manual)" in prompt
        assert "Always validate input" in prompt

    def test_includes_global_and_project(self, pdb):
        add_learning(pdb, "Global rule", scope="global")
        add_learning(pdb, "Project rule", scope="project")
        prompt = get_learnings_for_prompt(pdb)
        assert "Global rule" in prompt
        assert "Project rule" in prompt

    def test_includes_phase_specific(self, seeded_db):
        add_learning(seeded_db, "Phase rule", scope="phase", phase_id=1)
        add_learning(seeded_db, "Project rule", scope="project")
        prompt = get_learnings_for_prompt(seeded_db, phase_id=1)
        assert "Phase rule" in prompt
        assert "Project rule" in prompt

    def test_excludes_other_phase(self, seeded_db):
        add_learning(seeded_db, "Phase 1 rule", scope="phase", phase_id=1)
        add_learning(seeded_db, "Phase 2 rule", scope="phase", phase_id=2)
        prompt = get_learnings_for_prompt(seeded_db, phase_id=1)
        assert "Phase 1 rule" in prompt
        assert "Phase 2 rule" not in prompt

    def test_increments_applied_count(self, pdb):
        created = add_learning(pdb, "test rule")
        get_learnings_for_prompt(pdb)
        updated = get_learning(pdb, created["id"])
        assert updated["applied_count"] == 1

    def test_respects_limit(self, pdb):
        for i in range(10):
            add_learning(pdb, f"rule number {i}")
        prompt = get_learnings_for_prompt(pdb, limit=3)
        # Should only have 3 rules in the output
        lines = [line for line in prompt.split("\n") if line.startswith("- ")]
        assert len(lines) == 3

    def test_prioritizes_least_applied(self, pdb):
        r1 = add_learning(pdb, "frequently used rule")
        add_learning(pdb, "never used rule")
        # Apply r1 many times
        for _ in range(10):
            increment_applied(pdb, r1["id"])
        prompt = get_learnings_for_prompt(pdb, limit=1)
        assert "never used rule" in prompt


# ── Pruning Tests ─────────────────────────────────────────────────────────────


class TestPruneStale:
    def test_prune_removes_old_unused(self, pdb):
        # Insert a learning with old timestamp
        pdb.execute(
            """INSERT INTO learning (project_id, scope, rule, source, created_at, applied_count)
               VALUES ('default', 'project', 'old rule', 'manual',
                       datetime('now', '-100 days'), 0)"""
        )
        pdb.commit()
        count = prune_stale(pdb, older_than_days=90)
        assert count == 1

    def test_prune_keeps_recent(self, pdb):
        add_learning(pdb, "recent rule")
        count = prune_stale(pdb, older_than_days=90)
        assert count == 0

    def test_prune_keeps_applied(self, pdb):
        # Old but applied learning should survive
        pdb.execute(
            """INSERT INTO learning (project_id, scope, rule, source, created_at, applied_count)
               VALUES ('default', 'project', 'applied rule', 'manual',
                       datetime('now', '-100 days'), 5)"""
        )
        pdb.commit()
        count = prune_stale(pdb, min_applied=0, older_than_days=90)
        assert count == 0

    def test_prune_empty_db(self, pdb):
        assert prune_stale(pdb) == 0
