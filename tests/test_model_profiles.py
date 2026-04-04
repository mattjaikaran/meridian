#!/usr/bin/env python3
"""Tests for Meridian model profile management."""

import pytest

from scripts.model_profiles import (
    AGENT_TYPES,
    PROFILES,
    VALID_PROFILES,
    format_profile_display,
    get_active_profile,
    get_profile_table,
    resolve_model,
    set_active_profile,
)
from scripts.state import create_project


class TestConstants:
    def test_all_profiles_cover_all_agents(self):
        for profile_name, mapping in PROFILES.items():
            for agent in AGENT_TYPES:
                assert agent in mapping, f"{profile_name} missing {agent}"

    def test_valid_profiles_includes_inherit(self):
        assert "inherit" in VALID_PROFILES

    def test_valid_profiles_matches_profiles_keys(self):
        for key in PROFILES:
            assert key in VALID_PROFILES

    def test_model_values_are_valid(self):
        valid_models = {"opus", "sonnet", "haiku"}
        for profile_name, mapping in PROFILES.items():
            for agent, model in mapping.items():
                assert model in valid_models, f"{profile_name}.{agent} = {model}"


class TestGetActiveProfile:
    def test_default_is_balanced(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        profile = get_active_profile(db)
        assert profile == "balanced"

    def test_returns_stored_profile(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        set_active_profile(db, "quality")
        db.commit()
        profile = get_active_profile(db)
        assert profile == "quality"

    def test_invalid_stored_falls_back(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        # Manually set an invalid value
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value, project_id) VALUES (?, ?, ?)",
            ("model_profile", "bogus", "default"),
        )
        db.commit()
        profile = get_active_profile(db)
        assert profile == "balanced"


class TestSetActiveProfile:
    def test_set_quality(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = set_active_profile(db, "quality")
        assert result["profile"] == "quality"
        assert result["agents"]["planner"] == "opus"

    def test_set_budget(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = set_active_profile(db, "budget")
        assert result["profile"] == "budget"
        assert result["agents"]["planner"] == "sonnet"

    def test_set_inherit(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = set_active_profile(db, "inherit")
        assert result["profile"] == "inherit"
        assert result["agents"] == {}  # inherit has no mapping

    def test_invalid_profile_raises(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        with pytest.raises(ValueError, match="Invalid profile"):
            set_active_profile(db, "nonexistent")

    def test_persists_across_reads(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        set_active_profile(db, "budget")
        db.commit()
        assert get_active_profile(db) == "budget"


class TestResolveModel:
    def test_balanced_planner_is_opus(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        model = resolve_model(db, "planner")
        assert model == "opus"

    def test_balanced_executor_is_sonnet(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        model = resolve_model(db, "executor")
        assert model == "sonnet"

    def test_budget_researcher_is_haiku(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        set_active_profile(db, "budget")
        db.commit()
        model = resolve_model(db, "researcher")
        assert model == "haiku"

    def test_inherit_returns_inherit(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        set_active_profile(db, "inherit")
        db.commit()
        model = resolve_model(db, "planner")
        assert model == "inherit"

    def test_unknown_agent_defaults_to_sonnet(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        model = resolve_model(db, "unknown_agent_type")
        assert model == "sonnet"


class TestGetProfileTable:
    def test_returns_full_mapping(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        result = get_profile_table(db)
        assert result["profile"] == "balanced"
        assert len(result["agents"]) == len(AGENT_TYPES)

    def test_inherit_returns_empty_agents(self, db):
        create_project(db, name="Test", repo_path="/tmp/test")
        set_active_profile(db, "inherit")
        db.commit()
        result = get_profile_table(db)
        assert result["profile"] == "inherit"
        assert result["agents"] == {}


class TestFormatProfileDisplay:
    def test_contains_markdown_table(self):
        data = {"profile": "balanced", "agents": PROFILES["balanced"]}
        output = format_profile_display(data)
        assert "| Agent | Model |" in output
        assert "| planner | opus |" in output
        assert "| mapper | haiku |" in output

    def test_profile_name_in_header(self):
        data = {"profile": "quality", "agents": PROFILES["quality"]}
        output = format_profile_display(data)
        assert "**Profile: quality**" in output

    def test_handles_empty_agents(self):
        data = {"profile": "inherit", "agents": {}}
        output = format_profile_display(data)
        assert "inherit" in output
        # Missing agents show as —
        assert "—" in output
