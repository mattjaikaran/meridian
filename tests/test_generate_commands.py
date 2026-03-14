"""Tests for scripts/generate_commands.py — command generator for meridian skills."""

from pathlib import Path

import pytest


def _create_skill(skills_dir: Path, name: str, title: str, arguments: list[str] | None = None) -> Path:
    """Helper: create a minimal SKILL.md in a skills subdirectory."""
    skill_dir = skills_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# /meridian:{name} — {title}", "", f"{title}.", ""]
    if arguments:
        lines.append("## Arguments")
        for arg in arguments:
            lines.append(f"- {arg}")
        lines.append("")
    lines.append("## Procedure")
    lines.append("")
    lines.append("Do the thing.")
    (skill_dir / "SKILL.md").write_text("\n".join(lines))
    return skill_dir


ALL_SKILL_NAMES = [
    "checkpoint", "dashboard", "debug", "dispatch", "execute",
    "init", "plan", "quick", "resume", "review", "roadmap", "ship", "status",
]


class TestDiscoverSkills:
    """discover_skills() scans skills/*/SKILL.md and returns metadata dicts."""

    def test_discovers_all_13_skills(self, tmp_path: Path) -> None:
        from scripts.generate_commands import discover_skills

        skills_dir = tmp_path / "skills"
        for name in ALL_SKILL_NAMES:
            _create_skill(skills_dir, name, f"Description for {name}")

        result = discover_skills(tmp_path)
        assert len(result) == 13
        names = [s["name"] for s in result]
        assert sorted(names) == sorted(ALL_SKILL_NAMES)

    def test_returns_sorted_by_name(self, tmp_path: Path) -> None:
        from scripts.generate_commands import discover_skills

        skills_dir = tmp_path / "skills"
        for name in ["status", "init", "plan"]:
            _create_skill(skills_dir, name, f"Desc {name}")

        result = discover_skills(tmp_path)
        assert [s["name"] for s in result] == ["init", "plan", "status"]

    def test_skips_non_directories(self, tmp_path: Path) -> None:
        from scripts.generate_commands import discover_skills

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "README.md").write_text("Not a skill")
        _create_skill(skills_dir, "init", "Init")

        result = discover_skills(tmp_path)
        assert len(result) == 1

    def test_skips_dirs_without_skill_md(self, tmp_path: Path) -> None:
        from scripts.generate_commands import discover_skills

        skills_dir = tmp_path / "skills"
        (skills_dir / "empty_skill").mkdir(parents=True)
        _create_skill(skills_dir, "init", "Init")

        result = discover_skills(tmp_path)
        assert len(result) == 1


class TestExtractMetadata:
    """extract_metadata() parses SKILL.md for description and argument hints."""

    def test_extracts_description_from_title(self, tmp_path: Path) -> None:
        from scripts.generate_commands import extract_metadata

        skill_dir = _create_skill(tmp_path, "init", "Initialize Meridian in Current Project")
        result = extract_metadata(skill_dir / "SKILL.md")
        assert result["description"] == "Initialize Meridian in Current Project"

    def test_extracts_arguments(self, tmp_path: Path) -> None:
        from scripts.generate_commands import extract_metadata

        skill_dir = _create_skill(
            tmp_path, "plan", "Planning Pipeline",
            arguments=["`<goal>` — What to build", "`--milestone <id>` — Target milestone"],
        )
        result = extract_metadata(skill_dir / "SKILL.md")
        assert result["argument_hint"] == "<goal> --milestone <id>"

    def test_no_arguments_section(self, tmp_path: Path) -> None:
        from scripts.generate_commands import extract_metadata

        skill_dir = _create_skill(tmp_path, "dashboard", "Project Dashboard")
        result = extract_metadata(skill_dir / "SKILL.md")
        assert result["argument_hint"] == ""

    def test_handles_em_dash_separator(self, tmp_path: Path) -> None:
        from scripts.generate_commands import extract_metadata

        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# /meridian:test — Test Description\n")
        result = extract_metadata(skill_dir / "SKILL.md")
        assert result["description"] == "Test Description"

    def test_handles_en_dash_separator(self, tmp_path: Path) -> None:
        from scripts.generate_commands import extract_metadata

        skill_dir = tmp_path / "test_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# /meridian:test \u2013 Test Description\n")
        result = extract_metadata(skill_dir / "SKILL.md")
        assert result["description"] == "Test Description"


class TestGenerateWrapper:
    """generate_wrapper() produces the correct command file content."""

    def test_wrapper_starts_with_frontmatter_and_contains_marker(self) -> None:
        from scripts.generate_commands import generate_wrapper

        result = generate_wrapper({"name": "init", "description": "Init", "argument_hint": ""})
        assert result.startswith("---\n")
        assert "<!-- meridian:generated -->" in result

    def test_wrapper_has_frontmatter(self) -> None:
        from scripts.generate_commands import generate_wrapper

        result = generate_wrapper({"name": "init", "description": "Initialize", "argument_hint": "<goal>"})
        assert "name: meridian:init" in result
        assert "description: Initialize" in result
        assert 'argument-hint: "<goal>"' in result

    def test_wrapper_has_at_reference(self) -> None:
        from scripts.generate_commands import generate_wrapper

        result = generate_wrapper({"name": "init", "description": "Init", "argument_hint": ""})
        assert "@/Users/mattjaikaran/.claude/skills/meridian/skills/init/SKILL.md" in result

    def test_wrapper_no_argument_hint_when_empty(self) -> None:
        from scripts.generate_commands import generate_wrapper

        result = generate_wrapper({"name": "dashboard", "description": "Dashboard", "argument_hint": ""})
        assert "argument-hint" not in result


class TestIsGenerated:
    """is_generated() detects generator-produced files by marker."""

    def test_generated_file(self, tmp_path: Path) -> None:
        from scripts.generate_commands import is_generated

        f = tmp_path / "test.md"
        f.write_text("<!-- meridian:generated -->\n---\nname: test\n---\n")
        assert is_generated(f) is True

    def test_custom_file(self, tmp_path: Path) -> None:
        from scripts.generate_commands import is_generated

        f = tmp_path / "custom.md"
        f.write_text("# Custom command\nDo something custom.\n")
        assert is_generated(f) is False

    def test_empty_file(self, tmp_path: Path) -> None:
        from scripts.generate_commands import is_generated

        f = tmp_path / "empty.md"
        f.write_text("")
        assert is_generated(f) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        from scripts.generate_commands import is_generated

        assert is_generated(tmp_path / "nope.md") is False


class TestWriteCommands:
    """write_commands() writes generated files and preserves custom ones."""

    def test_creates_command_files(self, tmp_path: Path) -> None:
        from scripts.generate_commands import write_commands

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        skills = [
            {"name": "init", "description": "Init", "argument_hint": ""},
            {"name": "plan", "description": "Plan", "argument_hint": "<goal>"},
        ]
        created, skipped = write_commands(skills, commands_dir)
        assert created == 2
        assert skipped == 0
        assert (commands_dir / "init.md").exists()
        assert (commands_dir / "plan.md").exists()

    def test_preserves_custom_files(self, tmp_path: Path) -> None:
        from scripts.generate_commands import write_commands

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        custom = commands_dir / "custom.md"
        custom.write_text("# My custom command\n")
        # Use name "custom" so it would conflict
        skills = [{"name": "custom", "description": "Custom", "argument_hint": ""}]
        created, skipped = write_commands(skills, commands_dir)
        assert created == 0
        assert skipped == 1
        assert custom.read_text() == "# My custom command\n"

    def test_overwrites_generated_files(self, tmp_path: Path) -> None:
        from scripts.generate_commands import write_commands

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        existing = commands_dir / "init.md"
        existing.write_text("<!-- meridian:generated -->\nold content")
        skills = [{"name": "init", "description": "Updated Init", "argument_hint": ""}]
        created, _ = write_commands(skills, commands_dir)
        assert created == 1
        assert "Updated Init" in existing.read_text()

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        from scripts.generate_commands import write_commands

        commands_dir = tmp_path / "commands" / "meridian"
        skills = [{"name": "init", "description": "Init", "argument_hint": ""}]
        created, _ = write_commands(skills, commands_dir)
        assert created == 1
        assert commands_dir.exists()


class TestCleanupOrphans:
    """cleanup_orphans() removes stale generated files."""

    def test_removes_orphaned_generated_file(self, tmp_path: Path) -> None:
        from scripts.generate_commands import cleanup_orphans

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        orphan = commands_dir / "old_skill.md"
        orphan.write_text("<!-- meridian:generated -->\n---\nname: old\n---\n")
        removed = cleanup_orphans(commands_dir, {"init", "plan"})
        assert "old_skill.md" in removed
        assert not orphan.exists()

    def test_preserves_custom_files(self, tmp_path: Path) -> None:
        from scripts.generate_commands import cleanup_orphans

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        custom = commands_dir / "custom.md"
        custom.write_text("# Custom\n")
        removed = cleanup_orphans(commands_dir, set())
        assert len(removed) == 0
        assert custom.exists()

    def test_preserves_valid_generated_files(self, tmp_path: Path) -> None:
        from scripts.generate_commands import cleanup_orphans

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        valid = commands_dir / "init.md"
        valid.write_text("<!-- meridian:generated -->\n---\nname: init\n---\n")
        removed = cleanup_orphans(commands_dir, {"init"})
        assert len(removed) == 0
        assert valid.exists()


class TestVerifySymlink:
    """verify_symlink() checks symlink existence and target."""

    def test_valid_symlink(self, tmp_path: Path) -> None:
        from scripts.generate_commands import verify_symlink

        target = tmp_path / "repo"
        target.mkdir()
        link = tmp_path / "link"
        link.symlink_to(target)
        assert verify_symlink(link, target) is True

    def test_missing_symlink(self, tmp_path: Path) -> None:
        from scripts.generate_commands import verify_symlink

        assert verify_symlink(tmp_path / "nope", tmp_path / "target") is False

    def test_wrong_target(self, tmp_path: Path) -> None:
        from scripts.generate_commands import verify_symlink

        target = tmp_path / "repo"
        target.mkdir()
        wrong = tmp_path / "other"
        wrong.mkdir()
        link = tmp_path / "link"
        link.symlink_to(wrong)
        assert verify_symlink(link, target) is False


class TestFixSymlink:
    """fix_symlink() creates or repairs the skills symlink."""

    def test_creates_new_symlink(self, tmp_path: Path) -> None:
        from scripts.generate_commands import fix_symlink

        target = tmp_path / "repo"
        target.mkdir()
        link = tmp_path / "link"
        fix_symlink(link, target)
        assert link.is_symlink()
        assert link.resolve() == target.resolve()

    def test_replaces_wrong_symlink(self, tmp_path: Path) -> None:
        from scripts.generate_commands import fix_symlink

        target = tmp_path / "repo"
        target.mkdir()
        wrong = tmp_path / "other"
        wrong.mkdir()
        link = tmp_path / "link"
        link.symlink_to(wrong)
        fix_symlink(link, target)
        assert link.resolve() == target.resolve()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        from scripts.generate_commands import fix_symlink

        target = tmp_path / "repo"
        target.mkdir()
        link = tmp_path / "deep" / "nested" / "link"
        fix_symlink(link, target)
        assert link.is_symlink()


class TestUninstall:
    """uninstall() removes only generated files."""

    def test_removes_generated_keeps_custom(self, tmp_path: Path) -> None:
        from scripts.generate_commands import uninstall

        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        gen = commands_dir / "init.md"
        gen.write_text("<!-- meridian:generated -->\ncontent")
        custom = commands_dir / "custom.md"
        custom.write_text("# Custom\n")
        removed = uninstall(commands_dir)
        assert len(removed) == 1
        assert "init.md" in removed
        assert not gen.exists()
        assert custom.exists()


class TestUpdateRootSkill:
    """update_root_skill() regenerates SKILL.md without Commands section."""

    def test_no_commands_section(self, tmp_path: Path) -> None:
        from scripts.generate_commands import update_root_skill

        skills_dir = tmp_path / "skills"
        for name in ["init", "plan", "status"]:
            _create_skill(skills_dir, name, f"Desc {name}")

        skills = [
            {"name": "init", "description": "Init"},
            {"name": "plan", "description": "Plan"},
            {"name": "status", "description": "Status"},
        ]
        update_root_skill(tmp_path, skills)
        content = (tmp_path / "SKILL.md").read_text()
        assert "## Commands" not in content
        # Should still have architecture and scripts
        assert "## Architecture" in content
        assert "## Scripts" in content

    def test_lists_available_commands_informational(self, tmp_path: Path) -> None:
        from scripts.generate_commands import update_root_skill

        skills_dir = tmp_path / "skills"
        _create_skill(skills_dir, "init", "Init")
        skills = [{"name": "init", "description": "Init"}]
        update_root_skill(tmp_path, skills)
        content = (tmp_path / "SKILL.md").read_text()
        # Should have informational list but NOT /meridian: invocation syntax
        assert "init" in content
        assert "/meridian:init" not in content
