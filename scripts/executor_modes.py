#!/usr/bin/env python3
"""Interactive executor mode — pause-and-review execution for pair-programming style workflow."""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewAction(Enum):
    """User review actions after a plan completes."""

    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"


@dataclass
class PlanResult:
    """Result of executing a single plan."""

    plan_id: int
    plan_name: str
    files_changed: list[str] = field(default_factory=list)
    tests_run: int = 0
    tests_passed: int = 0
    commit_sha: str | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


@dataclass
class ReviewDecision:
    """User's review decision for a completed plan."""

    action: ReviewAction
    feedback: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class InteractiveExecutor:
    """Executes plans one at a time, pausing for user review after each.

    When --interactive is passed to /meridian:execute:
    1. Execute one plan at a time (no parallel waves)
    2. After each plan completes, show: files changed, tests run, commit made
    3. Pause and ask user: [A]pprove / [R]eject / [M]odify
    4. Approve → proceed to next plan
    5. Reject → mark plan as failed with user feedback, continue or stop
    6. Modify → user provides additional instructions, re-run plan
    """

    def __init__(self, plans: list[dict], interactive: bool = True) -> None:
        self.plans = plans
        self.interactive = interactive
        self.results: list[PlanResult] = []
        self.decisions: list[ReviewDecision] = []
        self._current_index: int = 0

    @property
    def current_plan(self) -> dict | None:
        """Return the current plan to execute, or None if all done."""
        if self._current_index >= len(self.plans):
            return None
        return self.plans[self._current_index]

    @property
    def is_complete(self) -> bool:
        """True when all plans have been processed."""
        return self._current_index >= len(self.plans)

    @property
    def progress(self) -> dict:
        """Return execution progress summary."""
        approved = sum(1 for d in self.decisions if d.action == ReviewAction.APPROVE)
        rejected = sum(1 for d in self.decisions if d.action == ReviewAction.REJECT)
        modified = sum(1 for d in self.decisions if d.action == ReviewAction.MODIFY)
        return {
            "total": len(self.plans),
            "completed": self._current_index,
            "remaining": max(0, len(self.plans) - self._current_index),
            "approved": approved,
            "rejected": rejected,
            "modified": modified,
        }

    def record_result(self, result: PlanResult) -> None:
        """Record the result of executing the current plan."""
        self.results.append(result)

    def apply_decision(self, decision: ReviewDecision) -> dict:
        """Apply a user review decision and advance state.

        Returns a dict describing what should happen next:
        - {"action": "next", "plan_index": N} — move to next plan
        - {"action": "rerun", "plan_index": N, "feedback": "..."} — re-run current plan
        - {"action": "stop", "reason": "..."} — stop execution
        - {"action": "done"} — all plans processed
        """
        self.decisions.append(decision)

        if decision.action == ReviewAction.APPROVE:
            self._current_index += 1
            if self.is_complete:
                return {"action": "done"}
            return {"action": "next", "plan_index": self._current_index}

        elif decision.action == ReviewAction.REJECT:
            # Mark as rejected and move on
            self._current_index += 1
            if self.is_complete:
                return {"action": "done"}
            return {"action": "next", "plan_index": self._current_index}

        elif decision.action == ReviewAction.MODIFY:
            # Stay on current plan for re-execution
            return {
                "action": "rerun",
                "plan_index": self._current_index,
                "feedback": decision.feedback,
            }

        return {"action": "stop", "reason": f"Unknown action: {decision.action}"}


def should_pause_for_review(interactive: bool, plan_result: PlanResult) -> bool:
    """Determine whether execution should pause for user review.

    Always pauses in interactive mode. In autonomous mode, only pauses on failure.
    """
    if interactive:
        return True
    # In autonomous mode, pause only if the plan failed
    return not plan_result.success


def format_task_review_prompt(result: PlanResult, progress: dict) -> str:
    """Format a human-readable review prompt after plan execution.

    Shows files changed, test results, commit info, then asks for user action.
    """
    lines: list[str] = []

    # Header
    lines.append(f"── Plan #{result.plan_id}: {result.plan_name} ──")
    lines.append(f"Progress: {progress['completed']}/{progress['total']} plans")
    lines.append("")

    # Status
    if result.success:
        lines.append("Status: SUCCESS")
    else:
        lines.append(f"Status: FAILED — {result.error}")
    lines.append("")

    # Files changed
    if result.files_changed:
        lines.append(f"Files changed ({len(result.files_changed)}):")
        for f in result.files_changed:
            lines.append(f"  - {f}")
    else:
        lines.append("Files changed: none")
    lines.append("")

    # Tests
    lines.append(f"Tests: {result.tests_passed}/{result.tests_run} passed")

    # Commit
    if result.commit_sha:
        lines.append(f"Commit: {result.commit_sha[:8]}")
    lines.append("")

    # Action prompt
    lines.append("[A]pprove  [R]eject  [M]odify")

    return "\n".join(lines)
