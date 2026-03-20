#!/usr/bin/env python3
"""Tests for edit scope lock (scripts/freeze.py)."""

import os

import pytest

from scripts.freeze import (
    check_freeze,
    clear_freeze,
    format_freeze_status,
    get_freeze,
    is_path_allowed,
    set_freeze,
)
from scripts.state import create_project


@pytest.fixture
def pdb(db):
    """DB with default project for settings table FK."""
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── Set/Get/Clear Tests ──────────────────────────────────────────────────────


class TestSetFreeze:
    def test_set_basic(self, pdb):
        result = set_freeze(pdb, "/tmp/project/src/auth")
        assert result["active"] is True
        assert result["frozen_directory"] == "/tmp/project/src/auth"

    def test_set_stores_absolute(self, pdb):
        set_freeze(pdb, "src/auth")
        frozen = get_freeze(pdb)
        assert os.path.isabs(frozen)

    def test_set_empty_raises(self, pdb):
        with pytest.raises(ValueError, match="empty"):
            set_freeze(pdb, "")

    def test_set_whitespace_raises(self, pdb):
        with pytest.raises(ValueError, match="empty"):
            set_freeze(pdb, "   ")

    def test_set_overwrites_previous(self, pdb):
        set_freeze(pdb, "/tmp/a")
        set_freeze(pdb, "/tmp/b")
        assert get_freeze(pdb) == "/tmp/b"


class TestGetFreeze:
    def test_get_none_when_not_set(self, pdb):
        assert get_freeze(pdb) is None

    def test_get_after_set(self, pdb):
        set_freeze(pdb, "/tmp/project/src")
        assert get_freeze(pdb) == "/tmp/project/src"


class TestClearFreeze:
    def test_clear_active(self, pdb):
        set_freeze(pdb, "/tmp/project/src")
        assert clear_freeze(pdb) is True
        assert get_freeze(pdb) is None

    def test_clear_when_none(self, pdb):
        assert clear_freeze(pdb) is False


# ── Path Checking Tests ──────────────────────────────────────────────────────


class TestIsPathAllowed:
    def test_file_inside_dir(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/src/main.py") is True

    def test_file_outside_dir(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/tests/test.py") is False

    def test_file_in_nested_subdir(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/src/auth/login.py") is True

    def test_sibling_directory(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/src2/file.py") is False

    def test_parent_directory(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/file.py") is False

    def test_exact_match(self):
        assert is_path_allowed("/tmp/project/src", "/tmp/project/src") is True

    def test_prefix_attack(self):
        """Ensure /src doesn't match /src-backup."""
        assert is_path_allowed("/tmp/src", "/tmp/src-backup/file.py") is False

    def test_trailing_slash(self):
        assert is_path_allowed("/tmp/project/src/", "/tmp/project/src/main.py") is True


# ── Integration Tests ─────────────────────────────────────────────────────────


class TestCheckFreeze:
    def test_no_freeze_always_allowed(self, pdb):
        result = check_freeze(pdb, "/any/file.py")
        assert result["allowed"] is True
        assert result["frozen_directory"] is None

    def test_file_inside_frozen(self, pdb):
        set_freeze(pdb, "/tmp/project/src")
        result = check_freeze(pdb, "/tmp/project/src/main.py")
        assert result["allowed"] is True

    def test_file_outside_frozen(self, pdb):
        set_freeze(pdb, "/tmp/project/src")
        result = check_freeze(pdb, "/tmp/project/tests/test.py")
        assert result["allowed"] is False
        assert result["frozen_directory"] == "/tmp/project/src"


class TestFormatFreezeStatus:
    def test_no_freeze(self, pdb):
        assert format_freeze_status(pdb) == "Edit lock: none"

    def test_active_freeze(self, pdb):
        set_freeze(pdb, "/tmp/project/src")
        status = format_freeze_status(pdb)
        assert "active" in status
        assert "/tmp/project/src" in status
