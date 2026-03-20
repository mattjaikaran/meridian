#!/usr/bin/env python3
"""Tests for executor modes — interactive review loop and prompt formatting."""

import pytest

from scripts.executor_modes import (
    InteractiveExecutor,
    PlanResult,
    ReviewAction,
    ReviewDecision,
    format_task_review_prompt,
    should_pause_for_review,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_plans() -> list[dict]:
    return [
        {"id": 1, "name": "Setup DB schema", "wave": 1},
        {"id": 2, "name": "Add API routes", "wave": 1},
        {"id": 3, "name": "Write tests", "wave": 2},
    ]


@pytest.fixture
def success_result() -> PlanResult:
    return PlanResult(
        plan_id=1,
        plan_name="Setup DB schema",
        files_changed=["scripts/db.py", "tests/test_db.py"],
        tests_run=5,
        tests_passed=5,
        commit_sha="abc1234def5678",
    )


@pytest.fixture
def failure_result() -> PlanResult:
    return PlanResult(
        plan_id=2,
        plan_name="Add API routes",
        files_changed=["scripts/api.py"],
        tests_run=3,
        tests_passed=1,
        error="2 tests failed: test_get_route, test_post_route",
    )


# ── PlanResult Tests ─────────────────────────────────────────────────────────


class TestPlanResult:
    def test_success_property(self, success_result: PlanResult) -> None:
        assert success_result.success is True

    def test_failure_property(self, failure_result: PlanResult) -> None:
        assert failure_result.success is False

    def test_default_fields(self) -> None:
        r = PlanResult(plan_id=1, plan_name="test")
        assert r.files_changed == []
        assert r.tests_run == 0
        assert r.commit_sha is None
        assert r.error is None
        assert r.success is True


# ── InteractiveExecutor Tests ────────────────────────────────────────────────


class TestInteractiveExecutor:
    def test_initial_state(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        assert exe.current_plan == sample_plans[0]
        assert not exe.is_complete
        assert exe.progress["total"] == 3
        assert exe.progress["completed"] == 0
        assert exe.progress["remaining"] == 3

    def test_approve_advances(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        result = exe.apply_decision(ReviewDecision(action=ReviewAction.APPROVE))
        assert result["action"] == "next"
        assert result["plan_index"] == 1
        assert exe.current_plan == sample_plans[1]

    def test_approve_all_completes(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        for _ in range(2):
            exe.apply_decision(ReviewDecision(action=ReviewAction.APPROVE))
        result = exe.apply_decision(ReviewDecision(action=ReviewAction.APPROVE))
        assert result["action"] == "done"
        assert exe.is_complete
        assert exe.current_plan is None

    def test_reject_advances(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        result = exe.apply_decision(
            ReviewDecision(action=ReviewAction.REJECT, feedback="Not ready")
        )
        assert result["action"] == "next"
        assert exe.progress["rejected"] == 1

    def test_modify_reruns(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        result = exe.apply_decision(
            ReviewDecision(action=ReviewAction.MODIFY, feedback="Add error handling")
        )
        assert result["action"] == "rerun"
        assert result["plan_index"] == 0
        assert result["feedback"] == "Add error handling"
        # Still on the same plan
        assert exe.current_plan == sample_plans[0]

    def test_progress_tracking(self, sample_plans: list[dict]) -> None:
        exe = InteractiveExecutor(sample_plans)
        exe.apply_decision(ReviewDecision(action=ReviewAction.APPROVE))
        exe.apply_decision(ReviewDecision(action=ReviewAction.REJECT, feedback="bad"))
        exe.apply_decision(ReviewDecision(action=ReviewAction.APPROVE))
        prog = exe.progress
        assert prog["approved"] == 2
        assert prog["rejected"] == 1
        assert prog["modified"] == 0
        assert prog["completed"] == 3

    def test_record_result(self, sample_plans: list[dict], success_result: PlanResult) -> None:
        exe = InteractiveExecutor(sample_plans)
        exe.record_result(success_result)
        assert len(exe.results) == 1
        assert exe.results[0].plan_id == 1

    def test_empty_plans(self) -> None:
        exe = InteractiveExecutor([])
        assert exe.is_complete
        assert exe.current_plan is None
        assert exe.progress["total"] == 0


# ── should_pause_for_review Tests ────────────────────────────────────────────


class TestShouldPause:
    def test_interactive_always_pauses(self, success_result: PlanResult) -> None:
        assert should_pause_for_review(True, success_result) is True

    def test_interactive_pauses_on_failure(self, failure_result: PlanResult) -> None:
        assert should_pause_for_review(True, failure_result) is True

    def test_autonomous_skips_on_success(self, success_result: PlanResult) -> None:
        assert should_pause_for_review(False, success_result) is False

    def test_autonomous_pauses_on_failure(self, failure_result: PlanResult) -> None:
        assert should_pause_for_review(False, failure_result) is True


# ── format_task_review_prompt Tests ──────────────────────────────────────────


class TestFormatPrompt:
    def test_success_prompt(self, success_result: PlanResult) -> None:
        progress = {"total": 3, "completed": 1}
        prompt = format_task_review_prompt(success_result, progress)
        assert "Plan #1" in prompt
        assert "Setup DB schema" in prompt
        assert "SUCCESS" in prompt
        assert "scripts/db.py" in prompt
        assert "5/5 passed" in prompt
        assert "abc1234d" in prompt
        assert "[A]pprove" in prompt
        assert "1/3 plans" in prompt

    def test_failure_prompt(self, failure_result: PlanResult) -> None:
        progress = {"total": 3, "completed": 2}
        prompt = format_task_review_prompt(failure_result, progress)
        assert "FAILED" in prompt
        assert "2 tests failed" in prompt
        assert "1/3 passed" in prompt

    def test_no_files_changed(self) -> None:
        result = PlanResult(plan_id=1, plan_name="Noop")
        progress = {"total": 1, "completed": 0}
        prompt = format_task_review_prompt(result, progress)
        assert "Files changed: none" in prompt

    def test_no_commit(self) -> None:
        result = PlanResult(plan_id=1, plan_name="Noop")
        progress = {"total": 1, "completed": 0}
        prompt = format_task_review_prompt(result, progress)
        assert "Commit:" not in prompt
