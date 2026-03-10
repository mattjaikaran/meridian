# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `state.py`, `axis_sync.py`, `context_window.py`
- Test files mirror source files with `test_` prefix: `test_state.py`, `test_resume.py`, `test_metrics.py`, `test_sync.py`
- Package markers are empty `__init__.py` files in `scripts/` and `tests/`

**Functions:**
- Use `snake_case` for all functions: `create_project()`, `transition_phase()`, `compute_next_action()`
- CRUD functions follow `{verb}_{entity}` pattern: `create_milestone()`, `get_plan()`, `list_phases()`, `update_project()`
- Transition functions use `transition_{entity}()` pattern: `transition_milestone()`, `transition_phase()`, `transition_plan()`
- Private/internal functions use leading underscore: `_now()`, `_row_to_dict()`, `_get_git_state()`, `_nero_rpc()`, `_parse_ts()`

**Variables:**
- Use `snake_case` for all variables
- SQLite connections are always named `conn`
- Database row results use `row` (single) or `rows` (multiple)
- Constants use `UPPER_SNAKE_CASE`: `SCHEMA_VERSION`, `PHASE_TRANSITIONS`, `AUTO_CHECKPOINT_TOKENS`, `VALID_PRIORITIES`

**Types:**
- Use Python 3.11+ union syntax: `str | None`, `int | None`, `str | Path | None`
- Return types are `dict`, `dict | None`, `list[dict]`, or `str`
- Database entities are represented as plain `dict` (converted from `sqlite3.Row`)

## Code Style

**Formatting:**
- Tool: ruff (configured in `pyproject.toml`)
- Line length: 100 characters
- Target: Python 3.11

**Linting:**
- Tool: ruff
- Rule sets: `["E", "F", "I", "N", "W", "UP"]` (pycodestyle, pyflakes, isort, pep8-naming, warnings, pyupgrade)
- Inline suppressions used sparingly: `# noqa: S608` for intentional dynamic SQL in `scripts/state.py`

**General:**
- Shebang line on every executable module: `#!/usr/bin/env python3`
- Module-level docstring on every file describing purpose
- No external dependencies — stdlib only (`sqlite3`, `json`, `pathlib`, `datetime`, `textwrap`, `subprocess`, `urllib`)

## Import Organization

**Order:**
1. Standard library imports (`import json`, `import sqlite3`, `import subprocess`)
2. Local imports (`from scripts.db import connect, get_db_path`)
3. No third-party imports exist (stdlib-only project)

**Style:**
- Use `from X import Y` for specific names from local modules
- Use `import X` for stdlib modules
- Group by stdlib then local, separated by blank line

**Example from `scripts/dispatch.py`:**
```python
import json
import urllib.error
import urllib.request
from pathlib import Path

from scripts.db import connect, get_db_path
from scripts.state import (
    create_nero_dispatch,
    get_phase,
    get_plan,
    get_project,
    list_plans,
    update_nero_dispatch,
)
```

**Path Aliases:**
- None used. All imports are relative to project root.
- Tests use `sys.path.insert(0, str(Path(__file__).parent.parent))` to make `scripts` importable

## Error Handling

**Patterns:**
- Raise `ValueError` for invalid state transitions, missing entities, and invalid arguments
- Use descriptive error messages with context: `f"Invalid transition: {current['status']} -> {new_status}. Valid: {TRANSITIONS[current['status']]}"`
- `try/finally` pattern for database connection cleanup (not context managers)
- Bare `except Exception` only for non-critical operations (git commands, file reads)
- `urllib.error.URLError` caught specifically for HTTP failures in `scripts/dispatch.py` and `scripts/sync.py`
- Return error dicts instead of raising for user-facing operations: `{"status": "error", "message": "..."}`

**Two error strategies used:**
1. **Raise exceptions** for programming errors and invalid state (transitions, missing data): `scripts/state.py`
2. **Return error dicts** for runtime/external failures (network, missing config): `scripts/dispatch.py`, `scripts/sync.py`

**Example raise pattern from `scripts/state.py`:**
```python
def transition_phase(conn, phase_id, new_status):
    current = get_phase(conn, phase_id)
    if not current:
        raise ValueError(f"Phase {phase_id} not found")
    if new_status not in PHASE_TRANSITIONS.get(current["status"], []):
        raise ValueError(
            f"Invalid phase transition: {current['status']} -> {new_status}. "
            f"Valid: {PHASE_TRANSITIONS[current['status']]}"
        )
```

**Example return-error pattern from `scripts/dispatch.py`:**
```python
except urllib.error.URLError as e:
    return {
        "status": "error",
        "message": f"Failed to connect to Nero at {url}: {e}",
    }
```

## Logging

**Framework:** None. No logging framework is used.

**Patterns:**
- `print()` used only in `__main__` blocks for CLI output
- Functions return structured dicts with status/message fields instead of logging
- No debug/info/warning logging anywhere in the codebase

## Comments

**When to Comment:**
- Section dividers using box-drawing characters to separate CRUD groups within a module: `# -- Project CRUD ──────────`
- Inline comments for non-obvious logic: explaining idempotent migration checks, SQL quirks
- No redundant comments on straightforward code

**Docstrings:**
- Module-level docstrings on every file (one-line summary)
- Function docstrings on public functions that have non-obvious behavior
- Use triple-quoted strings with imperative mood: `"""Get the path to the Meridian database."""`
- Multi-line docstrings include `Args:` and `Returns:` sections (see `scripts/state.py` `add_priority()`, `scripts/metrics.py`)
- No docstrings on private helper functions or simple getters

**Section Dividers:**
- Used consistently in `scripts/state.py` to group CRUD by entity type:
```python
# -- Project CRUD ──────────────────────────────────────────────────────────────
# -- Milestone CRUD ────────────────────────────────────────────────────────────
# -- Phase CRUD ────────────────────────────────────────────────────────────────
```

## Function Design

**Size:** Functions are kept short (typically 10-40 lines). The largest function is `compute_next_action()` at ~80 lines due to its decision tree nature.

**Parameters:**
- First parameter is always `conn: sqlite3.Connection` for database functions
- Use `project_id: str = "default"` as a default parameter throughout
- Optional parameters use `X | None = None` pattern
- `**kwargs` used for flexible update functions with an `allowed` set whitelist

**Update pattern from `scripts/state.py`:**
```python
def update_project(conn, project_id, **kwargs):
    allowed = {"name", "repo_path", "repo_url", "tech_stack", "nero_endpoint", "axis_project_id"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return get_project(conn, project_id)
    # ... build dynamic SQL
```

**Return Values:**
- CRUD functions return `dict` (entity) or `dict | None`
- List functions return `list[dict]`
- Status/action functions return structured `dict` with `action`, `status`, and `message` keys
- Create functions always return the created entity by re-fetching it

## Module Design

**Exports:**
- No `__all__` declarations
- All public functions are importable directly
- Private functions prefixed with underscore

**Barrel Files:**
- `scripts/__init__.py` and `tests/__init__.py` are empty (package markers only)
- No barrel/re-export pattern used

**Module Responsibilities:**
- Each module has a single responsibility (db, state, dispatch, resume, sync, metrics, etc.)
- `scripts/state.py` is the core module; other modules import from it
- `scripts/db.py` handles schema only; `scripts/state.py` handles all CRUD

## Database Patterns

**Connection Management:**
- Use `try/finally` with explicit `conn.close()` (not context managers)
- Functions that open their own connections always close them in `finally`
- Functions that receive `conn` as a parameter do NOT close it

**Row Conversion:**
- `sqlite3.Row` factory set on all connections
- Helper functions convert rows to dicts: `_row_to_dict()`, `_rows_to_list()`
- JSON fields stored as strings, parsed with `json.loads()` / `json.dumps()` at boundaries

**Dynamic SQL:**
- Update functions build SET clauses dynamically from allowed field dicts
- Pattern: `set_clause = ", ".join(f"{k} = ?" for k in updates)`
- Always parameterized (no string interpolation of values)

**State Machine:**
- Valid transitions defined as dict constants at module level: `PHASE_TRANSITIONS`, `PLAN_TRANSITIONS`, `MILESTONE_TRANSITIONS`
- Every state change validated against transition map before execution
- Timestamps (`started_at`, `completed_at`) set automatically on relevant transitions

---

*Convention analysis: 2026-03-10*
