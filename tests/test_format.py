"""Tests for scripts/format.py output formatting utilities."""

from __future__ import annotations

from scripts.format import (
    error,
    header,
    progress_bar,
    status_line,
    step,
    success,
    table,
    warning,
)


class TestHeader:
    def test_default_header(self):
        result = header("My Section")
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert "My Section" in lines[1]
        assert lines[0] == "─" * 60
        assert lines[2] == "─" * 60

    def test_custom_char_and_width(self):
        result = header("Title", char="=", width=20)
        assert "=" * 20 in result
        assert "Title" in result

    def test_leading_newline(self):
        result = header("X")
        assert result.startswith("\n")


class TestStatusLine:
    def test_basic_alignment(self):
        result = status_line("Name", "Meridian")
        assert "Name" in result
        assert "Meridian" in result
        assert result.startswith("  ")

    def test_custom_width(self):
        result = status_line("Key", "Val", width=10)
        # Key should be left-padded to width 10
        assert "Key       " in result

    def test_long_label(self):
        result = status_line("A very long label here", "short")
        assert "A very long label here" in result
        assert "short" in result


class TestTable:
    def test_basic_table(self):
        result = table(["Name", "Age"], [["Alice", "30"], ["Bob", "25"]])
        assert "Name" in result
        assert "Age" in result
        assert "Alice" in result
        assert "Bob" in result
        assert "─" in result

    def test_empty_rows(self):
        result = table(["A", "B"], [])
        assert "(no data)" in result

    def test_mismatched_columns_short_row(self):
        # Row has fewer columns than headers
        result = table(["A", "B", "C"], [["x"]])
        assert "x" in result
        # Should not crash

    def test_mismatched_columns_long_row(self):
        # Row has more columns than headers -- extra cells ignored in width calc
        result = table(["A"], [["x", "extra"]])
        assert "x" in result

    def test_column_width_adapts_to_data(self):
        result = table(["N"], [["LongValue"]])
        # Column should be at least as wide as "LongValue"
        lines = result.split("\n")
        header_line = lines[0]
        divider_line = lines[1]
        # Divider should be at least 9 chars (len("LongValue"))
        divider_content = divider_line.strip()
        assert len(divider_content) >= 9

    def test_custom_padding(self):
        result = table(["A", "B"], [["1", "2"]], padding=5)
        # With padding=5, there should be 5 spaces between columns
        assert "     " in result


class TestProgressBar:
    def test_zero_percent(self):
        result = progress_bar(0, 100)
        assert "0%" in result
        assert "█" not in result
        assert "░" in result

    def test_fifty_percent(self):
        result = progress_bar(50, 100)
        assert "50%" in result
        assert "█" in result
        assert "░" in result

    def test_hundred_percent(self):
        result = progress_bar(100, 100)
        assert "100%" in result
        assert "░" not in result
        assert "█" in result

    def test_zero_total(self):
        result = progress_bar(5, 0)
        assert "0%" in result

    def test_over_hundred(self):
        result = progress_bar(200, 100)
        assert "100%" in result

    def test_custom_width(self):
        result = progress_bar(50, 100, width=10)
        # Bar portion should be 10 chars inside brackets
        bar_content = result.split("[")[1].split("]")[0]
        assert len(bar_content) == 10


class TestStep:
    def test_basic_step(self):
        result = step(1, 3, "Installing")
        assert result == "[1/3] Installing"

    def test_step_numbers(self):
        result = step(10, 20, "Processing")
        assert "[10/20]" in result
        assert "Processing" in result


class TestMessageFormatters:
    def test_success(self):
        result = success("Done")
        assert result == "  OK: Done"

    def test_error(self):
        result = error("Failed")
        assert result == "  ERROR: Failed"

    def test_warning(self):
        result = warning("Careful")
        assert result == "  WARN: Careful"
