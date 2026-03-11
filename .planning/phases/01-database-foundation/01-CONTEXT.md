# Phase 1: Database Foundation - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Every database interaction goes through a single reliable pattern with retry, busy tolerance, and backup capability. Pytest runs cleanly from repo root without path hacks. This phase touches `scripts/db.py`, all scripts that open connections, `pyproject.toml`, and `tests/`.

</domain>

<decisions>
## Implementation Decisions

### Context Manager Design
- `open_project(path)` context manager yields a single connection for the entire command duration
- Functions continue to receive `conn` as first parameter (existing convention preserved)
- Auto-commit on clean exit, rollback on exception, close in finally
- All pragmas (WAL, busy_timeout, foreign_keys) set inside open_project() — Claude's discretion on whether to keep connect() internal or wrap it
- All old try/finally + manual conn.close() patterns fully removed — no dual patterns in codebase
- connect() becomes internal to open_project() only (not public API)

### Retry & Busy Tolerance
- `@retry_on_busy` decorator applied to write operations (not reads)
- 3 retries with exponential backoff starting at 0.5s (0.5, 1.0, 2.0)
- busy_timeout=5000ms set at connection level (SQLite-side wait before Python retry kicks in)
- Random jitter of +/-25% on backoff delays to avoid thundering herd from concurrent subagents
- On retry exhaustion, raise `DatabaseBusyError` (custom exception with retry count and total wait time)
- DatabaseBusyError is a standalone exception in Phase 1 — Phase 2 will integrate it into the full MeridianError hierarchy

### Backup Mechanism
- Backups stored in `.meridian/backups/` directory (sibling to state.db)
- Naming: `state-{ISO-timestamp}.db`
- Uses SQLite `connection.backup()` API for hot, consistent snapshots
- Two triggers: manual via backup function + automatic before schema migrations
- Retention: keep last 100 backups (files are small ~100KB), auto-prune oldest beyond limit

### Pytest Configuration
- `pyproject.toml` gets `[tool.pytest.ini_options]` with `pythonpath = ["."]`
- All `sys.path.insert` hacks removed from test files
- Shared `conftest.py` in `tests/` with:
  - `db` fixture: in-memory SQLite with schema (replaces per-file duplicates)
  - `seeded_db` fixture: db + project/milestone/phases pre-created
  - `file_db` fixture: tmp_path-backed DB for path-dependent tests (resume)
- All fixtures use `open_project()` (the new context manager) — tests validate the same path as production
- Existing per-file fixture definitions removed after conftest consolidation

### Claude's Discretion
- Whether connect() stays as a separate internal function or gets inlined into open_project()
- Exact pragma setup location (open_project vs thin wrapper around connect)
- How to handle the in-memory DB case in open_project() for tests (may need a variant or param)
- Exact jitter implementation (random module vs simpler approach)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches for all implementation details.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/db.py`: Already has `connect()`, `get_db_path()`, `init_schema()` — open_project() builds on these
- `scripts/state.py`: All CRUD functions already take `conn` as first param — no signature changes needed
- Test fixtures: `db` and `seeded_db` patterns already established — just need consolidation

### Established Patterns
- `conn` naming convention for connections used consistently everywhere
- `sqlite3.Row` factory set on all connections
- `_row_to_dict()` / `_rows_to_list()` helpers for row conversion
- Functions that receive `conn` never close it (clean ownership convention)

### Integration Points
- `scripts/db.py`: Where open_project() and retry decorator will live
- `pyproject.toml`: pytest config addition
- `tests/conftest.py`: New file for shared fixtures
- Every `__main__` block in scripts/: Will need updating to use open_project()
- Schema migration code: Will need auto-backup call before migrate

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-database-foundation*
*Context gathered: 2026-03-10*
