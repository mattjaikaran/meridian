#!/usr/bin/env python3
"""Node repair operators — automatic recovery when plan execution fails."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)

# Default number of repair attempts before giving up
DEFAULT_REPAIR_BUDGET: int = 2


class RepairStrategy(Enum):
    """Available repair strategies for failed plans."""

    RETRY = "retry"
    DECOMPOSE = "decompose"
    PRUNE = "prune"


@dataclass
class RepairAttempt:
    """Record of a single repair attempt."""

    strategy: RepairStrategy
    plan_id: int
    attempt_number: int
    error_context: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    success: bool = False
    result_detail: str = ""


@dataclass
class RepairState:
    """Tracks repair budget and history for a plan."""

    plan_id: int
    budget: int = DEFAULT_REPAIR_BUDGET
    attempts: list[RepairAttempt] = field(default_factory=list)
    last_error: str = ""

    @property
    def budget_exhausted(self) -> bool:
        return self.budget <= 0

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)


def select_strategy(state: RepairState, error: str) -> RepairStrategy:
    """Select a repair strategy based on failure history and error type.

    Heuristic:
    - First failure → always RETRY
    - Second failure, same error → DECOMPOSE if possible, else PRUNE
    - Non-test failure (syntax error, import error) → RETRY with fix hint
    """
    if state.budget_exhausted:
        return RepairStrategy.PRUNE

    # First attempt → always retry
    if state.attempt_count == 0:
        return RepairStrategy.RETRY

    # Check if this is a non-test failure (syntax/import errors) — retry with fix
    error_lower = error.lower()
    if any(kw in error_lower for kw in ("syntaxerror", "importerror", "modulenotfounderror")):
        return RepairStrategy.RETRY

    # Repeated failure with same error → decompose
    if state.last_error and _errors_similar(state.last_error, error):
        return RepairStrategy.DECOMPOSE

    # Default: retry
    return RepairStrategy.RETRY


def _errors_similar(prev: str, current: str) -> bool:
    """Check if two errors are similar enough to indicate retry won't help."""
    # Simple heuristic: if the first 60 chars match, consider them similar
    normalize = lambda s: s.strip().lower()[:60]
    return normalize(prev) == normalize(current)


def retry_plan(plan: dict, error: str, state: RepairState) -> dict:
    """RETRY strategy: re-execute the same plan with error context appended.

    Returns a dict describing the retry action to take.
    """
    state.budget -= 1
    attempt = RepairAttempt(
        strategy=RepairStrategy.RETRY,
        plan_id=plan.get("id", 0),
        attempt_number=state.attempt_count + 1,
        error_context=error,
    )
    state.attempts.append(attempt)
    state.last_error = error

    logger.info(
        "RETRY plan %s (attempt %d, budget remaining: %d)",
        plan.get("name", plan.get("id")),
        attempt.attempt_number,
        state.budget,
    )

    return {
        "strategy": RepairStrategy.RETRY.value,
        "plan": plan,
        "error_context": error,
        "attempt": attempt.attempt_number,
        "budget_remaining": state.budget,
        "event": {
            "type": "repair_retry",
            "plan_id": plan.get("id", 0),
            "attempt": attempt.attempt_number,
            "error": error[:200],
        },
    }


def decompose_plan(plan: dict, error: str, state: RepairState) -> dict:
    """DECOMPOSE strategy: split the failed plan into 2-3 smaller sub-plans.

    Returns a dict with sub-plan descriptions derived from the original.
    The caller is responsible for creating the actual plan records.
    """
    state.budget -= 1
    attempt = RepairAttempt(
        strategy=RepairStrategy.DECOMPOSE,
        plan_id=plan.get("id", 0),
        attempt_number=state.attempt_count + 1,
        error_context=error,
    )
    state.attempts.append(attempt)
    state.last_error = error

    plan_name = plan.get("name", "Unknown plan")
    sub_plans = _generate_sub_plans(plan_name, error)

    logger.info(
        "DECOMPOSE plan %s into %d sub-plans (budget remaining: %d)",
        plan_name,
        len(sub_plans),
        state.budget,
    )

    return {
        "strategy": RepairStrategy.DECOMPOSE.value,
        "original_plan": plan,
        "sub_plans": sub_plans,
        "error_context": error,
        "budget_remaining": state.budget,
        "event": {
            "type": "repair_decompose",
            "plan_id": plan.get("id", 0),
            "sub_plan_count": len(sub_plans),
            "error": error[:200],
        },
    }


def _generate_sub_plans(plan_name: str, error: str) -> list[dict]:
    """Generate sub-plan descriptions from a failed plan.

    Splits into: implementation, tests, integration.
    """
    return [
        {
            "name": f"{plan_name} — core implementation",
            "description": f"Implement the core logic for: {plan_name}",
            "wave": 1,
        },
        {
            "name": f"{plan_name} — tests",
            "description": f"Write tests for: {plan_name}. Previous error: {error[:100]}",
            "wave": 2,
        },
        {
            "name": f"{plan_name} — integration",
            "description": f"Wire up and verify: {plan_name}",
            "wave": 3,
        },
    ]


def prune_plan(plan: dict, reason: str, state: RepairState) -> dict:
    """PRUNE strategy: mark the plan as skipped and continue with remaining plans.

    Returns a dict describing the prune action.
    """
    attempt = RepairAttempt(
        strategy=RepairStrategy.PRUNE,
        plan_id=plan.get("id", 0),
        attempt_number=state.attempt_count + 1,
        error_context=reason,
    )
    state.attempts.append(attempt)

    logger.info(
        "PRUNE plan %s: %s",
        plan.get("name", plan.get("id")),
        reason,
    )

    return {
        "strategy": RepairStrategy.PRUNE.value,
        "plan": plan,
        "reason": reason,
        "event": {
            "type": "repair_prune",
            "plan_id": plan.get("id", 0),
            "reason": reason[:200],
        },
    }


def attempt_repair(plan: dict, error: str, state: RepairState) -> dict:
    """Main entry point: attempt to repair a failed plan.

    Selects a strategy and executes it. Returns a dict describing the action taken.
    If the repair budget is exhausted, returns a prune action.
    """
    if state.budget_exhausted:
        return prune_plan(plan, f"Repair budget exhausted. Last error: {error}", state)

    strategy = select_strategy(state, error)

    if strategy == RepairStrategy.RETRY:
        return retry_plan(plan, error, state)
    elif strategy == RepairStrategy.DECOMPOSE:
        return decompose_plan(plan, error, state)
    else:
        return prune_plan(plan, error, state)
