#!/usr/bin/env python3
"""Tests for node repair operators — retry, decompose, prune strategies."""

import pytest

from scripts.node_repair import (
    DEFAULT_REPAIR_BUDGET,
    RepairState,
    RepairStrategy,
    attempt_repair,
    decompose_plan,
    prune_plan,
    retry_plan,
    select_strategy,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def plan() -> dict:
    return {"id": 1, "name": "Add user authentication", "wave": 1}


@pytest.fixture
def fresh_state() -> RepairState:
    return RepairState(plan_id=1)


@pytest.fixture
def one_attempt_state() -> RepairState:
    """State after one failed retry attempt."""
    state = RepairState(plan_id=1)
    retry_plan({"id": 1, "name": "test"}, "test failed", state)
    return state


# ── RepairState Tests ────────────────────────────────────────────────────────


class TestRepairState:
    def test_default_budget(self, fresh_state: RepairState) -> None:
        assert fresh_state.budget == DEFAULT_REPAIR_BUDGET
        assert fresh_state.budget == 2

    def test_budget_exhausted(self) -> None:
        state = RepairState(plan_id=1, budget=0)
        assert state.budget_exhausted is True

    def test_budget_not_exhausted(self, fresh_state: RepairState) -> None:
        assert fresh_state.budget_exhausted is False

    def test_attempt_count(self, fresh_state: RepairState) -> None:
        assert fresh_state.attempt_count == 0

    def test_custom_budget(self) -> None:
        state = RepairState(plan_id=1, budget=5)
        assert state.budget == 5
        assert not state.budget_exhausted


# ── select_strategy Tests ────────────────────────────────────────────────────


class TestSelectStrategy:
    def test_first_failure_retries(self, fresh_state: RepairState) -> None:
        strategy = select_strategy(fresh_state, "AssertionError: expected 5 got 3")
        assert strategy == RepairStrategy.RETRY

    def test_syntax_error_retries(self, one_attempt_state: RepairState) -> None:
        strategy = select_strategy(one_attempt_state, "SyntaxError: invalid syntax line 42")
        assert strategy == RepairStrategy.RETRY

    def test_import_error_retries(self, one_attempt_state: RepairState) -> None:
        strategy = select_strategy(one_attempt_state, "ImportError: cannot import 'foo'")
        assert strategy == RepairStrategy.RETRY

    def test_module_not_found_retries(self, one_attempt_state: RepairState) -> None:
        strategy = select_strategy(one_attempt_state, "ModuleNotFoundError: No module named 'bar'")
        assert strategy == RepairStrategy.RETRY

    def test_repeated_same_error_decomposes(self, one_attempt_state: RepairState) -> None:
        # The last_error from one_attempt_state is "test failed"
        strategy = select_strategy(one_attempt_state, "test failed")
        assert strategy == RepairStrategy.DECOMPOSE

    def test_different_second_error_retries(self, one_attempt_state: RepairState) -> None:
        strategy = select_strategy(one_attempt_state, "completely different error message here")
        assert strategy == RepairStrategy.RETRY

    def test_budget_exhausted_prunes(self) -> None:
        state = RepairState(plan_id=1, budget=0)
        strategy = select_strategy(state, "any error")
        assert strategy == RepairStrategy.PRUNE


# ── retry_plan Tests ─────────────────────────────────────────────────────────


class TestRetryPlan:
    def test_decrements_budget(self, plan: dict, fresh_state: RepairState) -> None:
        result = retry_plan(plan, "test failed", fresh_state)
        assert fresh_state.budget == DEFAULT_REPAIR_BUDGET - 1
        assert result["strategy"] == "retry"
        assert result["budget_remaining"] == DEFAULT_REPAIR_BUDGET - 1

    def test_records_attempt(self, plan: dict, fresh_state: RepairState) -> None:
        retry_plan(plan, "assertion error", fresh_state)
        assert fresh_state.attempt_count == 1
        assert fresh_state.attempts[0].strategy == RepairStrategy.RETRY
        assert fresh_state.attempts[0].error_context == "assertion error"

    def test_includes_error_context(self, plan: dict, fresh_state: RepairState) -> None:
        result = retry_plan(plan, "ValueError: invalid input", fresh_state)
        assert result["error_context"] == "ValueError: invalid input"

    def test_event_logged(self, plan: dict, fresh_state: RepairState) -> None:
        result = retry_plan(plan, "test error", fresh_state)
        assert result["event"]["type"] == "repair_retry"
        assert result["event"]["plan_id"] == 1

    def test_updates_last_error(self, plan: dict, fresh_state: RepairState) -> None:
        retry_plan(plan, "first error", fresh_state)
        assert fresh_state.last_error == "first error"


# ── decompose_plan Tests ─────────────────────────────────────────────────────


class TestDecomposePlan:
    def test_produces_sub_plans(self, plan: dict, fresh_state: RepairState) -> None:
        result = decompose_plan(plan, "multiple failures", fresh_state)
        assert result["strategy"] == "decompose"
        assert len(result["sub_plans"]) == 3

    def test_sub_plan_names(self, plan: dict, fresh_state: RepairState) -> None:
        result = decompose_plan(plan, "err", fresh_state)
        names = [sp["name"] for sp in result["sub_plans"]]
        assert any("core implementation" in n for n in names)
        assert any("tests" in n for n in names)
        assert any("integration" in n for n in names)

    def test_sub_plans_have_waves(self, plan: dict, fresh_state: RepairState) -> None:
        result = decompose_plan(plan, "err", fresh_state)
        waves = [sp["wave"] for sp in result["sub_plans"]]
        assert waves == [1, 2, 3]

    def test_decrements_budget(self, plan: dict, fresh_state: RepairState) -> None:
        decompose_plan(plan, "err", fresh_state)
        assert fresh_state.budget == DEFAULT_REPAIR_BUDGET - 1

    def test_event_logged(self, plan: dict, fresh_state: RepairState) -> None:
        result = decompose_plan(plan, "err", fresh_state)
        assert result["event"]["type"] == "repair_decompose"
        assert result["event"]["sub_plan_count"] == 3


# ── prune_plan Tests ─────────────────────────────────────────────────────────


class TestPrunePlan:
    def test_prune_returns_reason(self, plan: dict, fresh_state: RepairState) -> None:
        result = prune_plan(plan, "non-critical, skip", fresh_state)
        assert result["strategy"] == "prune"
        assert result["reason"] == "non-critical, skip"

    def test_prune_does_not_decrement_budget(self, plan: dict, fresh_state: RepairState) -> None:
        prune_plan(plan, "skip it", fresh_state)
        # Prune doesn't cost budget
        assert fresh_state.budget == DEFAULT_REPAIR_BUDGET

    def test_prune_records_attempt(self, plan: dict, fresh_state: RepairState) -> None:
        prune_plan(plan, "reason", fresh_state)
        assert fresh_state.attempt_count == 1
        assert fresh_state.attempts[0].strategy == RepairStrategy.PRUNE

    def test_event_logged(self, plan: dict, fresh_state: RepairState) -> None:
        result = prune_plan(plan, "reason", fresh_state)
        assert result["event"]["type"] == "repair_prune"


# ── attempt_repair (integration) Tests ───────────────────────────────────────


class TestAttemptRepair:
    def test_first_attempt_retries(self, plan: dict) -> None:
        state = RepairState(plan_id=1)
        result = attempt_repair(plan, "test failed", state)
        assert result["strategy"] == "retry"

    def test_budget_exhausted_prunes(self, plan: dict) -> None:
        state = RepairState(plan_id=1, budget=0)
        result = attempt_repair(plan, "test failed", state)
        assert result["strategy"] == "prune"
        assert "budget exhausted" in result["reason"].lower()

    def test_full_repair_cycle(self, plan: dict) -> None:
        """Simulate: first fail → retry, second fail same error → decompose."""
        state = RepairState(plan_id=1)

        # First failure → retry
        r1 = attempt_repair(plan, "AssertionError: expected 5", state)
        assert r1["strategy"] == "retry"
        assert state.budget == 1

        # Second failure, same error → decompose
        r2 = attempt_repair(plan, "AssertionError: expected 5", state)
        assert r2["strategy"] == "decompose"
        assert state.budget == 0

    def test_budget_one_then_exhausted(self, plan: dict) -> None:
        """With budget=1, first attempt retries, second prunes."""
        state = RepairState(plan_id=1, budget=1)
        r1 = attempt_repair(plan, "error", state)
        assert r1["strategy"] == "retry"
        assert state.budget == 0

        r2 = attempt_repair(plan, "error", state)
        assert r2["strategy"] == "prune"
