#!/usr/bin/env python3
"""Quality gate checks — regression, coverage, stub detection.

Provides pre-execution gates that verify prior phases haven't regressed,
requirements are covered by plans, and post-execution stub scanning.
Uses only the standard library (no external dependencies).
"""

import re
import shlex
import subprocess
from pathlib import Path

from scripts.nyquist import parse_validation_md

# ── Stub Detection (Plan 03) ────────────────────────────────────────────────

DEFAULT_STUB_PATTERNS: list[dict[str, str]] = [
    {"name": "TODO", "regex": r"\bTODO\b"},
    {"name": "FIXME", "regex": r"\bFIXME\b"},
    {"name": "XXX", "regex": r"\bXXX\b"},
    {"name": "HACK", "regex": r"\bHACK\b"},
    {"name": "NotImplementedError", "regex": r"raise\s+NotImplementedError"},
    {"name": "pass-only function", "regex": r"^\s*pass\s*$"},
    {"name": "placeholder comment", "regex": r"#\s*(placeholder|stub|temporary)\b"},
    {"name": "ellipsis body", "regex": r"^\s*\.\.\.\s*$"},
]


# ── Plan 01: Cross-Phase Regression Gate ─────────────────────────────────────


def collect_prior_test_commands(
    planning_dir: Path,
    up_to_phase: int,
) -> list[dict[str, str | int]]:
    """Collect full_suite_command from completed phases' VALIDATION.md files.

    Scans phases 1..up_to_phase-1 for VALIDATION.md files and extracts
    the full suite command from each.

    Args:
        planning_dir: Path to the .planning directory.
        up_to_phase: Current phase number (exclusive upper bound).

    Returns:
        List of dicts with keys: phase_num, phase_dir, command.
        Phases without VALIDATION.md or without a command are skipped.
    """
    phases_dir = planning_dir / "phases"
    if not phases_dir.is_dir():
        return []

    commands: list[dict[str, str | int]] = []

    for phase_dir in sorted(phases_dir.iterdir()):
        if not phase_dir.is_dir():
            continue

        # Extract phase number from directory name (e.g., "01-database-foundation" -> 1)
        match = re.match(r"^(\d+)", phase_dir.name)
        if not match:
            continue

        phase_num = int(match.group(1))
        if phase_num >= up_to_phase:
            continue

        parsed = parse_validation_md(phase_dir)
        if parsed is None:
            continue  # No VALIDATION.md — skip silently

        if "error" in parsed:
            continue  # Malformed — skip

        cmd = parsed.get("full_command")
        if not cmd:
            continue  # No command — skip

        commands.append({
            "phase_num": phase_num,
            "phase_dir": str(phase_dir),
            "command": cmd,
        })

    return commands


def run_regression_gate(
    planning_dir: Path,
    current_phase: int,
    repo_path: str = ".",
    skip_regression: bool = False,
    timeout: int = 120,
) -> dict:
    """Run cross-phase regression gate before phase execution.

    Collects test commands from all prior phases' VALIDATION.md files
    and runs them sequentially. If any fail, returns a failure result
    blocking execution.

    Args:
        planning_dir: Path to the .planning directory.
        current_phase: Phase number about to start executing.
        repo_path: Working directory for command execution.
        skip_regression: If True, skip the gate (emergency bypass).
        timeout: Timeout in seconds per command.

    Returns:
        Dict with keys: passed, skipped, results, summary.
        Each result has: phase_num, command, passed, output.
    """
    if skip_regression:
        return {
            "passed": True,
            "skipped": True,
            "results": [],
            "summary": "Regression gate skipped (--skip-regression)",
        }

    commands = collect_prior_test_commands(planning_dir, current_phase)

    if not commands:
        return {
            "passed": True,
            "skipped": False,
            "results": [],
            "summary": "No prior phase test commands found",
        }

    results: list[dict] = []
    all_passed = True

    for entry in commands:
        cmd = entry["command"]
        phase_num = entry["phase_num"]

        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                cwd=repo_path,
                timeout=timeout,
            )
            passed = result.returncode == 0
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            passed = False
            output = f"Command timed out after {timeout} seconds"
        except (OSError, subprocess.SubprocessError) as exc:
            passed = False
            output = str(exc)

        if not passed:
            all_passed = False

        results.append({
            "phase_num": phase_num,
            "command": cmd,
            "passed": passed,
            "output": output,
        })

    failed = [r for r in results if not r["passed"]]
    if all_passed:
        summary = f"All {len(results)} prior phase(s) pass regression check"
    else:
        phases = ", ".join(str(r["phase_num"]) for r in failed)
        summary = f"Regression failure in phase(s): {phases}"

    return {
        "passed": all_passed,
        "skipped": False,
        "results": results,
        "summary": summary,
    }


# ── Plan 02: Requirements Coverage Gate ──────────────────────────────────────


def check_requirements_coverage(
    phase_requirements: list[str],
    plan_requirements: dict[str, list[str]],
    strict: bool = False,
) -> dict:
    """Check that all phase requirements are covered by at least one plan.

    Args:
        phase_requirements: List of requirement IDs assigned to the phase.
        plan_requirements: Mapping of plan name/id to its list of requirement IDs.
        strict: If True, uncovered requirements cause a hard block.

    Returns:
        Dict with keys: covered, uncovered, coverage_pct, plan_map, passed, warnings.
        plan_map maps each requirement to the list of plans covering it.
    """
    if not phase_requirements:
        return {
            "covered": [],
            "uncovered": [],
            "coverage_pct": 100.0,
            "plan_map": {},
            "passed": True,
            "warnings": [],
        }

    # Build mapping: requirement -> list of plans
    plan_map: dict[str, list[str]] = {}
    for plan_name, reqs in plan_requirements.items():
        for req in reqs:
            plan_map.setdefault(req, []).append(plan_name)

    covered: list[str] = []
    uncovered: list[str] = []

    for req in phase_requirements:
        if req in plan_map:
            covered.append(req)
        else:
            uncovered.append(req)

    total = len(phase_requirements)
    coverage_pct = (len(covered) / total) * 100.0 if total > 0 else 100.0

    warnings: list[str] = []
    if uncovered:
        warnings.append(
            f"Uncovered requirements: {', '.join(uncovered)}"
        )

    passed = True
    if uncovered and strict:
        passed = False

    return {
        "covered": covered,
        "uncovered": uncovered,
        "coverage_pct": coverage_pct,
        "plan_map": plan_map,
        "passed": passed,
        "warnings": warnings,
    }


# ── Plan 03: Stub/Placeholder Detection ─────────────────────────────────────


def detect_stubs(
    file_paths: list[str | Path],
    patterns: list[dict[str, str]] | None = None,
) -> list[dict[str, str | int]]:
    """Scan files for stub/placeholder patterns.

    Args:
        file_paths: List of file paths to scan.
        patterns: List of pattern dicts with 'name' and 'regex' keys.
                  Defaults to DEFAULT_STUB_PATTERNS.

    Returns:
        List of dicts with keys: file, line, pattern, context.
    """
    if patterns is None:
        patterns = DEFAULT_STUB_PATTERNS

    findings: list[dict[str, str | int]] = []

    for fpath in file_paths:
        path = Path(fpath)
        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        lines = text.splitlines()
        for line_num, line_text in enumerate(lines, start=1):
            for pat in patterns:
                if re.search(pat["regex"], line_text):
                    findings.append({
                        "file": str(path),
                        "line": line_num,
                        "pattern": pat["name"],
                        "context": line_text.strip(),
                    })

    return findings
