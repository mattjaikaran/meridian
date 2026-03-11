---
phase: 1
slug: database-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (latest, already in use) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] — needs creating |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DBRL-01 | unit | `pytest tests/test_db.py::test_open_project -x` | No — W0 | pending |
| 01-01-02 | 01 | 1 | DBRL-02 | unit | `pytest tests/test_db.py::test_busy_timeout_pragma -x` | No — W0 | pending |
| 01-01-03 | 01 | 1 | DBRL-03 | unit | `pytest tests/test_db.py::test_retry_on_busy -x` | No — W0 | pending |
| 01-01-04 | 01 | 1 | DBRL-04 | unit | `pytest tests/test_db.py::test_backup -x` | No — W0 | pending |
| 01-02-01 | 02 | 1 | DBRL-05 | smoke | `grep -r "conn.close()" scripts/ \| grep -v __pycache__` returns empty | No | pending |
| 01-03-01 | 03 | 1 | TEST-01 | smoke | `python -c "import tomllib; c=tomllib.load(open('pyproject.toml','rb')); assert c['tool']['pytest']['ini_options']['pythonpath']"` | No — W0 | pending |
| 01-03-02 | 03 | 1 | TEST-02 | smoke | `grep -r "sys.path.insert" tests/ \| grep -v __pycache__` returns empty | No | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db.py` — stubs for DBRL-01, DBRL-02, DBRL-03, DBRL-04
- [ ] `tests/conftest.py` — shared fixtures (db, seeded_db, file_db) replacing per-file duplicates
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section — TEST-01
- [ ] Verify pytest dev dependency: `uv add --dev pytest`

*Wave 0 creates the test infrastructure that subsequent plans validate against.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| All scripts use open_project() | DBRL-05 | Pattern compliance check across codebase | `grep -r "conn.close()" scripts/ \| grep -v __pycache__` must return empty |
| No sys.path.insert in tests | TEST-02 | Absence check across test files | `grep -r "sys.path.insert" tests/ \| grep -v __pycache__` must return empty |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
