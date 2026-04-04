#!/usr/bin/env python3
"""Meridian session reports — summarize work done, estimate token usage."""

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta

from scripts.db import retry_on_busy
from scripts.next_action import determine_next_step

logger = logging.getLogger(__name__)


@retry_on_busy()
def get_recent_events(
    conn: sqlite3.Connection,
    project_id: str = "default",
    hours: int = 24,
) -> list[dict]:
    """Query state_event table for events in the last N hours.

    Returns list of event dicts sorted by timestamp ascending.
    """
    cutoff = (datetime.now(UTC) - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute(
        """
        SELECT id, entity_type, entity_id, old_status, new_status,
               timestamp, metadata
        FROM state_event
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
        """,
        (cutoff,),
    ).fetchall()

    events: list[dict] = []
    for row in rows:
        meta = None
        if row[6]:
            try:
                meta = json.loads(row[6])
            except (json.JSONDecodeError, TypeError):
                meta = row[6]
        events.append(
            {
                "id": row[0],
                "entity_type": row[1],
                "entity_id": row[2],
                "old_status": row[3],
                "new_status": row[4],
                "timestamp": row[5],
                "metadata": meta,
            }
        )
    return events


def generate_session_report(
    conn: sqlite3.Connection,
    project_id: str = "default",
    since: str | None = None,
) -> dict:
    """Gather work done since a timestamp (default: last 24h).

    Queries state_events for transitions in the timeframe and counts
    plans completed, phases advanced, and decisions made.
    """
    if since:
        cutoff_dt = datetime.fromisoformat(since)
        hours_back = max(
            1,
            int((datetime.now(UTC) - cutoff_dt).total_seconds() / 3600),
        )
    else:
        hours_back = 24
        cutoff_dt = datetime.now(UTC) - timedelta(hours=hours_back)

    events = get_recent_events(conn, project_id=project_id, hours=hours_back)

    plans_completed = sum(
        1 for e in events if e["entity_type"] == "plan" and e["new_status"] == "complete"
    )
    phases_advanced = sum(
        1
        for e in events
        if e["entity_type"] == "phase"
        and e["new_status"] in ("executing", "complete")
        and e["old_status"] != e["new_status"]
    )
    decisions_made = sum(
        1
        for e in events
        if e["entity_type"] == "review"
        or (
            e.get("metadata")
            and isinstance(e["metadata"], dict)
            and e["metadata"].get("type") == "decision"
        )
    )

    next_action: str | None = None
    try:
        na = determine_next_step(conn, project_id)
        next_action = na.get("description") or na.get("action")
    except Exception:
        logger.debug("Could not compute next action for report")

    period_start = cutoff_dt.strftime("%Y-%m-%d %H:%M UTC")
    period_end = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    return {
        "period": f"{period_start} — {period_end}",
        "plans_completed": plans_completed,
        "phases_advanced": phases_advanced,
        "decisions_made": decisions_made,
        "events": events,
        "next_action": next_action,
    }


def estimate_token_usage(events: list[dict]) -> dict:
    """Rough token estimate based on event count and types.

    Heuristics: plan execution ~50k, review ~20k, discussion ~10k tokens.
    Output tokens estimated at 30% of input.
    """
    token_map = {
        "plan": 50_000,
        "phase": 20_000,
        "review": 20_000,
        "milestone": 10_000,
        "quick_task": 10_000,
        "nero_dispatch": 10_000,
    }

    estimated_input = sum(token_map.get(e["entity_type"], 10_000) for e in events)
    estimated_output = int(estimated_input * 0.3)

    return {
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_total": estimated_input + estimated_output,
    }


def format_session_report(report: dict, token_estimate: dict) -> str:
    """Format session report and token estimate as readable markdown."""
    lines: list[str] = []

    lines.append("# Session Report")
    lines.append("")
    lines.append(f"**Period:** {report['period']}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Plans completed: **{report['plans_completed']}**")
    lines.append(f"- Phases advanced: **{report['phases_advanced']}**")
    lines.append(f"- Decisions made: **{report['decisions_made']}**")
    lines.append(f"- Total events: **{len(report['events'])}**")
    lines.append("")

    if report["events"]:
        lines.append("## Event Timeline")
        lines.append("")
        lines.append("| Time | Type | Entity | Transition |")
        lines.append("|------|------|--------|------------|")
        for e in report["events"]:
            ts = e["timestamp"] or "—"
            old = e["old_status"] or "—"
            new = e["new_status"]
            lines.append(f"| {ts} | {e['entity_type']} | {e['entity_id']} | {old} -> {new} |")
        lines.append("")

    lines.append("## Token Usage Estimate")
    lines.append("")
    inp = token_estimate["estimated_input_tokens"]
    out = token_estimate["estimated_output_tokens"]
    total = token_estimate["estimated_total"]
    lines.append(f"- Input tokens: ~{inp:,}")
    lines.append(f"- Output tokens: ~{out:,}")
    lines.append(f"- **Total: ~{total:,}**")
    lines.append("")

    if report.get("next_action"):
        lines.append("## Suggested Next Action")
        lines.append("")
        lines.append(f"{report['next_action']}")
        lines.append("")

    return "\n".join(lines)
