#!/usr/bin/env python3
"""Phase manipulation — insert, remove, and renumber phases within a milestone."""

import logging
import sqlite3

from scripts.db import retry_on_busy
from scripts.state import _log_event, create_phase, get_phase, list_phases, list_plans

logger = logging.getLogger(__name__)


@retry_on_busy()
def insert_phase(
    conn: sqlite3.Connection,
    milestone_id: str,
    after_sequence: int,
    name: str,
    description: str,
    acceptance_criteria: list[str] | None = None,
) -> dict:
    """Insert a new phase after the given sequence number.

    Computes a decimal midpoint between after_sequence and the next existing
    sequence. SQLite's dynamic typing allows storing floats in INTEGER columns,
    and the UNIQUE(milestone_id, sequence) constraint still holds.
    """
    rows = conn.execute(
        "SELECT sequence FROM phase "
        "WHERE milestone_id = ? AND sequence > ? "
        "ORDER BY sequence LIMIT 1",
        (milestone_id, after_sequence),
    ).fetchone()

    if rows is None:
        new_sequence = after_sequence + 1.0
    else:
        next_sequence = rows["sequence"]
        new_sequence = (after_sequence + next_sequence) / 2.0

    logger.info(
        "inserting phase after sequence %s → new sequence %s",
        after_sequence,
        new_sequence,
    )

    phase = create_phase(
        conn,
        milestone_id=milestone_id,
        name=name,
        description=description,
        acceptance_criteria=acceptance_criteria,
        sequence=new_sequence,
    )
    return phase


@retry_on_busy()
def remove_phase(conn: sqlite3.Connection, phase_id: int) -> dict:
    """Remove a phase that is still in 'planned' status.

    Deletes associated plans first (FK constraint), then the phase itself.
    Returns a summary dict with the removed phase, renumber count, and message.
    """
    phase = get_phase(conn, phase_id)
    if phase is None:
        raise ValueError(f"Phase {phase_id} not found")

    if phase["status"] != "planned":
        raise ValueError(
            f"Cannot remove phase {phase_id} in '{phase['status']}' status (must be 'planned')"
        )

    milestone_id = phase["milestone_id"]

    plans = list_plans(conn, phase_id)
    if plans:
        conn.execute("DELETE FROM plan WHERE phase_id = ?", (phase_id,))
        logger.info(
            "deleted %d plans for phase %d before removal",
            len(plans),
            phase_id,
        )

    conn.execute("DELETE FROM phase WHERE id = ?", (phase_id,))
    _log_event(conn, "phase", phase_id, phase["status"], "removed")
    conn.commit()

    renumbered = renumber_phases(conn, milestone_id)

    return {
        "removed": phase,
        "renumbered": len(renumbered),
        "message": (
            f"Removed phase '{phase['name']}' (id={phase_id}) "
            f"and {len(plans)} associated plans. "
            f"Renumbered {len(renumbered)} remaining phases."
        ),
    }


@retry_on_busy()
def renumber_phases(conn: sqlite3.Connection, milestone_id: str) -> list[dict]:
    """Reassign integer sequences 1, 2, 3... based on current order.

    Returns a list of dicts describing the renumbering for each phase.
    """
    phases = list_phases(conn, milestone_id)
    results: list[dict] = []

    for idx, phase in enumerate(phases, start=1):
        new_seq = idx
        old_seq = phase["sequence"]

        if old_seq != new_seq:
            conn.execute(
                "UPDATE phase SET sequence = ? WHERE id = ?",
                (new_seq, phase["id"]),
            )
            logger.info(
                "phase %d: sequence %s → %d",
                phase["id"],
                old_seq,
                new_seq,
            )

        results.append(
            {
                "phase_id": phase["id"],
                "old_sequence": old_seq,
                "new_sequence": new_seq,
            }
        )

    conn.commit()
    return results


def list_phases_ordered(conn: sqlite3.Connection, milestone_id: str) -> list[dict]:
    """List phases sorted by sequence, supporting decimal sequences."""
    rows = conn.execute(
        "SELECT * FROM phase WHERE milestone_id = ? ORDER BY sequence",
        (milestone_id,),
    ).fetchall()
    return [dict(row) for row in rows]
