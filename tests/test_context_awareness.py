#!/usr/bin/env python3
"""Tests for context window awareness module."""

import os

from scripts.context_awareness import (
    CODE_FRACTION,
    DEFAULT_CONTEXT_SIZE,
    LARGE_CONTEXT_THRESHOLD,
    MODEL_CONTEXT_SIZES,
    PLAN_FRACTION,
    RESERVE_FRACTION,
    SYSTEM_FRACTION,
    WARNING_THRESHOLD,
    ContextBudget,
    allocate_context_budget,
    check_budget_warning,
    detect_context_size,
    trim_to_budget,
)


class TestDetectContextSize:
    def test_returns_default_when_no_model(self):
        result = detect_context_size()
        assert result == DEFAULT_CONTEXT_SIZE

    def test_returns_known_model_size(self):
        result = detect_context_size(model="claude-opus-4-6")
        assert result == 1_000_000

    def test_returns_default_for_unknown_model(self):
        result = detect_context_size(model="unknown-model-xyz")
        assert result == DEFAULT_CONTEXT_SIZE

    def test_override_takes_priority(self):
        result = detect_context_size(model="claude-opus-4-6", override=42_000)
        assert result == 42_000

    def test_env_var_takes_priority_over_model(self, monkeypatch):
        monkeypatch.setenv("MERIDIAN_CONTEXT_SIZE", "500000")
        result = detect_context_size(model="claude-opus-4-6")
        assert result == 500_000

    def test_override_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("MERIDIAN_CONTEXT_SIZE", "500000")
        result = detect_context_size(override=99_000)
        assert result == 99_000

    def test_invalid_env_var_falls_through(self, monkeypatch):
        monkeypatch.setenv("MERIDIAN_CONTEXT_SIZE", "not_a_number")
        result = detect_context_size(model="claude-sonnet-4")
        assert result == MODEL_CONTEXT_SIZES["claude-sonnet-4"]

    def test_all_known_models_have_positive_sizes(self):
        for model, size in MODEL_CONTEXT_SIZES.items():
            assert size > 0, f"{model} has non-positive context size"


class TestAllocateContextBudget:
    def test_allocates_correct_fractions(self):
        budget = allocate_context_budget(total=100_000)
        assert budget.total == 100_000
        assert budget.system == int(100_000 * SYSTEM_FRACTION)
        assert budget.plan == int(100_000 * PLAN_FRACTION)
        assert budget.code == int(100_000 * CODE_FRACTION)
        assert budget.reserve == int(100_000 * RESERVE_FRACTION)

    def test_fractions_sum_to_one(self):
        total = SYSTEM_FRACTION + PLAN_FRACTION + CODE_FRACTION + RESERVE_FRACTION
        assert abs(total - 1.0) < 1e-9

    def test_auto_detects_when_total_not_given(self):
        budget = allocate_context_budget(model="claude-opus-4-6")
        assert budget.total == 1_000_000

    def test_is_large_context_for_1m(self):
        budget = allocate_context_budget(total=1_000_000)
        assert budget.is_large_context is True

    def test_is_not_large_context_for_200k(self):
        budget = allocate_context_budget(total=200_000)
        assert budget.is_large_context is False

    def test_small_total(self):
        budget = allocate_context_budget(total=100)
        assert budget.system == 10
        assert budget.plan == 20
        assert budget.code == 50
        assert budget.reserve == 20


class TestTrimToBudget:
    def test_no_trim_when_within_budget(self):
        content = "short text"
        result, trimmed = trim_to_budget(content, budget_tokens=1000)
        assert result == content
        assert trimmed is False

    def test_trims_when_over_budget(self):
        content = "x" * 10_000  # ~3000 tokens
        result, trimmed = trim_to_budget(content, budget_tokens=100)
        assert trimmed is True
        assert len(result) < len(content)

    def test_tail_strategy_keeps_end(self):
        content = "START" + "x" * 10_000 + "END"
        result, trimmed = trim_to_budget(content, budget_tokens=100, strategy="tail")
        assert trimmed is True
        assert "END" in result
        assert "START" not in result

    def test_head_strategy_keeps_beginning(self):
        content = "START" + "x" * 10_000 + "END"
        result, trimmed = trim_to_budget(content, budget_tokens=100, strategy="head")
        assert trimmed is True
        assert "START" in result
        assert "END" not in result

    def test_zero_budget_returns_empty(self):
        result, trimmed = trim_to_budget("some content", budget_tokens=0)
        assert result == ""
        assert trimmed is True

    def test_includes_trim_indicator_tail(self):
        content = "x" * 10_000
        result, _ = trim_to_budget(content, budget_tokens=100, strategy="tail")
        assert "trimmed" in result.lower()

    def test_includes_trim_indicator_head(self):
        content = "x" * 10_000
        result, _ = trim_to_budget(content, budget_tokens=100, strategy="head")
        assert "trimmed" in result.lower()

    def test_exact_budget_no_trim(self):
        # 10 chars at 0.3 tokens/char = 3 tokens
        content = "abcdefghij"
        result, trimmed = trim_to_budget(content, budget_tokens=3)
        assert result == content
        assert trimmed is False


class TestCheckBudgetWarning:
    def test_no_warning_below_threshold(self):
        budget = ContextBudget(total=100_000, system=10_000, plan=20_000, code=50_000, reserve=20_000)
        result = check_budget_warning(50_000, budget)
        assert result is None

    def test_warning_at_threshold(self):
        budget = ContextBudget(total=100_000, system=10_000, plan=20_000, code=50_000, reserve=20_000)
        result = check_budget_warning(80_000, budget)
        assert result is not None
        assert "80%" in result

    def test_warning_above_threshold(self):
        budget = ContextBudget(total=100_000, system=10_000, plan=20_000, code=50_000, reserve=20_000)
        result = check_budget_warning(95_000, budget)
        assert result is not None
        assert "95%" in result

    def test_warning_includes_token_counts(self):
        budget = ContextBudget(total=200_000, system=20_000, plan=40_000, code=100_000, reserve=40_000)
        result = check_budget_warning(180_000, budget)
        assert result is not None
        assert "180,000" in result
        assert "200,000" in result

    def test_zero_total_always_warns(self):
        budget = ContextBudget(total=0, system=0, plan=0, code=0, reserve=0)
        result = check_budget_warning(0, budget)
        assert result is not None

    def test_just_below_threshold_no_warning(self):
        budget = ContextBudget(total=100_000, system=10_000, plan=20_000, code=50_000, reserve=20_000)
        # 79% is below 80% threshold
        result = check_budget_warning(79_000, budget)
        assert result is None
