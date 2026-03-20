#!/usr/bin/env python3
"""Tests for Meridian discussion audit trail."""

from scripts.discussion import (
    _next_disc_id,
    get_discussions_for_decision,
    load_discussion_log,
    log_discussion,
)


# ── Helper Tests ─────────────────────────────────────────────────────────────


class TestNextDiscId:
    def test_empty_content(self):
        assert _next_disc_id("") == "DISC-001"

    def test_single_entry(self):
        assert _next_disc_id("[DISC-001] test") == "DISC-002"

    def test_multiple_entries(self):
        content = "[DISC-001] a\n[DISC-003] b\n[DISC-002] c"
        assert _next_disc_id(content) == "DISC-004"


# ── Log Discussion Tests ────────────────────────────────────────────────────


class TestLogDiscussion:
    def test_log_creates_file(self, tmp_path):
        result = log_discussion(
            tmp_path,
            topic="Auth approach",
            options=[
                {"name": "JWT", "description": "Stateless tokens"},
                {"name": "Sessions", "description": "Server-side state"},
            ],
            decision="JWT",
            rationale="Need stateless for API-first",
            decision_id="DEC-001",
        )
        assert result["disc_id"] == "DISC-001"
        assert result["topic"] == "Auth approach"
        assert result["decision_id"] == "DEC-001"
        log_file = tmp_path / ".meridian" / "DISCUSSION-LOG.md"
        assert log_file.exists()

    def test_log_content_format(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Database choice",
            options=[
                {"name": "PostgreSQL", "description": "Full-featured RDBMS"},
                {"name": "SQLite", "description": "Embedded, zero-config"},
            ],
            decision="SQLite",
            rationale="Simplicity for local-first tool",
            decision_id="DEC-002",
        )
        content = (tmp_path / ".meridian" / "DISCUSSION-LOG.md").read_text()
        assert "[DISC-001]" in content
        assert "Database choice" in content
        assert "PostgreSQL" in content
        assert "SQLite" in content
        assert "DEC-002" in content

    def test_log_multiple_entries(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="First topic",
            options=[{"name": "A", "description": ""}],
            decision="A",
            rationale="Simple",
            decision_id="DEC-001",
        )
        result = log_discussion(
            tmp_path,
            topic="Second topic",
            options=[{"name": "B", "description": "Option B"}],
            decision="B",
            rationale="Better",
            decision_id="DEC-002",
        )
        assert result["disc_id"] == "DISC-002"

    def test_log_creates_meridian_dir(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Test",
            options=[{"name": "X", "description": ""}],
            decision="X",
            rationale="Because",
            decision_id="DEC-001",
        )
        assert (tmp_path / ".meridian").is_dir()

    def test_append_only(self, tmp_path):
        """Entries are appended, never overwritten."""
        log_discussion(
            tmp_path,
            topic="First",
            options=[{"name": "A", "description": ""}],
            decision="A",
            rationale="First reason",
            decision_id="DEC-001",
        )
        log_discussion(
            tmp_path,
            topic="Second",
            options=[{"name": "B", "description": ""}],
            decision="B",
            rationale="Second reason",
            decision_id="DEC-002",
        )
        content = (tmp_path / ".meridian" / "DISCUSSION-LOG.md").read_text()
        assert "First" in content
        assert "Second" in content
        assert content.index("First") < content.index("Second")


# ── Load Tests ──────────────────────────────────────────────────────────────


class TestLoadDiscussionLog:
    def test_empty_dir(self, tmp_path):
        assert load_discussion_log(tmp_path) == []

    def test_loads_entries(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Auth approach",
            options=[
                {"name": "JWT", "description": "Stateless"},
                {"name": "Sessions", "description": "Stateful"},
            ],
            decision="JWT",
            rationale="API-first",
            decision_id="DEC-001",
        )
        entries = load_discussion_log(tmp_path)
        assert len(entries) == 1
        entry = entries[0]
        assert entry["disc_id"] == "DISC-001"
        assert entry["topic"] == "Auth approach"
        assert entry["decision"] == "JWT"
        assert entry["rationale"] == "API-first"
        assert entry["decision_id"] == "DEC-001"
        assert len(entry["options"]) == 2
        assert entry["options"][0]["name"] == "JWT"

    def test_loads_multiple(self, tmp_path):
        for i in range(3):
            log_discussion(
                tmp_path,
                topic=f"Topic {i}",
                options=[{"name": f"Opt {i}", "description": ""}],
                decision=f"Opt {i}",
                rationale=f"Reason {i}",
                decision_id=f"DEC-{i:03d}",
            )
        entries = load_discussion_log(tmp_path)
        assert len(entries) == 3
        assert entries[0]["disc_id"] == "DISC-001"
        assert entries[2]["disc_id"] == "DISC-003"

    def test_parses_options_with_descriptions(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Test",
            options=[
                {"name": "Alpha", "description": "First option"},
                {"name": "Beta", "description": "Second option"},
            ],
            decision="Alpha",
            rationale="Better fit",
            decision_id="DEC-001",
        )
        entries = load_discussion_log(tmp_path)
        opts = entries[0]["options"]
        assert opts[0]["name"] == "Alpha"
        assert opts[0]["description"] == "First option"
        assert opts[1]["name"] == "Beta"


# ── Query Tests ─────────────────────────────────────────────────────────────


class TestGetDiscussionsForDecision:
    def test_finds_matching_entries(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Auth",
            options=[{"name": "JWT", "description": ""}],
            decision="JWT",
            rationale="Stateless",
            decision_id="DEC-005",
        )
        log_discussion(
            tmp_path,
            topic="DB",
            options=[{"name": "SQLite", "description": ""}],
            decision="SQLite",
            rationale="Simple",
            decision_id="DEC-006",
        )
        results = get_discussions_for_decision(tmp_path, "DEC-005")
        assert len(results) == 1
        assert results[0]["topic"] == "Auth"

    def test_no_matches(self, tmp_path):
        log_discussion(
            tmp_path,
            topic="Test",
            options=[{"name": "X", "description": ""}],
            decision="X",
            rationale="Because",
            decision_id="DEC-001",
        )
        results = get_discussions_for_decision(tmp_path, "DEC-999")
        assert len(results) == 0

    def test_empty_log(self, tmp_path):
        results = get_discussions_for_decision(tmp_path, "DEC-001")
        assert results == []

    def test_multiple_discussions_same_decision(self, tmp_path):
        """Multiple discussions can reference the same decision."""
        log_discussion(
            tmp_path,
            topic="Initial auth discussion",
            options=[{"name": "JWT", "description": ""}],
            decision="JWT",
            rationale="First pass",
            decision_id="DEC-005",
        )
        log_discussion(
            tmp_path,
            topic="Auth follow-up",
            options=[{"name": "JWT + refresh", "description": ""}],
            decision="JWT + refresh",
            rationale="Revised approach",
            decision_id="DEC-005",
        )
        results = get_discussions_for_decision(tmp_path, "DEC-005")
        assert len(results) == 2
