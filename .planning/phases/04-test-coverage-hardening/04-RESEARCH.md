# Phase 4: Test Coverage & Hardening - Research

**Researched:** 2026-03-11
**Domain:** Python testing (pytest), SQLite query optimization, bug fixes
**Confidence:** HIGH

## Summary

Phase 4 covers two distinct work streams: (1) writing test coverage for 6 untested or under-tested modules (dispatch, export, axis_sync, context_window, auto-advance, migrations), and (2) fixing 6 known code quality issues (three N+1 query bugs, one logic bug in auto-advance, one truthiness bug in update_nero_dispatch, one inline import).

The codebase already has a solid test foundation: 150 tests pass across 8 test files, pytest is configured with `pythonpath = ["."]`, and `conftest.py` provides `db`, `seeded_db`, and `file_db` fixtures. All test patterns use in-memory SQLite and `unittest.mock` for external dependencies (subprocess, HTTP). No new dependencies are needed.

**Primary recommendation:** Split into two plans -- tests first (TEST-03 through TEST-08), then quality fixes (QUAL-01 through QUAL-06). Tests-first ensures the quality fixes have regression coverage.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TEST-03 | Test coverage for dispatch.py (payload construction, error handling, connection creation) | Needs test_dispatch.py; mock _send_to_nero and open_project; verify payload structure, error paths |
| TEST-04 | Test coverage for export.py (JSON format, file I/O, nested entity export) | Needs test_export.py; use tmp_path for file output; verify nested milestone->phase->plan structure |
| TEST-05 | Test coverage for axis_sync.py (command construction, ticket parsing, status mapping) | test_axis_sync.py exists but only tests _run_pm_command; add sync_phase_to_axis, create_axis_tickets, status mapping tests |
| TEST-06 | Test coverage for context_window.py (token estimation, checkpoint thresholds) | Needs test_context_window.py; pure functions, no mocking needed |
| TEST-07 | Test coverage for check_auto_advance() (milestone readiness, edge cases, empty plans) | Add to test_state.py; test incomplete plans, all-complete, empty-plans, non-executing phase |
| TEST-08 | Test coverage for schema migration path (v1->v2 upgrade, idempotency) | Add to test_db.py; create v1 schema, run migration, verify columns added, verify idempotency |
| QUAL-01 | N+1 queries in generate_resume_prompt() replaced with single JOIN | resume.py lines 158-163 call list_plans(conn, p["id"]) inside a loop over phases |
| QUAL-02 | N+1 queries in compute_progress() replaced with single aggregated query | metrics.py lines 251-253 execute per-phase plan query inside loop |
| QUAL-03 | N+1 queries in export_state() replaced with bulk fetch + Python assembly | export.py lines 35-41 call list_phases then list_plans per phase in nested loop |
| QUAL-04 | check_auto_advance() milestone_ready only true when phase is actually complete | state.py line 612-615: current phase just moved to verifying but incomplete check excludes it by ID, incorrectly flagging milestone_ready |
| QUAL-05 | update_nero_dispatch() uses `is not None` instead of truthiness check | state.py line 552: `if status:` fails for status="" (empty string); should be `if status is not None:` |
| QUAL-06 | Inline timedelta import in forecast_completion() moved to module level | metrics.py line 216: `from datetime import timedelta` is inside function body |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | latest (via uv) | Test framework | Already configured in pyproject.toml |
| unittest.mock | stdlib | Mocking HTTP, subprocess, file I/O | Already used throughout test suite |
| sqlite3 | stdlib | In-memory test databases | Already used in conftest.py fixtures |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tmp_path (pytest) | builtin | Temporary file system for export tests | TEST-04 (export_state writes JSON file) |
| monkeypatch (pytest) | builtin | Environment/attribute patching | Alternative to unittest.mock.patch |

### Alternatives Considered
None needed. The existing test stack (pytest + unittest.mock + in-memory SQLite) covers all requirements.

**Installation:**
```bash
# No new packages needed - pytest already in dev dependencies
uv sync --group dev
```

## Architecture Patterns

### Recommended Test Structure
```
tests/
  conftest.py           # Existing: db, seeded_db, file_db fixtures
  test_db.py            # Existing: add migration tests (TEST-08)
  test_state.py         # Existing: add check_auto_advance tests (TEST-07)
  test_axis_sync.py     # Existing: expand with sync/create tests (TEST-05)
  test_dispatch.py      # NEW: dispatch_plan, dispatch_phase, check_dispatch_status (TEST-03)
  test_export.py        # NEW: export_state, export_status_summary (TEST-04)
  test_context_window.py  # NEW: pure function tests (TEST-06)
  test_metrics.py       # Existing: already well covered
  test_resume.py        # Existing: already well covered
```

### Pattern 1: Mock External Dependencies, Use Real DB
**What:** All tests use real in-memory SQLite for state, but mock HTTP calls (_send_to_nero) and subprocess calls (_run_pm_command).
**When to use:** Every test that touches dispatch.py, sync.py, or axis_sync.py.
**Example:**
```python
# Established pattern from test_sync.py
from unittest.mock import patch, MagicMock
from scripts.db import open_project

def test_dispatch_plan(self, seeded_db):
    # Seed real DB state, mock only the HTTP layer
    with patch("scripts.dispatch._send_to_nero") as mock_send:
        mock_send.return_value = {"task_id": "nero-123"}
        # ... test dispatch_plan with real DB queries
```

### Pattern 2: In-Memory Database via open_project(":memory:")
**What:** Use `open_project(":memory:")` for integration-style tests that need the full context manager flow.
**When to use:** When testing functions that call `open_project` internally (dispatch_plan, export_state, sync_phase_to_axis).
**Example:**
```python
# From existing test_axis_sync.py pattern
with open_project(":memory:") as conn:
    create_project(conn, name="Test", repo_path="/tmp")
    # ... seed data, then patch open_project to return this conn
```

### Pattern 3: Fixture-Based DB for Unit Tests
**What:** Use `db` or `seeded_db` fixture from conftest.py for direct function tests.
**When to use:** When testing functions that accept a `conn` parameter (check_auto_advance, compute_progress, update_nero_dispatch).
**Example:**
```python
def test_auto_advance_incomplete_plans(self, seeded_db):
    phase = list_phases(seeded_db, "v1.0")[0]
    # transition to executing, add plans, verify behavior
```

### Anti-Patterns to Avoid
- **Mocking the database:** Never mock SQLite queries. Use in-memory databases instead -- they're fast and test real SQL.
- **Testing internal SQL strings:** Test behavior (return values, side effects), not query text.
- **Shared mutable state between tests:** Each test gets its own `db` fixture (fresh in-memory SQLite).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test database setup | Custom schema init | conftest.py `db` fixture | Already handles schema + row_factory |
| HTTP mocking | Fake HTTP server | `unittest.mock.patch` on `_send_to_nero` | Established pattern in test_sync.py |
| Subprocess mocking | Shell script stubs | `unittest.mock.patch` on `_run_pm_command` | Established pattern in test_axis_sync.py |
| N+1 query detection | Custom profiling | Manual code review + test verification | Small codebase, easy to verify by reading |

## Common Pitfalls

### Pitfall 1: check_auto_advance milestone_ready False Positive (QUAL-04)
**What goes wrong:** `check_auto_advance()` at line 612 excludes the current phase by ID when checking for incomplete phases, but the current phase was just moved to "verifying" (not "complete"). So if this is the only non-complete phase, `incomplete` is empty and `milestone_ready=True` is incorrectly set.
**Why it happens:** The exclusion filter `p["id"] != phase_id` removes the just-transitioned phase from the check, making it look like all phases are complete.
**How to avoid:** Don't exclude current phase from the check. After moving to "verifying", the phase IS incomplete. Only flag milestone_ready when ALL phases (including current) are complete.
**Warning signs:** milestone_ready=True when the current phase is still in "verifying" state.

### Pitfall 2: update_nero_dispatch Truthiness Bug (QUAL-05)
**What goes wrong:** `if status:` on line 552 evaluates `""` (empty string) as falsy, so passing `status=""` does nothing.
**Why it happens:** Python truthiness -- empty string is falsy.
**How to avoid:** Use `if status is not None:` for explicit None checking.
**Warning signs:** Status updates with empty string are silently ignored.

### Pitfall 3: N+1 Queries in Phase Overview (QUAL-01/02/03)
**What goes wrong:** Three functions loop over phases and execute a query per phase to get plans.
**Where:**
  - `generate_resume_prompt()` lines 158-163: `list_plans(conn, p["id"])` in loop
  - `compute_progress()` lines 252-253: per-phase plan query in loop
  - `export_state()` lines 36-40: `list_phases` then `list_plans` per phase in nested loop
**How to fix:** Single query with JOIN or bulk fetch all plans for milestone, then group in Python.

### Pitfall 4: Inline Import in forecast_completion (QUAL-06)
**What goes wrong:** `from datetime import timedelta` on line 216 is inside the function body.
**Why it happens:** Likely added during development and never moved.
**How to fix:** Move to module-level imports. `timedelta` is already available from `datetime` which is imported at line 6.

## Code Examples

### N+1 Fix Pattern: Bulk Fetch + Python Assembly
```python
# BEFORE (N+1): one query per phase
for phase in phases:
    plans = conn.execute(
        "SELECT status FROM plan WHERE phase_id = ?", (phase["id"],)
    ).fetchall()

# AFTER (bulk): single query, Python grouping
from collections import defaultdict

all_plans = conn.execute(
    """SELECT p.phase_id, p.status FROM plan p
    JOIN phase ph ON p.phase_id = ph.id
    WHERE ph.milestone_id = ?""",
    (milestone_id,),
).fetchall()

plans_by_phase = defaultdict(list)
for plan in all_plans:
    plans_by_phase[plan["phase_id"]].append(dict(plan))

# Then use plans_by_phase[phase["id"]] in the loop
```

### check_auto_advance Fix Pattern
```python
# BEFORE (buggy): excludes current phase
incomplete = [p for p in all_phases if p["status"] != "complete" and p["id"] != phase_id]
if not incomplete:
    result["milestone_ready"] = True

# AFTER (correct): check ALL phases including current (which is now "verifying")
all_phases_after = list_phases(conn, milestone_id)  # re-fetch after transition
incomplete = [p for p in all_phases_after if p["status"] != "complete"]
if not incomplete:
    result["milestone_ready"] = True
# Note: this will correctly return False since current phase is "verifying"
```

### update_nero_dispatch Fix Pattern
```python
# BEFORE (buggy)
if status:
    updates["status"] = status

# AFTER (correct)
if status is not None:
    updates["status"] = status
if pr_url is not None:
    updates["pr_url"] = pr_url
```

### Migration Idempotency Test Pattern
```python
def test_migration_v1_to_v2_idempotent(self, db):
    """Running migration twice doesn't error."""
    from scripts.db import _migrate_v1_to_v2
    _migrate_v1_to_v2(db)  # First run
    _migrate_v1_to_v2(db)  # Second run -- should not raise
    # Verify priority column exists
    columns = {row[1] for row in db.execute("PRAGMA table_info(phase)").fetchall()}
    assert "priority" in columns
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via uv dev dependency) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TEST-03 | dispatch.py payload construction, error paths | unit | `uv run pytest tests/test_dispatch.py -x` | -- Wave 0 |
| TEST-04 | export.py JSON output, file I/O, nested entities | unit | `uv run pytest tests/test_export.py -x` | -- Wave 0 |
| TEST-05 | axis_sync.py status mapping, ticket creation | unit | `uv run pytest tests/test_axis_sync.py -x` | Partial (only _run_pm_command) |
| TEST-06 | context_window.py token estimation, thresholds | unit | `uv run pytest tests/test_context_window.py -x` | -- Wave 0 |
| TEST-07 | check_auto_advance edge cases | unit | `uv run pytest tests/test_state.py::TestAutoAdvance -x` | -- Wave 0 |
| TEST-08 | Schema migration v1->v2, idempotency | unit | `uv run pytest tests/test_db.py::TestMigration -x` | -- Wave 0 |
| QUAL-01 | generate_resume_prompt uses single query | unit | `uv run pytest tests/test_resume.py -x` | Existing (verify after fix) |
| QUAL-02 | compute_progress uses single query | unit | `uv run pytest tests/test_metrics.py -x` | Existing (verify after fix) |
| QUAL-03 | export_state uses bulk fetch | unit | `uv run pytest tests/test_export.py -x` | -- Wave 0 |
| QUAL-04 | check_auto_advance milestone_ready correct | unit | `uv run pytest tests/test_state.py::TestAutoAdvance -x` | -- Wave 0 |
| QUAL-05 | update_nero_dispatch None vs empty string | unit | `uv run pytest tests/test_state.py::TestNeroDispatch -x` | -- Wave 0 |
| QUAL-06 | timedelta import at module level | unit | `uv run pytest tests/test_metrics.py -x` | Existing |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q`
- **Per wave merge:** `uv run pytest -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_dispatch.py` -- covers TEST-03
- [ ] `tests/test_export.py` -- covers TEST-04, QUAL-03
- [ ] `tests/test_context_window.py` -- covers TEST-06
- [ ] Expand `tests/test_axis_sync.py` -- covers TEST-05 (sync/create functions)
- [ ] Expand `tests/test_state.py` -- covers TEST-07 (TestAutoAdvance), QUAL-04, QUAL-05 (TestNeroDispatch)
- [ ] Expand `tests/test_db.py` -- covers TEST-08 (TestMigration)

## Specific Bug Analysis

### QUAL-04: check_auto_advance milestone_ready
**Location:** `scripts/state.py` lines 571-619
**Current behavior:** After transitioning current phase to "verifying", it checks other phases excluding current by ID. If only 2 phases exist and the other is already complete, `incomplete` is empty, so `milestone_ready=True`.
**Correct behavior:** milestone_ready should only be True when the current phase is "complete" (after review), not just "verifying". The simplest fix: re-fetch all phases after the transition and check without excluding any.
**Test case:** Create milestone with 2 phases. Complete phase 1. Execute phase 2 with all plans complete. Call check_auto_advance(). Verify milestone_ready is False (phase 2 is "verifying", not "complete").

### QUAL-05: update_nero_dispatch truthiness
**Location:** `scripts/state.py` lines 545-562
**Bug:** Line 552 `if status:` and line 554 `if pr_url:` use truthiness, which fails for empty strings.
**Fix:** Change both to `if status is not None:` and `if pr_url is not None:`.
**Test case:** Create dispatch, call `update_nero_dispatch(conn, id, status="")`. Verify status is set to empty string in DB.

### QUAL-01/02/03: N+1 Query Locations
**QUAL-01 (resume.py:158-163):** `generate_resume_prompt` Phase Overview section loops over phases and calls `list_plans(conn, p["id"])` for each.
**QUAL-02 (metrics.py:251-253):** `compute_progress` loops over phases and queries plans per phase.
**QUAL-03 (export.py:35-41):** `export_state` nested loop: `list_phases` per milestone, then `list_plans` per phase.
**Fix pattern:** For each, fetch all plans for the milestone in one query and group by phase_id in Python.

## Open Questions

1. **N+1 fix scope for resume.py**
   - What we know: The Phase Overview section (lines 158-163) has the N+1 loop
   - What's unclear: Whether the plans fetched on lines 110-116 (for current phase only) should also be consolidated
   - Recommendation: Only fix the Phase Overview loop (lines 158-163) since lines 110-116 fetch plans for a single known phase (not N+1)

2. **QUAL-04 fix approach**
   - What we know: milestone_ready is incorrectly True after phase moves to "verifying"
   - What's unclear: Whether the intent was "all plans done" (current behavior) or "all phases complete" (correct per requirement)
   - Recommendation: Follow the requirement literally -- milestone_ready=False when phase has incomplete plans (i.e., phase is not "complete"). Simply remove the `p["id"] != phase_id` exclusion so the just-transitioned "verifying" phase is counted as incomplete.

## Sources

### Primary (HIGH confidence)
- Direct source code analysis of all scripts/*.py and tests/*.py files
- pyproject.toml for test configuration
- conftest.py for existing fixture patterns
- REQUIREMENTS.md for exact requirement text

### Secondary (MEDIUM confidence)
- STATE.md for project decisions context

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - already established, no new dependencies
- Architecture: HIGH - following existing test patterns verbatim
- Pitfalls: HIGH - bugs identified by direct code reading, not inference
- Test coverage gaps: HIGH - verified by comparing scripts/*.py against tests/*.py

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- stdlib-only project)
