"""Consistent output formatting for Meridian skills.

Provides helpers for tables, status messages, progress indicators,
and section headers to ensure uniform UX across all commands.
"""

from __future__ import annotations


def header(title: str, char: str = "─", width: int = 60) -> str:
    """Format a section header with decorative line."""
    line = char * width
    return f"\n{line}\n  {title}\n{line}"


def status_line(label: str, value: str, width: int = 30) -> str:
    """Format a key-value status line with aligned columns."""
    return f"  {label:<{width}} {value}"


def table(headers: list[str], rows: list[list[str]], padding: int = 2) -> str:
    """Format data as an aligned text table.

    Args:
        headers: Column header names
        rows: List of row data (each row is a list of strings)
        padding: Spaces between columns

    Returns:
        Formatted table string
    """
    if not rows:
        return "  (no data)"

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))

    sep = " " * padding

    # Header row
    header_line = sep.join(h.ljust(w) for h, w in zip(headers, col_widths))
    divider = sep.join("─" * w for w in col_widths)

    # Data rows
    data_lines = []
    for row in rows:
        cells = []
        for i, w in enumerate(col_widths):
            cell = str(row[i]) if i < len(row) else ""
            cells.append(cell.ljust(w))
        data_lines.append(sep.join(cells))

    return "\n".join(["  " + header_line, "  " + divider] + ["  " + line for line in data_lines])


def progress_bar(current: int, total: int, width: int = 30) -> str:
    """Format a text-based progress bar.

    Args:
        current: Current progress value
        total: Total/target value
        width: Character width of the bar

    Returns:
        Formatted progress bar like [████████░░░░░░░] 53%
    """
    if total <= 0:
        pct = 0
    else:
        pct = min(100, int(current / total * 100))

    filled = int(width * pct / 100)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"[{bar}] {pct}%"


def step(number: int, total: int, message: str) -> str:
    """Format a step indicator for multi-step operations."""
    return f"[{number}/{total}] {message}"


def success(message: str) -> str:
    """Format a success message."""
    return f"  OK: {message}"


def error(message: str) -> str:
    """Format an error message."""
    return f"  ERROR: {message}"


def warning(message: str) -> str:
    """Format a warning message."""
    return f"  WARN: {message}"
