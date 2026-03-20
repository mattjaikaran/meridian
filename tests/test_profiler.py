#!/usr/bin/env python3
"""Tests for Meridian developer profiler."""

from pathlib import Path
from unittest.mock import patch

from scripts.profiler import (
    analyze_project_patterns,
    generate_profile,
    save_profile,
)


# ── Analysis Tests ──────────────────────────────────────────────────────────


class TestAnalyzeProjectPatterns:
    def test_returns_expected_keys(self, tmp_path: Path):
        patterns = analyze_project_patterns(tmp_path)
        assert "commit_style" in patterns
        assert "languages" in patterns
        assert "frameworks" in patterns
        assert "branch_style" in patterns
        assert "test_style" in patterns
        assert "structure" in patterns

    def test_detects_python_files(self, tmp_path: Path):
        (tmp_path / "main.py").write_text("print('hello')")
        patterns = analyze_project_patterns(tmp_path)
        assert "Python" in patterns["languages"]

    def test_detects_frameworks_from_config(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")
        patterns = analyze_project_patterns(tmp_path)
        assert "Python (pyproject)" in patterns["frameworks"]

    def test_detects_test_dirs(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        patterns = analyze_project_patterns(tmp_path)
        assert "tests" in patterns["test_style"]["test_dirs"]

    def test_detects_pytest_framework(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text('[tool.pytest.ini_options]\nminversion = "6.0"')
        patterns = analyze_project_patterns(tmp_path)
        assert "pytest" in patterns["test_style"]["frameworks"]

    def test_structure_lists_top_dirs(self, tmp_path: Path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "tests").mkdir()
        patterns = analyze_project_patterns(tmp_path)
        assert "scripts" in patterns["structure"]["top_level_dirs"]
        assert "tests" in patterns["structure"]["top_level_dirs"]

    def test_structure_lists_config_files(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / ".gitignore").write_text("")
        patterns = analyze_project_patterns(tmp_path)
        assert "pyproject.toml" in patterns["structure"]["config_files"]
        assert ".gitignore" in patterns["structure"]["config_files"]

    def test_commit_style_no_git(self, tmp_path: Path):
        """Non-git directory returns unknown convention."""
        patterns = analyze_project_patterns(tmp_path)
        assert patterns["commit_style"]["convention"] == "unknown"

    def test_branch_style_no_git(self, tmp_path: Path):
        patterns = analyze_project_patterns(tmp_path)
        assert patterns["branch_style"]["convention"] == "unknown"


# ── Profile Generation Tests ────────────────────────────────────────────────


class TestGenerateProfile:
    def test_generates_markdown(self):
        patterns = {
            "commit_style": {"convention": "conventional", "conventional_ratio": 0.85, "sample_count": 20},
            "languages": ["Python", "TypeScript"],
            "frameworks": ["Python (pyproject)", "Docker"],
            "branch_style": {"convention": "prefixed", "prefixed_ratio": 0.6, "sample_count": 10},
            "test_style": {"test_dirs": ["tests"], "frameworks": ["pytest"]},
            "structure": {"top_level_dirs": ["scripts", "tests"], "config_files": ["pyproject.toml"]},
        }
        profile = generate_profile(patterns)
        assert "# Developer Profile" in profile
        assert "conventional" in profile
        assert "Python" in profile
        assert "TypeScript" in profile
        assert "pytest" in profile

    def test_handles_empty_patterns(self):
        patterns = {
            "commit_style": {"convention": "unknown", "sample_count": 0},
            "languages": [],
            "frameworks": [],
            "branch_style": {"convention": "unknown", "sample_count": 0},
            "test_style": {"test_dirs": [], "frameworks": []},
            "structure": {"top_level_dirs": [], "config_files": []},
        }
        profile = generate_profile(patterns)
        assert "# Developer Profile" in profile
        assert "No language files detected" in profile

    def test_includes_timestamp(self):
        patterns = {
            "commit_style": {"convention": "unknown", "sample_count": 0},
            "languages": [],
            "frameworks": [],
            "branch_style": {"convention": "unknown", "sample_count": 0},
            "test_style": {"test_dirs": [], "frameworks": []},
            "structure": {"top_level_dirs": [], "config_files": []},
        }
        profile = generate_profile(patterns)
        assert "_Generated:" in profile


# ── Save Profile Tests ──────────────────────────────────────────────────────


class TestSaveProfile:
    def test_saves_to_meridian_dir(self, tmp_path: Path):
        content = "# Test Profile\n"
        path = save_profile(tmp_path, content)
        assert path.exists()
        assert path.name == "USER-PROFILE.md"
        assert path.parent.name == ".meridian"
        assert path.read_text(encoding="utf-8") == content

    def test_creates_meridian_dir(self, tmp_path: Path):
        save_profile(tmp_path, "# Profile\n")
        assert (tmp_path / ".meridian").is_dir()

    def test_overwrites_existing(self, tmp_path: Path):
        save_profile(tmp_path, "# Old\n")
        save_profile(tmp_path, "# New\n")
        content = (tmp_path / ".meridian" / "USER-PROFILE.md").read_text(encoding="utf-8")
        assert "# New" in content
        assert "# Old" not in content
