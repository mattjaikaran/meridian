#!/usr/bin/env python3
"""Structured learning extraction from completed phase artifacts."""

import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from scripts.learnings import add_learning, find_similar


# Artifact globs to read, in priority order
_ARTIFACT_GLOBS = [
    "*-PLAN.md",
    "*-SUMMARY.md",
    "VERIFICATION.md",
    "*-VERIFICATION.md",
    "VALIDATION.md",
    "CONTEXT.md",
    "UAT*.md",
    "RESEARCH.md",
]

# Regex banks per category — each captures the key phrase in group 1
#
# Covers two artifact formats:
#   1. YAML frontmatter lists:  key-decisions:\n  - "text"
#   2. Markdown prose sections: ## Decisions Made\n- bullet
#   3. Verification tables:     | FAILED | reason |

# YAML list items immediately under a key-decisions or key-decision block
_YAML_DECISION_RE = re.compile(
    r"(?im)^key-decisions?:\s*\n((?:[ \t]+-[^\n]+\n?)+)", re.MULTILINE
)
_YAML_PATTERNS_RE = re.compile(
    r"(?im)^patterns-established:\s*\n((?:[ \t]+-[^\n]+\n?)+)", re.MULTILINE
)
_YAML_ISSUES_RE = re.compile(
    r"(?im)^(?:issues?|deviations?|blockers?):\s*\n((?:[ \t]+-[^\n]+\n?)+)", re.MULTILINE
)
_YAML_LIST_ITEM_RE = re.compile(r'[ \t]+-\s*"?([^"\n]+)"?')

_DECISION_RES = [
    # YAML frontmatter: key-decisions items extracted via _extract_yaml_list
    r"(?im)^\*{0,2}(?:decision|decided|chose|chosen|selected|approach)[:：]\*{0,2}\s*(.{10,300})",
    r"(?im)^#+\s*(?:Decisions? Made|ADR)[:：]?\s*$",  # section header — items extracted below
    r"(?i)\bwe (?:decided|chose|went with|selected|opted)\b(.{10,200})",
    # Bullet under "## Decisions Made"
    r"(?im)(?<=## Decisions Made\n)(?:\n-\s+(.{10,200}))+",
]

_SURPRISE_RES = [
    r"(?im)^\*{0,2}(?:surprise|unexpected|gotcha|caveat|watch out)[:：]\*{0,2}\s*(.{10,300})",
    r"(?i)\b(?:unexpectedly|surprisingly|turns? out|discovered|found that|realized)\b(.{10,200})",
    # Deviation / auto-fixed issue blocks
    r"(?im)\*\*Issue:\*\*\s*(.{10,300})",
]

_FAILURE_RES = [
    r"(?im)^\*{0,2}(?:failure|failed|error|bug|problem|blocker|regression)[:：]\*{0,2}\s*(.{10,300})",
    r"(?i)\b(?:broke|broken|failed|didn't work|didn't pass|rejected|reverted)\b(.{10,200})",
    # Verification table FAILED rows
    r"(?im)\|\s*FAILED\s*\|[^|]*\|[^|]*\|\s*([^|]{10,200})\s*\|",
    r"(?im)\|\s*PARTIAL\s*\|[^|]*\|[^|]*\|\s*([^|]{10,200})\s*\|",
]

_PATTERN_RES = [
    # YAML frontmatter: patterns-established items extracted via _extract_yaml_list
    r"(?im)^\*{0,2}(?:pattern|rule|convention|always|never|prefer|avoid)[:：]\*{0,2}\s*(.{10,300})",
    r"(?im)^#+\s*(?:Pattern|Rule|Convention|Best Practice)[:：]?\s*(.{5,200})",
    # tech-stack.patterns YAML list
    r"(?im)patterns:\s*\[([^\]]+)\]",
]


def _clean(text: str) -> str:
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:300]


def _dedup(items: list[str], cap: int = 8, min_len: int = 20) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.lower()[:60]
        if key not in seen and len(item) >= min_len:
            seen.add(key)
            out.append(item)
    return out[:cap]


def _extract_yaml_list(content: str, block_re: re.Pattern) -> list[str]:
    """Extract string items from a YAML list block matched by block_re."""
    results = []
    for m in block_re.finditer(content):
        block = m.group(1)
        for item_m in _YAML_LIST_ITEM_RE.finditer(block):
            text = _clean(item_m.group(1))
            if text:
                results.append(text)
    return results


def _extract_section_bullets(content: str, section_header: str) -> list[str]:
    """Extract bullet items immediately following a markdown section header."""
    pattern = re.compile(
        r"(?im)^#+\s*" + re.escape(section_header) + r"\s*$\n((?:\s*[-*]\s+.+\n?)+)",
        re.MULTILINE,
    )
    results = []
    for m in pattern.finditer(content):
        block = m.group(1)
        for line in block.splitlines():
            stripped = re.sub(r"^\s*[-*]\s+", "", line).strip()
            text = _clean(stripped)
            if text and len(text) > 10:
                results.append(text)
    return results


def _extract_matches(content: str, patterns: list[str]) -> list[str]:
    results = []
    for pat in patterns:
        for m in re.finditer(pat, content, re.MULTILINE):
            group = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
            text = _clean(group)
            if text and len(text) > 15:
                results.append(text)
    return results


def extract_from_phase_dir(phase_dir: Path) -> dict:
    """Read all artifacts in phase_dir and return structured extraction dict.

    Returns:
        {
            "decisions": list[str],
            "surprises": list[str],
            "patterns":  list[str],
            "failures":  list[str],
            "phase_dir": str,
            "artifacts_read": list[str],
        }
    """
    phase_dir = Path(phase_dir)
    chunks: list[str] = []
    artifacts_read: list[str] = []

    for glob in _ARTIFACT_GLOBS:
        for path in sorted(phase_dir.glob(glob)):
            try:
                chunks.append(path.read_text(encoding="utf-8", errors="replace"))
                artifacts_read.append(path.name)
            except OSError:
                pass

    combined = "\n\n".join(chunks)

    decisions = (
        _extract_yaml_list(combined, _YAML_DECISION_RE)
        + _extract_section_bullets(combined, "Decisions Made")
        + _extract_matches(combined, _DECISION_RES)
    )

    patterns = (
        _extract_yaml_list(combined, _YAML_PATTERNS_RE)
        + _extract_section_bullets(combined, "Patterns")
        + _extract_matches(combined, _PATTERN_RES)
    )

    surprises = (
        _extract_yaml_list(combined, _YAML_ISSUES_RE)
        + _extract_section_bullets(combined, "Issues Encountered")
        + _extract_matches(combined, _SURPRISE_RES)
    )

    failures = (
        _extract_section_bullets(combined, "Deviations from Plan")
        + _extract_matches(combined, _FAILURE_RES)
    )

    return {
        "decisions": _dedup(decisions),
        "surprises": _dedup(surprises),
        "patterns": _dedup(patterns),
        "failures": _dedup(failures),
        "phase_dir": str(phase_dir),
        "artifacts_read": artifacts_read,
    }


def write_learnings_md(phase_dir: Path, extraction: dict) -> Path:
    """Write LEARNINGS.md into phase_dir from extraction result. Returns path."""
    phase_dir = Path(phase_dir)
    now = datetime.now(UTC).strftime("%Y-%m-%d")

    lines = [
        "# Phase Learnings",
        "",
        f"Generated: {now}  ",
        f"Source artifacts: {', '.join(extraction['artifacts_read']) or 'none found'}",
        "",
    ]

    sections = [
        ("Decisions", extraction["decisions"]),
        ("Patterns", extraction["patterns"]),
        ("Surprises / Gotchas", extraction["surprises"]),
        ("Failures / Issues", extraction["failures"]),
    ]

    for title, items in sections:
        lines.append(f"## {title}")
        lines.append("")
        if items:
            for item in items:
                lines.append(f"- {item}")
        else:
            lines.append("_None detected_")
        lines.append("")

    out_path = phase_dir / "LEARNINGS.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _ensure_project(conn: sqlite3.Connection, project_id: str = "default") -> None:
    """Ensure a project record exists; insert stub if missing (FK guard)."""
    exists = conn.execute("SELECT 1 FROM project WHERE id = ?", (project_id,)).fetchone()
    if not exists:
        conn.execute(
            "INSERT OR IGNORE INTO project (id, name, repo_path) VALUES (?, ?, ?)",
            (project_id, project_id, "."),
        )
        conn.commit()


def save_extracted_to_db(
    conn: sqlite3.Connection,
    extraction: dict,
    phase_id: int | None = None,
    project_id: str = "default",
    skip_duplicates: bool = True,
) -> list[dict]:
    """Save extracted learnings to the DB learning table.

    Uses source='execution', sets category per item type.
    Returns list of saved learning dicts (skipped duplicates not included).
    """
    _ensure_project(conn, project_id)
    saved: list[dict] = []

    category_map = [
        ("decision", extraction["decisions"]),
        ("pattern", extraction["patterns"]),
        ("surprise", extraction["surprises"]),
        ("failure", extraction["failures"]),
    ]

    for category, items in category_map:
        for rule in items:
            if skip_duplicates:
                existing = find_similar(conn, rule, project_id=project_id, threshold=0.7)
                if existing:
                    continue
            learning = add_learning(
                conn,
                rule=rule,
                scope="project",
                source="execution",
                phase_id=phase_id,
                project_id=project_id,
                category=category,
            )
            saved.append(learning)

    return saved


def find_phases_without_learnings(project_dir: Path) -> list[Path]:
    """Return phase dirs under .planning/phases/ that have no LEARNINGS.md.

    Only includes dirs that contain at least one .md artifact (i.e., real phases).
    """
    phases_dir = Path(project_dir) / ".planning" / "phases"
    if not phases_dir.exists():
        return []

    pending: list[Path] = []
    for phase_dir in sorted(phases_dir.iterdir()):
        if not phase_dir.is_dir():
            continue
        if (phase_dir / "LEARNINGS.md").exists():
            continue
        artifacts = [p for g in _ARTIFACT_GLOBS for p in phase_dir.glob(g)]
        if artifacts:
            pending.append(phase_dir)

    return pending


def check_extraction_pending(project_dir: Path) -> dict:
    """Return a summary of extraction status for the project.

    Returns:
        {
            "total_phases": int,
            "extracted": int,
            "pending": list[str],   # relative dir names
        }
    """
    phases_dir = Path(project_dir) / ".planning" / "phases"
    if not phases_dir.exists():
        return {"total_phases": 0, "extracted": 0, "pending": []}

    all_dirs = [d for d in phases_dir.iterdir() if d.is_dir()]
    pending_dirs = find_phases_without_learnings(project_dir)
    extracted_count = sum(1 for d in all_dirs if (d / "LEARNINGS.md").exists())

    return {
        "total_phases": len(all_dirs),
        "extracted": extracted_count,
        "pending": [d.name for d in pending_dirs],
    }
