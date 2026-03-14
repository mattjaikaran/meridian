#!/usr/bin/env python3
"""Tests for Meridian context window estimation module."""

from scripts.context_window import (
    AUTO_CHECKPOINT_TOKENS,
    SUBAGENT_CONTEXT_BUDGET,
    TOKENS_PER_CHAR,
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


class TestEstimateTokensEdgeCases:
    """Additional edge cases for estimate_tokens."""

    def test_unicode_characters(self):
        """Unicode chars are counted by Python len() (char count, not bytes)."""
        text = "\u2728\U0001f600\u2603"  # sparkles, grinning face, snowman
        result = estimate_tokens(text)
        assert result == int(len(text) * TOKENS_PER_CHAR)

    def test_very_large_input(self):
        """1MB input returns correct estimate without error."""
        text = "x" * 1_000_000
        result = estimate_tokens(text)
        assert result == int(1_000_000 * TOKENS_PER_CHAR)

    def test_whitespace_only(self):
        """Whitespace-only strings are estimated normally."""
        text = "   \n\t\n   "
        result = estimate_tokens(text)
        assert result == int(len(text) * TOKENS_PER_CHAR)

    def test_single_character(self):
        """Single character returns 0 (int(0.3) == 0)."""
        assert estimate_tokens("a") == 0

    def test_four_characters_returns_one(self):
        """Four characters: int(4 * 0.3) = int(1.2) = 1."""
        assert estimate_tokens("abcd") == 1


class TestEstimateFileTokensEdgeCases:
    """Additional edge cases for estimate_file_tokens."""

    def test_empty_file(self, tmp_path):
        """Empty file returns 0."""
        f = tmp_path / "empty.txt"
        f.write_text("")
        assert estimate_file_tokens(str(f)) == 0

    def test_directory_path_returns_zero(self, tmp_path):
        """Passing a directory instead of file returns 0 (IsADirectoryError is OSError)."""
        result = estimate_file_tokens(str(tmp_path))
        assert result == 0

    def test_large_file(self, tmp_path):
        """Large file estimation works correctly."""
        f = tmp_path / "large.txt"
        content = "line\n" * 100_000  # 500K chars
        f.write_text(content)
        result = estimate_file_tokens(str(f))
        assert result == int(len(content) * TOKENS_PER_CHAR)


class TestShouldCheckpointEdgeCases:
    """Additional edge cases for should_checkpoint."""

    def test_custom_threshold_below(self):
        """Custom threshold: below returns False."""
        assert should_checkpoint(50, threshold=100) is False

    def test_custom_threshold_at(self):
        """Custom threshold: at threshold returns True."""
        assert should_checkpoint(100, threshold=100) is True

    def test_custom_threshold_above(self):
        """Custom threshold: above returns True."""
        assert should_checkpoint(200, threshold=100) is True

    def test_threshold_zero_with_zero_tokens(self):
        """Threshold of 0 with 0 tokens: 0 >= 0 is True."""
        assert should_checkpoint(0, threshold=0) is True

    def test_threshold_zero_with_positive_tokens(self):
        """Threshold of 0 with positive tokens returns True."""
        assert should_checkpoint(1, threshold=0) is True

    def test_uses_constant_as_default(self):
        """Default threshold matches AUTO_CHECKPOINT_TOKENS constant."""
        assert should_checkpoint(AUTO_CHECKPOINT_TOKENS - 1) is False
        assert should_checkpoint(AUTO_CHECKPOINT_TOKENS) is True


class TestEstimatePlanContextEdgeCases:
    """Additional edge cases for estimate_plan_context."""

    def test_with_missing_file_paths(self):
        """Missing files contribute 0 tokens without crashing."""
        result = estimate_plan_context("desc", file_paths=["/nonexistent/file.py"])
        expected = estimate_tokens("desc") + 0 + 5000
        assert result == expected

    def test_multiple_files(self, tmp_path):
        """Multiple files are all summed."""
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f3 = tmp_path / "c.py"
        f1.write_text("aaaa")  # 4 chars
        f2.write_text("bbbbbb")  # 6 chars
        f3.write_text("cc")  # 2 chars

        result = estimate_plan_context("x", file_paths=[str(f1), str(f2), str(f3)])
        expected = (
            estimate_tokens("x")
            + estimate_file_tokens(str(f1))
            + estimate_file_tokens(str(f2))
            + estimate_file_tokens(str(f3))
            + 5000
        )
        assert result == expected

    def test_empty_file_paths_list(self):
        """Empty file_paths list is handled (no files to add)."""
        result = estimate_plan_context("desc", file_paths=[])
        expected = estimate_tokens("desc") + 5000
        assert result == expected

    def test_empty_description_with_context(self):
        """Empty description with context doc still works."""
        result = estimate_plan_context("", context_doc="some context")
        expected = 0 + estimate_tokens("some context") + 5000
        assert result == expected


class TestFitsInSubagentEdgeCases:
    """Additional edge cases for fits_in_subagent."""

    def test_just_below_budget(self):
        """One token below budget fits."""
        assert fits_in_subagent(SUBAGENT_CONTEXT_BUDGET - 1) is True

    def test_negative_value(self):
        """Negative token count fits (edge case, shouldn't happen in practice)."""
        assert fits_in_subagent(-1) is True

    def test_uses_strict_less_than(self):
        """Boundary: exactly at budget does NOT fit (strict less-than)."""
        assert fits_in_subagent(SUBAGENT_CONTEXT_BUDGET) is False
        assert fits_in_subagent(SUBAGENT_CONTEXT_BUDGET - 1) is True
