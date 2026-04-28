#!/usr/bin/env python3
"""Scale detection — auto-tune planning depth based on codebase size and phase count."""

import subprocess
from pathlib import Path


_SMALL_LOC = 5_000
_LARGE_LOC = 50_000
_SMALL_PHASES = 3
_LARGE_PHASES = 10


def count_loc(project_dir: str | Path = ".") -> int:
    """Count total lines of code (excludes .git, node_modules, __pycache__, .venv)."""
    project = Path(project_dir).resolve()
    try:
        result = subprocess.run(
            [
                "find", str(project),
                "-type", "f",
                "(",
                "-name", "*.py",
                "-o", "-name", "*.ts",
                "-o", "-name", "*.tsx",
                "-o", "-name", "*.js",
                "-o", "-name", "*.jsx",
                "-o", "-name", "*.rs",
                "-o", "-name", "*.go",
                "-o", "-name", "*.java",
                "-o", "-name", "*.cpp",
                "-o", "-name", "*.c",
                "-o", "-name", "*.swift",
                ")",
                "!", "-path", "*/.git/*",
                "!", "-path", "*/node_modules/*",
                "!", "-path", "*/__pycache__/*",
                "!", "-path", "*/.venv/*",
                "!", "-path", "*/dist/*",
                "!", "-path", "*/build/*",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        files = [f for f in result.stdout.strip().splitlines() if f]
        if not files:
            return 0
        wc = subprocess.run(
            ["wc", "-l"] + files,
            capture_output=True,
            text=True,
            check=False,
        )
        for line in reversed(wc.stdout.strip().splitlines()):
            parts = line.strip().split()
            if parts and parts[-1] == "total":
                return int(parts[0])
        return 0
    except Exception:
        return 0


def detect_scale(
    project_dir: str | Path = ".",
    phase_count: int | None = None,
    override: str | None = None,
) -> dict:
    """Detect project scale and return planning mode recommendation.

    Args:
        project_dir: Root of the project.
        phase_count: Number of phases in the active milestone (if known).
        override: Explicit override value: 'small', 'medium', or 'large'.

    Returns dict with keys:
        scale: 'small' | 'medium' | 'large'
        loc: int
        phase_count: int | None
        source: 'override' | 'detected'
        planning_mode: 'fast' | 'standard' | 'deep'
        skip_research: bool
        force_deep: bool
        parallel_research: bool
        rationale: str
    """
    if override:
        override = override.lower().strip()
        if override not in ("small", "medium", "large"):
            raise ValueError(f"Invalid scale override '{override}'. Use: small, medium, large")
        scale = override
        loc = 0
        source = "override"
    else:
        loc = count_loc(project_dir)
        source = "detected"
        if loc < _SMALL_LOC and (phase_count is None or phase_count <= _SMALL_PHASES):
            scale = "small"
        elif loc >= _LARGE_LOC or (phase_count is not None and phase_count >= _LARGE_PHASES):
            scale = "large"
        else:
            scale = "medium"

    if scale == "small":
        planning_mode = "fast"
        skip_research = True
        force_deep = False
        parallel_research = False
        rationale = (
            f"Small project ({loc:,} LOC"
            + (f", {phase_count} phases" if phase_count else "")
            + "): skipping deep research, using fast planning."
        )
    elif scale == "large":
        planning_mode = "deep"
        skip_research = False
        force_deep = True
        parallel_research = True
        rationale = (
            f"Large project ({loc:,} LOC"
            + (f", {phase_count} phases" if phase_count else "")
            + "): forcing --deep mode with multi-subagent research."
        )
    else:
        planning_mode = "standard"
        skip_research = False
        force_deep = False
        parallel_research = False
        rationale = (
            f"Medium project ({loc:,} LOC"
            + (f", {phase_count} phases" if phase_count else "")
            + "): standard planning depth."
        )

    return {
        "scale": scale,
        "loc": loc,
        "phase_count": phase_count,
        "source": source,
        "planning_mode": planning_mode,
        "skip_research": skip_research,
        "force_deep": force_deep,
        "parallel_research": parallel_research,
        "rationale": rationale,
    }


def get_scale_override(conn) -> str | None:
    """Read meridian_scale from settings table, if set."""
    try:
        cur = conn.execute(
            "SELECT value FROM settings WHERE key = 'meridian_scale' LIMIT 1"
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def set_scale_override(conn, scale: str) -> None:
    """Persist meridian_scale in settings table."""
    if scale not in ("small", "medium", "large", "auto"):
        raise ValueError(f"Invalid scale '{scale}'. Use: small, medium, large, auto")
    value = None if scale == "auto" else scale
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('meridian_scale', ?) "
        "ON CONFLICT(project_id, key) DO UPDATE SET value = excluded.value",
        (value,),
    )
    conn.commit()
