"""Roadmap sync module -- pure text transformations for ROADMAP.md and REQUIREMENTS.md.

Updates markdown checkboxes, progress table rows, and traceability status
using regex substitution. All functions are pure (text in, text out) with
no file I/O. Missing targets return text unchanged with a logged warning.
"""

import logging
import re

logger = logging.getLogger(__name__)


def sync_roadmap_plan_checkbox(
    text: str, plan_slug: str, is_complete: bool,
) -> str:
    """Toggle a plan checkbox line in ROADMAP.md.

    Finds ``- [ ] {plan_slug}`` or ``- [x] {plan_slug}`` and sets the
    checkbox to match *is_complete*. Returns text unchanged if the slug
    is not found.
    """
    if not text:
        return text

    mark = "x" if is_complete else " "
    escaped_slug = re.escape(plan_slug)
    pattern = rf"^(- \[)[ x](\] {escaped_slug})"

    new_text, count = re.subn(
        pattern, rf"\g<1>{mark}\2", text, flags=re.MULTILINE,
    )
    if count == 0:
        logger.warning("Plan slug %r not found in roadmap text", plan_slug)
    return new_text


def sync_roadmap_phase_checkbox(
    text: str, phase_number: int, is_complete: bool,
) -> str:
    """Toggle a phase checkbox line in ROADMAP.md milestone section.

    Targets lines like ``- [ ] **Phase N:`` and sets the checkbox
    to match *is_complete*. Returns text unchanged if the phase
    line is not found.
    """
    if not text:
        return text

    mark = "x" if is_complete else " "
    pattern = rf"^(- \[)[ x](\] \*\*Phase {phase_number}:)"

    new_text, count = re.subn(
        pattern, rf"\g<1>{mark}\2", text, flags=re.MULTILINE,
    )
    if count == 0:
        logger.warning(
            "Phase %d checkbox not found in roadmap text", phase_number,
        )
    return new_text


def sync_roadmap_progress_table(
    text: str,
    phase_number: int,
    status: str,
    completed_date: str | None = None,
) -> str:
    """Update a progress table row in ROADMAP.md.

    Targets the row starting with ``| N. `` and replaces the Status
    and Completed columns. Returns text unchanged if the row is not found.
    """
    if not text:
        return text

    date_str = completed_date if completed_date else "-"

    # Match table row: | N. Phase Name | milestone | plans | Status | Date |
    pattern = rf"^(\| {phase_number}\. [^|]+\|[^|]+\|[^|]+\|)[^|]+\|[^|]+\|"

    def _replace_row(m: re.Match) -> str:
        return f"{m.group(1)} {status} | {date_str} |"

    new_text, count = re.subn(
        pattern, _replace_row, text, flags=re.MULTILINE,
    )
    if count == 0:
        logger.warning(
            "Progress table row for phase %d not found", phase_number,
        )
    return new_text


def sync_requirements_status(
    text: str, req_id: str, new_status: str,
) -> str:
    """Update a requirement's status in the REQUIREMENTS.md traceability table.

    Targets the row containing ``| {req_id} |`` and replaces the status
    column. Returns text unchanged if the requirement is not found.
    """
    if not text:
        return text

    escaped_id = re.escape(req_id)
    # Match: | REQ-ID | Phase N | OldStatus |
    pattern = rf"^(\| {escaped_id} \|[^|]+\|)[^|]+\|"

    def _replace_status(m: re.Match) -> str:
        return f"{m.group(1)} {new_status} |"

    new_text, count = re.subn(
        pattern, _replace_status, text, flags=re.MULTILINE,
    )
    if count == 0:
        logger.warning("Requirement %r not found in traceability table", req_id)
    return new_text
