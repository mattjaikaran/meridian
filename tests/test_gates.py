#!/usr/bin/env python3
"""Tests for quality gate checks (scripts/gates.py)."""

from pathlib import Path

from scripts.gates import (
    DEFAULT_STUB_PATTERNS,
    check_requirements_coverage,
    collect_prior_test_commands,
    detect_stubs,
    run_regression_gate,
)

# ── Sample VALIDATION.md content ─────────────────────────────────────────────

SAMPLE_VALIDATION = """\
---
phase: 1
slug: database-foundation
status: validated
nyquist_compliant: true
---

# Phase 1 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Quick run command** | `echo quick` |
| **Full suite command** | `echo PASS` |
| **Estimated runtime** | ~5 seconds |
"""

SAMPLE_VALIDATION_NO_CMD = """\
---
phase: 2
slug: error-infra
status: draft
---

# Phase 2 — Validation

No test table here.
"""


# ── Plan 01: Regression Gate Tests ───────────────────────────────────────────


def _make_phase_dir(tmp_path: Path, name: str, content: str) -> Path:
    """Create a phase directory with a VALIDATION.md file."""
    phase_dir = tmp_path / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    (phase_dir / "01-VALIDATION.md").write_text(content)
    return phase_dir


class TestCollectPriorTestCommands:
    def test_collects_commands_from_prior_phases(self, tmp_path: Path) -> None:
        _make_phase_dir(tmp_path, "01-foundation", SAMPLE_VALIDATION)
        _make_phase_dir(tmp_path, "02-error-infra", SAMPLE_VALIDATION_NO_CMD)

        result = collect_prior_test_commands(tmp_path, up_to_phase=3)
        assert len(result) == 1
        assert result[0]["phase_num"] == 1
        assert result[0]["command"] == "echo PASS"

    def test_excludes_current_and_future_phases(self, tmp_path: Path) -> None:
        _make_phase_dir(tmp_path, "01-foundation", SAMPLE_VALIDATION)
        _make_phase_dir(tmp_path, "03-routing", SAMPLE_VALIDATION)

        result = collect_prior_test_commands(tmp_path, up_to_phase=2)
        assert len(result) == 1
        assert result[0]["phase_num"] == 1

    def test_skips_phases_without_validation(self, tmp_path: Path) -> None:
        phase_dir = tmp_path / "phases" / "01-foundation"
        phase_dir.mkdir(parents=True)
        # No VALIDATION.md file

        result = collect_prior_test_commands(tmp_path, up_to_phase=5)
        assert result == []

    def test_returns_empty_for_missing_dir(self, tmp_path: Path) -> None:
        result = collect_prior_test_commands(tmp_path / "nonexistent", up_to_phase=5)
        assert result == []


class TestRunRegressionGate:
    def test_skip_flag_bypasses_gate(self, tmp_path: Path) -> None:
        result = run_regression_gate(
            tmp_path, current_phase=5, skip_regression=True
        )
        assert result["passed"] is True
        assert result["skipped"] is True

    def test_no_prior_commands_passes(self, tmp_path: Path) -> None:
        (tmp_path / "phases").mkdir(parents=True)
        result = run_regression_gate(tmp_path, current_phase=1)
        assert result["passed"] is True
        assert result["skipped"] is False

    def test_passing_commands(self, tmp_path: Path) -> None:
        _make_phase_dir(tmp_path, "01-foundation", SAMPLE_VALIDATION)
        result = run_regression_gate(tmp_path, current_phase=2)
        assert result["passed"] is True
        assert len(result["results"]) == 1
        assert result["results"][0]["passed"] is True

    def test_failing_command_blocks(self, tmp_path: Path) -> None:
        fail_validation = SAMPLE_VALIDATION.replace(
            "`echo PASS`", "`exit 1`"
        )
        _make_phase_dir(tmp_path, "01-foundation", fail_validation)
        result = run_regression_gate(tmp_path, current_phase=2)
        assert result["passed"] is False
        assert "1" in result["summary"]

    def test_mixed_pass_fail(self, tmp_path: Path) -> None:
        _make_phase_dir(tmp_path, "01-foundation", SAMPLE_VALIDATION)
        fail_validation = SAMPLE_VALIDATION.replace(
            "phase: 1", "phase: 2"
        ).replace("`echo PASS`", "`exit 1`")
        _make_phase_dir(tmp_path, "02-error-infra", fail_validation)
        result = run_regression_gate(tmp_path, current_phase=3)
        assert result["passed"] is False
        assert len(result["results"]) == 2


# ── Plan 02: Requirements Coverage Tests ─────────────────────────────────────


class TestCheckRequirementsCoverage:
    def test_full_coverage(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=["REQ-01", "REQ-02"],
            plan_requirements={"plan-01": ["REQ-01"], "plan-02": ["REQ-02"]},
        )
        assert result["passed"] is True
        assert result["coverage_pct"] == 100.0
        assert result["uncovered"] == []
        assert set(result["covered"]) == {"REQ-01", "REQ-02"}

    def test_partial_coverage(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=["REQ-01", "REQ-02", "REQ-03"],
            plan_requirements={"plan-01": ["REQ-01"]},
        )
        assert result["passed"] is True  # non-strict
        assert len(result["uncovered"]) == 2
        assert "REQ-02" in result["uncovered"]
        assert "REQ-03" in result["uncovered"]
        assert len(result["warnings"]) == 1

    def test_partial_coverage_strict_blocks(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=["REQ-01", "REQ-02"],
            plan_requirements={"plan-01": ["REQ-01"]},
            strict=True,
        )
        assert result["passed"] is False
        assert result["uncovered"] == ["REQ-02"]

    def test_zero_coverage(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=["REQ-01", "REQ-02"],
            plan_requirements={},
        )
        assert result["coverage_pct"] == 0.0
        assert len(result["uncovered"]) == 2

    def test_empty_requirements(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=[],
            plan_requirements={"plan-01": ["REQ-01"]},
        )
        assert result["passed"] is True
        assert result["coverage_pct"] == 100.0

    def test_plan_map_tracks_multiple_plans(self) -> None:
        result = check_requirements_coverage(
            phase_requirements=["REQ-01"],
            plan_requirements={
                "plan-01": ["REQ-01"],
                "plan-02": ["REQ-01"],
            },
        )
        assert "REQ-01" in result["plan_map"]
        assert len(result["plan_map"]["REQ-01"]) == 2


# ── Plan 03: Stub Detection Tests ───────────────────────────────────────────


class TestDetectStubs:
    def test_detects_todo(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# TODO: implement this\ndef foo():\n    pass\n")
        findings = detect_stubs([str(f)])
        names = [r["pattern"] for r in findings]
        assert "TODO" in names
        assert "pass-only function" in names

    def test_detects_fixme_and_hack(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# FIXME: broken\n# HACK: workaround\n")
        findings = detect_stubs([str(f)])
        names = [r["pattern"] for r in findings]
        assert "FIXME" in names
        assert "HACK" in names

    def test_detects_not_implemented(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("def foo():\n    raise NotImplementedError\n")
        findings = detect_stubs([str(f)])
        assert any(r["pattern"] == "NotImplementedError" for r in findings)

    def test_detects_placeholder_comments(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# placeholder for real logic\n# stub implementation\n# temporary hack\n")
        findings = detect_stubs([str(f)])
        assert any(r["pattern"] == "placeholder comment" for r in findings)

    def test_detects_ellipsis_body(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("def foo():\n    ...\n")
        findings = detect_stubs([str(f)])
        assert any(r["pattern"] == "ellipsis body" for r in findings)

    def test_clean_file_returns_empty(self, tmp_path: Path) -> None:
        f = tmp_path / "clean.py"
        f.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
        findings = detect_stubs([str(f)])
        assert findings == []

    def test_nonexistent_file_skipped(self, tmp_path: Path) -> None:
        findings = detect_stubs([str(tmp_path / "missing.py")])
        assert findings == []

    def test_custom_patterns(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("# REVIEW_NEEDED: check this\n")
        custom = [{"name": "review", "regex": r"REVIEW_NEEDED"}]
        findings = detect_stubs([str(f)], patterns=custom)
        assert len(findings) == 1
        assert findings[0]["pattern"] == "review"

    def test_findings_include_line_and_context(self, tmp_path: Path) -> None:
        f = tmp_path / "example.py"
        f.write_text("line one\n# TODO: fix later\nline three\n")
        findings = detect_stubs([str(f)])
        assert findings[0]["line"] == 2
        assert findings[0]["context"] == "# TODO: fix later"
        assert findings[0]["file"] == str(f)

    def test_default_patterns_is_list(self) -> None:
        assert isinstance(DEFAULT_STUB_PATTERNS, list)
        assert all("name" in p and "regex" in p for p in DEFAULT_STUB_PATTERNS)
