"""Tests for the Meridian thread system."""

import pytest

from scripts.threads import (
    _sanitize_slug,
    close_thread,
    create_thread,
    get_thread,
    list_threads,
    promote_to_backlog,
    reopen_thread,
    update_thread_body,
)
from scripts.state import create_project


# ── Slug sanitization ─────────────────────────────────────────────────────────


class TestSanitizeSlug:
    def test_simple_title(self):
        assert _sanitize_slug("Auth refactor") == "auth-refactor"

    def test_special_chars_stripped(self):
        assert _sanitize_slug("Fix bug #123!") == "fix-bug-123"

    def test_multiple_spaces_collapsed(self):
        assert _sanitize_slug("a  b   c") == "a-b-c"

    def test_leading_trailing_hyphens_removed(self):
        assert _sanitize_slug("  !!hello!!  ") == "hello"

    def test_truncated_to_60_chars(self):
        long = "a" * 80
        result = _sanitize_slug(long)
        assert len(result) <= 60

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot derive"):
            _sanitize_slug("!!!")

    def test_unicode_stripped(self):
        result = _sanitize_slug("résumé work")
        assert result == "rsum-work"


# ── Create ────────────────────────────────────────────────────────────────────


class TestCreateThread:
    def test_creates_open_thread(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        t = create_thread(db, "Auth design", "Some ideas here")
        assert t["slug"] == "auth-design"
        assert t["status"] == "open"
        assert t["body"] == "Some ideas here"

    def test_explicit_slug(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        t = create_thread(db, "Title", "Body", slug="custom-slug")
        assert t["slug"] == "custom-slug"

    def test_duplicate_slug_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Auth design", "First")
        with pytest.raises(Exception):
            create_thread(db, "Auth design", "Second")

    def test_has_timestamps(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        t = create_thread(db, "Timestamps test", "body")
        assert t["created_at"] is not None
        assert t["updated_at"] is not None

    def test_default_project_id(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        t = create_thread(db, "Default project", "body")
        assert t["project_id"] == "default"


# ── Get ───────────────────────────────────────────────────────────────────────


class TestGetThread:
    def test_returns_none_for_missing(self, db):
        assert get_thread(db, "nonexistent") is None

    def test_returns_thread_dict(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Found it", "body text")
        t = get_thread(db, "found-it")
        assert t is not None
        assert t["slug"] == "found-it"
        assert t["body"] == "body text"


# ── List ──────────────────────────────────────────────────────────────────────


class TestListThreads:
    def test_empty_list(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        assert list_threads(db) == []

    def test_lists_all_threads(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "First thread", "body")
        create_thread(db, "Second thread", "body")
        threads = list_threads(db)
        assert len(threads) == 2

    def test_filter_open(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Open thread", "body")
        t2 = create_thread(db, "Will close", "body")
        close_thread(db, t2["slug"])
        open_threads = list_threads(db, status="open")
        assert len(open_threads) == 1
        assert open_threads[0]["slug"] == "open-thread"

    def test_filter_resolved(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Keep open", "body")
        t2 = create_thread(db, "Will close", "body")
        close_thread(db, t2["slug"])
        resolved = list_threads(db, status="resolved")
        assert len(resolved) == 1
        assert resolved[0]["slug"] == "will-close"

    def test_invalid_status_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        with pytest.raises(ValueError, match="Invalid status filter"):
            list_threads(db, status="invalid")

    def test_newest_first(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Older thread", "body")
        create_thread(db, "Newer thread", "body")
        threads = list_threads(db)
        assert threads[0]["slug"] == "newer-thread"


# ── Close ─────────────────────────────────────────────────────────────────────


class TestCloseThread:
    def test_closes_open_thread(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Will close", "body")
        t = close_thread(db, "will-close")
        assert t["status"] == "resolved"

    def test_close_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            close_thread(db, "ghost")

    def test_close_already_resolved_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Double close", "body")
        close_thread(db, "double-close")
        with pytest.raises(ValueError, match="already resolved"):
            close_thread(db, "double-close")


# ── Reopen ────────────────────────────────────────────────────────────────────


class TestReopenThread:
    def test_reopens_resolved_thread(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Reopen me", "body")
        close_thread(db, "reopen-me")
        t = reopen_thread(db, "reopen-me")
        assert t["status"] == "open"

    def test_reopen_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            reopen_thread(db, "ghost")

    def test_reopen_already_open_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Already open", "body")
        with pytest.raises(ValueError, match="already open"):
            reopen_thread(db, "already-open")


# ── Update body ───────────────────────────────────────────────────────────────


class TestUpdateThreadBody:
    def test_updates_body(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Updatable", "original body")
        t = update_thread_body(db, "updatable", "new body")
        assert t["body"] == "new body"

    def test_update_nonexistent_raises(self, db):
        with pytest.raises(ValueError, match="not found"):
            update_thread_body(db, "ghost", "body")

    def test_updates_updated_at(self, db):
        create_project(db, name="Test", repo_path="/tmp/t")
        create_thread(db, "Timestamp check", "body")
        original = get_thread(db, "timestamp-check")
        t = update_thread_body(db, "timestamp-check", "new body")
        assert t["updated_at"] >= original["updated_at"]


# ── Promote to backlog ────────────────────────────────────────────────────────


class TestPromoteToBacklog:
    def test_creates_backlog_file(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_thread(db, "Big idea", "This is the body content")
        result = promote_to_backlog(db, "big-idea", tmp_path)
        backlog_file = tmp_path / ".planning" / "backlog" / "big-idea.md"
        assert backlog_file.exists()
        content = backlog_file.read_text()
        assert "Thread: big-idea" in content
        assert "This is the body content" in content

    def test_closes_thread_after_promote(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_thread(db, "Promote close", "body")
        promote_to_backlog(db, "promote-close", tmp_path)
        t = get_thread(db, "promote-close")
        assert t["status"] == "resolved"

    def test_returns_file_path(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        create_thread(db, "Return path", "body")
        result = promote_to_backlog(db, "return-path", tmp_path)
        assert "file" in result
        assert "return-path.md" in result["file"]

    def test_promote_nonexistent_raises(self, db, tmp_path):
        create_project(db, name="Test", repo_path=str(tmp_path))
        with pytest.raises(ValueError, match="not found"):
            promote_to_backlog(db, "ghost", tmp_path)
