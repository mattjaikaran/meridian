#!/usr/bin/env python3
"""MCP tool discovery and relevance scoring for subagent prompts.

Scans available MCP servers for tools relevant to the current task,
scores them by keyword matching, and formats them for inclusion in
subagent prompts. Results are cached per session.

For now, tools are loaded from a config file `.meridian/mcp-tools.json`.
Real MCP integration can be wired in later via the protocol's list_tools endpoint.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MCPTool:
    """Represents a single MCP tool."""

    name: str
    description: str
    server: str
    input_schema: dict[str, Any] = field(default_factory=dict)


# Module-level session cache
_discovery_cache: dict[str, list[MCPTool]] | None = None


def _load_tools_from_config(config_path: str | None = None) -> list[MCPTool]:
    """Load MCP tool definitions from a JSON config file.

    Config format:
    {
      "servers": {
        "server-name": {
          "tools": [
            {"name": "tool_name", "description": "...", "input_schema": {...}}
          ]
        }
      }
    }
    """
    if config_path is None:
        config_path = os.path.join(".meridian", "mcp-tools.json")

    try:
        with open(config_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    tools: list[MCPTool] = []
    servers = data.get("servers", {})
    for server_name, server_config in servers.items():
        for tool_def in server_config.get("tools", []):
            tools.append(
                MCPTool(
                    name=tool_def.get("name", ""),
                    description=tool_def.get("description", ""),
                    server=server_name,
                    input_schema=tool_def.get("input_schema", {}),
                )
            )

    return tools


def discover_mcp_tools(
    config_path: str | None = None,
    use_cache: bool = True,
) -> list[MCPTool]:
    """Discover available MCP tools from configured servers.

    Args:
        config_path: Path to MCP tools config file. Defaults to .meridian/mcp-tools.json.
        use_cache: If True, return cached results on subsequent calls.

    Returns:
        List of available MCPTool instances. Empty list if no servers configured.
    """
    global _discovery_cache

    cache_key = config_path or "__default__"

    if use_cache and _discovery_cache is not None and cache_key in _discovery_cache:
        return _discovery_cache[cache_key]

    tools = _load_tools_from_config(config_path)

    if _discovery_cache is None:
        _discovery_cache = {}
    _discovery_cache[cache_key] = tools

    return tools


def clear_cache() -> None:
    """Clear the discovery cache. Useful for testing."""
    global _discovery_cache
    _discovery_cache = None


def score_tool_relevance(tool: MCPTool, plan_description: str) -> float:
    """Score how relevant a tool is to a plan description.

    Uses keyword matching between the tool's name/description and the plan.
    Returns a score between 0.0 and 1.0.

    Args:
        tool: The MCP tool to score.
        plan_description: Description of the current plan/task.

    Returns:
        Relevance score from 0.0 (no match) to 1.0 (highly relevant).
    """
    if not plan_description:
        return 0.0

    plan_words = set(plan_description.lower().split())
    tool_words = set()
    tool_words.update(tool.name.lower().replace("_", " ").replace("-", " ").split())
    tool_words.update(tool.description.lower().split())

    # Remove common stop words
    stop_words = {"the", "a", "an", "and", "or", "is", "it", "to", "for", "of", "in", "on", "with"}
    plan_words -= stop_words
    tool_words -= stop_words

    if not plan_words or not tool_words:
        return 0.0

    # Count matching words
    matches = plan_words & tool_words
    if not matches:
        return 0.0

    # Score: proportion of tool words that match plan, capped at 1.0
    score = len(matches) / max(len(tool_words), 1)
    return min(score, 1.0)


def format_tools_for_prompt(
    tools: list[MCPTool],
    plan_description: str = "",
    relevance_threshold: float = 0.1,
    max_tools: int = 10,
) -> str:
    """Format discovered tools as context for a subagent prompt.

    If a plan_description is provided, tools are filtered by relevance
    and sorted by score (highest first).

    Args:
        tools: List of MCP tools to format.
        plan_description: Optional plan description for relevance filtering.
        relevance_threshold: Minimum relevance score to include a tool.
        max_tools: Maximum number of tools to include.

    Returns:
        Formatted string describing available tools for the prompt.
    """
    if not tools:
        return ""

    if plan_description:
        scored = [
            (tool, score_tool_relevance(tool, plan_description))
            for tool in tools
        ]
        scored = [(t, s) for t, s in scored if s >= relevance_threshold]
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [t for t, _s in scored[:max_tools]]
    else:
        selected = tools[:max_tools]

    if not selected:
        return ""

    lines = ["## Available MCP Tools", ""]
    for tool in selected:
        lines.append(f"- **{tool.name}** ({tool.server}): {tool.description}")

    lines.append("")
    return "\n".join(lines)
