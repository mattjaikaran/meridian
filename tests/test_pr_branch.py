#!/usr/bin/env python3
"""Tests for scripts/pr_branch.py — commit filtering and PR branch creation."""

import subprocess

import pytest

from scripts.db import MeridianError
from scripts.pr_branch import create_pr_branch, filter_commits, has_code_changes


def _git(args: list[str], cwd) -> str:
    """Helper to run git commands in test repos."""
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout.strip()


def _init_repo(tmp_path):
    """Create a git repo with an initial commit on main."""
    _git(["init", "-b", "main"], cwd=tmp_path)
    _git(["config", "user.email", "test@test.com"], cwd=tmp_path)
    _git(["config", "user.name", "Test"], cwd=tmp_path)
    # Initial commit so main exists
    (tmp_path / "README.md").write_text("init")
    _git(["add", "README.md"], cwd=tmp_path)
    _git(["commit", "-m", "initial"], cwd=tmp_path)


def _make_commit(tmp_path, files: dict[str, str], message: str) -> str:
    """Create files and commit them. Returns the commit SHA."""
    for path, content in files.items():
        fpath = tmp_path / path
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content)
        _git(["add", str(path)], cwd=tmp_path)
    _git(["commit", "-m", message], cwd=tmp_path)
    return _git(["rev-parse", "HEAD"], cwd=tmp_path)


# -- has_code_changes tests ---------------------------------------------------


class TestHasCodeChanges:
    def test_code_only_commit(self, tmp_path):
        _init_repo(tmp_path)
        sha = _make_commit(tmp_path, {"src/main.py": "print('hi')"}, "code")
        assert has_code_changes(sha, cwd=tmp_path) is True

    def test_planning_only_commit(self, tmp_path):
        _init_repo(tmp_path)
        sha = _make_commit(
            tmp_path, {".planning/notes.md": "# notes"}, "planning"
        )
        assert has_code_changes(sha, cwd=tmp_path) is False

    def test_meridian_only_commit(self, tmp_path):
        _init_repo(tmp_path)
        sha = _make_commit(
            tmp_path, {".meridian/state.db": "data"}, "meridian"
        )
        assert has_code_changes(sha, cwd=tmp_path) is False

    def test_mixed_commit(self, tmp_path):
        _init_repo(tmp_path)
        sha = _make_commit(
            tmp_path,
            {"src/app.py": "code", ".planning/plan.md": "plan"},
            "mixed",
        )
        assert has_code_changes(sha, cwd=tmp_path) is True

    def test_planning_and_meridian_only(self, tmp_path):
        _init_repo(tmp_path)
        sha = _make_commit(
            tmp_path,
            {".planning/a.md": "a", ".meridian/b.db": "b"},
            "both planning",
        )
        assert has_code_changes(sha, cwd=tmp_path) is False


# -- filter_commits tests -----------------------------------------------------


class TestFilterCommits:
    def test_filters_planning_only(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/test"], cwd=tmp_path)
        _make_commit(tmp_path, {".planning/plan.md": "plan"}, "planning only")
        sha_code = _make_commit(tmp_path, {"src/main.py": "code"}, "code")
        result = filter_commits("main", cwd=tmp_path)
        assert result == [sha_code]

    def test_returns_empty_for_all_planning(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/docs"], cwd=tmp_path)
        _make_commit(tmp_path, {".planning/a.md": "a"}, "planning 1")
        _make_commit(tmp_path, {".meridian/b.md": "b"}, "planning 2")
        result = filter_commits("main", cwd=tmp_path)
        assert result == []

    def test_preserves_chronological_order(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/multi"], cwd=tmp_path)
        sha1 = _make_commit(tmp_path, {"a.py": "a"}, "first code")
        _make_commit(tmp_path, {".planning/x.md": "x"}, "planning")
        sha2 = _make_commit(tmp_path, {"b.py": "b"}, "second code")
        result = filter_commits("main", cwd=tmp_path)
        assert result == [sha1, sha2]

    def test_empty_when_no_commits(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/empty"], cwd=tmp_path)
        result = filter_commits("main", cwd=tmp_path)
        assert result == []


# -- create_pr_branch tests ---------------------------------------------------


class TestCreatePrBranch:
    def test_creates_branch_with_code_commits(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/stuff"], cwd=tmp_path)
        _make_commit(tmp_path, {".planning/plan.md": "plan"}, "planning")
        _make_commit(tmp_path, {"src/main.py": "code"}, "real code")

        branch = create_pr_branch("stuff", "main", cwd=tmp_path)
        assert branch == "pr/stuff"

        # Verify we're back on original branch
        current = _git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=tmp_path)
        assert current == "feature/stuff"

        # Verify pr branch exists and has the code commit
        log = _git(["log", "--oneline", "pr/stuff"], cwd=tmp_path)
        assert "real code" in log
        assert "planning" not in log

    def test_raises_when_all_planning(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/docs"], cwd=tmp_path)
        _make_commit(tmp_path, {".planning/a.md": "a"}, "planning only")

        with pytest.raises(MeridianError, match="planning-only"):
            create_pr_branch("docs", "main", cwd=tmp_path)

    def test_multiple_code_commits(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/multi"], cwd=tmp_path)
        _make_commit(tmp_path, {"a.py": "a"}, "first code")
        _make_commit(tmp_path, {"b.py": "b"}, "second code")
        _make_commit(tmp_path, {".planning/x.md": "x"}, "planning")

        branch = create_pr_branch("multi", "main", cwd=tmp_path)
        assert branch == "pr/multi"

        log = _git(["log", "--oneline", "pr/multi"], cwd=tmp_path)
        assert "first code" in log
        assert "second code" in log
        assert "planning" not in log

    def test_single_code_commit(self, tmp_path):
        _init_repo(tmp_path)
        _git(["checkout", "-b", "feature/single"], cwd=tmp_path)
        _make_commit(tmp_path, {"app.py": "code"}, "one commit")

        branch = create_pr_branch("single", "main", cwd=tmp_path)
        assert branch == "pr/single"
