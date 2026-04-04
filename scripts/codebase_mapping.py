#!/usr/bin/env python3
"""Codebase mapping and analysis for Meridian workflow engine.

Plans and manages domain-specific codebase scans using Explore subagents.
Each domain (architecture, stack, testing, etc.) gets a focused analysis
prompt and produces a markdown report stored in .meridian/codebase/.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

ANALYSIS_DOMAINS: list[dict] = [
    {
        "name": "architecture",
        "focus": "High-level architecture, modules, dependencies",
    },
    {
        "name": "stack",
        "focus": "Languages, frameworks, build tools, package managers",
    },
    {
        "name": "structure",
        "focus": (
            "Directory layout, naming conventions, file organization"
        ),
    },
    {
        "name": "testing",
        "focus": "Test framework, patterns, coverage, fixtures",
    },
    {
        "name": "conventions",
        "focus": "Code style, patterns, error handling, logging",
    },
    {
        "name": "integrations",
        "focus": (
            "External services, APIs, databases, message queues"
        ),
    },
    {
        "name": "concerns",
        "focus": (
            "Tech debt, security issues, performance bottlenecks"
        ),
    },
]


def generate_analysis_prompt(domain: dict, project_dir: str) -> str:
    """Build a focused prompt for an Explore subagent analyzing one domain.

    Args:
        domain: Dict with 'name' and 'focus' keys.
        project_dir: Absolute path to the project root.

    Returns:
        Prompt string for the subagent.
    """
    name = domain["name"]
    focus = domain["focus"]
    return (
        f"Analyze the codebase at {project_dir} focusing on"
        f" **{name}**.\n\n"
        f"Focus area: {focus}\n\n"
        "Output format:\n"
        f"# {name.title()} Analysis\n\n"
        "Use markdown with headers for each finding. Include:\n"
        "- Key observations with file paths as evidence\n"
        "- Patterns and conventions detected\n"
        "- Notable decisions or trade-offs\n"
        "- Recommendations if applicable\n"
    )


def plan_codebase_scan(
    project_dir: str,
    domains: list[str] | None = None,
) -> list[dict]:
    """Plan which domains to scan.

    Args:
        project_dir: Absolute path to the project root.
        domains: Optional list of domain names to filter to.
            Uses all 7 domains when None.

    Returns:
        List of dicts with 'domain', 'prompt', and 'output_file' keys.
    """
    selected = ANALYSIS_DOMAINS
    if domains is not None:
        domain_set = set(domains)
        selected = [d for d in ANALYSIS_DOMAINS if d["name"] in domain_set]
        missing = domain_set - {d["name"] for d in selected}
        if missing:
            logger.warning("Unknown domains requested: %s", missing)

    plans: list[dict] = []
    for domain in selected:
        name = domain["name"]
        output_file = str(
            Path(project_dir) / ".meridian" / "codebase" / f"{name}.md"
        )
        plans.append(
            {
                "domain": name,
                "prompt": generate_analysis_prompt(domain, project_dir),
                "output_file": output_file,
            }
        )
    return plans


def save_analysis(
    project_dir: str, domain: str, content: str
) -> str:
    """Write analysis content to .meridian/codebase/{domain}.md.

    Args:
        project_dir: Absolute path to the project root.
        domain: Domain name (e.g. 'architecture').
        content: Markdown content to write.

    Returns:
        Absolute path to the written file.
    """
    output_path = (
        Path(project_dir) / ".meridian" / "codebase" / f"{domain}.md"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    logger.info("Saved %s analysis to %s", domain, output_path)
    return str(output_path)


def load_analysis(
    project_dir: str, domain: str | None = None
) -> dict[str, str]:
    """Load one or all analysis docs from .meridian/codebase/.

    Args:
        project_dir: Absolute path to the project root.
        domain: Single domain name to load, or None for all.

    Returns:
        Mapping of domain name to markdown content.
    """
    codebase_dir = Path(project_dir) / ".meridian" / "codebase"
    results: dict[str, str] = {}

    if domain is not None:
        target = codebase_dir / f"{domain}.md"
        if target.is_file():
            results[domain] = target.read_text(encoding="utf-8")
        else:
            logger.warning(
                "Analysis not found for domain %s at %s",
                domain,
                target,
            )
        return results

    if not codebase_dir.is_dir():
        logger.warning("Codebase directory not found: %s", codebase_dir)
        return results

    for path in sorted(codebase_dir.glob("*.md")):
        results[path.stem] = path.read_text(encoding="utf-8")
    return results


def generate_scan_summary(analyses: dict[str, str]) -> str:
    """Combine all domain analyses into a summary markdown.

    Args:
        analyses: Mapping of domain name to markdown content.

    Returns:
        Formatted summary string.
    """
    if not analyses:
        return "# Codebase Scan Summary\n\nNo analyses available.\n"

    sections: list[str] = ["# Codebase Scan Summary\n"]
    sections.append(
        f"Scanned {len(analyses)} domain(s):"
        f" {', '.join(sorted(analyses.keys()))}\n"
    )

    for domain in sorted(analyses.keys()):
        content = analyses[domain]
        sections.append(f"---\n\n## {domain.title()}\n\n{content}\n")

    return "\n".join(sections)
