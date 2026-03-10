# Domain Pitfalls

**Domain:** Claude Code skill engine / SQLite-backed CLI workflow tool
**Researched:** 2026-03-10
**Overall confidence:** HIGH (based on codebase analysis and domain expertise)

## Critical Pitfalls

Mistakes that cause rewrites, data loss, or broken user-facing functionality.

### Pitfall 1: Skill Registration Architecture Mismatch

**What goes wrong:** Claude Code discovers skills by folder name under `~/.claude/skills/`. A symlink at `~/.claude/skills/meridian` pointing to the repo root registers only `/meridian` as a single skill. The 13 subcommands (`:init`, `:plan`, `:execute`, etc.) listed in the root `SKILL.md` are **not discoverable** as separate slash commands because Claude Code uses folder-level routing, not colon-delimited subcommand parsing within a single SKILL.md.

**Why it happens:** The `skills/` directory with 13 subdirectories (each containing their own SKILL.md) exists in the repo, but the symlink points to the repo root, not to individual skill folders. Claude Code sees one skill called "meridian" and reads the root SKILL.md. It never traverses `skills/init/SKILL.md`, `skills/plan/SKILL.md`, etc.

**Consequences:** None of the 13 commands work as individual `/meridian:init` slash commands. Users must manually invoke instructions from the root SKILL.md or run Python scripts directly. The entire command UX is broken.

**Prevention:**
- Each skill folder must be independently discoverable. Two viable approaches:
  1. **Flat symlinks:** Create 13 separate symlinks: `~/.claude/skills/meridian-init -> /path/to/meridian/skills/init`, etc. Commands become `/meridian-init`, `/meridian-plan`.
  2. **Nested skills discovery:** If Claude Code supports nested folder scanning (verify this), restructure so `~/.claude/skills/meridian/init/SKILL.md` is found. Current evidence suggests it does NOT scan subdirectories.
- **Do not assume colon-delimited routing works.** The `:` syntax in SKILL.md is documentation convention, not a routing mechanism.
- Test each command is discoverable after registration changes by invoking it in a fresh Claude Code session.

**Detection:** Run each `/meridian:X` command in Claude Code. If Claude says "I don't know that command" or falls back to the root SKILL.md for all of them, registration is broken.

**Phase mapping:** Phase 1 (Skill Registration Fix) -- this is the foundation; nothing else works until commands are discoverable.

---

### Pitfall 2: SQLite SQLITE_BUSY Under Concurrent Subagent Writes

**What goes wrong:** When multiple subagents execute plans in parallel (wave-based execution), they each open their own `sqlite3.Connection` and attempt writes. SQLite's single-writer model means concurrent writes serialize, and with the default 5-second busy timeout, writers get `sqlite3.OperationalError: database is locked` errors that are **not retried anywhere in the codebase**.

**Why it happens:** The `connect()` function in `db.py` enables WAL mode (good) but sets no busy timeout (`PRAGMA busy_timeout`). The default is 0ms -- immediate failure on lock contention. Every function that writes (`transition_plan`, `create_checkpoint`, `update_nero_dispatch`) will raise an unhandled `OperationalError` on contention.

**Consequences:** Plan execution fails silently or with cryptic errors. State becomes inconsistent -- a plan may have completed its work (code changes, commits) but the state DB never records the completion. Resume prompts then re-execute already-done plans, causing duplicate work or conflicts.

**Prevention:**
- Add `conn.execute("PRAGMA busy_timeout=5000")` in `connect()` immediately after WAL mode. This makes SQLite retry internally for up to 5 seconds before raising.
- Wrap all write operations in a retry decorator: catch `sqlite3.OperationalError`, wait with exponential backoff (100ms, 200ms, 400ms), retry up to 3 times.
- The context manager refactor (`open_project()`) is the natural place to add both busy_timeout and retry logic in one location.
- **Never rely on WAL mode alone for concurrency.** WAL allows concurrent reads during writes, but does not allow concurrent writes.

**Detection:** Run 3+ subagent plans in the same wave. If any fail with "database is locked" or plans complete without state updates, this pitfall has triggered.

**Phase mapping:** Phase 2 (SQLite Hardening) -- must be solved before parallel execution is reliable.

---

### Pitfall 3: Connection Leak on Exception Paths

**What goes wrong:** The `try/finally` pattern used for connection cleanup works, but `dispatch_phase()` opens its own connection AND calls `dispatch_plan()` which opens a second connection. Each `dispatch_plan` call creates a new connection to the same database. Under WAL mode this is safe for reads but creates write contention. More critically, if an exception occurs between opening a connection and reaching the `finally` block (e.g., in argument validation), the connection leaks.

**Why it happens:** No context manager pattern. Each function manages its own connection lifecycle with manual `try/finally`. The `dispatch_phase` function at line 149 calls `dispatch_plan` in a loop, each of which opens and closes its own connection -- creating N+1 connection open/close cycles for N plans.

**Consequences:** File descriptor exhaustion on large dispatches. On macOS, the default ulimit is 256 file descriptors. Dispatching 100+ plans in a phase could exhaust this. More practically, the constant open/close/open/close pattern adds latency and increases lock contention probability.

**Prevention:**
- Extract the `open_project()` context manager as described in CONCERNS.md. Pass `conn` down instead of having each function open its own.
- `dispatch_phase` should open one connection and pass it to a lower-level `_dispatch_plan_with_conn(conn, ...)` function.
- Use `@contextmanager` from `contextlib` (stdlib) for clean resource management.

**Detection:** Monitor open file descriptors during a large phase dispatch. Or add logging to `connect()` and watch for excessive open/close cycles.

**Phase mapping:** Phase 2 (SQLite Hardening) -- part of the connection management refactor.

---

### Pitfall 4: State Transition Map / Schema Constraint Divergence

**What goes wrong:** The valid transitions are defined in two places that must stay synchronized: Python dicts in `state.py` (lines 11-36) and SQL CHECK constraints in `db.py` (lines 48-51, 68-70). Adding a new status to one but not the other creates a state machine that either rejects valid transitions (Python side) or allows invalid ones to persist in the database (SQL side).

**Why it happens:** No single source of truth. The Python transition maps are the runtime enforcement; the SQL CHECK constraints are the persistence-level enforcement. They evolved independently.

**Consequences:** If a new status is added to the CHECK constraint but not the Python map, `transition_phase()` will raise `ValueError` even though the database would accept it. If added to Python but not SQL, the transition succeeds in Python but `INSERT`/`UPDATE` fails with a constraint violation -- and the error message from SQLite is not helpful ("CHECK constraint failed").

**Prevention:**
- Add a startup validation test that verifies every status in every CHECK constraint appears in the corresponding Python transition map, and vice versa.
- When adding migrations that alter status enums, create a checklist: (1) ALTER the CHECK constraint, (2) update the Python transition dict, (3) add test cases for the new transition.
- Consider generating CHECK constraints from the Python dicts at schema creation time, making Python the single source of truth.

**Detection:** Write a test that parses the CHECK constraint SQL and compares it to the keys in `PHASE_TRANSITIONS`, `PLAN_TRANSITIONS`, and `MILESTONE_TRANSITIONS`.

**Phase mapping:** Phase 3 (Test Coverage) -- the validation test prevents future drift.

---

### Pitfall 5: Dynamic SQL Injection Surface During Refactoring

**What goes wrong:** The `update_*` functions in `state.py` build SQL dynamically from `**kwargs` keys. The allowlist pattern (`allowed = {"name", "description", ...}`) is correct but fragile. During refactoring, a developer might add a new field to `allowed` that contains user input in the column name position, or worse, copy the pattern for a new function and forget the allowlist entirely.

**Why it happens:** The `add_priority` function at line 621 already demonstrates the risk: it interpolates `entity_type` directly into `f"UPDATE {entity_type} SET ..."`. Although currently validated against `("phase", "plan")`, this pattern invites copy-paste mistakes.

**Consequences:** SQL injection via column name or table name. Even in a local-only tool, this could corrupt the state database or cause data loss.

**Prevention:**
- Replace `f"UPDATE {entity_type} SET ..."` with a mapping dict: `ENTITY_TABLES = {"phase": "phase", "plan": "plan"}` and use `ENTITY_TABLES[entity_type]`.
- Create a `safe_update(conn, table, entity_id, allowed_fields, **kwargs)` helper that centralizes the dynamic SQL pattern. All update functions delegate to this single implementation.
- Add the `S608` ruff rule (or equivalent) as a project-wide error (not just a suppressed warning) so any new f-string SQL is flagged immediately.
- The `# noqa: S608` suppressions in `state.py` should be audited and replaced with safe patterns, not just suppressed.

**Detection:** `ruff check --select S608` on the codebase. Any new suppressions added during refactoring are a red flag.

**Phase mapping:** Phase 2 (SQLite Hardening) -- fix before adding new update functions.

---

## Moderate Pitfalls

### Pitfall 6: Test sys.path Hacking Breaks in CI and Parallel Test Runs

**What goes wrong:** Every test file does `sys.path.insert(0, str(Path(__file__).parent.parent))` at line 12. This works when running `pytest` from the project root but fails when: (a) running from a different directory, (b) running in CI where the working directory may differ, (c) running tests in parallel with `pytest-xdist` where import paths can collide.

**Prevention:**
- Add to `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  pythonpath = ["."]
  ```
- Remove all `sys.path.insert` lines from test files.
- Do NOT make the project pip-installable just for tests -- the `pythonpath` config is sufficient and keeps the stdlib-only constraint clean.

**Detection:** Run `cd /tmp && pytest /path/to/meridian/tests/` -- if it fails, the path hacking is the problem.

**Phase mapping:** Phase 3 (Test Coverage) -- fix before adding new test files so new tests don't copy the anti-pattern.

---

### Pitfall 7: Missing Busy-Timeout Causes Silent Data Loss in Nero Sync

**What goes wrong:** `sync.py` pulls status updates from Nero and writes them to SQLite. If the database is locked (another subagent writing), the status update fails silently because `urllib.error.URLError` is caught but `sqlite3.OperationalError` is not -- it propagates up and the Nero status is lost. The status was successfully fetched from Nero but never persisted.

**Prevention:**
- Add `sqlite3.OperationalError` to the exception handling in sync operations.
- Implement a write-ahead queue: if the database write fails, store the pending update in memory or a temp file and retry on next sync cycle.
- This is a specific instance of the general SQLITE_BUSY problem (Pitfall 2) but with the added consequence of losing external state.

**Detection:** Check for nero_dispatch records where `status` is stale (still "dispatched" or "running") despite Nero reporting completion.

**Phase mapping:** Phase 2 (SQLite Hardening) -- addressed by the retry logic.

---

### Pitfall 8: Schema Migration Without Rollback or Backup

**What goes wrong:** The `_migrate_v1_to_v2` function modifies the live database with no backup. If a migration partially fails (e.g., the first ALTER succeeds but the second fails due to disk space), the database is left in an inconsistent state -- partially migrated with no way to roll back.

**Prevention:**
- Before any migration, copy `state.db` to `state.db.backup-v{N}` in the same directory.
- Make each migration a single transaction (currently the ALTER statements are not wrapped in a transaction -- SQLite's ALTER TABLE is auto-committed).
- Add a `--dry-run` flag to the migration that reports what would change without executing.
- Test migrations against a snapshot of a real v1 database, not just a freshly created one.

**Detection:** Check for `state.db` files where `schema_version` says v2 but the expected columns don't exist (partial migration).

**Phase mapping:** Phase 2 (SQLite Hardening) -- part of database backup/restore mechanism.

---

### Pitfall 9: N+1 Query Patterns Compound During Refactoring

**What goes wrong:** The codebase has three known N+1 patterns (resume, metrics, export). During refactoring, it is tempting to "fix later" and accidentally introduce more N+1 patterns in new code (e.g., test setup, status commands, dashboard views).

**Prevention:**
- Establish a convention: any function that iterates entities and queries children must use a JOIN or bulk fetch. Add this to the conventions document.
- When writing new tests, avoid test helpers that call single-entity functions in loops. Create bulk seed helpers instead.
- The N+1 patterns are not performance-critical today (single-user, small datasets), so deprioritize fixing existing ones. Focus on preventing new ones.

**Detection:** Add a query counter to the connection wrapper during tests. Assert that specific operations complete in O(1) queries.

**Phase mapping:** Phase 3 (Test Coverage) -- add query-count assertions for critical paths.

---

### Pitfall 10: Error Dict vs Exception Inconsistency Confuses Callers

**What goes wrong:** The codebase uses two error strategies: `state.py` raises `ValueError` for invalid operations, while `dispatch.py` and `sync.py` return `{"status": "error", "message": "..."}` dicts. SKILL.md instructions call Python via `uv run python -c "..."`, which means a raised exception crashes the inline script with a traceback, while an error dict is returned silently (the calling Claude Code instance must check the return value).

**Prevention:**
- Do NOT unify to one pattern right now. Both patterns are valid for their contexts (programming errors vs runtime failures).
- But DO document the convention explicitly: `state.py` raises for caller bugs; `dispatch.py`/`sync.py` return error dicts for external failures.
- In SKILL.md procedures, wrap `state.py` calls in try/except that prints a clear message instead of a raw traceback.
- When adding new modules during refactoring, follow the established convention for that module's domain.

**Detection:** Search for bare `except Exception` blocks -- these often swallow the wrong kind of error.

**Phase mapping:** Phase 3 (Test Coverage) -- test both error paths explicitly.

---

## Minor Pitfalls

### Pitfall 11: Premature `milestone_ready` Flag

**What goes wrong:** `check_auto_advance` at line 593 sets `milestone_ready=True` when the current phase moves to "verifying", but "verifying" is not "complete". The flag is misleading. A caller acting on it would attempt to complete the milestone while a phase is still in review.

**Prevention:** Already documented as a known bug. Fix by only setting `milestone_ready` when the phase reaches "complete", not "verifying". This is a one-line fix but needs a test case first.

**Phase mapping:** Phase 1 (Bug Fixes) -- low effort, high correctness impact.

---

### Pitfall 12: `command.split()` in axis_sync.py

**What goes wrong:** The `_run_pm_command` function splits a command string on whitespace, breaking arguments that contain spaces (phase names, descriptions).

**Prevention:** Build the command as a list from the start: `["axis", "create-ticket", "--name", name, "--description", desc]` instead of formatting a string and splitting it.

**Phase mapping:** Phase 1 (Bug Fixes) -- fix when adding axis_sync tests.

---

### Pitfall 13: Empty String Falsiness in `update_nero_dispatch`

**What goes wrong:** `if status:` at line 528 treats empty string `""` as falsy, silently skipping the update. Should be `if status is not None:`.

**Prevention:** One-line fix. Add a test case that passes `status=""` and verifies it persists.

**Phase mapping:** Phase 1 (Bug Fixes) -- trivial fix.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Skill Registration | Assuming colon-delimited routing works (Pitfall 1) | Test each command in a fresh Claude Code session after any registration change |
| Skill Registration | Breaking existing root SKILL.md while restructuring | Keep root SKILL.md as fallback documentation even after registration fix |
| SQLite Hardening | Introducing connection leaks during context manager refactor (Pitfall 3) | Use `@contextmanager` with explicit cleanup; add connection-tracking in tests |
| SQLite Hardening | Breaking existing tests when changing `connect()` signature | Keep backward-compatible API; add `busy_timeout` as default parameter |
| SQLite Hardening | Partial migration corrupting database (Pitfall 8) | Always backup before migration; test against real v1 databases |
| Test Coverage | Copying `sys.path` hack into new test files (Pitfall 6) | Fix `pyproject.toml` pythonpath FIRST, before writing any new tests |
| Test Coverage | Mocking too much in dispatch/sync tests, hiding real bugs | Use in-memory SQLite for DB layer; only mock HTTP calls to Nero |
| Test Coverage | Tests that pass individually but fail when run together (shared state) | Use `tmp_path` fixtures for all database files; never share connections between tests |
| Bug Fixes | Fixing `check_auto_advance` without a regression test first | Write the failing test BEFORE changing the implementation |
| Bug Fixes | Fixing `command.split()` but breaking existing Axis integration | The current code is already broken for multi-word names; the fix cannot make it worse |

## Sources

- Codebase analysis: `scripts/db.py`, `scripts/state.py`, `scripts/dispatch.py`, `scripts/axis_sync.py`
- Known issues: `.planning/codebase/CONCERNS.md` (2026-03-10 audit)
- Convention analysis: `.planning/codebase/CONVENTIONS.md`
- Skill structure: `skills/*/SKILL.md`, `~/.claude/skills/meridian` symlink
- SQLite documentation on WAL mode and busy timeout (training data, HIGH confidence -- well-established SQLite behavior)
- Claude Code skill discovery behavior (observed from codebase evidence and symlink analysis, MEDIUM confidence -- could not verify current Claude Code docs)

---

*Pitfalls audit: 2026-03-10*
