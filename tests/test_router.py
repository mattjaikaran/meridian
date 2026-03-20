#!/usr/bin/env python3
"""Tests for Meridian freeform text router."""

import pytest

from scripts.router import (
    _parse_skill_md,
    _score_command,
    load_command_registry,
    route_freeform,
)


# ── Registry Loading ─────────────────────────────────────────────────────────


class TestParseSkillMd:
    def test_valid_skill(self):
        content = """# /meridian:fast — Inline Fast Task

Execute a trivial task inline.

## Keywords
fast, quick, trivial, fix, typo
"""
        result = _parse_skill_md(content, "fast")
        assert result["name"] == "fast"
        assert result["description"] == "Inline Fast Task"
        assert "fast" in result["keywords"]
        assert "typo" in result["keywords"]

    def test_missing_header(self):
        content = "Just some text"
        result = _parse_skill_md(content, "test")
        assert result is None

    def test_no_keywords(self):
        content = "# /meridian:test — Test Command\n\nSome description."
        result = _parse_skill_md(content, "test")
        assert result is not None
        assert result["keywords"] == []

    def test_em_dash_header(self):
        content = "# /meridian:plan — Create execution plans"
        result = _parse_skill_md(content, "plan")
        assert result["name"] == "plan"
        assert result["description"] == "Create execution plans"


class TestLoadCommandRegistry:
    def test_loads_from_skills_dir(self, tmp_path):
        skill_dir = tmp_path / "fast"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "# /meridian:fast — Inline Fast Task\n\n## Keywords\nfast, quick, fix"
        )
        registry = load_command_registry(tmp_path)
        assert len(registry) == 1
        assert registry[0]["name"] == "fast"

    def test_empty_dir(self, tmp_path):
        registry = load_command_registry(tmp_path)
        assert registry == []

    def test_missing_dir(self, tmp_path):
        registry = load_command_registry(tmp_path / "nonexistent")
        assert registry == []

    def test_skips_invalid_skill(self, tmp_path):
        skill_dir = tmp_path / "bad"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("Not a valid skill file")
        registry = load_command_registry(tmp_path)
        assert registry == []


# ── Scoring ──────────────────────────────────────────────────────────────────


class TestScoreCommand:
    def test_exact_name_match(self):
        cmd = {"name": "fast", "description": "Inline Fast Task", "keywords": ["fast"]}
        score = _score_command("run fast", {"run", "fast"}, cmd)
        assert score >= 10.0  # Exact name match

    def test_keyword_match(self):
        cmd = {"name": "note", "description": "Capture notes", "keywords": ["note", "idea", "capture"]}
        score = _score_command("capture an idea", {"capture", "an", "idea"}, cmd)
        assert score > 0

    def test_no_match(self):
        cmd = {"name": "fast", "description": "Inline Fast Task", "keywords": ["fast", "quick"]}
        score = _score_command("deploy production", {"deploy", "production"}, cmd)
        assert score == 0.0


# ── Routing ──────────────────────────────────────────────────────────────────


MOCK_REGISTRY: list[dict] = [
    {
        "name": "fast",
        "description": "Inline Fast Task",
        "keywords": ["fast", "quick", "trivial", "fix", "typo"],
        "dir_name": "fast",
    },
    {
        "name": "note",
        "description": "Capture notes and ideas",
        "keywords": ["note", "idea", "capture", "remember"],
        "dir_name": "note",
    },
    {
        "name": "next",
        "description": "Advance to next workflow step",
        "keywords": ["next", "advance", "continue", "what's next"],
        "dir_name": "next",
    },
    {
        "name": "plan",
        "description": "Create execution plans",
        "keywords": ["plan", "design", "architect", "phases"],
        "dir_name": "plan",
    },
]


class TestRouteFreeform:
    def test_exact_match(self):
        result = route_freeform("run fast on this", registry=MOCK_REGISTRY)
        assert result["match"] == "exact"
        assert result["command"] == "fast"

    def test_confident_match(self):
        result = route_freeform("fix a typo quickly", registry=MOCK_REGISTRY)
        assert result["match"] in ("exact", "confident")
        assert result["command"] == "fast"

    def test_note_match(self):
        result = route_freeform("capture an idea about auth", registry=MOCK_REGISTRY)
        assert result["command"] == "note"

    def test_next_match(self):
        result = route_freeform("what should I do next", registry=MOCK_REGISTRY)
        assert result["command"] == "next"

    def test_no_match(self):
        result = route_freeform("deploy to production servers", registry=MOCK_REGISTRY)
        assert result["match"] == "none"
        assert result["command"] is None

    def test_ambiguous_match(self):
        # "quick fix" could match fast (keywords: quick, fix) and note less so
        result = route_freeform("plan some quick design ideas", registry=MOCK_REGISTRY)
        assert result["candidates"]  # Should have candidates

    def test_empty_registry(self):
        result = route_freeform("do something", registry=[])
        assert result["match"] == "none"

    def test_returns_candidates(self):
        result = route_freeform("fix a typo quickly", registry=MOCK_REGISTRY)
        assert len(result["candidates"]) >= 1
        assert result["candidates"][0]["name"] == "fast"

    def test_message_present(self):
        result = route_freeform("fix something", registry=MOCK_REGISTRY)
        assert result["message"]
