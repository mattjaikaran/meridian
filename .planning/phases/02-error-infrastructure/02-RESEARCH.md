# Phase 2: Error Infrastructure - Research

**Researched:** 2026-03-10
**Domain:** Python error handling, stdlib logging, HTTP retry, SQL safety
**Confidence:** HIGH

## Summary

Phase 2 transforms Meridian's error handling from a mix of `ValueError` raises and silent error-dict returns into a structured exception hierarchy with retry logic and proper logging. The scope is well-bounded: 3 new exception classes in `db.py`, a `@retry_on_http_error` decorator for Nero calls, stdlib `logging` replacing operational `print()` calls, and a `safe_update()` helper eliminating dynamic SQL column interpolation.

All changes use Python stdlib only (no external dependencies). The existing `@retry_on_busy` decorator and `DatabaseBusyError` in `db.py` provide a proven pattern to follow for the HTTP retry decorator. The codebase has clear integration points: 10 `raise ValueError` calls in `state.py` (8 are transition-related), 3 error-dict returns in `dispatch.py`, 1 `_nero_rpc` returning `None` in `sync.py`, and 1 unsafe `command.split()` in `axis_sync.py`.

**Primary recommendation:** Keep all error classes in `db.py`, put `@retry_on_http_error` in `db.py` alongside `@retry_on_busy`, add `setup_logging()` to `db.py` called from `open_project()`. This follows the established pattern of `db.py` as the infrastructure/reliability layer.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Minimal error hierarchy: 3 new classes (MeridianError, StateTransitionError, NeroUnreachableError) plus existing DatabaseBusyError
- All live in `scripts/db.py` -- no new files
- Message-only (simple Exception subclass with descriptive string, no structured context dict)
- DatabaseBusyError re-parented under MeridianError
- Replace return-error-dict pattern in dispatch.py and sync.py with NeroUnreachableError exceptions
- Existing ValueError raises in state.py transition functions -> StateTransitionError
- Default log level: WARNING, configured via `MERIDIAN_LOG_LEVEL` env var
- Format: human-readable (`module: message`) to stderr
- Keep `print()` for intentional CLI output in `__main__` blocks
- Per-module loggers: `logger = logging.getLogger(__name__)`
- Centralized `setup_logging()` called from `open_project()` or module init
- Separate `@retry_on_http_error` decorator (not reusing `@retry_on_busy`)
- 3 retries with 1s/2s/4s exponential backoff
- Retry on: connection refused, timeout, URLError (network), HTTP 500/502/503/504
- Fail immediately on HTTP 4xx
- Applied to both dispatch.py and sync.py
- Final failure raises NeroUnreachableError
- `safe_update()` with hardcoded per-table column allowlists (not PRAGMA table_info)
- `add_priority()` table interpolation -> explicit TABLE_MAP
- `axis_sync.py` `_run_pm_command` -> build subprocess argument list directly
- Scope: fix injection risks only, not a full dynamic SQL refactor

### Claude's Discretion
- Exact placement of `setup_logging()` call (open_project, module init, or lazy)
- Whether `@retry_on_http_error` lives in db.py or a new retry utility section
- How to handle `# noqa: S608` suppressions after safe_update migration
- Test structure for new error classes and retry logic

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERRL-01 | `MeridianError` base class with `StateTransitionError`, `DatabaseBusyError`, `NeroUnreachableError` subclasses | Error hierarchy pattern in db.py, re-parent DatabaseBusyError |
| ERRL-02 | All state transition failures raise `StateTransitionError` instead of generic `ValueError` | 8 transition ValueError raises in state.py identified at lines 137-141, 203-208, 307-312, 484-486 |
| ERRL-03 | Structured logging via stdlib `logging` module to stderr, replacing ad-hoc `print()` calls | 14 print() calls identified; 8 are `__main__` CLI output (keep), 0 are operational (all prints are already in __main__ blocks) |
| ERRL-04 | Nero HTTP dispatch/sync calls retry with exponential backoff (3 attempts, 1s/2s/4s) | `@retry_on_http_error` decorator pattern based on existing `@retry_on_busy` |
| ERRL-05 | Failed Nero calls raise `NeroUnreachableError` after retry exhaustion instead of returning None | dispatch.py line 91-95 (error dict return), sync.py line 34 (None return), sync.py line 184 (error dict return) |
| SECR-01 | Dynamic SQL column interpolation replaced with safe_update helper | 8 f-string UPDATE statements in state.py at lines 99, 148, 216, 230, 324, 350, 494, 537 |
| SECR-02 | `add_priority()` table name interpolation replaced with explicit mapping dict | state.py line 621, single `# noqa: S608` |
| SECR-03 | `_run_pm_command` in axis_sync uses proper list arguments instead of `command.split()` | axis_sync.py line 41, affects lines 78 and 126-129 |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| logging (stdlib) | Python 3.11+ | Structured log output to stderr | Built-in, zero dependencies, per-module loggers |
| urllib.request (stdlib) | Python 3.11+ | HTTP client for Nero RPC | Already in use, stdlib-only constraint |
| urllib.error (stdlib) | Python 3.11+ | HTTP error handling | Already in use for URLError catching |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| functools (stdlib) | Python 3.11+ | `@functools.wraps` for decorator | Already used in `@retry_on_busy` |
| time (stdlib) | Python 3.11+ | `time.sleep()` for backoff delays | Already used in `@retry_on_busy` |
| os (stdlib) | Python 3.11+ | `os.environ.get()` for log level | Read `MERIDIAN_LOG_LEVEL` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib logging | structlog/loguru | Better API but adds dependency -- violates stdlib-only constraint |
| urllib retry | tenacity/urllib3 | More features but adds dependency -- violates stdlib-only constraint |
| Hardcoded allowlists | PRAGMA table_info | More dynamic but adds DB round-trip on every update, harder to reason about |

## Architecture Patterns

### Error Hierarchy (in db.py)

```python
# -- Exceptions ----------------------------------------------------------------

class MeridianError(Exception):
    """Base class for all Meridian errors."""

class DatabaseBusyError(MeridianError):
    """Raised when database remains locked after all retry attempts."""
    def __init__(self, retries: int, total_wait: float) -> None:
        self.retries = retries
        self.total_wait = total_wait
        super().__init__(
            f"Database busy after {retries} retries ({total_wait:.1f}s total wait)"
        )

class StateTransitionError(MeridianError):
    """Raised when an invalid state transition is attempted."""

class NeroUnreachableError(MeridianError):
    """Raised when Nero is unreachable after retry exhaustion."""
```

**Key detail:** `DatabaseBusyError` already has structured `__init__` with retries/total_wait. Keep that. `StateTransitionError` and `NeroUnreachableError` are message-only (inherit plain `Exception.__init__`).

### Logging Setup Pattern

```python
import logging
import os

def setup_logging() -> None:
    """Configure Meridian logging. Call once at process start."""
    level_name = os.environ.get("MERIDIAN_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
        force=True,  # Override any prior basicConfig
    )
```

**Placement recommendation:** Call `setup_logging()` at the top of `open_project()` using a module-level flag to ensure it runs exactly once. This is the cleanest approach since `open_project()` is the canonical entry point for all Meridian operations.

```python
_logging_configured = False

@contextlib.contextmanager
def open_project(path: str | Path | None = None):
    global _logging_configured
    if not _logging_configured:
        setup_logging()
        _logging_configured = True
    # ... rest of open_project
```

### Per-Module Logger Pattern

Each module that needs logging adds at module level:

```python
import logging
logger = logging.getLogger(__name__)
```

Usage: `logger.warning("Retrying Nero call (%d/%d)", attempt, max_retries)`

### HTTP Retry Decorator Pattern

```python
def retry_on_http_error(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that retries on transient HTTP/network errors.

    Retries on: URLError (network), timeout, HTTP 500/502/503/504.
    Fails immediately on: HTTP 4xx (client errors).
    Raises NeroUnreachableError after exhausting retries.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code < 500:
                        raise  # 4xx = client error, don't retry
                    if attempt == max_retries:
                        raise NeroUnreachableError(
                            f"Nero unreachable after {max_retries} retries: HTTP {e.code}"
                        ) from e
                    delay = base_delay * (2 ** attempt)
                    logger.warning("Nero HTTP %d, retrying in %.0fs (%d/%d)",
                                   e.code, delay, attempt + 1, max_retries)
                    time.sleep(delay)
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    if attempt == max_retries:
                        raise NeroUnreachableError(
                            f"Nero unreachable after {max_retries} retries: {e}"
                        ) from e
                    delay = base_delay * (2 ** attempt)
                    logger.warning("Nero connection error, retrying in %.0fs (%d/%d): %s",
                                   delay, attempt + 1, max_retries, e)
                    time.sleep(delay)
        return wrapper
    return decorator
```

**Key differences from `@retry_on_busy`:**
- Catches `urllib.error.HTTPError` and `urllib.error.URLError` instead of `sqlite3.OperationalError`
- Distinguishes retryable 5xx from non-retryable 4xx
- No jitter needed (not competing for a shared resource)
- Backoff: 1s, 2s, 4s (vs 0.5s base for DB)
- Logs at WARNING on each retry, ERROR on final failure

### safe_update() Pattern

```python
# Centralized column allowlists
ALLOWED_COLUMNS = {
    "project": {"name", "repo_path", "repo_url", "tech_stack", "nero_endpoint",
                "axis_project_id", "updated_at"},
    "milestone": {"status", "completed_at"},
    "phase": {"name", "description", "context_doc", "acceptance_criteria",
              "axis_ticket_id", "status", "started_at", "completed_at", "priority"},
    "plan": {"name", "description", "wave", "tdd_required", "files_to_create",
             "files_to_modify", "test_command", "executor_type", "status",
             "started_at", "completed_at", "commit_sha", "error_message", "priority"},
    "quick_task": {"status", "completed_at", "commit_sha"},
    "nero_dispatch": {"status", "pr_url", "completed_at"},
}

def safe_update(conn, table: str, row_id, updates: dict, id_column: str = "id") -> None:
    """Execute a parameterized UPDATE with column validation.

    Raises ValueError if any column is not in the allowlist for the table.
    """
    allowed = ALLOWED_COLUMNS.get(table)
    if allowed is None:
        raise ValueError(f"Unknown table: {table}")
    invalid = set(updates.keys()) - allowed
    if invalid:
        raise ValueError(f"Invalid columns for {table}: {invalid}")
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [row_id]
    conn.execute(f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?", values)
```

**Important:** The f-string for SET clause and table name is still technically dynamic SQL, but both are validated against hardcoded allowlists. The `table` parameter is validated against `ALLOWED_COLUMNS` keys, and columns are validated against per-table sets. This is the standard safe pattern for dynamic updates.

### TABLE_MAP for add_priority()

```python
_PRIORITY_SQL = {
    "phase": "UPDATE phase SET priority = ? WHERE id = ?",
    "plan": "UPDATE plan SET priority = ? WHERE id = ?",
}

def add_priority(conn, entity_type: str, entity_id: int, priority: str) -> dict:
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"Invalid priority '{priority}'. Valid: {VALID_PRIORITIES}")
    sql = _PRIORITY_SQL.get(entity_type)
    if sql is None:
        raise ValueError(f"Invalid entity_type '{entity_type}'. Must be 'phase' or 'plan'.")
    conn.execute(sql, (priority, entity_id))
    conn.commit()
    # ...
```

This eliminates the `# noqa: S608` suppression entirely.

### Anti-Patterns to Avoid
- **Catching too broadly in retry:** Don't catch `Exception` in the HTTP retry decorator. Only catch the specific urllib errors that indicate transient failures.
- **Logging in `__init__` of exception classes:** Keep exception classes simple. Log at the call site, not inside the exception.
- **Calling `setup_logging()` in every module:** Call it once from `open_project()`. Modules just get loggers with `logging.getLogger(__name__)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Log formatting | Custom format string builder | `logging.basicConfig(format=...)` | stdlib handles encoding, threading, stream management |
| Log level parsing | Custom env var parsing | `getattr(logging, level_name, logging.WARNING)` | Handles all standard level names, graceful fallback |
| Retry backoff | Custom sleep loop | Decorator pattern with `functools.wraps` | Already proven in `@retry_on_busy`, consistent API |

## Common Pitfalls

### Pitfall 1: Double logging from basicConfig
**What goes wrong:** Calling `logging.basicConfig()` multiple times (e.g., in tests) silently does nothing after the first call.
**Why it happens:** `basicConfig` is a no-op if the root logger already has handlers.
**How to avoid:** Use `force=True` parameter (Python 3.8+) in `basicConfig()` to allow reconfiguration. Guard with `_logging_configured` flag for performance.
**Warning signs:** Log output disappearing or going to wrong stream.

### Pitfall 2: urllib.error.HTTPError is a subclass of URLError
**What goes wrong:** If you catch `URLError` before `HTTPError`, the HTTPError branch never executes.
**Why it happens:** `HTTPError` inherits from `URLError` in Python's urllib.
**How to avoid:** Always catch `HTTPError` first, then `URLError` in except chains.
**Warning signs:** 4xx errors being retried instead of failing immediately.

### Pitfall 3: Breaking existing callers of dispatch functions
**What goes wrong:** Code that checks `result["status"] == "error"` breaks when functions now raise exceptions.
**Why it happens:** Changing return-error-dict to raise-exception changes the API contract.
**How to avoid:** Search the entire codebase for callers of `dispatch_plan`, `_nero_rpc`, `push_state_to_nero`. Update all call sites to use try/except.
**Warning signs:** Unhandled `NeroUnreachableError` exceptions in `__main__` blocks.

### Pitfall 4: safe_update column set drift
**What goes wrong:** A new column is added to the schema but not to `ALLOWED_COLUMNS`, causing valid updates to be silently rejected (or raise ValueError).
**Why it happens:** Two separate places need updating (schema + allowlist).
**How to avoid:** Add a comment in `ALLOWED_COLUMNS` pointing to the schema, and vice versa. Consider a test that verifies allowlist matches schema.
**Warning signs:** Updates that work in raw SQL but fail through `safe_update()`.

### Pitfall 5: StateTransitionError vs ValueError scope
**What goes wrong:** Converting ALL ValueErrors in state.py to StateTransitionError, including non-transition errors like "entity not found" or "invalid priority".
**Why it happens:** Overly broad conversion.
**How to avoid:** Only convert ValueErrors that are about invalid state transitions. Keep ValueError for "not found" and "invalid argument" errors. Per CONTEXT.md: "Existing ValueError raises in state.py transition functions -> StateTransitionError" -- this means the transition validity errors, not the "not found" errors.
**Warning signs:** Callers catching `StateTransitionError` when they should catch `ValueError`.

## Code Examples

### Exact integration points in state.py

Lines to change from `raise ValueError` to `raise StateTransitionError`:
```
Line 139-141: transition_milestone invalid transition
Line 205-208: transition_phase invalid transition
Line 309-312: transition_plan invalid transition
Line 486: transition_quick_task invalid transition
```

Lines to KEEP as `raise ValueError` (not transition errors):
```
Line 137: "Milestone not found" -- entity lookup failure
Line 203: "Phase not found" -- entity lookup failure
Line 307: "Plan not found" -- entity lookup failure
Line 484: "Quick task not found" -- entity lookup failure
Line 616: "Invalid priority" -- argument validation
Line 618: "Invalid entity_type" -- argument validation
```

### Exact integration points in dispatch.py

```python
# Line 91-95: Currently returns error dict, should raise NeroUnreachableError
# But this is inside the HTTP call -- the @retry_on_http_error decorator handles this.
# After decorator is applied, the try/except at line 88-95 can be removed entirely.
# The decorator catches URLError/HTTPError and retries, then raises NeroUnreachableError.
```

### Exact integration points in sync.py

```python
# Line 30-34: _nero_rpc returns None on failure
# After @retry_on_http_error: remove try/except, let decorator handle retries
# Callers of _nero_rpc that check `if not result:` need updating

# Line 71-79: check for `if not result:` returns unreachable message
# After change: _nero_rpc raises NeroUnreachableError instead of returning None
# This except block becomes unnecessary (let exception propagate)

# Line 183-184: push_state_to_nero returns error dict on failure
# Same pattern: let NeroUnreachableError propagate
```

### axis_sync.py fix

```python
# Current (line 41):
result = subprocess.run(
    ["bash", str(pm_script)] + command.split(),
    ...
)

# Fixed: _run_pm_command takes args as list
def _run_pm_command(args: list[str]) -> str:
    pm_script = Path.home() / "zeroclaw" / "skills" / "kanban" / "pm.sh"
    if not pm_script.exists():
        raise FileNotFoundError(f"PM script not found at {pm_script}")
    result = subprocess.run(
        ["bash", str(pm_script)] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip()

# Callers change from:
_run_pm_command(f"ticket move {ticket_id} {axis_status}")
# To:
_run_pm_command(["ticket", "move", ticket_id, axis_status])

# And from:
_run_pm_command(
    f'ticket add {axis_project} "{phase["name"]}" '
    f'--description "{phase.get("description", "")}"'
)
# To:
_run_pm_command([
    "ticket", "add", axis_project, phase["name"],
    "--description", phase.get("description", ""),
])
```

### Print audit results

All `print()` calls in the codebase are inside `if __name__ == "__main__"` blocks:
- `scripts/db.py`: 4 prints (CLI usage/output) -- KEEP
- `scripts/sync.py`: 1 print (JSON output) -- KEEP
- `scripts/axis_sync.py`: 3 prints (CLI usage/output) -- KEEP
- `scripts/resume.py`: 1 print (resume prompt output) -- KEEP
- `scripts/export.py`: 2 prints (CLI output) -- KEEP
- `scripts/context_window.py`: 2 prints (CLI output) -- KEEP

**Result:** There are ZERO operational `print()` calls to convert. All prints are intentional CLI output in `__main__` blocks. The logging work is about adding logging to operations that currently have no visibility (retries, errors), not converting existing prints.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Return error dicts | Raise typed exceptions | This phase | Callers use try/except instead of checking dict keys |
| No logging | stdlib logging to stderr | This phase | Retry visibility, error audit trail |
| Per-function allowlists | Centralized ALLOWED_COLUMNS | This phase | Single source of truth for valid columns |
| `command.split()` | Explicit list construction | This phase | Safe handling of args with spaces |

## Open Questions

1. **Should `_nero_rpc` in sync.py be decorated or should the decorator go on the caller functions?**
   - What we know: `_nero_rpc` is the lowest-level HTTP call, used by `pull_dispatch_status` and `push_state_to_nero`. In `dispatch.py`, the HTTP call is inline (no helper function).
   - Recommendation: Decorate `_nero_rpc` in sync.py. For dispatch.py, extract the HTTP call into a similar helper and decorate that. OR decorate the higher-level functions. The cleanest approach is to decorate `_nero_rpc` and create an equivalent in dispatch.py (or have dispatch.py import and use `_nero_rpc` from sync.py).

2. **Should `safe_update()` live in `db.py` or `state.py`?**
   - What we know: `db.py` is the infrastructure layer; `state.py` has all the CRUD functions that use dynamic updates.
   - Recommendation: Put `safe_update()` and `ALLOWED_COLUMNS` in `state.py` since it's about state CRUD column validation, not database infrastructure. The column lists are tightly coupled to the CRUD functions in state.py.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (no pinned version) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ERRL-01 | MeridianError hierarchy, DatabaseBusyError re-parenting | unit | `uv run pytest tests/test_db.py::TestErrorHierarchy -x` | No -- Wave 0 |
| ERRL-02 | StateTransitionError raised on invalid transitions | unit | `uv run pytest tests/test_state.py::TestTransitions -x` | Partial -- existing tests check ValueError, need update |
| ERRL-03 | Logging to stderr, no operational print() | unit | `uv run pytest tests/test_db.py::TestLogging -x` | No -- Wave 0 |
| ERRL-04 | HTTP retry with exponential backoff | unit | `uv run pytest tests/test_db.py::TestRetryOnHttpError -x` | No -- Wave 0 |
| ERRL-05 | NeroUnreachableError after retry exhaustion | unit | `uv run pytest tests/test_db.py::TestRetryOnHttpError::test_raises_nero_unreachable -x` | No -- Wave 0 |
| SECR-01 | safe_update validates columns against allowlist | unit | `uv run pytest tests/test_state.py::TestSafeUpdate -x` | No -- Wave 0 |
| SECR-02 | add_priority uses TABLE_MAP not f-string | unit | `uv run pytest tests/test_state.py::TestAddPriority -x` | No -- Wave 0 |
| SECR-03 | _run_pm_command uses list args | unit | `uv run pytest tests/test_axis_sync.py::TestRunPmCommand -x` | No -- Wave 0 (file doesn't exist) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/ -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_db.py::TestErrorHierarchy` -- verify MeridianError base, subclass relationships
- [ ] `tests/test_db.py::TestRetryOnHttpError` -- verify retry behavior, backoff, NeroUnreachableError
- [ ] `tests/test_db.py::TestLogging` -- verify setup_logging configures stderr, respects env var
- [ ] `tests/test_state.py::TestSafeUpdate` -- verify column validation, rejection of invalid columns
- [ ] `tests/test_state.py` -- update existing transition tests to expect StateTransitionError instead of ValueError
- [ ] Existing tests must be updated: `test_state.py` tests that assert `pytest.raises(ValueError)` for transitions need to assert `StateTransitionError` instead

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of `scripts/db.py`, `scripts/state.py`, `scripts/dispatch.py`, `scripts/sync.py`, `scripts/axis_sync.py`
- Python 3.11 stdlib docs: `logging`, `urllib.error`, `functools`

### Secondary (MEDIUM confidence)
- Phase 1 implementation patterns (proven in production): `@retry_on_busy`, `DatabaseBusyError`, `open_project()`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- stdlib only, all libraries already in use
- Architecture: HIGH -- patterns directly extend existing code, minimal new concepts
- Pitfalls: HIGH -- based on actual code analysis, known Python stdlib behaviors

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- stdlib-only, no external dependency drift risk)
