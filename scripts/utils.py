from __future__ import annotations

import re
import sqlite3
from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_dt() -> datetime:
    return datetime.now(UTC)


def sanitize_slug(text: str) -> str:
    slug = text.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug).strip("-")
    slug = slug[:60].rstrip("-")
    if not slug:
        raise ValueError(f"Cannot derive a valid slug from: {text!r}")
    return slug


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def parse_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except (ValueError, AttributeError):
        return None


def phase_slug(phase: dict) -> str:
    name = phase["name"].lower()
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return f"{phase['sequence']:02d}-{slug}"
