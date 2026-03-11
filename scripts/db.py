#!/usr/bin/env python3
"""Meridian database schema initialization, migrations, and reliability layer."""

import contextlib
import functools
import logging
import os
import random
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_logging_configured = False

SCHEMA_VERSION = 2

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT DEFAULT (datetime('now'))
);

-- Projects
CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY DEFAULT 'default',
    name TEXT NOT NULL,
    repo_path TEXT NOT NULL,
    repo_url TEXT,
    tech_stack TEXT,
    nero_endpoint TEXT,
    axis_project_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Milestones
CREATE TABLE IF NOT EXISTS milestone (
    id TEXT PRIMARY KEY,
    project_id TEXT DEFAULT 'default' REFERENCES project(id),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'planned' CHECK (status IN ('planned','active','complete','archived')),
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Phases
CREATE TABLE IF NOT EXISTS phase (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    milestone_id TEXT NOT NULL REFERENCES milestone(id),
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'planned' CHECK (status IN (
        'planned','context_gathered','planned_out',
        'executing','verifying','reviewing','complete','blocked'
    )),
    context_doc TEXT,
    acceptance_criteria TEXT,
    axis_ticket_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(milestone_id, sequence)
);

-- Plans
CREATE TABLE IF NOT EXISTS plan (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id INTEGER NOT NULL REFERENCES phase(id),
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN (
        'pending','executing','paused','failed','complete','skipped'
    )),
    wave INTEGER DEFAULT 1,
    tdd_required INTEGER DEFAULT 1,
    files_to_create TEXT,
    files_to_modify TEXT,
    test_command TEXT,
    executor_type TEXT DEFAULT 'subagent' CHECK (executor_type IN ('subagent','nero','inline')),
    commit_sha TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(phase_id, sequence)
);

-- Checkpoints
CREATE TABLE IF NOT EXISTS checkpoint (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT DEFAULT 'default' REFERENCES project(id),
    trigger TEXT NOT NULL CHECK (trigger IN (
        'manual','auto_context_limit','plan_complete','phase_complete','error','pause'
    )),
    milestone_id TEXT,
    phase_id INTEGER,
    plan_id INTEGER,
    plan_status TEXT,
    decisions TEXT,
    blockers TEXT,
    notes TEXT,
    git_branch TEXT,
    git_sha TEXT,
    git_dirty INTEGER DEFAULT 0,
    estimated_tokens_used INTEGER,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Decisions
CREATE TABLE IF NOT EXISTS decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT DEFAULT 'default' REFERENCES project(id),
    phase_id INTEGER REFERENCES phase(id),
    category TEXT CHECK (category IN (
        'architecture','approach','trade_off','tooling','constraint','deviation'
    )),
    summary TEXT NOT NULL,
    rationale TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Nero dispatches
CREATE TABLE IF NOT EXISTS nero_dispatch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_id INTEGER REFERENCES plan(id),
    phase_id INTEGER REFERENCES phase(id),
    dispatch_type TEXT CHECK (dispatch_type IN ('plan','phase','pr_factory')),
    nero_task_id TEXT,
    status TEXT DEFAULT 'dispatched' CHECK (status IN (
        'dispatched','accepted','running','completed','failed','rejected'
    )),
    pr_url TEXT,
    dispatched_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);

-- Quick tasks
CREATE TABLE IF NOT EXISTS quick_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT DEFAULT 'default' REFERENCES project(id),
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','executing','complete','failed')),
    commit_sha TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT
);
"""


MIGRATION_V2 = """
-- Add priority column to phase and plan tables
ALTER TABLE phase ADD COLUMN priority TEXT CHECK (priority IN ('critical','high','medium','low'));
ALTER TABLE plan ADD COLUMN priority TEXT CHECK (priority IN ('critical','high','medium','low'));
"""


# -- Exceptions ----------------------------------------------------------------


class MeridianError(Exception):
    """Base class for all Meridian exceptions."""


class DatabaseBusyError(MeridianError):
    """Raised when database remains locked after all retry attempts."""

    def __init__(self, retries: int, total_wait: float) -> None:
        self.retries = retries
        self.total_wait = total_wait
        super().__init__(
            f"Database busy after {retries} retries ({total_wait:.1f}s total wait)"
        )


class StateTransitionError(MeridianError):
    """Raised when a state transition is invalid."""


class NeroUnreachableError(MeridianError):
    """Raised when Nero API is unreachable after retry exhaustion."""


# -- Logging -------------------------------------------------------------------


def setup_logging() -> None:
    """Configure root logger for Meridian with stderr output.

    Reads level from MERIDIAN_LOG_LEVEL env var (default: WARNING).
    """
    global _logging_configured
    level_name = os.environ.get("MERIDIAN_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    _logging_configured = True


# -- Retry decorator -----------------------------------------------------------


def retry_on_busy(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator that retries on 'database is locked' OperationalError.

    Uses exponential backoff with +/-25% jitter. Raises DatabaseBusyError
    after exhausting all retries. Does NOT retry other OperationalErrors.
    """

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
                    delay = base_delay * (2**attempt)
                    jitter = random.uniform(-0.25, 0.25) * delay
                    sleep_time = delay + jitter
                    time.sleep(sleep_time)
                    total_wait += sleep_time

        return wrapper

    return decorator


# -- HTTP retry decorator ------------------------------------------------------


def retry_on_http_error(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator that retries on HTTP 5xx and network errors.

    Fails immediately on 4xx errors. Raises NeroUnreachableError after
    exhausting all retries. Uses exponential backoff without jitter.
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as e:
                    if e.code < 500:
                        raise
                    last_exception = e
                    if attempt == max_retries:
                        break
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "HTTP %d on attempt %d/%d, retrying in %.1fs",
                        e.code,
                        attempt + 1,
                        max_retries,
                        delay,
                    )
                    time.sleep(delay)
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    delay = base_delay * (2**attempt)
                    logger.warning(
                        "Network error on attempt %d/%d, retrying in %.1fs: %s",
                        attempt + 1,
                        max_retries,
                        delay,
                        e,
                    )
                    time.sleep(delay)
            raise NeroUnreachableError(
                f"Nero unreachable after {max_retries} retries: {last_exception}"
            ) from last_exception

        return wrapper

    return decorator


# -- Internal connect ----------------------------------------------------------


def _connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Connect to the Meridian database with row factory and pragmas enabled.

    Prefer open_project() for new code -- it handles commit/rollback/close.
    """
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


# Backward-compatible alias -- prefer open_project() for new code
connect = _connect


# -- Context manager -----------------------------------------------------------


@contextlib.contextmanager
def open_project(path: str | Path | None = None):
    """Yield a configured sqlite3.Connection that auto-commits on clean exit.

    Rolls back on exception. Closes connection in finally block.
    For path=":memory:", creates an in-memory connection with schema initialized.
    """
    global _logging_configured
    if not _logging_configured:
        setup_logging()

    if str(path) == ":memory:":
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        init_schema(conn)
        try:
            yield conn
        finally:
            conn.close()
        return

    db_path = get_db_path(path) if path is not None else get_db_path()
    conn = _connect(db_path)
    try:
        init_schema(conn, db_path=db_path)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# -- Backup --------------------------------------------------------------------


def backup_database(
    source_path: str | Path,
    backup_dir: Path | None = None,
    max_backups: int = 100,
) -> Path:
    """Create a hot snapshot of the database using connection.backup().

    Returns the path to the backup file.
    """
    source_path = Path(source_path)
    if backup_dir is None:
        backup_dir = source_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")
    backup_path = backup_dir / f"state-{timestamp}.db"

    src_conn = sqlite3.connect(str(source_path))
    dst_conn = sqlite3.connect(str(backup_path))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    _prune_backups(backup_dir, max_backups)
    return backup_path


def _prune_backups(backup_dir: Path, max_backups: int) -> None:
    """Remove oldest backup files when count exceeds max_backups."""
    backups = sorted(backup_dir.glob("state-*.db"))
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        oldest.unlink()


# -- Schema / migrations -------------------------------------------------------


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add priority column to phase and plan tables."""
    columns = {row[1] for row in conn.execute("PRAGMA table_info(phase)").fetchall()}
    if "priority" not in columns:
        conn.execute(
            "ALTER TABLE phase ADD COLUMN priority TEXT"
            " CHECK (priority IN ('critical','high','medium','low'))"
        )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(plan)").fetchall()}
    if "priority" not in columns:
        conn.execute(
            "ALTER TABLE plan ADD COLUMN priority TEXT"
            " CHECK (priority IN ('critical','high','medium','low'))"
        )
    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (2,))
    conn.commit()


def get_db_path(project_dir: str | Path | None = None) -> Path:
    """Get the path to the Meridian database for a project directory."""
    if project_dir is None:
        project_dir = Path.cwd()
    else:
        project_dir = Path(project_dir)
    return project_dir / ".meridian" / "state.db"


def init_schema(conn: sqlite3.Connection, db_path: str | Path | None = None) -> None:
    """Initialize the database schema and run pending migrations.

    If db_path is provided and not :memory:, creates a backup before migration.
    """
    conn.executescript(SCHEMA_SQL)
    # Record initial schema version if fresh DB
    existing = conn.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    if not existing:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (1,))
        conn.commit()
    # Run migrations
    current_version = get_schema_version(conn)
    if current_version < 2:
        if db_path is not None and str(db_path) != ":memory:":
            db_path = Path(db_path)
            if db_path.exists():
                backup_database(db_path)
        _migrate_v1_to_v2(conn)


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get the current schema version."""
    try:
        row = conn.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return row["version"] if row else 0
    except sqlite3.OperationalError:
        return 0


def init(project_dir: str | Path | None = None) -> Path:
    """Initialize Meridian in a project directory. Returns the db path."""
    db_path = get_db_path(project_dir)
    with open_project(project_dir):
        pass
    return db_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python db.py init [project_dir]")
        sys.exit(1)

    cmd = sys.argv[1]
    project_dir = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "init":
        db_path = init(project_dir)
        print(f"Meridian database initialized at {db_path}")
    elif cmd == "version":
        with open_project(project_dir) as conn:
            print(f"Schema version: {get_schema_version(conn)}")
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
