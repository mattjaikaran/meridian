---
phase: 2
slug: error-infrastructure
status: validated
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-10
wave_0_validated: "2026-03-16T16:51:57Z"
---
# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (via uv) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/ -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ERRL-01 | unit | `uv run pytest tests/test_db.py::TestErrorHierarchy -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ERRL-02 | unit | `uv run pytest tests/test_state.py::TestTransitions -x` | ✅ partial | ⬜ pending |
| 02-01-03 | 01 | 1 | ERRL-03 | unit | `uv run pytest tests/test_db.py::TestLogging -x` | ❌ W0 | ⬜ pending |
| 02-01-04 | 01 | 1 | ERRL-04 | unit | `uv run pytest tests/test_db.py::TestRetryOnHttpError -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | ERRL-05 | unit | `uv run pytest tests/test_db.py::TestRetryOnHttpError::test_raises_nero_unreachable -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | SECR-01 | unit | `uv run pytest tests/test_state.py::TestSafeUpdate -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | SECR-02 | unit | `uv run pytest tests/test_state.py::TestAddPriority -x` | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 1 | SECR-03 | unit | `uv run pytest tests/test_axis_sync.py::TestRunPmCommand -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db.py::TestErrorHierarchy` — stubs for ERRL-01 (MeridianError base, subclass relationships)
- [ ] `tests/test_db.py::TestRetryOnHttpError` — stubs for ERRL-04, ERRL-05 (retry behavior, backoff, NeroUnreachableError)
- [ ] `tests/test_db.py::TestLogging` — stubs for ERRL-03 (setup_logging configures stderr, respects env var)
- [ ] `tests/test_state.py::TestSafeUpdate` — stubs for SECR-01 (column validation, rejection of invalid columns)
- [ ] `tests/test_state.py` — update existing transition tests to expect StateTransitionError instead of ValueError
- [ ] `tests/test_axis_sync.py` — create file with TestRunPmCommand stubs for SECR-03

*Existing infrastructure (conftest.py, pytest config) covers framework needs.*

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
