#!/usr/bin/env python3
"""Test coverage audit — find scripts without corresponding test files."""

from pathlib import Path


def audit_test_coverage(
    scripts_dir: str | Path,
    tests_dir: str | Path,
) -> dict:
    """Scan scripts/ and tests/ to find coverage gaps.

    Returns:
        {
            "covered": [{"script": str, "test": str}],
            "uncovered": [{"script": str, "expected_test": str}],
            "orphaned_tests": [{"test": str}],
            "coverage_pct": float,
        }
    """
    scripts_dir = Path(scripts_dir)
    tests_dir = Path(tests_dir)

    # Get all script modules (excluding __init__ and private)
    scripts = sorted([
        f.stem for f in scripts_dir.glob("*.py")
        if f.stem != "__init__" and not f.stem.startswith("_")
    ])

    # Get all test modules
    tests = sorted([
        f.stem for f in tests_dir.glob("test_*.py")
    ])

    # Map test names back to module names
    test_modules = {t.removeprefix("test_") for t in tests}

    covered = []
    uncovered = []

    for script in scripts:
        expected_test = f"test_{script}"
        if script in test_modules:
            covered.append({
                "script": f"{script}.py",
                "test": f"{expected_test}.py",
            })
        else:
            uncovered.append({
                "script": f"{script}.py",
                "expected_test": f"{expected_test}.py",
            })

    # Find orphaned tests (tests without corresponding scripts)
    orphaned = []
    for test in tests:
        module_name = test.removeprefix("test_")
        if module_name not in scripts:
            orphaned.append({"test": f"{test}.py"})

    total = len(scripts)
    covered_count = len(covered)
    coverage_pct = round(covered_count / total * 100, 1) if total > 0 else 0.0

    return {
        "covered": covered,
        "uncovered": uncovered,
        "orphaned_tests": orphaned,
        "coverage_pct": coverage_pct,
        "total_scripts": total,
        "total_covered": covered_count,
    }


def format_coverage_report(audit: dict) -> str:
    """Format coverage audit as markdown."""
    lines = [
        "## Test Coverage Audit",
        "",
        f"**Coverage: {audit['coverage_pct']}%** ({audit['total_covered']}/{audit['total_scripts']} modules)",
        "",
    ]

    if audit["uncovered"]:
        lines.append("### Uncovered Modules")
        for item in audit["uncovered"]:
            lines.append(f"- `{item['script']}` → needs `{item['expected_test']}`")
        lines.append("")

    if audit["covered"]:
        lines.append("### Covered Modules")
        for item in audit["covered"]:
            lines.append(f"- `{item['script']}` ✓")
        lines.append("")

    if audit["orphaned_tests"]:
        lines.append("### Orphaned Tests (no matching script)")
        for item in audit["orphaned_tests"]:
            lines.append(f"- `{item['test']}`")
        lines.append("")

    return "\n".join(lines)
