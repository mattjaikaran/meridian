---
phase: 4
slug: test-coverage-hardening
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-11
wave_0_validated: "2026-03-16T16:52:02Z"
---
# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via uv dev dependency) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest -x -q`
- **After every plan wave:** Run `uv run pytest -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | TEST-03 | unit | `uv run pytest tests/test_dispatch.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | TEST-04 | unit | `uv run pytest tests/test_export.py -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | TEST-05 | unit | `uv run pytest tests/test_axis_sync.py -x` | Partial | ⬜ pending |
| 04-01-04 | 01 | 1 | TEST-06 | unit | `uv run pytest tests/test_context_window.py -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | TEST-07 | unit | `uv run pytest tests/test_state.py::TestAutoAdvance -x` | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 1 | TEST-08 | unit | `uv run pytest tests/test_db.py::TestMigration -x` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | QUAL-01 | unit | `uv run pytest tests/test_resume.py -x` | ✅ | ⬜ pending |
| 04-02-02 | 02 | 2 | QUAL-02 | unit | `uv run pytest tests/test_metrics.py -x` | ✅ | ⬜ pending |
| 04-02-03 | 02 | 2 | QUAL-03 | unit | `uv run pytest tests/test_export.py -x` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 2 | QUAL-04 | unit | `uv run pytest tests/test_state.py::TestAutoAdvance -x` | ❌ W0 | ⬜ pending |
| 04-02-05 | 02 | 2 | QUAL-05 | unit | `uv run pytest tests/test_state.py::TestNeroDispatch -x` | ❌ W0 | ⬜ pending |
| 04-02-06 | 02 | 2 | QUAL-06 | unit | `uv run pytest tests/test_metrics.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_dispatch.py` — stubs for TEST-03
- [ ] `tests/test_export.py` — stubs for TEST-04, QUAL-03
- [ ] `tests/test_context_window.py` — stubs for TEST-06
- [ ] Expand `tests/test_axis_sync.py` — stubs for TEST-05 (sync/create functions)
- [ ] Expand `tests/test_state.py` — stubs for TEST-07 (TestAutoAdvance), QUAL-04, QUAL-05 (TestNeroDispatch)
- [ ] Expand `tests/test_db.py` — stubs for TEST-08 (TestMigration)

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
