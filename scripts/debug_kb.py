#!/usr/bin/env python3
"""Persistent debug knowledge base — append, search, and dedup debug findings."""

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

KB_FILENAME = "debug-kb.md"


@dataclass
class DebugEntry:
    """A single debug knowledge base entry."""

    entry_id: str
    timestamp: str
    title: str
    symptom: str
    root_cause: str
    fix: str
    files: list[str]

    def to_markdown(self) -> str:
        """Render this entry as a markdown section."""
        files_str = ", ".join(self.files) if self.files else "none"
        return (
            f"## [{self.entry_id}] {self.timestamp} — {self.title}\n"
            f"\n"
            f"**Symptom:** {self.symptom}\n"
            f"**Root Cause:** {self.root_cause}\n"
            f"**Fix:** {self.fix}\n"
            f"**Files:** {files_str}\n"
        )


def _get_kb_path(project_dir: str | Path) -> Path:
    """Return path to debug-kb.md in .meridian/ directory."""
    return Path(project_dir) / ".meridian" / KB_FILENAME


def _hash_root_cause(root_cause: str) -> str:
    """Generate a stable hash of a root cause string for dedup."""
    normalized = root_cause.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _next_entry_id(existing_entries: list[DebugEntry]) -> str:
    """Generate the next DBG-NNN entry ID."""
    max_num = 0
    for entry in existing_entries:
        match = re.match(r"DBG-(\d+)", entry.entry_id)
        if match:
            max_num = max(max_num, int(match.group(1)))
    return f"DBG-{max_num + 1:03d}"


def load_kb(project_dir: str | Path) -> list[DebugEntry]:
    """Load all entries from the debug knowledge base.

    Returns an empty list if the file doesn't exist.
    """
    kb_path = _get_kb_path(project_dir)
    if not kb_path.exists():
        return []

    text = kb_path.read_text(encoding="utf-8")
    return _parse_kb(text)


def _parse_kb(text: str) -> list[DebugEntry]:
    """Parse markdown KB text into DebugEntry objects."""
    entries: list[DebugEntry] = []

    # Split on ## [DBG-NNN] headers
    pattern = r"^## \[(DBG-\d+)\]\s+(\S+)\s+—\s+(.+)$"
    sections = re.split(r"(?=^## \[DBG-\d+\])", text, flags=re.MULTILINE)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(pattern, section, re.MULTILINE)
        if not header_match:
            continue

        entry_id = header_match.group(1)
        timestamp = header_match.group(2)
        title = header_match.group(3).strip()

        symptom = _extract_field(section, "Symptom")
        root_cause = _extract_field(section, "Root Cause")
        fix = _extract_field(section, "Fix")
        files_str = _extract_field(section, "Files")
        files = [f.strip() for f in files_str.split(",") if f.strip()] if files_str else []

        entries.append(DebugEntry(
            entry_id=entry_id,
            timestamp=timestamp,
            title=title,
            symptom=symptom,
            root_cause=root_cause,
            fix=fix,
            files=files,
        ))

    return entries


def _extract_field(section: str, field_name: str) -> str:
    """Extract a **FieldName:** value from a markdown section."""
    pattern = rf"\*\*{re.escape(field_name)}:\*\*\s*(.+)"
    match = re.search(pattern, section)
    return match.group(1).strip() if match else ""


def append_debug_entry(
    project_dir: str | Path,
    title: str,
    symptom: str,
    root_cause: str,
    fix: str,
    files: list[str] | None = None,
) -> DebugEntry | None:
    """Append a new debug entry to the knowledge base.

    Returns the new entry, or None if a duplicate root cause was detected.
    """
    project_dir = Path(project_dir)
    existing = load_kb(project_dir)

    # Dedup: check if root cause already exists
    new_hash = _hash_root_cause(root_cause)
    for entry in existing:
        if _hash_root_cause(entry.root_cause) == new_hash:
            logger.info(
                "Duplicate root cause detected (matches %s), skipping",
                entry.entry_id,
            )
            return None

    entry_id = _next_entry_id(existing)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d")

    entry = DebugEntry(
        entry_id=entry_id,
        timestamp=timestamp,
        title=title,
        symptom=symptom,
        root_cause=root_cause,
        fix=fix,
        files=files or [],
    )

    kb_path = _get_kb_path(project_dir)
    kb_path.parent.mkdir(parents=True, exist_ok=True)

    # Append to file
    existing_text = ""
    if kb_path.exists():
        existing_text = kb_path.read_text(encoding="utf-8")

    # Add header if this is the first entry
    if not existing_text.strip():
        existing_text = "# Debug Knowledge Base\n\n"

    # Ensure trailing newline before appending
    if existing_text and not existing_text.endswith("\n"):
        existing_text += "\n"

    kb_path.write_text(
        existing_text + entry.to_markdown() + "\n",
        encoding="utf-8",
    )

    logger.info("Appended debug entry %s: %s", entry_id, title)
    return entry


def search_kb(
    project_dir: str | Path,
    query: str,
) -> list[DebugEntry]:
    """Search the debug knowledge base by keyword.

    Matches against symptom and root_cause fields (case-insensitive).
    Returns matching entries sorted by relevance (number of keyword matches).
    """
    entries = load_kb(project_dir)
    if not entries:
        return []

    keywords = query.lower().split()
    if not keywords:
        return []

    scored: list[tuple[int, DebugEntry]] = []
    for entry in entries:
        searchable = f"{entry.symptom} {entry.root_cause} {entry.title}".lower()
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored]
