#!/usr/bin/env python3
"""Tests for the Nyquist validation engine (scripts/nyquist.py)."""

import re
from pathlib import Path

from scripts.nyquist import (
    backfill_validation,
    parse_validation_md,
    run_wave_validation,
    update_validation_frontmatter,
)

# ── Sample VALIDATION.md content for tests ─────────────────────────────────

SAMPLE_VALIDATION = """\
---
phase: 5
slug: lint-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 5 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `ruff check scripts/ --select E501` |
| **Full suite command** | `echo PASS` |
| **Estimated runtime** | ~15 seconds |

## Rest of body content here.
"""

SAMPLE_VALIDATION_MULTI_WAVE = """\
---
phase: 3
slug: multi-wave
status: draft
nyquist_compliant: false
wave_0_complete: true
wave_0_validated: "2026-03-10"
wave_1_complete: false
created: 2026-03-10
---

# Phase 3 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Quick run command** | `echo quick` |
| **Full suite command** | `echo PASS` |
"""


# ── parse_validation_md ─────────────────────────────────────────────────────


def test_parse_extracts_frontmatter_and_commands(tmp_path: Path):
    """Parse extracts YAML frontmatter fields and test commands from body."""
    vmd = tmp_path / "05-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION)

    result = parse_validation_md(tmp_path)
    assert result is not None
    assert result["phase"] == 5
    assert result["slug"] == "lint-cleanup"
    assert result["status"] == "draft"
    assert result["nyquist_compliant"] is False
    assert result["wave_0_complete"] is False
    assert result["quick_command"] == "ruff check scripts/ --select E501"
    assert result["full_command"] == "echo PASS"


def test_parse_returns_none_for_missing_file(tmp_path: Path):
    """parse_validation_md returns None when VALIDATION.md does not exist."""
    result = parse_validation_md(tmp_path)
    assert result is None


def test_parse_handles_malformed_frontmatter(tmp_path: Path):
    """parse_validation_md returns partial dict with error for bad frontmatter."""
    vmd = tmp_path / "99-VALIDATION.md"
    vmd.write_text("not valid frontmatter at all\n---\nbody\n")

    result = parse_validation_md(tmp_path)
    assert result is not None
    assert "error" in result


def test_parse_handles_no_test_commands(tmp_path: Path):
    """parse_validation_md works when no test commands in body."""
    vmd = tmp_path / "01-VALIDATION.md"
    vmd.write_text("---\nphase: 1\nstatus: draft\n---\n\nNo table here.\n")

    result = parse_validation_md(tmp_path)
    assert result is not None
    assert result.get("quick_command") is None
    assert result.get("full_command") is None


# ── run_wave_validation ─────────────────────────────────────────────────────


def test_run_wave_validation_with_passing_command(tmp_path: Path):
    """run_wave_validation returns structured result with passing command."""
    vmd = tmp_path / "05-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION)

    result = run_wave_validation(tmp_path, wave=1, repo_path=str(tmp_path))
    assert result["wave"] == 1
    assert result["passed"] is True
    assert result["command"] == "echo PASS"
    assert "validated_at" in result


def test_run_wave_validation_with_failing_command(tmp_path: Path):
    """run_wave_validation returns passed=False for failing command."""
    content = SAMPLE_VALIDATION.replace(
        "| **Full suite command** | `echo PASS` |",
        "| **Full suite command** | `false` |",
    )
    vmd = tmp_path / "05-VALIDATION.md"
    vmd.write_text(content)

    result = run_wave_validation(tmp_path, wave=1, repo_path=str(tmp_path))
    assert result["passed"] is False


def test_run_wave_validation_missing_validation_md(tmp_path: Path):
    """run_wave_validation returns passed=False when no VALIDATION.md."""
    result = run_wave_validation(tmp_path, wave=1, repo_path=str(tmp_path))
    assert result["passed"] is False
    assert "error" in result


# ── update_validation_frontmatter ────────────────────────────────────────────


def test_update_frontmatter_writes_wave_results(tmp_path: Path):
    """update_validation_frontmatter writes wave_N_complete and wave_N_validated."""
    vmd = tmp_path / "05-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION)

    wave_result = {
        "wave": 1,
        "passed": True,
        "command": "echo PASS",
        "output": "PASS\n",
        "validated_at": "2026-03-15T00:00:00Z",
    }

    update_validation_frontmatter(tmp_path, wave_result)

    updated = vmd.read_text()
    assert "wave_1_complete: true" in updated
    assert "wave_1_validated:" in updated
    # Body must still be present
    assert "# Phase 5" in updated
    assert "Rest of body content here." in updated


def test_update_frontmatter_preserves_existing_fields(tmp_path: Path):
    """update_validation_frontmatter preserves all existing frontmatter fields."""
    vmd = tmp_path / "05-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION)

    wave_result = {
        "wave": 0,
        "passed": True,
        "command": "echo ok",
        "output": "ok\n",
        "validated_at": "2026-03-15T00:00:00Z",
    }

    update_validation_frontmatter(tmp_path, wave_result)

    updated = vmd.read_text()
    assert "phase: 5" in updated
    assert "slug: lint-cleanup" in updated
    assert "created: 2026-03-14" in updated


def test_nyquist_compliant_false_when_any_wave_fails(tmp_path: Path):
    """nyquist_compliant stays false when not all waves pass."""
    vmd = tmp_path / "03-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION_MULTI_WAVE)

    # Wave 1 fails
    wave_result = {
        "wave": 1,
        "passed": False,
        "command": "false",
        "output": "",
        "validated_at": "2026-03-15T00:00:00Z",
    }

    update_validation_frontmatter(tmp_path, wave_result)

    updated = vmd.read_text()
    assert "nyquist_compliant: false" in updated
    assert "status: failed" in updated


def test_nyquist_compliant_true_when_all_waves_pass(tmp_path: Path):
    """nyquist_compliant becomes true only when all wave_N_complete are true."""
    vmd = tmp_path / "03-VALIDATION.md"
    vmd.write_text(SAMPLE_VALIDATION_MULTI_WAVE)

    # Wave 1 passes (wave 0 already true in fixture)
    wave_result = {
        "wave": 1,
        "passed": True,
        "command": "echo ok",
        "output": "ok\n",
        "validated_at": "2026-03-15T00:00:00Z",
    }

    update_validation_frontmatter(tmp_path, wave_result)

    updated = vmd.read_text()
    assert "nyquist_compliant: true" in updated
    assert "status: validated" in updated


# ── backfill_validation ────────────────────────────────────────────────────


BACKFILL_COMPLIANT = """\
---
phase: 5
slug: lint-cleanup
status: validated
nyquist_compliant: true
wave_0_complete: true
wave_0_validated: "2026-03-14"
created: 2026-03-14
---

# Phase 5 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Quick run command** | `echo quick` |
| **Full suite command** | `echo PASS` |
"""

BACKFILL_NON_COMPLIANT_PASS = """\
---
phase: 1
slug: database-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 1 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Quick run command** | `echo quick` |
| **Full suite command** | `true` |
"""

BACKFILL_NON_COMPLIANT_FAIL = """\
---
phase: 2
slug: error-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 2 — Validation Strategy

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Quick run command** | `echo quick` |
| **Full suite command** | `false` |
"""


def _setup_backfill_dirs(tmp_path: Path) -> Path:
    """Create a fake planning dir with phases for backfill tests."""
    planning = tmp_path / ".planning"
    phases = planning / "phases"

    # Phase 5: already compliant
    p5 = phases / "05-lint-cleanup"
    p5.mkdir(parents=True)
    (p5 / "05-VALIDATION.md").write_text(BACKFILL_COMPLIANT)

    # Phase 1: non-compliant, command passes
    p1 = phases / "01-database-foundation"
    p1.mkdir(parents=True)
    (p1 / "01-VALIDATION.md").write_text(BACKFILL_NON_COMPLIANT_PASS)

    # Phase 2: non-compliant, command fails
    p2 = phases / "02-error-infrastructure"
    p2.mkdir(parents=True)
    (p2 / "02-VALIDATION.md").write_text(BACKFILL_NON_COMPLIANT_FAIL)

    # Phase 3: no VALIDATION.md at all
    p3 = phases / "03-command-routing"
    p3.mkdir(parents=True)

    return planning


def test_backfill_skips_compliant(tmp_path: Path):
    """backfill_validation skips phases already nyquist_compliant: true."""
    planning = _setup_backfill_dirs(tmp_path)
    results = backfill_validation(
        planning_dir=planning, repo_path=str(tmp_path)
    )

    # Phase 5 should not appear in results (it was skipped)
    slugs = [r["slug"] for r in results]
    assert "lint-cleanup" not in slugs

    # Phase 5 VALIDATION.md should be untouched
    p5_vmd = (
        planning / "phases" / "05-lint-cleanup" / "05-VALIDATION.md"
    )
    text = p5_vmd.read_text()
    assert "nyquist_compliant: true" in text
    assert "status: validated" in text


def test_backfill_updates_passing(tmp_path: Path):
    """backfill_validation updates non-compliant phase to validated when tests pass."""
    planning = _setup_backfill_dirs(tmp_path)
    backfill_validation(planning_dir=planning, repo_path=str(tmp_path))

    p1_vmd = (
        planning / "phases" / "01-database-foundation" / "01-VALIDATION.md"
    )
    text = p1_vmd.read_text()
    assert "nyquist_compliant: true" in text
    assert "status: validated" in text
    assert "wave_0_complete: true" in text


def test_backfill_updates_failing(tmp_path: Path):
    """backfill_validation updates non-compliant phase to failed with failure_reason."""
    planning = _setup_backfill_dirs(tmp_path)
    backfill_validation(planning_dir=planning, repo_path=str(tmp_path))

    p2_vmd = (
        planning / "phases" / "02-error-infrastructure" / "02-VALIDATION.md"
    )
    text = p2_vmd.read_text()
    assert "nyquist_compliant: false" in text
    assert "status: failed" in text
    assert "failure_reason:" in text


def test_backfill_returns_summary(tmp_path: Path):
    """backfill_validation returns list of result dicts with correct fields."""
    planning = _setup_backfill_dirs(tmp_path)
    results = backfill_validation(
        planning_dir=planning, repo_path=str(tmp_path)
    )

    assert isinstance(results, list)
    # Should have results for phase 1 and 2 (not 5 which is compliant, not 3 which has no VALIDATION.md)
    assert len(results) == 2

    for r in results:
        assert "phase" in r
        assert "slug" in r
        assert "passed" in r
        assert "command" in r

    # Check specific results
    by_slug = {r["slug"]: r for r in results}
    assert by_slug["database-foundation"]["passed"] is True
    assert by_slug["error-infrastructure"]["passed"] is False
