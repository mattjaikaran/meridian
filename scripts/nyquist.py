#!/usr/bin/env python3
"""Nyquist validation engine -- parse VALIDATION.md, run tests, update frontmatter.

Parses VALIDATION.md files to extract test commands, executes them on wave
completion, and updates frontmatter with actual pass/fail results. Uses only
the standard library (no PyYAML dependency).
"""

import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def _parse_frontmatter(text: str) -> tuple[dict | None, str]:
    """Split text into frontmatter dict and body string.

    Returns (frontmatter_dict, body) or (None, full_text) if no valid
    frontmatter delimiters found.
    """
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.DOTALL)
    if not match:
        return None, text

    fm_text = match.group(1)
    body = match.group(2)
    fm: dict = {}

    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Type coercion for known patterns
        if value.lower() == "true":
            fm[key] = True
        elif value.lower() == "false":
            fm[key] = False
        elif re.match(r"^\d+$", value):
            fm[key] = int(value)
        else:
            fm[key] = value

    return fm, body


def _serialize_frontmatter(fm: dict) -> str:
    """Serialize a dict back to YAML-like frontmatter string."""
    lines = ["---"]
    for key, value in fm.items():
        if isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key}: {value}")
        elif value is None:
            lines.append(f"{key}: null")
        else:
            # Quote strings that contain special chars
            sv = str(value)
            if re.search(r"[:\[\]{}#&*!|>'\"%@`]", sv) or sv.startswith("-"):
                lines.append(f'{key}: "{sv}"')
            else:
                lines.append(f"{key}: {sv}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _extract_command(body: str, label: str) -> str | None:
    """Extract a backtick-delimited command from a markdown table row.

    Matches: | **label** | `command here` |
    """
    pattern = (
        r"\|\s*\*\*"
        + re.escape(label)
        + r"\*\*\s*\|\s*`([^`]+)`\s*\|"
    )
    match = re.search(pattern, body)
    return match.group(1) if match else None


def parse_validation_md(phase_dir: Path) -> dict | None:
    """Parse a VALIDATION.md file from a phase directory.

    Args:
        phase_dir: Path to the phase directory containing VALIDATION.md.

    Returns:
        Dict with frontmatter fields + quick_command + full_command,
        or None if file missing, or dict with 'error' key if malformed.
    """
    vmd = phase_dir / "VALIDATION.md"
    if not vmd.exists():
        return None

    text = vmd.read_text()
    fm, body = _parse_frontmatter(text)

    if fm is None:
        return {"error": "No valid frontmatter found", "body": body}

    # Extract test commands from body
    fm["quick_command"] = _extract_command(body, "Quick run command")
    fm["full_command"] = _extract_command(body, "Full suite command")

    return fm


def run_wave_validation(
    phase_dir: Path,
    wave: int,
    repo_path: str = ".",
) -> dict:
    """Run the full suite command from VALIDATION.md and return results.

    Args:
        phase_dir: Path to the phase directory.
        wave: Wave number being validated.
        repo_path: Working directory for command execution.

    Returns:
        Dict with keys: wave, passed, command, output, validated_at.
        On error: includes 'error' key and passed=False.
    """
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    parsed = parse_validation_md(phase_dir)

    if parsed is None:
        return {
            "wave": wave,
            "passed": False,
            "command": "",
            "output": "",
            "validated_at": now,
            "error": "VALIDATION.md not found",
        }

    if "error" in parsed:
        return {
            "wave": wave,
            "passed": False,
            "command": "",
            "output": "",
            "validated_at": now,
            "error": parsed["error"],
        }

    cmd = parsed.get("full_command")
    if not cmd:
        return {
            "wave": wave,
            "passed": False,
            "command": "",
            "output": "",
            "validated_at": now,
            "error": "No full suite command found in VALIDATION.md",
        }

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=120,
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        passed = False
        output = "Command timed out after 120 seconds"
    except (OSError, subprocess.SubprocessError) as exc:
        passed = False
        output = str(exc)

    return {
        "wave": wave,
        "passed": passed,
        "command": cmd,
        "output": output,
        "validated_at": now,
    }


def update_validation_frontmatter(phase_dir: Path, wave_results: dict) -> None:
    """Update VALIDATION.md frontmatter with wave validation results.

    Writes wave_N_complete (bool) and wave_N_validated (timestamp) fields.
    Computes nyquist_compliant: true only when ALL wave_*_complete fields
    are true. Updates status to 'validated' (all pass) or 'failed' (any fail).

    Args:
        phase_dir: Path to the phase directory.
        wave_results: Dict from run_wave_validation with wave, passed,
                      validated_at keys.
    """
    vmd = phase_dir / "VALIDATION.md"
    if not vmd.exists():
        return

    text = vmd.read_text()
    fm, body = _parse_frontmatter(text)
    if fm is None:
        return

    wave = wave_results["wave"]
    passed = wave_results["passed"]
    validated_at = wave_results["validated_at"]

    # Set per-wave fields
    fm[f"wave_{wave}_complete"] = passed
    fm[f"wave_{wave}_validated"] = validated_at

    # Compute nyquist_compliant: all wave_*_complete must be true
    wave_fields = {
        k: v for k, v in fm.items()
        if re.match(r"^wave_\d+_complete$", k)
    }
    all_pass = bool(wave_fields) and all(
        v is True for v in wave_fields.values()
    )
    fm["nyquist_compliant"] = all_pass

    # Update status
    if all_pass:
        fm["status"] = "validated"
    elif not passed:
        fm["status"] = "failed"

    # Write back
    vmd.write_text(_serialize_frontmatter(fm) + body)
