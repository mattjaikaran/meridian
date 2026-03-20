#!/usr/bin/env python3
"""Tests for UAT audit scanning (scripts/audit.py)."""

from pathlib import Path

from scripts.audit import (
    audit_uat,
    collect_verification_debt,
)

# ── Sample content ───────────────────────────────────────────────────────────

VALIDATION_WITH_DEBT = """\
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
| **Full suite command** | `echo PASS` |

## Validation Sign-Off

- [x] All tasks verified
- [ ] Sampling continuity confirmed
- [ ] Wave 0 covers all MISSING references
"""

VALIDATION_NO_DEBT = """\
---
phase: 2
slug: error-infra
status: validated
---

# Phase 2 — Validation

## Validation Sign-Off

- [x] All tasks verified
- [x] Everything covered
"""

VERIFICATION_WITH_HUMAN = """\
---
phase: 01-database-foundation
verified: 2026-03-10
status: passed
---

# Phase 1 Verification Report

## Human Verification Required

### 1. Concurrent Write Survival

**Test:** Run two concurrent writes
**Expected:** Both complete without crash

### 2. Backup Under Load

**Test:** Backup while writing
**Expected:** Backup completes
**Status: confirmed**
"""

VERIFICATION_CLEAN = """\
---
phase: 02-error-infra
verified: 2026-03-10
status: passed
---

# Phase 2 Verification Report

## Human Verification Required

No human verification items.
"""


# ── Helper ───────────────────────────────────────────────────────────────────


def _setup_phase(
    tmp_path: Path,
    name: str,
    validation: str | None = None,
    verification: str | None = None,
) -> Path:
    """Create a phase directory with optional validation/verification files."""
    phase_dir = tmp_path / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    if validation is not None:
        (phase_dir / "01-VALIDATION.md").write_text(validation)
    if verification is not None:
        (phase_dir / "01-VERIFICATION.md").write_text(verification)
    return phase_dir


# ── Tests ────────────────────────────────────────────────────────────────────


class TestCollectVerificationDebt:
    def test_detects_unchecked_signoff(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "01-foundation", validation=VALIDATION_WITH_DEBT)
        results = collect_verification_debt(tmp_path)
        assert len(results) == 1
        assert results[0]["has_debt"] is True
        assert len(results[0]["unchecked_signoff"]) == 2

    def test_clean_validation(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "02-error-infra", validation=VALIDATION_NO_DEBT)
        results = collect_verification_debt(tmp_path)
        assert len(results) == 1
        assert results[0]["has_debt"] is False
        assert results[0]["unchecked_signoff"] == []

    def test_detects_pending_human_verification(self, tmp_path: Path) -> None:
        _setup_phase(
            tmp_path, "01-foundation",
            verification=VERIFICATION_WITH_HUMAN,
        )
        results = collect_verification_debt(tmp_path)
        assert results[0]["has_debt"] is True
        # Only "Concurrent Write Survival" should be pending (Backup is confirmed)
        assert len(results[0]["pending_human"]) == 1
        assert "Concurrent Write Survival" in results[0]["pending_human"][0]["title"]

    def test_phase_without_files(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "03-routing")
        results = collect_verification_debt(tmp_path)
        assert len(results) == 1
        assert results[0]["has_debt"] is False

    def test_multiple_phases_mixed(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "01-foundation", validation=VALIDATION_WITH_DEBT)
        _setup_phase(tmp_path, "02-error-infra", validation=VALIDATION_NO_DEBT)
        results = collect_verification_debt(tmp_path)
        assert len(results) == 2
        has_debt_phases = [r for r in results if r["has_debt"]]
        assert len(has_debt_phases) == 1

    def test_missing_planning_dir(self, tmp_path: Path) -> None:
        results = collect_verification_debt(tmp_path / "nonexistent")
        assert results == []

    def test_phase_num_extraction(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "05-lint-cleanup", validation=VALIDATION_NO_DEBT)
        results = collect_verification_debt(tmp_path)
        assert results[0]["phase_num"] == 5


class TestAuditUat:
    def test_produces_report_with_debt(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "01-foundation", validation=VALIDATION_WITH_DEBT)
        result = audit_uat(tmp_path)
        assert result["has_debt"] is True
        assert result["total_debt"] >= 2
        assert "# UAT Audit Report" in result["report"]
        assert "01-foundation" in result["report"]

    def test_clean_report(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "01-foundation", validation=VALIDATION_NO_DEBT)
        result = audit_uat(tmp_path)
        assert result["has_debt"] is False
        assert result["total_debt"] == 0
        assert "all clear" in result["report"]

    def test_exit_code_semantics(self, tmp_path: Path) -> None:
        _setup_phase(tmp_path, "01-foundation", validation=VALIDATION_WITH_DEBT)
        result = audit_uat(tmp_path)
        # has_debt=True means nonzero exit in CLI usage
        assert result["has_debt"] is True

    def test_report_structure(self, tmp_path: Path) -> None:
        _setup_phase(
            tmp_path, "01-foundation",
            validation=VALIDATION_WITH_DEBT,
            verification=VERIFICATION_WITH_HUMAN,
        )
        result = audit_uat(tmp_path)
        assert "phases" in result
        assert "total_debt" in result
        assert "has_debt" in result
        assert "report" in result
        assert isinstance(result["phases"], list)
