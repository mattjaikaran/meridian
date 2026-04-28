#!/usr/bin/env python3
"""Party mode review — concurrent multi-perspective review synthesis."""

import json
import re
from pathlib import Path


_PERSPECTIVES = {
    "code-quality": {
        "label": "Code Quality",
        "tag": "CODE",
        "focus": (
            "Review for correctness, maintainability, and performance. "
            "Check: naming clarity, function complexity, duplication, dead code, "
            "error handling completeness, and algorithmic efficiency. "
            "Flag anything that will hurt the next developer."
        ),
    },
    "security": {
        "label": "Security",
        "tag": "SEC",
        "focus": (
            "Review for OWASP Top 10 vulnerabilities and common security issues. "
            "Check: injection vectors, auth/authz gaps, sensitive data exposure, "
            "unsafe deserialization, insecure dependencies, missing input validation, "
            "hardcoded secrets, and overly permissive CORS or headers. "
            "Rate each finding: CRITICAL, HIGH, MEDIUM, or LOW."
        ),
    },
    "ux": {
        "label": "UX / Accessibility",
        "tag": "UX",
        "focus": (
            "Review for user experience and accessibility. "
            "Check: loading states, error messages (are they actionable?), "
            "keyboard navigation, ARIA labels, color contrast, responsive layout, "
            "form validation feedback, and empty states. "
            "Only apply to frontend code — skip for backend-only changes."
        ),
    },
}


def build_reviewer_prompt(
    perspective_key: str,
    changed_files: list[str],
    phase_name: str,
    phase_description: str,
    file_contents: dict[str, str] | None = None,
) -> str:
    """Build an independent reviewer prompt for a given perspective."""
    p = _PERSPECTIVES[perspective_key]
    files_block = "\n".join(f"- {f}" for f in changed_files) if changed_files else "- (no files)"

    content_block = ""
    if file_contents:
        sections = []
        for path, content in file_contents.items():
            sections.append(f"### {path}\n```\n{content}\n```")
        content_block = "\n\n## File Contents\n\n" + "\n\n".join(sections)

    return f"""# {p['label']} Review

You are an independent {p['label']} reviewer. You are NOT aware of any other reviewers.
Your job is to find real issues — not to validate work that is already done.

## Your Focus
{p['focus']}

## Phase Under Review
**Name:** {phase_name}
**Description:** {phase_description}

## Changed Files
{files_block}{content_block}

## Output Format

Return a JSON object with this exact structure:
```json
{{
  "perspective": "{perspective_key}",
  "verdict": "PASS" | "PASS_WITH_NOTES" | "REQUEST_CHANGES",
  "findings": [
    {{
      "severity": "critical" | "high" | "medium" | "low" | "note",
      "file": "<path or null>",
      "line": <int or null>,
      "summary": "<one-line summary>",
      "detail": "<explanation and suggested fix>"
    }}
  ],
  "summary": "<2-3 sentence overall assessment>"
}}
```

Do not include any text outside the JSON block.
"""


def synthesize_findings(reviewer_outputs: list[dict]) -> dict:
    """Merge findings from multiple reviewers into a unified result.

    Each reviewer_output dict must have keys:
      perspective, verdict, findings, summary

    Returns a unified dict with:
      overall_verdict, findings (tagged with source), summary_by_perspective,
      critical_count, total_findings
    """
    verdict_rank = {"REQUEST_CHANGES": 2, "PASS_WITH_NOTES": 1, "PASS": 0}
    overall_rank = 0
    all_findings = []
    summary_by_perspective = {}

    for output in reviewer_outputs:
        p_key = output.get("perspective", "unknown")
        p_info = _PERSPECTIVES.get(p_key, {"tag": p_key.upper(), "label": p_key})
        tag = p_info["tag"]

        verdict = output.get("verdict", "PASS")
        overall_rank = max(overall_rank, verdict_rank.get(verdict, 0))
        summary_by_perspective[p_info["label"]] = output.get("summary", "")

        for finding in output.get("findings", []):
            all_findings.append({**finding, "source": tag})

    rank_to_verdict = {2: "REQUEST_CHANGES", 1: "PASS_WITH_NOTES", 0: "PASS"}
    overall_verdict = rank_to_verdict[overall_rank]

    critical_count = sum(
        1 for f in all_findings if f.get("severity") in ("critical", "high")
    )

    return {
        "overall_verdict": overall_verdict,
        "findings": all_findings,
        "summary_by_perspective": summary_by_perspective,
        "critical_count": critical_count,
        "total_findings": len(all_findings),
    }


def format_review_md(
    phase_name: str,
    synthesis: dict,
    reviewer_outputs: list[dict],
) -> str:
    """Render synthesis + per-perspective summaries as REVIEW.md content."""
    verdict = synthesis["overall_verdict"]
    verdict_emoji = {"REQUEST_CHANGES": "FAIL", "PASS_WITH_NOTES": "PASS (notes)", "PASS": "PASS"}.get(verdict, verdict)

    lines = [
        f"# Party Review — {phase_name}",
        "",
        f"**Overall Verdict:** {verdict_emoji}  ",
        f"**Findings:** {synthesis['total_findings']} total, {synthesis['critical_count']} critical/high",
        "",
        "## Perspective Summaries",
        "",
    ]

    for label, summary in synthesis["summary_by_perspective"].items():
        lines += [f"### {label}", "", summary, ""]

    lines += ["## All Findings", ""]

    severity_order = ["critical", "high", "medium", "low", "note"]
    findings = sorted(
        synthesis["findings"],
        key=lambda f: (
            severity_order.index(f.get("severity", "note")) if f.get("severity") in severity_order else 99
        ),
    )

    if not findings:
        lines.append("_No findings._")
    else:
        for f in findings:
            sev = f.get("severity", "note").upper()
            source = f.get("source", "?")
            file_ref = f.get("file") or ""
            line_ref = f" L{f['line']}" if f.get("line") else ""
            summary = f.get("summary", "")
            detail = f.get("detail", "")
            lines += [
                f"### [{source}] {sev} — {summary}",
                "",
            ]
            if file_ref:
                lines.append(f"**File:** `{file_ref}`{line_ref}  ")
            if detail:
                lines.append(detail)
            lines.append("")

    return "\n".join(lines)


def parse_json_from_output(raw: str) -> dict:
    """Extract a JSON object from reviewer output, ignoring surrounding text."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"(\{.*\})", raw, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    raise ValueError("No JSON found in reviewer output")


def list_perspectives() -> list[dict]:
    """Return metadata for all available review perspectives."""
    return [
        {"key": k, "label": v["label"], "tag": v["tag"]}
        for k, v in _PERSPECTIVES.items()
    ]
