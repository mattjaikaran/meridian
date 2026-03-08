#!/usr/bin/env python3
"""Meridian database schema initialization and migrations."""

import sqlite3
import sys
from pathlib import Path

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


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Add priority column to phase and plan tables."""
    # Check if column already exists (idempotent)
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


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Connect to the Meridian database with row factory enabled."""
    if db_path is None:
        db_path = get_db_path()
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Initialize the database schema and run pending migrations."""
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
    conn = connect(db_path)
    try:
        init_schema(conn)
    finally:
        conn.close()
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
        db_path = get_db_path(project_dir)
        conn = connect(db_path)
        print(f"Schema version: {get_schema_version(conn)}")
        conn.close()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
