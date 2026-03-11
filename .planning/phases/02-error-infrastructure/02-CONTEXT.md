# Phase 2: Error Infrastructure - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

All failures produce structured, actionable errors instead of silent None returns or generic ValueErrors. Structured logging replaces ad-hoc print() for operational output. HTTP retry logic makes Nero communication reliable. SQL injection surface is eliminated.

Requirements: ERRL-01, ERRL-02, ERRL-03, ERRL-04, ERRL-05, SECR-01, SECR-02, SECR-03

</domain>

<decisions>
## Implementation Decisions

### Error hierarchy
- Minimal: 3 new classes (MeridianError, StateTransitionError, NeroUnreachableError) plus existing DatabaseBusyError
- All live in `scripts/db.py` — no new files
- Message-only (simple Exception subclass with descriptive string, no structured context dict)
- DatabaseBusyError re-parented under MeridianError (already exists from Phase 1)
- Replace return-error-dict pattern in dispatch.py and sync.py with NeroUnreachableError exceptions
- Existing ValueError raises in state.py transition functions → StateTransitionError

### Logging
- Default level: WARNING (quiet on success, visible on retries/errors)
- Configuration: `MERIDIAN_LOG_LEVEL` environment variable (no CLI flags)
- Format: human-readable (`module: message`) to stderr
- Keep `print()` for intentional CLI output in `__main__` blocks (usage, results, JSON dumps)
- Convert operational/diagnostic print() calls to `logging.warning()` / `logging.info()`
- Per-module loggers: `logger = logging.getLogger(__name__)`
- Centralized `setup_logging()` called from `open_project()` or module init

### Nero HTTP retry
- Separate `@retry_on_http_error` decorator (not reusing `@retry_on_busy` from Phase 1)
- 3 retries with 1s/2s/4s exponential backoff (matches spec)
- Log each retry at WARNING level, final failure at ERROR
- Retry on: connection refused, timeout, URLError (network), HTTP 500/502/503/504
- Fail immediately on: HTTP 4xx (client errors — request is wrong, retrying won't help)
- Applied to both `dispatch.py` and `sync.py` (both make HTTP calls to Nero)
- Final failure raises `NeroUnreachableError` (not error dict)

### SQL injection elimination
- `safe_update()` helper with hardcoded per-table column allowlists (not PRAGMA table_info)
- Centralized `ALLOWED_COLUMNS` dict mapping table names to allowed column sets
- Existing `update_*` functions become thin wrappers around `safe_update()`
- `add_priority()` table interpolation → explicit `TABLE_MAP = {"phase": "phase", "plan": "plan"}`
- `axis_sync.py` `_run_pm_command` → build subprocess argument list directly (no string building + split)
- Scope: fix the injection risks only, not a full dynamic SQL refactor

### Claude's Discretion
- Exact placement of `setup_logging()` call (open_project, module init, or lazy)
- Whether `@retry_on_http_error` lives in db.py or a new retry utility section
- How to handle the `# noqa: S608` suppressions after safe_update migration
- Test structure for the new error classes and retry logic

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `@retry_on_busy` decorator in `scripts/db.py`: Pattern reference for the new HTTP retry decorator (same backoff style, different error types)
- `DatabaseBusyError` in `scripts/db.py`: Already exists, needs re-parenting under MeridianError
- `open_project()` context manager in `scripts/db.py`: Natural place to wire up logging initialization

### Established Patterns
- Per-function `allowed` set for column filtering: Already exists in every `update_*` function — `safe_update()` centralizes this
- `_row_to_dict()` / `_rows_to_list()` helpers: Pattern for small utility functions in db.py
- Section dividers (`# -- Entity CRUD ──────`) in state.py: Follow same style for new error section

### Integration Points
- `scripts/state.py`: 8 `raise ValueError` calls → `raise StateTransitionError`
- `scripts/dispatch.py`: 3 error-dict returns → `raise NeroUnreachableError`
- `scripts/sync.py`: error-dict returns → `raise NeroUnreachableError`
- `scripts/axis_sync.py:41`: `command.split()` → direct list construction
- `scripts/state.py:621`: `f"UPDATE {entity_type}"` → TABLE_MAP lookup
- All `scripts/*.py __main__` blocks: keep print(), add logging to operational code

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. User consistently chose the recommended (simplest) option for all decisions, indicating preference for minimal, targeted changes.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-error-infrastructure*
*Context gathered: 2026-03-10*
