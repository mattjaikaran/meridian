#!/usr/bin/env python3
"""Tests for context bridge (scripts/context_bridge.py)."""

import json

import pytest

from scripts.context_bridge import (
    extract_project_context,
    format_context_for_prompt,
    import_context_file,
    import_matt_stack_context,
)
from scripts.state import create_project


@pytest.fixture
def pdb(db):
    create_project(db, name="Test", repo_path="/tmp/test", project_id="default")
    return db


# ── Import Context File ──────────────────────────────────────────────────────


class TestImportContextFile:
    def test_import_markdown(self, pdb, tmp_path):
        ctx_file = tmp_path / "context.md"
        ctx_file.write_text("# Project Context\n\nThis is a test project.")
        result = import_context_file(pdb, ctx_file)
        assert result["imported"] is True
        assert result["format"] == "markdown"
        assert result["target"] == "project"

    def test_import_json(self, pdb, tmp_path):
        ctx_file = tmp_path / "context.json"
        ctx_file.write_text(json.dumps({"name": "test", "stack": ["python"]}))
        result = import_context_file(pdb, ctx_file)
        assert result["imported"] is True
        assert result["format"] == "json"

    def test_import_to_phase(self, seeded_db, tmp_path):
        ctx_file = tmp_path / "context.md"
        ctx_file.write_text("Phase context content")
        result = import_context_file(seeded_db, ctx_file, phase_id=1)
        assert result["target"] == "phase:1"
        # Verify stored
        phase = seeded_db.execute("SELECT context_doc FROM phase WHERE id = 1").fetchone()
        assert phase["context_doc"] == "Phase context content"

    def test_file_not_found(self, pdb, tmp_path):
        with pytest.raises(FileNotFoundError):
            import_context_file(pdb, tmp_path / "nonexistent.md")


# ── Matt-Stack Import ────────────────────────────────────────────────────────


class TestMattStackImport:
    def test_no_context_found(self, pdb, tmp_path):
        result = import_matt_stack_context(pdb, tmp_path)
        assert result["imported"] is False
        assert result["source"] == "matt-stack"

    def test_finds_context_md(self, pdb, tmp_path):
        ms_dir = tmp_path / ".matt-stack"
        ms_dir.mkdir()
        (ms_dir / "context.md").write_text("# Matt Stack Context\nPython + React")
        result = import_matt_stack_context(pdb, tmp_path)
        assert result["imported"] is True
        assert result["source"] == "matt-stack"

    def test_finds_context_json(self, pdb, tmp_path):
        ms_dir = tmp_path / ".matt-stack"
        ms_dir.mkdir()
        (ms_dir / "context.json").write_text(json.dumps({"stack": "python"}))
        result = import_matt_stack_context(pdb, tmp_path)
        assert result["imported"] is True


# ── Extract Project Context ──────────────────────────────────────────────────


class TestExtractProjectContext:
    def test_empty_project(self, tmp_path):
        ctx = extract_project_context(tmp_path)
        assert ctx["files_found"] == []
        assert ctx["stack"] == []

    def test_detects_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "myapp"\n')
        ctx = extract_project_context(tmp_path)
        assert "pyproject.toml" in ctx["files_found"]
        assert "python" in ctx["stack"]
        assert ctx["project_name"] == "myapp"

    def test_detects_package_json(self, tmp_path):
        (tmp_path / "package.json").write_text(json.dumps({
            "name": "my-app",
            "scripts": {"test": "jest", "dev": "next dev", "build": "next build"}
        }))
        ctx = extract_project_context(tmp_path)
        assert "package.json" in ctx["files_found"]
        assert "javascript" in ctx["stack"]
        assert ctx["commands"]["test"] == "jest"
        assert ctx["commands"]["dev"] == "next dev"

    def test_detects_claude_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Project Rules\nUse uv for Python.\n")
        ctx = extract_project_context(tmp_path)
        assert "CLAUDE.md" in ctx["files_found"]
        assert "claude_md" in ctx

    def test_detects_docker(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("version: '3'\n")
        ctx = extract_project_context(tmp_path)
        assert "docker" in ctx["stack"]

    def test_detects_makefile(self, tmp_path):
        (tmp_path / "Makefile").write_text("all:\n\techo hello\n")
        ctx = extract_project_context(tmp_path)
        assert "Makefile" in ctx["files_found"]

    def test_combined_stack(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "app"\n')
        (tmp_path / "package.json").write_text('{"name": "app"}')
        ctx = extract_project_context(tmp_path)
        assert "python" in ctx["stack"]
        assert "javascript" in ctx["stack"]


# ── Format for Prompt ────────────────────────────────────────────────────────


class TestFormatForPrompt:
    def test_basic_format(self):
        ctx = {"project_name": "MyApp", "stack": ["python"], "files_found": ["pyproject.toml"]}
        output = format_context_for_prompt(ctx)
        assert "## Project Context" in output
        assert "MyApp" in output
        assert "python" in output

    def test_with_commands(self):
        ctx = {
            "project_name": "App",
            "stack": [],
            "files_found": [],
            "commands": {"test": "pytest", "dev": "uvicorn main:app"},
        }
        output = format_context_for_prompt(ctx)
        assert "pytest" in output
        assert "uvicorn" in output

    def test_empty_context(self):
        ctx = {"stack": [], "files_found": []}
        output = format_context_for_prompt(ctx)
        assert "## Project Context" in output
