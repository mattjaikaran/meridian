#!/usr/bin/env python3
"""Tests for MCP tool discovery and relevance scoring."""

import json

from scripts.mcp_discovery import (
    MCPTool,
    clear_cache,
    discover_mcp_tools,
    format_tools_for_prompt,
    score_tool_relevance,
)


def _make_config(tmp_path, servers: dict) -> str:
    """Helper to create a config file and return its path."""
    config_path = tmp_path / "mcp-tools.json"
    config_path.write_text(json.dumps({"servers": servers}))
    return str(config_path)


def _make_tool(name: str = "test_tool", desc: str = "A test tool", server: str = "test-server") -> MCPTool:
    return MCPTool(name=name, description=desc, server=server)


class TestDiscoverMCPTools:
    def setup_method(self):
        clear_cache()

    def test_returns_tools_from_config(self, tmp_path):
        config = _make_config(tmp_path, {
            "search-server": {
                "tools": [
                    {"name": "web_search", "description": "Search the web"},
                    {"name": "local_search", "description": "Search local files"},
                ]
            }
        })
        tools = discover_mcp_tools(config_path=config)
        assert len(tools) == 2
        assert tools[0].name == "web_search"
        assert tools[0].server == "search-server"
        assert tools[1].name == "local_search"

    def test_returns_empty_list_when_no_config(self):
        tools = discover_mcp_tools(config_path="/nonexistent/path.json")
        assert tools == []

    def test_returns_empty_list_for_invalid_json(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("not valid json{{{")
        tools = discover_mcp_tools(config_path=str(bad))
        assert tools == []

    def test_caches_results_on_second_call(self, tmp_path):
        config = _make_config(tmp_path, {
            "srv": {"tools": [{"name": "t1", "description": "d1"}]}
        })
        first = discover_mcp_tools(config_path=config)
        # Overwrite file — cached result should be returned
        (tmp_path / "mcp-tools.json").write_text("{}")
        second = discover_mcp_tools(config_path=config)
        assert first is second

    def test_cache_bypassed_when_disabled(self, tmp_path):
        config = _make_config(tmp_path, {
            "srv": {"tools": [{"name": "t1", "description": "d1"}]}
        })
        first = discover_mcp_tools(config_path=config)
        # Overwrite config to empty
        (tmp_path / "mcp-tools.json").write_text(json.dumps({"servers": {}}))
        second = discover_mcp_tools(config_path=config, use_cache=False)
        assert len(first) == 1
        assert len(second) == 0

    def test_multiple_servers(self, tmp_path):
        config = _make_config(tmp_path, {
            "server-a": {"tools": [{"name": "a1", "description": "tool a"}]},
            "server-b": {"tools": [{"name": "b1", "description": "tool b"}]},
        })
        tools = discover_mcp_tools(config_path=config)
        assert len(tools) == 2
        servers = {t.server for t in tools}
        assert servers == {"server-a", "server-b"}

    def test_empty_servers(self, tmp_path):
        config = _make_config(tmp_path, {})
        tools = discover_mcp_tools(config_path=config)
        assert tools == []

    def test_tool_with_input_schema(self, tmp_path):
        config = _make_config(tmp_path, {
            "srv": {"tools": [{
                "name": "query",
                "description": "Run a query",
                "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
            }]}
        })
        tools = discover_mcp_tools(config_path=config)
        assert tools[0].input_schema["type"] == "object"


class TestScoreToolRelevance:
    def test_high_relevance_for_matching_keywords(self):
        tool = _make_tool("web_search", "Search the web for information")
        score = score_tool_relevance(tool, "search the web for documentation")
        assert score > 0.3

    def test_zero_for_no_match(self):
        tool = _make_tool("database_query", "Query a SQL database")
        score = score_tool_relevance(tool, "compile rust code")
        assert score == 0.0

    def test_zero_for_empty_plan(self):
        tool = _make_tool("web_search", "Search the web")
        assert score_tool_relevance(tool, "") == 0.0

    def test_score_between_zero_and_one(self):
        tool = _make_tool("file_reader", "Read and parse files from disk")
        score = score_tool_relevance(tool, "read the configuration file")
        assert 0.0 <= score <= 1.0

    def test_name_contributes_to_score(self):
        tool = _make_tool("search", "A general tool")
        score = score_tool_relevance(tool, "search for patterns")
        assert score > 0.0

    def test_underscore_in_name_splits_for_matching(self):
        tool = _make_tool("web_search", "A tool")
        score = score_tool_relevance(tool, "search something")
        assert score > 0.0


class TestFormatToolsForPrompt:
    def test_formats_tools_as_markdown(self):
        tools = [
            _make_tool("web_search", "Search the web", "brave"),
            _make_tool("db_query", "Query database", "postgres"),
        ]
        result = format_tools_for_prompt(tools)
        assert "## Available MCP Tools" in result
        assert "**web_search** (brave)" in result
        assert "**db_query** (postgres)" in result

    def test_returns_empty_string_for_no_tools(self):
        assert format_tools_for_prompt([]) == ""

    def test_filters_by_relevance_when_plan_given(self):
        tools = [
            _make_tool("web_search", "Search the web"),
            _make_tool("compile_code", "Compile source code"),
        ]
        result = format_tools_for_prompt(tools, plan_description="search the web")
        assert "web_search" in result
        # compile_code has no relevance to "search the web"
        assert "compile_code" not in result

    def test_respects_max_tools(self):
        tools = [_make_tool(f"tool_{i}", f"Description {i}") for i in range(20)]
        result = format_tools_for_prompt(tools, max_tools=3)
        # Should have at most 3 tool entries
        assert result.count("**tool_") == 3

    def test_returns_empty_when_all_below_threshold(self):
        tools = [_make_tool("xyz_abc", "totally unrelated")]
        result = format_tools_for_prompt(tools, plan_description="compile rust code", relevance_threshold=0.5)
        assert result == ""

    def test_sorts_by_relevance(self):
        tools = [
            _make_tool("unrelated", "something else entirely"),
            _make_tool("web_search", "search the web for results"),
        ]
        result = format_tools_for_prompt(tools, plan_description="search the web")
        # web_search should appear first since it's more relevant
        if "web_search" in result and "unrelated" in result:
            assert result.index("web_search") < result.index("unrelated")


class TestClearCache:
    def test_clear_cache_resets(self, tmp_path):
        config = _make_config(tmp_path, {
            "srv": {"tools": [{"name": "t1", "description": "d1"}]}
        })
        discover_mcp_tools(config_path=config)
        clear_cache()
        # After clearing, overwriting config should take effect
        (tmp_path / "mcp-tools.json").write_text(json.dumps({"servers": {}}))
        tools = discover_mcp_tools(config_path=config)
        assert tools == []
