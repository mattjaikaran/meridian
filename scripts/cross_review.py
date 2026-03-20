#!/usr/bin/env python3
"""Cross-model review — optional independent review from a secondary AI model."""

import json
import shutil
import subprocess
from pathlib import Path


# Supported secondary models and their CLI binaries
SUPPORTED_MODELS = {
    "codex": {"binary": "codex", "name": "OpenAI Codex CLI"},
    "gemini": {"binary": "gemini", "name": "Google Gemini CLI"},
    "aider": {"binary": "aider", "name": "Aider CLI"},
}


def detect_models() -> list[dict]:
    """Detect which secondary AI CLIs are installed.

    Returns list of available models with their binary paths.
    """
    available = []
    for model_id, info in SUPPORTED_MODELS.items():
        binary_path = shutil.which(info["binary"])
        if binary_path is not None:
            available.append({
                "id": model_id,
                "name": info["name"],
                "binary": binary_path,
            })
    return available


def build_review_prompt(
    files: list[str],
    phase_name: str = "",
    phase_description: str = "",
    acceptance_criteria: str = "",
) -> str:
    """Construct a code review prompt for an external model.

    Returns a prompt string suitable for CLI invocation.
    """
    lines = [
        "You are a code reviewer. Review the following files for:",
        "1. Bugs that could cause production issues",
        "2. Security vulnerabilities",
        "3. Performance concerns",
        "4. Code quality issues",
        "",
    ]

    if phase_name:
        lines.append(f"Context: This code implements '{phase_name}'.")
    if phase_description:
        lines.append(f"Description: {phase_description}")
    if acceptance_criteria:
        lines.append(f"Acceptance Criteria: {acceptance_criteria}")
    lines.append("")

    lines.append("Files to review:")
    for f in files:
        lines.append(f"- {f}")
    lines.append("")

    lines.append("For each issue found, report:")
    lines.append("- File and line number")
    lines.append("- Severity (critical/warning/info)")
    lines.append("- Description of the issue")
    lines.append("- Suggested fix")
    lines.append("")
    lines.append("If no issues found, state 'No issues found.'")

    return "\n".join(lines)


def run_external_review(
    model_id: str,
    prompt: str,
    timeout_seconds: int = 120,
) -> dict:
    """Run a review using an external CLI model.

    Returns:
        {"model": str, "output": str, "success": bool, "error": str|None}
    """
    if model_id not in SUPPORTED_MODELS:
        return {
            "model": model_id,
            "output": "",
            "success": False,
            "error": f"Unsupported model: {model_id}",
        }

    info = SUPPORTED_MODELS[model_id]
    binary = shutil.which(info["binary"])
    if binary is None:
        return {
            "model": model_id,
            "output": "",
            "success": False,
            "error": f"{info['name']} not installed",
        }

    try:
        result = subprocess.run(
            [binary, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "model": model_id,
            "output": result.stdout.strip(),
            "success": result.returncode == 0,
            "error": result.stderr.strip() if result.returncode != 0 else None,
        }
    except subprocess.TimeoutExpired:
        return {
            "model": model_id,
            "output": "",
            "success": False,
            "error": f"Review timed out after {timeout_seconds}s",
        }
    except FileNotFoundError:
        return {
            "model": model_id,
            "output": "",
            "success": False,
            "error": f"{info['name']} binary not found",
        }


def parse_findings(raw_output: str) -> list[dict]:
    """Extract structured findings from model output.

    Parses common patterns like file:line references and severity tags.
    Returns list of finding dicts.
    """
    if not raw_output or "no issues found" in raw_output.lower():
        return []

    findings = []
    current_finding: dict | None = None

    for line in raw_output.split("\n"):
        line = line.strip()
        if not line:
            if current_finding:
                findings.append(current_finding)
                current_finding = None
            continue

        # Detect severity markers
        severity = "info"
        lower = line.lower()
        if "critical" in lower or "bug" in lower or "security" in lower:
            severity = "critical"
        elif "warning" in lower or "performance" in lower:
            severity = "warning"

        # Detect file references (file.py:123 or file.py line 123)
        import re
        file_match = re.search(r"(\S+\.\w+)[:\s]+(?:line\s+)?(\d+)", line)

        if file_match or any(kw in lower for kw in ("issue", "bug", "warning", "error", "concern")):
            if current_finding:
                findings.append(current_finding)
            current_finding = {
                "severity": severity,
                "file": file_match.group(1) if file_match else None,
                "line": int(file_match.group(2)) if file_match else None,
                "description": line,
            }
        elif current_finding:
            current_finding["description"] += " " + line

    if current_finding:
        findings.append(current_finding)

    return findings


def compare_findings(
    claude_findings: list[dict],
    external_findings: list[dict],
) -> dict:
    """Compare findings from Claude and external model.

    Returns:
        {"claude_only": [...], "external_only": [...], "overlapping": [...]}
    """
    # Simple comparison based on file + rough description overlap
    def _key(finding: dict) -> str:
        return f"{finding.get('file', '')}:{finding.get('severity', '')}"

    claude_keys = {_key(f): f for f in claude_findings}
    external_keys = {_key(f): f for f in external_findings}

    claude_only = [f for k, f in claude_keys.items() if k not in external_keys]
    external_only = [f for k, f in external_keys.items() if k not in claude_keys]
    overlapping = [f for k, f in claude_keys.items() if k in external_keys]

    return {
        "claude_only": claude_only,
        "external_only": external_only,
        "overlapping": overlapping,
        "claude_total": len(claude_findings),
        "external_total": len(external_findings),
    }


def format_comparison(comparison: dict, model_name: str = "external") -> str:
    """Format a cross-model comparison as markdown."""
    lines = [
        "## Cross-Model Review Comparison",
        "",
        f"| Source | Findings |",
        f"|--------|----------|",
        f"| Claude | {comparison['claude_total']} |",
        f"| {model_name} | {comparison['external_total']} |",
        f"| Overlapping | {len(comparison['overlapping'])} |",
        "",
    ]

    if comparison["claude_only"]:
        lines.append("### Claude-Only Findings")
        for f in comparison["claude_only"]:
            lines.append(f"- [{f.get('severity', '?')}] {f.get('description', 'N/A')}")
        lines.append("")

    if comparison["external_only"]:
        lines.append(f"### {model_name}-Only Findings")
        for f in comparison["external_only"]:
            lines.append(f"- [{f.get('severity', '?')}] {f.get('description', 'N/A')}")
        lines.append("")

    if comparison["overlapping"]:
        lines.append("### Both Models Found")
        for f in comparison["overlapping"]:
            lines.append(f"- [{f.get('severity', '?')}] {f.get('description', 'N/A')}")
        lines.append("")

    if not any([comparison["claude_only"], comparison["external_only"], comparison["overlapping"]]):
        lines.append("No findings from either model.")
        lines.append("")

    return "\n".join(lines)
