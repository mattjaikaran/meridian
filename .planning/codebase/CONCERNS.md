# Codebase Concerns

**Analysis Date:** 2026-03-10

## Tech Debt

**Dynamic SQL Construction via f-strings:**
- Issue: Multiple functions build SQL SET clauses dynamically using f-strings with column names derived from `kwargs` keys. While column names are filtered through allowlists (mitigating injection for values), the column names themselves are interpolated unsafely.
- Files: `scripts/state.py` (lines 99, 148, 216, 230, 324, 350, 494, 537), `scripts/state.py:621` (`add_priority` uses `entity_type` directly in table name)
- Impact: The `add_priority` function at line 621 takes `entity_type` as a string and interpolates it into `f"UPDATE {entity_type} SET ..."`. Although validated against `("phase", "plan")`, this pattern is fragile. Any future caller passing unsanitized input would create a SQL injection vector. The `# noqa: S608` suppression acknowledges this.
- Fix approach: Use a mapping dict `{"phase": "UPDATE phase SET ...", "plan": "UPDATE plan SET ..."}` instead of interpolating table names. For dynamic SET clauses, consider a helper function that validates column names against a schema introspection or hardcoded allowlist, making the safety guarantee explicit.

**Duplicated Project Directory / Connection Boilerplate:**
- Issue: Every function in `scripts/dispatch.py`, `scripts/export.py`, `scripts/axis_sync.py`, and `scripts/resume.py` repeats the same pattern: accept `project_dir`, default to `Path.cwd()`, call `get_db_path()`, call `connect()`, wrap in try/finally.
- Files: `scripts/dispatch.py` (lines 22-32, 130-136, 166-171), `scripts/export.py` (lines 19-28, 72-77), `scripts/axis_sync.py` (lines 53-60, 109-113), `scripts/resume.py` (lines 72-81)
- Impact: Maintenance burden. Any change to connection setup (e.g., adding WAL checkpoint, read-only mode) must be replicated in 10+ locations.
- Fix approach: Create a context manager in `scripts/db.py`: `@contextmanager def open_project(project_dir=None, project_id="default")` that yields `(conn, project)` and handles cleanup.

**No `__init__.py` Exports / sys.path Hacking in Tests:**
- Issue: Test files manually insert the parent directory into `sys.path` at line 12 of each test file. The `scripts/` package has an empty `__init__.py` with no public API surface.
- Files: `tests/test_state.py:12`, `tests/test_resume.py:12`, `tests/test_metrics.py:12`, `tests/test_sync.py:12`
- Impact: Tests depend on import path manipulation rather than proper package installation. Running tests outside the project root may fail.
- Fix approach: Add a `[tool.pytest.ini_options]` section in `pyproject.toml` with `pythonpath = ["."]` and remove `sys.path.insert` from all test files. Alternatively, make the project installable with `uv pip install -e .`.

**Inline `timedelta` Import:**
- Issue: `from datetime import timedelta` is imported inside `forecast_completion()` instead of at module top.
- Files: `scripts/metrics.py:217`
- Impact: Minor style issue, but violates PEP 8 import ordering. Could confuse static analysis tools.
- Fix approach: Move to module-level imports.

## Known Bugs

**`check_auto_advance` Milestone Readiness Check is Misleading:**
- Symptoms: The function checks if all phases except the current one are complete, but the current phase just moved to "verifying" (not "complete"). Setting `milestone_ready=True` in the response is premature since the phase still needs review.
- Files: `scripts/state.py:589-596`
- Trigger: Complete all plans in the last phase of a milestone. The response will claim `milestone_ready=True` even though the phase is only in "verifying" state.
- Workaround: Callers must ignore `milestone_ready` until the phase actually reaches "complete" status. The flag is informational only.

**`update_nero_dispatch` Silently Ignores Empty Status:**
- Symptoms: If `status` is an empty string `""`, the truthiness check `if status:` fails, so the status update is silently skipped.
- Files: `scripts/state.py:528-529`
- Trigger: Call `update_nero_dispatch(conn, id, status="")`.
- Workaround: Always pass `None` instead of empty string for no-op. The check should use `if status is not None:` instead.

**`_run_pm_command` Uses Unsafe String Splitting:**
- Symptoms: `command.split()` breaks on commands containing spaces in arguments (e.g., ticket names with spaces).
- Files: `scripts/axis_sync.py:41`
- Trigger: Create a phase with a name containing spaces, then call `create_axis_tickets_for_phases`. The `--description` argument at line 133 embeds the description in quotes, but `split()` will still break it apart.
- Workaround: None. The Axis ticket creation will fail or produce garbled ticket names for multi-word descriptions.

## Security Considerations

**SQL Injection Surface in Dynamic Queries:**
- Risk: Column names from user-provided `kwargs` keys are interpolated into SQL strings. While allowlists exist, the pattern is inherently risky if allowlists become stale.
- Files: `scripts/state.py` (all `update_*` and `transition_*` functions)
- Current mitigation: Each function has an `allowed` set that filters keys. Values are parameterized with `?` placeholders.
- Recommendations: Add a centralized `safe_update()` helper that validates column names against the actual table schema using `PRAGMA table_info`. This makes the safety guarantee schema-driven rather than manually maintained.

**No Authentication on Nero RPC Calls:**
- Risk: All Nero dispatch and sync calls use plain HTTP POST with no authentication headers, API keys, or TLS verification.
- Files: `scripts/dispatch.py:82-87`, `scripts/sync.py:24-31`
- Current mitigation: None. The endpoint URL is stored in the project record and assumed to be on a trusted network.
- Recommendations: Add an optional `nero_api_key` field to the project table. Include it as a `Bearer` token in the `Authorization` header. At minimum, validate that the endpoint uses HTTPS in production.

**Subprocess Calls Without Input Sanitization:**
- Risk: `_run_pm_command` in `axis_sync.py` passes user-controlled phase names and descriptions to a shell command via string splitting.
- Files: `scripts/axis_sync.py:40-45`, `scripts/axis_sync.py:131-133`
- Current mitigation: Uses `subprocess.run` with list args (not `shell=True`), which avoids shell injection. However, the `command.split()` pattern means quotes in phase names could cause argument misalignment.
- Recommendations: Pass arguments as a proper list instead of splitting a formatted string. Use `shlex.quote()` if string building is necessary.

## Performance Bottlenecks

**N+1 Queries in Resume Prompt Generation:**
- Problem: `generate_resume_prompt` iterates over all phases and calls `list_plans(conn, p["id"])` for each one inside the loop.
- Files: `scripts/resume.py:162-168`
- Cause: Each phase triggers a separate SQL query for its plans. With many phases, this creates O(n) database roundtrips.
- Improvement path: Use a single JOIN query to fetch all phases with their plan counts in one query: `SELECT ph.*, COUNT(p.id) as plan_count, SUM(CASE WHEN p.status='complete' THEN 1 ELSE 0 END) as complete_count FROM phase ph LEFT JOIN plan p ON p.phase_id = ph.id WHERE ph.milestone_id = ? GROUP BY ph.id`

**N+1 Queries in `compute_progress`:**
- Problem: Same pattern. Iterates phases, queries plans for each phase individually.
- Files: `scripts/metrics.py:252-253`
- Cause: Separate `SELECT status FROM plan WHERE phase_id = ?` for each phase.
- Improvement path: Single aggregated query as above.

**N+1 Queries in `export_state`:**
- Problem: Nested loop: for each milestone, fetch phases; for each phase, fetch plans.
- Files: `scripts/export.py:38-44`
- Cause: Three levels of sequential queries.
- Improvement path: Fetch all phases and plans for the project in bulk, then assemble the tree in Python.

**Note:** These are not critical at current scale (single-user, small datasets). They would become noticeable with 50+ phases or 200+ plans.

## Fragile Areas

**State Transition Logic:**
- Files: `scripts/state.py:11-36` (transition maps), `scripts/state.py:200-218` (transition_phase), `scripts/state.py:298-326` (transition_plan)
- Why fragile: The transition maps are dictionaries that must stay in sync with the CHECK constraints in `scripts/db.py:48-51` and `scripts/db.py:68-70`. If a new status is added to the schema but not to the Python transition maps, the system will reject valid transitions.
- Safe modification: Always update both `scripts/db.py` (schema CHECK constraints) and `scripts/state.py` (transition dictionaries) simultaneously. Run `tests/test_state.py` after any change.
- Test coverage: Good. Transition tests cover valid and invalid paths for milestones, phases, and plans.

**`compute_next_action` Decision Tree:**
- Files: `scripts/state.py:634-808`
- Why fragile: This 170-line function is a deeply nested if/elif chain that encodes the entire workflow routing logic. Missing a branch or reordering checks could route users to wrong actions.
- Safe modification: Add a new test case in `tests/test_state.py::TestNextAction` for every new status or edge case before changing the function. Consider extracting each status handler into a separate function.
- Test coverage: Good coverage of the happy path. Missing edge cases: what happens when multiple phases are in non-terminal states simultaneously (e.g., one blocked, one executing).

**Schema Migration System:**
- Files: `scripts/db.py:147-169`
- Why fragile: Migrations are manually coded functions (`_migrate_v1_to_v2`). There is no migration runner framework; each new version requires a new function and a new `if current_version < N:` check in `init_schema`.
- Safe modification: When adding v3, create `_migrate_v2_to_v3` and add to `init_schema`. Always make migrations idempotent (check column existence before ALTER).
- Test coverage: Schema init is tested implicitly. No dedicated migration tests that verify upgrading from v1 to v2.

## Scaling Limits

**SQLite Single-Writer:**
- Current capacity: Single concurrent writer. Reads are concurrent with WAL mode.
- Limit: If multiple subagents or Nero workers try to write simultaneously, SQLite will serialize writes and may return SQLITE_BUSY errors.
- Scaling path: The `PRAGMA journal_mode=WAL` in `scripts/db.py:190` helps but does not eliminate the bottleneck. Add retry logic with backoff for `sqlite3.OperationalError` ("database is locked"). For multi-machine scenarios, migrate to PostgreSQL.

**Token Estimation Accuracy:**
- Current capacity: Rough 0.3 tokens/char estimate.
- Limit: The constant `TOKENS_PER_CHAR = 0.3` in `scripts/context_window.py:8` is a rough heuristic. For code-heavy content, actual tokenization can vary 2-3x.
- Scaling path: Use `tiktoken` library for accurate counts if precision matters for checkpoint triggers.

## Dependencies at Risk

**Zero External Dependencies (Positive):**
- The project uses only Python stdlib (`sqlite3`, `json`, `pathlib`, `datetime`, `textwrap`, `subprocess`, `urllib`). This is an explicit design choice per `pyproject.toml:6`.
- Risk: The `urllib.request` HTTP client lacks features like connection pooling, retry logic, and proper TLS certificate handling that `httpx` or `requests` would provide.
- Impact: Nero dispatch/sync calls have no retry logic. A transient network failure causes silent data loss (dispatch recorded as sent but status never updated).
- Migration plan: Consider adding `httpx` as an optional dependency for production Nero communication, keeping stdlib `urllib` as fallback.

**Pytest as Only Dev Dependency:**
- Risk: No pinned version of pytest. The `pyproject.toml` does not declare test dependencies.
- Impact: Test environment may differ between machines.
- Migration plan: Add `[project.optional-dependencies]` with `test = ["pytest>=7.0"]` to `pyproject.toml`.

## Missing Critical Features

**No Retry Logic for Nero Communication:**
- Problem: All HTTP calls to Nero (`dispatch.py`, `sync.py`) make a single attempt with a short timeout. Failures are silently swallowed or returned as error dicts.
- Blocks: Reliable autonomous execution. A brief network hiccup causes a plan dispatch to be lost.

**No Database Backup/Restore:**
- Problem: The SQLite database in `.meridian/state.db` is the single source of truth. There is no backup, snapshot, or restore mechanism.
- Blocks: Safe recovery from database corruption or accidental deletion.

**No Logging:**
- Problem: No logging framework is used anywhere in the codebase. Errors are returned as dicts or swallowed by bare `except Exception` blocks.
- Blocks: Debugging production issues. When a Nero dispatch fails or an Axis sync breaks, there is no audit trail.

## Test Coverage Gaps

**No Tests for `scripts/dispatch.py`:**
- What's not tested: The Nero HTTP dispatch client (`dispatch_plan`, `dispatch_phase`, `check_dispatch_status`).
- Files: `scripts/dispatch.py`
- Risk: Dispatch payload construction, error handling, and connection creation logic are all untested. A malformed payload would only be caught in production.
- Priority: High

**No Tests for `scripts/export.py`:**
- What's not tested: JSON state export (`export_state`, `export_status_summary`).
- Files: `scripts/export.py`
- Risk: Export format changes could silently break Nero consumption of the JSON. File I/O errors are not tested.
- Priority: Medium

**No Tests for `scripts/axis_sync.py`:**
- What's not tested: Axis PM ticket creation and sync. The `_run_pm_command` subprocess call, ticket ID parsing, and status mapping are all untested.
- Files: `scripts/axis_sync.py`
- Risk: The string-splitting command construction and fragile ticket ID parsing (line 137-139) are the most likely failure points. Would need mock-based tests similar to `test_sync.py`.
- Priority: Medium

**No Tests for `scripts/context_window.py`:**
- What's not tested: Token estimation, checkpoint threshold logic, subagent budget checks.
- Files: `scripts/context_window.py`
- Risk: Low -- the logic is simple arithmetic. But the file I/O in `estimate_file_tokens` could fail silently on encoding errors.
- Priority: Low

**No Tests for `scripts/db.py` Migration Path:**
- What's not tested: Upgrading a v1 database to v2. The `_migrate_v1_to_v2` function's idempotency check.
- Files: `scripts/db.py:154-169`
- Risk: A future migration could corrupt existing data if the idempotency check fails.
- Priority: Medium

**Auto-Advancement Not Directly Tested:**
- What's not tested: `check_auto_advance` in `scripts/state.py:549-597`. The function's milestone readiness logic and edge cases (empty plans, mixed terminal states) lack dedicated tests.
- Files: `scripts/state.py:549-597`
- Risk: Auto-advancement is called after plan completion in the workflow. A bug here could leave phases stuck or prematurely advance them.
- Priority: High

---

*Concerns audit: 2026-03-10*
