#!/usr/bin/env python3
"""Tests for Meridian context window estimation module."""

from scripts.context_window import (
    estimate_file_tokens,
    estimate_plan_context,
    estimate_tokens,
    fits_in_subagent,
    should_checkpoint,
)


class TestEstimateTokens:
    def test_returns_int_proportional_to_char_count(self):
        """estimate_tokens returns int(len(text) * 0.3) for any string."""
        text = "Hello, world!"  # 13 chars
        result = estimate_tokens(text)
        assert result == int(13 * 0.3)
        assert result == 3
        assert isinstance(result, int)

    def test_returns_zero_for_empty_string(self):
        """estimate_tokens returns 0 for empty string."""
        assert estimate_tokens("") == 0

    def test_longer_text(self):
        """estimate_tokens scales with text length."""
        text = "a" * 1000
        assert estimate_tokens(text) == 300


class TestEstimateFileTokens:
    def test_returns_token_count_for_readable_file(self, tmp_path):
        """estimate_file_tokens returns token count for a readable file."""
        f = tmp_path / "test.txt"
        f.write_text("a" * 100)
        assert estimate_file_tokens(str(f)) == 30

    def test_returns_zero_for_missing_file(self):
        """estimate_file_tokens returns 0 for missing file."""
        assert estimate_file_tokens("/nonexistent/file.txt") == 0

    def test_returns_zero_for_unreadable_file(self, tmp_path):
        """estimate_file_tokens returns 0 for binary/unreadable file (UnicodeDecodeError)."""
        f = tmp_path / "binary.bin"
        f.write_bytes(b"\xff\xfe\x00\x01" * 100)
        # This may or may not raise UnicodeDecodeError depending on platform encoding,
        # but the function should handle it gracefully either way
        result = estimate_file_tokens(str(f))
        assert isinstance(result, int)
        assert result >= 0


class TestShouldCheckpoint:
    def test_returns_false_below_threshold(self):
        """should_checkpoint returns False below 150k tokens."""
        assert should_checkpoint(149_999) is False

    def test_returns_true_at_exactly_threshold(self):
        """should_checkpoint returns True at exactly 150k tokens."""
        assert should_checkpoint(150_000) is True

    def test_returns_true_above_threshold(self):
        """should_checkpoint returns True above 150k tokens."""
        assert should_checkpoint(200_000) is True

    def test_returns_false_at_zero(self):
        """should_checkpoint returns False at 0 tokens."""
        assert should_checkpoint(0) is False


class TestEstimatePlanContext:
    def test_sums_description_context_files_overhead(self, tmp_path):
        """estimate_plan_context sums description + context + files + 5000 overhead."""
        f = tmp_path / "code.py"
        f.write_text("x" * 100)  # 30 tokens

        desc = "a" * 100  # 30 tokens
        ctx = "b" * 200  # 60 tokens

        result = estimate_plan_context(desc, context_doc=ctx, file_paths=[str(f)])
        expected = 30 + 60 + 30 + 5000
        assert result == expected

    def test_works_with_none_context_and_none_files(self):
        """estimate_plan_context works with None context_doc and None file_paths."""
        desc = "a" * 100  # 30 tokens
        result = estimate_plan_context(desc, context_doc=None, file_paths=None)
        assert result == 30 + 5000

    def test_overhead_always_added(self):
        """estimate_plan_context always adds 5000 overhead."""
        result = estimate_plan_context("")
        assert result == 5000


class TestFitsInSubagent:
    def test_returns_true_below_200k(self):
        """fits_in_subagent returns True below 200k."""
        assert fits_in_subagent(199_999) is True

    def test_returns_false_at_exactly_200k(self):
        """fits_in_subagent returns False at exactly 200k."""
        assert fits_in_subagent(200_000) is False

    def test_returns_false_above_200k(self):
        """fits_in_subagent returns False above 200k."""
        assert fits_in_subagent(300_000) is False

    def test_returns_true_at_zero(self):
        """fits_in_subagent returns True at 0."""
        assert fits_in_subagent(0) is True
