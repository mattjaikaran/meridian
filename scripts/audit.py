#!/usr/bin/env python3
"""UAT audit scanning — collect verification debt across all phases.

Scans phase directories for outstanding verification items including
unchecked sign-off items in VALIDATION.md and pending human verification
in VERIFICATION.md. Uses only the standard library.
"""

import re
from pathlib import Path

from scripts.nyquist import _find_validation_md, _parse_frontmatter


def _find_verification_md(phase_dir: Path) -> Path | None:
    """Find the VERIFICATION.md file in a phase directory.

    Handles both `VERIFICATION.md` and `NN-VERIFICATION.md` naming conventions.
    """
    matches = sorted(phase_dir.glob("*VERIFICATION.md"))
    return matches[0] if matches else None


def _extract_unchecked_items(text: str) -> list[str]:
    """Extract unchecked markdown checkbox items from text.

    Matches lines like: - [ ] Some description
    """
    return re.findall(r"^[\s]*-\s*\[\s*\]\s*(.+)$", text, re.MULTILINE)


def _extract_human_verification_items(text: str) -> list[dict[str, str]]:
    """Extract human verification sections from VERIFICATION.md.

    Looks for ### N. Title sections under "Human Verification Required"
    and checks if they have a confirmation marker.
    """
    items: list[dict[str, str]] = []

    # Find the Human Verification Required section
    hv_match = re.search(
        r"##\s*Human Verification Required\s*\n(.*?)(?=\n##\s[^#]|\Z)",
        text,
        re.DOTALL,
    )
    if not hv_match:
        return items

    hv_section = hv_match.group(1)

    # Extract numbered subsections
    subsections = re.findall(
        r"###\s*\d+\.\s*(.+?)(?=\n###|\Z)",
        hv_section,
        re.DOTALL,
    )

    for sub in subsections:
        title_line = sub.strip().split("\n")[0].strip()
        # Check if confirmed (look for "confirmed", "verified", "done" markers)
        body = sub.strip()
        confirmed = bool(
            re.search(r"\b(confirmed|verified|done|passed)\b", body, re.IGNORECASE)
            and re.search(r"\*\*Status:\s*(confirmed|verified|done|passed)", body, re.IGNORECASE)
        )
        if not confirmed:
            items.append({
                "title": title_line,
                "status": "pending",
            })

    return items


def collect_verification_debt(
    planning_dir: Path,
) -> list[dict]:
    """Scan all phases for outstanding verification items.

    For each phase directory:
    1. Parse VALIDATION.md for unchecked sign-off items (- [ ])
    2. Parse VERIFICATION.md for pending human verification items
    3. Check verification status from frontmatter

    Args:
        planning_dir: Path to the .planning directory.

    Returns:
        List of per-phase dicts with keys: phase_name, phase_num,
        unchecked_signoff, pending_human, status, has_debt.
    """
    phases_dir = planning_dir / "phases"
    if not phases_dir.is_dir():
        return []

    results: list[dict] = []

    for phase_dir in sorted(phases_dir.iterdir()):
        if not phase_dir.is_dir():
            continue

        # Extract phase number
        match = re.match(r"^(\d+)", phase_dir.name)
        phase_num = int(match.group(1)) if match else 0

        phase_result: dict = {
            "phase_name": phase_dir.name,
            "phase_num": phase_num,
            "unchecked_signoff": [],
            "pending_human": [],
            "status": "unknown",
            "has_debt": False,
        }

        # Check VALIDATION.md for unchecked sign-off items
        vmd = _find_validation_md(phase_dir)
        if vmd is not None:
            text = vmd.read_text()
            fm, body = _parse_frontmatter(text)

            # Get sign-off section unchecked items
            signoff_match = re.search(
                r"##\s*Validation Sign-Off\s*\n(.*?)(?=\n##|\Z)",
                body,
                re.DOTALL,
            )
            if signoff_match:
                phase_result["unchecked_signoff"] = _extract_unchecked_items(
                    signoff_match.group(1)
                )

            if fm:
                phase_result["status"] = fm.get("status", "unknown")

        # Check VERIFICATION.md for human verification items
        ver_md = _find_verification_md(phase_dir)
        if ver_md is not None:
            ver_text = ver_md.read_text()
            phase_result["pending_human"] = _extract_human_verification_items(
                ver_text
            )

        phase_result["has_debt"] = bool(
            phase_result["unchecked_signoff"] or phase_result["pending_human"]
        )

        results.append(phase_result)

    return results


def audit_uat(
    planning_dir: Path = Path(".planning"),
) -> dict:
    """Run full UAT audit across all phases.

    Produces a structured report and formatted markdown summary.

    Args:
        planning_dir: Path to the .planning directory.

    Returns:
        Dict with keys: phases, total_debt, has_debt, report.
        report is a formatted markdown string.
    """
    phases = collect_verification_debt(planning_dir)

    total_signoff = sum(len(p["unchecked_signoff"]) for p in phases)
    total_human = sum(len(p["pending_human"]) for p in phases)
    total_debt = total_signoff + total_human
    has_debt = total_debt > 0

    # Build markdown report
    lines: list[str] = [
        "# UAT Audit Report",
        "",
        f"**Total verification debt:** {total_debt} item(s)",
        f"- Unchecked sign-off items: {total_signoff}",
        f"- Pending human verification: {total_human}",
        "",
    ]

    for phase in phases:
        if phase["has_debt"]:
            lines.append(f"## {phase['phase_name']}")
            lines.append("")

            if phase["unchecked_signoff"]:
                lines.append(f"### Unchecked Sign-Off ({len(phase['unchecked_signoff'])})")
                for item in phase["unchecked_signoff"]:
                    lines.append(f"- [ ] {item}")
                lines.append("")

            if phase["pending_human"]:
                lines.append(f"### Pending Human Verification ({len(phase['pending_human'])})")
                for item in phase["pending_human"]:
                    lines.append(f"- [ ] {item['title']}")
                lines.append("")
        else:
            lines.append(f"## {phase['phase_name']} -- all clear")
            lines.append("")

    report = "\n".join(lines)

    return {
        "phases": phases,
        "total_debt": total_debt,
        "has_debt": has_debt,
        "report": report,
    }
