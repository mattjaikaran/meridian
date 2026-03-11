# Phase 1: Database Foundation - Research

**Researched:** 2026-03-10
**Domain:** Python stdlib sqlite3 — context manager, retry, backup, pytest configuration
**Confidence:** HIGH

## Summary

This phase wraps all SQLite access behind an `open_project()` context manager, adds retry-on-busy logic for concurrent subagent writes, implements hot backup via `connection.backup()`, and configures pytest to eliminate `sys.path.insert` hacks across 4 test files. The entire phase uses Python stdlib only — no external dependencies.

The codebase already follows clean patterns: all CRUD functions take `conn` as first parameter (never closing it), `sqlite3.Row` factory is set everywhere, and WAL + foreign_keys pragmas are already applied in `connect()`. The work is primarily a refactor of connection lifecycle management and test infrastructure consolidation.

**Primary recommendation:** Build `open_project()` as a `@contextlib.contextmanager` in `scripts/db.py` that wraps `connect()` + `init_schema()` + `busy_timeout` pragma, yielding `conn` with auto-commit/rollback/close semantics. Then sweep all 6 scripts with `__main__` blocks plus `db.init()` to use it.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- `open_project(path)` context manager yields a single connection for the entire command duration
- Functions continue to receive `conn` as first parameter (existing convention preserved)
- Auto-commit on clean exit, rollback on exception, close in finally
- All pragmas (WAL, busy_timeout, foreign_keys) set inside open_project()
- All old try/finally + manual conn.close() patterns fully removed
- connect() becomes internal to open_project() only (not public API)
- `@retry_on_busy` decorator applied to write operations (not reads)
- 3 retries with exponential backoff starting at 0.5s (0.5, 1.0, 2.0)
- busy_timeout=5000ms set at connection level
- Random jitter of +/-25% on backoff delays
- On retry exhaustion, raise `DatabaseBusyError` (custom exception with retry count and total wait time)
- DatabaseBusyError is a standalone exception in Phase 1 (Phase 2 integrates into MeridianError hierarchy)
- Backups stored in `.meridian/backups/` directory
- Naming: `state-{ISO-timestamp}.db`
- Uses SQLite `connection.backup()` API
- Two triggers: manual via backup function + automatic before schema migrations
- Retention: keep last 100 backups, auto-prune oldest beyond limit
- `pyproject.toml` gets `[tool.pytest.ini_options]` with `pythonpath = ["."]`
- All `sys.path.insert` hacks removed from test files
- Shared `conftest.py` in `tests/` with `db`, `seeded_db`, `file_db` fixtures
- All fixtures use `open_project()` — tests validate the same path as production
- Existing per-file fixture definitions removed after conftest consolidation

### Claude's Discretion
- Whether connect() stays as a separate internal function or gets inlined into open_project()
- Exact pragma setup location (open_project vs thin wrapper around connect)
- How to handle the in-memory DB case in open_project() for tests (may need a variant or param)
- Exact jitter implementation (random module vs simpler approach)

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DBRL-01 | `open_project()` context manager replaces all manual connect/try/finally/close patterns | Context manager pattern verified with Python 3.14 stdlib contextlib; 7 call sites identified across scripts |
| DBRL-02 | `PRAGMA busy_timeout=5000` is set on every connection for concurrent write tolerance | Verified: PRAGMA busy_timeout=5000 works on SQLite 3.51.2; returns correct value |
| DBRL-03 | Retry decorator with exponential backoff handles `sqlite3.OperationalError` ("database is locked") | stdlib `time.sleep` + `random.uniform` sufficient; catch `sqlite3.OperationalError` with string match on "database is locked" |
| DBRL-04 | `connection.backup()` creates hot snapshot of state.db before schema migrations | Verified: `sqlite3.Connection.backup()` available in Python 3.14, tested and works |
| DBRL-05 | All existing scripts updated to use `open_project()` instead of manual connection management | 6 scripts with `__main__` blocks + `db.init()` need updating; `state.py` functions already take conn (no change needed) |
| TEST-01 | `pyproject.toml` has `[tool.pytest.ini_options]` with `pythonpath = ["."]` | pyproject.toml currently has no pytest config; section needs adding |
| TEST-02 | All `sys.path.insert` hacks removed from test files | Found in 4 files: test_state.py, test_metrics.py, test_resume.py, test_sync.py |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | 3.51.2 (bundled) | Database engine | Already in use, stdlib, no deps |
| contextlib | stdlib | `@contextmanager` decorator | Standard Python context manager pattern |
| time | stdlib | `sleep()` for retry backoff | No external deps needed for simple delays |
| random | stdlib | Jitter on backoff delays | `random.uniform()` for +/-25% jitter |
| shutil/pathlib | stdlib | Backup file management | Directory creation, file listing, deletion |
| pytest | latest | Test framework | Already in use across 4 test files |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| functools | stdlib | `@wraps` for retry decorator | Preserve function metadata in decorator |
| datetime | stdlib | ISO timestamp for backup filenames | Already imported in state.py |
| logging | stdlib | Future-proof log points in retry | Optional — print() is fine for Phase 1 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Custom retry | tenacity | External dep for a 20-line function — not worth it for this project (stdlib only) |
| Manual backup | sqlite3 .backup() | .backup() is the correct choice — atomic, hot, handles WAL correctly |
| tmp_path fixture | tempfile.mkdtemp | pytest tmp_path is cleaner, auto-cleaned |

**Installation:**
```bash
# No new dependencies — stdlib only project
# pytest already available (dev dependency)
uv add --dev pytest  # if not already in dev deps
```

## Architecture Patterns

### Recommended Project Structure
```
scripts/
├── db.py              # open_project(), backup(), retry_on_busy, DatabaseBusyError
├── state.py           # CRUD functions (unchanged — already take conn)
├── resume.py          # Updated __main__ to use open_project()
├── export.py          # Updated __main__ to use open_project()
├── dispatch.py        # Updated __main__ to use open_project()
├── sync.py            # Updated __main__ to use open_project()
├── axis_sync.py       # Updated __main__ to use open_project()
└── context_window.py  # Updated __main__ to use open_project()
tests/
├── conftest.py        # NEW: shared db, seeded_db, file_db fixtures
├── test_state.py      # Remove sys.path hack + local fixture
├── test_metrics.py    # Remove sys.path hack + local fixture
├── test_resume.py     # Remove sys.path hack + local fixture
└── test_sync.py       # Remove sys.path hack + local fixture
pyproject.toml         # Add [tool.pytest.ini_options] pythonpath
```

### Pattern 1: Context Manager (open_project)
**What:** Single entry point for all database access
**When to use:** Every script that needs a database connection
**Example:**
```python
# Source: Python stdlib contextlib docs
import contextlib
import sqlite3
from pathlib import Path

@contextlib.contextmanager
def open_project(path: str | Path | None = None):
    """Open a Meridian project database with full configuration.

    Yields a configured connection. Auto-commits on clean exit,
    rolls back on exception, closes in finally.
    """
    conn = _connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Internal: create and configure a connection."""
    if db_path is None:
        db_path = get_db_path()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn
```

### Pattern 2: Retry Decorator
**What:** Catches `sqlite3.OperationalError` with "database is locked" and retries with jittered backoff
**When to use:** Applied to write operations that may conflict with concurrent subagent access
**Example:**
```python
import functools
import random
import time
import sqlite3

class DatabaseBusyError(Exception):
    """Raised when database remains locked after retry exhaustion."""
    def __init__(self, retries: int, total_wait: float):
        self.retries = retries
        self.total_wait = total_wait
        super().__init__(
            f"Database busy after {retries} retries ({total_wait:.1f}s total wait)"
        )

def retry_on_busy(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator: retry on sqlite3.OperationalError 'database is locked'."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            total_wait = 0.0
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" not in str(e):
                        raise
                    if attempt == max_retries:
                        raise DatabaseBusyError(max_retries, total_wait) from e
                    delay = base_delay * (2 ** attempt)
                    jitter = delay * random.uniform(-0.25, 0.25)
                    actual_delay = delay + jitter
                    time.sleep(actual_delay)
                    total_wait += actual_delay
        return wrapper
    return decorator
```

### Pattern 3: Hot Backup
**What:** Uses `connection.backup()` for atomic, WAL-safe snapshots
**When to use:** Before schema migrations (automatic) and on manual invocation
**Example:**
```python
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

def backup_database(source_path: Path, backup_dir: Path | None = None, max_backups: int = 100) -> Path:
    """Create a hot backup of the database. Returns the backup path."""
    if backup_dir is None:
        backup_dir = source_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"state-{timestamp}.db"

    source = sqlite3.connect(str(source_path))
    try:
        dest = sqlite3.connect(str(backup_path))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    # Prune old backups
    _prune_backups(backup_dir, max_backups)
    return backup_path

def _prune_backups(backup_dir: Path, max_backups: int) -> None:
    """Remove oldest backups beyond the retention limit."""
    backups = sorted(backup_dir.glob("state-*.db"))
    while len(backups) > max_backups:
        backups.pop(0).unlink()
```

### Pattern 4: Test Fixtures with open_project
**What:** Shared conftest.py using open_project for in-memory and file-backed DBs
**When to use:** All test files
**Example:**
```python
# tests/conftest.py
import pytest
import sqlite3
from scripts.db import init_schema

@pytest.fixture
def db():
    """In-memory database with schema initialized."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()

@pytest.fixture
def seeded_db(db):
    """Database with project, milestone, and phases pre-created."""
    from scripts.state import create_project, create_milestone, transition_milestone, create_phase
    create_project(db, name="Test Project", repo_path="/tmp/test", project_id="default")
    create_milestone(db, milestone_id="v1.0", name="Version 1.0", project_id="default")
    transition_milestone(db, "v1.0", "active")
    create_phase(db, milestone_id="v1.0", name="Foundation", description="Build the base")
    create_phase(db, milestone_id="v1.0", name="Features", description="Add features")
    return db

@pytest.fixture
def file_db(tmp_path):
    """File-backed database for path-dependent tests (resume, export)."""
    db_path = tmp_path / ".meridian" / "state.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn, tmp_path
    conn.close()
```

**Design note on in-memory DBs and open_project():** The `db` fixture cannot use `open_project()` directly because `:memory:` databases are per-connection — you cannot close and reopen them. The recommended approach: `open_project()` accepts an optional pre-created connection or a special `:memory:` mode parameter. Alternatively, the `db` fixture manually creates the connection mimicking what `open_project()` does internally (set same pragmas). The key is that `file_db` CAN use `open_project()` since it has a real path. This is Claude's discretion per CONTEXT.md.

### Anti-Patterns to Avoid
- **Double-commit:** `open_project()` auto-commits on clean exit. Functions like `create_project()` already call `conn.commit()` — this is fine (committing an already-committed transaction is a no-op in SQLite), but do NOT remove the per-function commits yet since they serve as savepoints for multi-step operations within a single `open_project()` session.
- **Catching all OperationalError:** The retry decorator MUST check the error message contains "database is locked" — other OperationalErrors (bad SQL, schema errors) should propagate immediately.
- **Retrying reads:** The `@retry_on_busy` decorator is for write operations only. Reads under WAL mode do not block.
- **Opening backup connection inside open_project():** Backup should use its own separate connections (source + dest), not the yielded connection.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Database backup | File copy of .db + .wal + .shm | `connection.backup()` | Atomic, handles WAL checkpointing, no partial copies |
| Busy timeout | Python-side polling loop | `PRAGMA busy_timeout=5000` | SQLite-native, more efficient, handles internal locking |
| Path resolution for tests | `sys.path.insert` hacks | `pyproject.toml` `pythonpath = ["."]` | Standard pytest config, no runtime path manipulation |
| Context manager protocol | Manual `__enter__`/`__exit__` | `@contextlib.contextmanager` | Simpler, less boilerplate, standard pattern |

**Key insight:** SQLite has built-in busy handling (PRAGMA busy_timeout) that should be the first line of defense. Python-side retry is the second layer for cases where 5 seconds of SQLite-internal waiting is not enough.

## Common Pitfalls

### Pitfall 1: WAL + backup interaction
**What goes wrong:** Copying .db file manually while WAL has uncommitted pages produces a corrupt backup
**Why it happens:** WAL journal is separate from the main DB file
**How to avoid:** Always use `connection.backup()` which handles WAL checkpointing atomically
**Warning signs:** Backup file is smaller than expected, or opens with "database disk image is malformed"

### Pitfall 2: In-memory DB cannot be shared across connections
**What goes wrong:** Opening `:memory:` in open_project(), then closing connection — data is gone
**Why it happens:** Each `:memory:` connection is a separate database
**How to avoid:** For test fixtures, either (a) pass a pre-opened connection, (b) accept `:memory:` as a special path that skips close-on-exit, or (c) use `file::memory:?cache=shared` URI (complex, not recommended)
**Warning signs:** Tests pass individually but fixtures yield empty databases

### Pitfall 3: commit() inside functions + auto-commit on exit
**What goes wrong:** Concern that double-commit causes issues
**Why it happens:** Functions like `create_project()` call `conn.commit()` and `open_project()` also commits on exit
**How to avoid:** This is actually fine in SQLite — committing when no transaction is active is a no-op. Leave function-level commits in place.
**Warning signs:** None — this is a non-issue, but it may cause confusion during review

### Pitfall 4: Retry decorator on functions that take conn
**What goes wrong:** Retrying a function after OperationalError, but the connection state may be corrupted
**Why it happens:** After "database is locked", the connection is still valid but any in-progress transaction was rolled back
**How to avoid:** The retry should be at the outermost call level (around the whole open_project block) or the decorator should be on functions that manage their own transactions. Since functions call `conn.commit()` individually, retrying individual write functions is safe.
**Warning signs:** IntegrityError on retry due to partial state from first attempt

### Pitfall 5: Timestamp collision in backup filenames
**What goes wrong:** Two backups in the same second overwrite each other
**Why it happens:** ISO timestamps have 1-second resolution
**How to avoid:** Include microseconds or use `%Y%m%dT%H%M%S_%f` format. Alternatively, check existence and append suffix.
**Warning signs:** Backup count is less than expected after multiple rapid migrations

### Pitfall 6: Removing sys.path.insert before adding pythonpath config
**What goes wrong:** Tests break during development because imports fail
**Why it happens:** Pytest config and path hack removal must happen atomically
**How to avoid:** Add `[tool.pytest.ini_options]` to pyproject.toml FIRST, verify `pytest --co` works, THEN remove sys.path hacks
**Warning signs:** `ModuleNotFoundError: No module named 'scripts'`

## Code Examples

### Updating a script's __main__ block
```python
# BEFORE (scripts/export.py pattern):
if __name__ == "__main__":
    db_path = get_db_path(project_dir)
    conn = connect(db_path)
    try:
        # ... do work with conn ...
        pass
    finally:
        conn.close()

# AFTER:
if __name__ == "__main__":
    with open_project(project_dir) as conn:
        # ... do work with conn ...
        pass
```

### Updating db.init()
```python
# BEFORE:
def init(project_dir=None):
    db_path = get_db_path(project_dir)
    conn = connect(db_path)
    try:
        init_schema(conn)
    finally:
        conn.close()
    return db_path

# AFTER:
def init(project_dir=None):
    db_path = get_db_path(project_dir)
    with open_project(db_path) as conn:
        init_schema(conn)
    return db_path
```

### Adding backup before migration
```python
# In init_schema(), before running migrations:
def init_schema(conn: sqlite3.Connection, db_path: Path | None = None) -> None:
    conn.executescript(SCHEMA_SQL)
    existing = conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if not existing:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        conn.commit()
    current_version = get_schema_version(conn)
    if current_version < SCHEMA_VERSION:
        # Auto-backup before migration
        if db_path and str(db_path) != ":memory:":
            backup_database(Path(db_path))
        if current_version < 2:
            _migrate_v1_to_v2(conn)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `conn.backup(target)` added | Always available | Python 3.7+ | Use directly, no version guard needed |
| `PRAGMA journal_mode=WAL` | Already set in connect() | Existing code | No change needed |
| pytest pythonpath config | Available since pytest 7.0 | 2022 | Standard approach, replaces rootdir hacks |

**Deprecated/outdated:**
- `sys.path.insert` for test imports: Replaced by pyproject.toml `pythonpath` config
- Manual file-copy backups: Replaced by `connection.backup()` API

## Open Questions

1. **init_schema needs db_path for auto-backup**
   - What we know: `init_schema()` currently only takes `conn`, but backup needs the file path
   - What's unclear: Whether to pass `db_path` as parameter or derive it from connection
   - Recommendation: Add optional `db_path` parameter to `init_schema()`. Inside `open_project()`, the path is known and can be passed through. For `:memory:` connections, skip backup.

2. **Exact scope of retry_on_busy application**
   - What we know: Decorator goes on write operations, not reads
   - What's unclear: Whether to decorate individual CRUD functions in state.py or the higher-level script functions
   - Recommendation: Decorate the higher-level functions in scripts (dispatch, sync, export) that orchestrate multiple writes. Individual CRUD functions in state.py are called within an open_project session and benefit from the connection-level busy_timeout. The decorator is for script-level operations where the 5-second busy_timeout was insufficient.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (latest, already in use) |
| Config file | `pyproject.toml` [tool.pytest.ini_options] — needs creating |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DBRL-01 | open_project yields conn, auto-commits, rollbacks on error, closes | unit | `pytest tests/test_db.py::test_open_project -x` | No — Wave 0 |
| DBRL-02 | busy_timeout=5000 set on every connection | unit | `pytest tests/test_db.py::test_busy_timeout_pragma -x` | No — Wave 0 |
| DBRL-03 | retry_on_busy decorator retries on locked, raises DatabaseBusyError | unit | `pytest tests/test_db.py::test_retry_on_busy -x` | No — Wave 0 |
| DBRL-04 | backup creates hot snapshot, prunes old backups | unit | `pytest tests/test_db.py::test_backup -x` | No — Wave 0 |
| DBRL-05 | All scripts use open_project (no manual connect/close) | smoke | `grep -r "conn.close()" scripts/ \| grep -v __pycache__` returns empty | No — manual verification |
| TEST-01 | pyproject.toml has pythonpath config | smoke | `python -c "import tomllib; c=tomllib.load(open('pyproject.toml','rb')); assert c['tool']['pytest']['ini_options']['pythonpath']"` | No — Wave 0 |
| TEST-02 | No sys.path.insert in test files | smoke | `grep -r "sys.path.insert" tests/ \| grep -v __pycache__` returns empty | No — manual verification |

### Sampling Rate
- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_db.py` — covers DBRL-01, DBRL-02, DBRL-03, DBRL-04 (open_project, busy_timeout, retry, backup)
- [ ] `tests/conftest.py` — shared fixtures (db, seeded_db, file_db) replacing per-file duplicates
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` section — TEST-01
- [ ] pytest dev dependency: `uv add --dev pytest` (verify it is already installed)

## Sources

### Primary (HIGH confidence)
- Python 3.14.3 runtime verification — `sqlite3.Connection.backup()` confirmed available
- SQLite 3.51.2 bundled — `PRAGMA busy_timeout` verified returns correct value
- Direct codebase analysis — all 7 scripts examined, 4 test files analyzed, all connection patterns catalogued

### Secondary (MEDIUM confidence)
- Python stdlib docs for contextlib.contextmanager — standard pattern, stable API
- pytest pythonpath config — available since pytest 7.0 (2022), well-established

### Tertiary (LOW confidence)
- None — all findings verified against running Python runtime and codebase

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, all APIs verified against running Python 3.14
- Architecture: HIGH — patterns derived directly from existing codebase analysis
- Pitfalls: HIGH — verified through API testing and codebase pattern analysis

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable stdlib domain, no moving parts)
