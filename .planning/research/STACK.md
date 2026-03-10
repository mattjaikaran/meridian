# Technology Stack — Claude Code Skill Hardening

**Project:** Meridian Workflow Engine (hardening milestone)
**Researched:** 2026-03-10
**Overall confidence:** HIGH (based on direct inspection of installed Claude Code infrastructure)

## Key Finding: Two Distinct Routing Mechanisms

Claude Code has **two separate command systems** that Meridian conflates:

| System | Location | Trigger | Discovery | Use Case |
|--------|----------|---------|-----------|----------|
| **Skills** | `~/.claude/skills/<name>/SKILL.md` | Automatic (description-matched) | Claude reads description, loads SKILL.md when relevant | Background knowledge, behavioral rules, domain expertise |
| **Commands** | `~/.claude/commands/<namespace>/<cmd>.md` | Explicit (`/namespace:cmd`) | User types `/` and sees list | Procedural workflows with arguments |

**This is the root cause of Meridian's routing problem.** Meridian uses the skills system (folder with SKILL.md) for what should be commands (explicit slash-command invocations). Skills are description-matched and passively loaded; commands are user-invoked with arguments.

### Evidence

- **GSD** (Get Shit Done) uses `~/.claude/commands/gsd/*.md` for all 30+ subcommands. Each `.md` file in the namespace folder becomes `/gsd:<filename>`. This works reliably with full subcommand routing, argument passing, and tool restrictions.
- **Meridian** uses `~/.claude/skills/meridian/skills/*/SKILL.md` via symlink. Claude Code discovers the top-level `SKILL.md` but does not auto-discover nested `skills/init/SKILL.md` etc. as separate slash commands.

**Confidence: HIGH** -- directly verified from installed GSD commands and Meridian skills on this machine.

## Recommended Stack (No Changes to Core)

Meridian's stdlib-only Python constraint is correct. The hardening milestone does not require new dependencies.

### Core (Keep As-Is)

| Technology | Version | Purpose | Rationale |
|------------|---------|---------|-----------|
| Python | 3.11+ (running 3.14.3) | All application logic | Stdlib-only constraint, works everywhere |
| SQLite3 | stdlib | State persistence | Single-user, per-project, no server needed |
| uv | 0.7.17 | Package management | Developer standard per CLAUDE.md |
| ruff | latest | Lint + format | Already configured in pyproject.toml |
| pytest | latest | Test runner | Only dev dependency, add to pyproject.toml properly |

### Infrastructure Changes Required

| Change | Technology | Purpose | Rationale |
|--------|-----------|---------|-----------|
| Command registration | `~/.claude/commands/meridian/*.md` | Slash command routing | The correct mechanism for explicit invocations |
| Structured logging | `logging` (stdlib) | Audit trail | Zero dependencies, replaces silent error swallowing |
| DB context manager | `contextlib.contextmanager` (stdlib) | Connection lifecycle | Eliminates duplicated boilerplate in 10+ locations |
| Retry decorator | Custom (stdlib `time.sleep`) | SQLite BUSY + Nero HTTP | No external deps needed for exponential backoff |

## Claude Code Command Registration (Critical Path)

### How Commands Work

Each `.md` file in `~/.claude/commands/<namespace>/` becomes a slash command:

```
~/.claude/commands/meridian/
  init.md          -> /meridian:init
  status.md        -> /meridian:status
  plan.md          -> /meridian:plan
  execute.md       -> /meridian:execute
  resume.md        -> /meridian:resume
  dispatch.md      -> /meridian:dispatch
  review.md        -> /meridian:review
  ship.md          -> /meridian:ship
  debug.md         -> /meridian:debug
  quick.md         -> /meridian:quick
  checkpoint.md    -> /meridian:checkpoint
  dashboard.md     -> /meridian:dashboard
  roadmap.md       -> /meridian:roadmap
```

### Command `.md` File Structure (Verified from GSD)

```markdown
---
name: meridian:init
description: Initialize Meridian in current project
argument-hint: "[project-name]"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<objective>
[What this command does, 2-3 sentences]
</objective>

<execution_context>
@/path/to/meridian/skills/init/SKILL.md
</execution_context>

<context>
Arguments: $ARGUMENTS
[Any additional context]
</context>

<process>
Execute the init workflow from @/path/to/meridian/skills/init/SKILL.md end-to-end.
</process>
```

### Key Properties

| Property | Purpose | Required |
|----------|---------|----------|
| `name` | Command identifier (appears in `/` menu) | Yes |
| `description` | Short description (shown in command list) | Yes |
| `argument-hint` | Placeholder shown after command name | No |
| `allowed-tools` | Restrict which tools the command can use | No |

### Relationship Between Skills and Commands

The **existing SKILL.md files stay as-is** -- they contain the procedural knowledge. The new command `.md` files are thin wrappers that:
1. Define the slash command interface (name, args, tool restrictions)
2. Use `@` references to load the existing SKILL.md content
3. Pass `$ARGUMENTS` into the execution context

This means:
- **Skills** = knowledge and procedure (existing `skills/*/SKILL.md`)
- **Commands** = routing and invocation (new `commands/meridian/*.md`)
- Keep the top-level `SKILL.md` as passive context (Claude loads it when working in Meridian projects)

**Confidence: HIGH** -- this is exactly how GSD does it with 30+ commands.

## SQLite Hardening Patterns

### Pattern 1: Retry with Exponential Backoff for SQLITE_BUSY

When multiple subagents write concurrently, SQLite serializes writes and raises `sqlite3.OperationalError` ("database is locked"). WAL mode helps but does not eliminate this.

```python
import sqlite3
import time
from functools import wraps

def retry_on_busy(max_retries=5, base_delay=0.1, max_delay=2.0):
    """Retry decorator for sqlite3.OperationalError (database locked)."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" not in str(e) or attempt == max_retries - 1:
                        raise
                    time.sleep(delay + (delay * 0.1 * (hash(time.time()) % 10)))  # jitter
                    delay = min(delay * 2, max_delay)
        return wrapper
    return decorator
```

**Confidence: HIGH** -- standard SQLite concurrency pattern, documented in SQLite official docs.

### Pattern 2: Connection Context Manager

Eliminates the duplicated try/finally pattern across 10+ locations:

```python
from contextlib import contextmanager

@contextmanager
def open_project(project_dir=None, read_only=False):
    """Yield (conn, project) with automatic cleanup."""
    project_dir = project_dir or Path.cwd()
    db_path = get_db_path(project_dir)
    conn = connect(db_path)
    try:
        if read_only:
            conn.execute("PRAGMA query_only = ON")
        project = get_project(conn)
        yield conn, project
    finally:
        conn.close()
```

**Confidence: HIGH** -- this is already identified as the fix in CONCERNS.md.

### Pattern 3: Database Backup via SQLite Online Backup API

```python
import sqlite3

def backup_database(src_path, dst_path):
    """Hot backup using SQLite's online backup API."""
    src = sqlite3.connect(src_path)
    dst = sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
```

The `connection.backup()` method (available since Python 3.7) performs a consistent snapshot even while the source database is being written to. This is the correct approach for `.meridian/state.db` backup.

**Confidence: HIGH** -- stdlib method, documented in Python docs.

### Pattern 4: Safe Dynamic SQL

Replace f-string interpolation with mapping-based dispatch:

```python
# Table name safety
VALID_TABLES = {"phase": "phase", "plan": "plan"}

def safe_table(entity_type: str) -> str:
    if entity_type not in VALID_TABLES:
        raise ValueError(f"Invalid table: {entity_type}")
    return VALID_TABLES[entity_type]

# Column name safety via schema introspection
def get_table_columns(conn, table: str) -> set[str]:
    cursor = conn.execute(f"PRAGMA table_info({safe_table(table)})")
    return {row[1] for row in cursor.fetchall()}

def safe_update(conn, table: str, row_id, **kwargs):
    valid_cols = get_table_columns(conn, table)
    filtered = {k: v for k, v in kwargs.items() if k in valid_cols}
    if not filtered:
        return
    set_clause = ", ".join(f"{col} = ?" for col in filtered)
    values = list(filtered.values()) + [row_id]
    conn.execute(f"UPDATE {safe_table(table)} SET {set_clause} WHERE id = ?", values)
    conn.commit()
```

**Confidence: HIGH** -- uses PRAGMA table_info for schema-driven validation.

## Testing Patterns for Claude Code Skills

### Pattern 1: pytest Configuration (Fix sys.path Hacking)

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

Then remove `sys.path.insert(0, ...)` from all test files.

**Confidence: HIGH** -- standard pytest configuration.

### Pattern 2: In-Memory SQLite for Test Isolation

```python
import pytest
from scripts.db import init_schema

@pytest.fixture
def db():
    """Fresh in-memory database for each test."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    yield conn
    conn.close()
```

Meridian already uses this pattern in `test_state.py`. Extend to all test files.

**Confidence: HIGH** -- already proven in the codebase.

### Pattern 3: Mock HTTP for Dispatch/Sync Tests

Use `unittest.mock.patch` on `urllib.request.urlopen` (stdlib, no httpx needed):

```python
from unittest.mock import patch, MagicMock
import json

@pytest.fixture
def mock_nero():
    """Mock Nero HTTP endpoint."""
    with patch("scripts.dispatch.urllib.request.urlopen") as mock:
        response = MagicMock()
        response.read.return_value = json.dumps({"status": "ok"}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock.return_value = response
        yield mock
```

**Confidence: HIGH** -- standard unittest.mock pattern for stdlib HTTP.

### Pattern 4: Subprocess Mock for Axis Sync Tests

```python
from unittest.mock import patch
import subprocess

@pytest.fixture
def mock_pm_command():
    """Mock the pm.sh subprocess calls."""
    with patch("scripts.axis_sync.subprocess.run") as mock:
        mock.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="TICKET-123\n", stderr=""
        )
        yield mock
```

**Confidence: HIGH** -- standard subprocess mocking.

### Pattern 5: Testing State Transitions Exhaustively

Meridian's state machine is the critical path. Generate transition test cases programmatically:

```python
from scripts.state import PHASE_TRANSITIONS, PLAN_TRANSITIONS

@pytest.mark.parametrize("from_status,to_status", [
    (f, t) for f, targets in PHASE_TRANSITIONS.items() for t in targets
])
def test_valid_phase_transitions(db, from_status, to_status):
    """Every valid transition in the map should succeed."""
    # Setup phase in from_status, attempt transition to to_status
    ...
```

**Confidence: HIGH** -- parametrize is the standard pytest pattern for combinatorial testing.

## Structured Logging Pattern

Replace silent error swallowing with stdlib logging:

```python
import logging

logger = logging.getLogger("meridian")

def setup_logging(level=logging.INFO):
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(handler)
    logger.setLevel(level)
```

Key places to add logging:
- Nero dispatch send/receive (currently silent on failure)
- State transitions (audit trail)
- SQLite retry attempts (visibility into contention)
- Axis sync command execution (currently uses bare except)

**Confidence: HIGH** -- stdlib logging, zero dependencies.

## HTTP Retry Pattern (Nero Communication)

```python
import time
import urllib.request
import urllib.error

def http_post_with_retry(url, data, max_retries=3, base_delay=1.0, timeout=10):
    """POST with exponential backoff retry."""
    delay = base_delay
    last_error = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last_error = e
            logger.warning(f"HTTP attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay *= 2
    raise last_error
```

**Confidence: HIGH** -- standard retry pattern, no external dependencies needed.

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Command routing | `~/.claude/commands/` | `~/.claude/skills/` subfolders | Skills are passive/description-matched, not for explicit invocation |
| HTTP client | `urllib.request` + retry wrapper | `httpx` or `requests` | Breaks stdlib-only constraint, not worth it for 3 endpoints |
| Logging | `logging` (stdlib) | `structlog`, `loguru` | Breaks stdlib-only constraint |
| DB migrations | Manual versioned functions | `alembic` | Overkill for 9 tables, breaks stdlib-only constraint |
| Testing | `pytest` + `unittest.mock` | `pytest-asyncio`, `pytest-httpx` | No async code, stdlib HTTP mocking is sufficient |
| SQLite retry | Custom decorator | `tenacity` | Breaks stdlib-only constraint for a 15-line function |

## Installation / Setup Changes

```bash
# No new dependencies. Add pytest properly to pyproject.toml:
# [project.optional-dependencies]
# test = ["pytest>=7.0"]

# Install for testing:
uv pip install -e ".[test]"

# Run tests (after pythonpath fix):
uv run pytest tests/ -v
```

### Command Registration (One-Time Setup)

```bash
# Create command namespace
mkdir -p ~/.claude/commands/meridian

# Generate thin command wrappers from existing SKILL.md files
# (This should be a script in the hardening milestone)
```

The existing symlink `~/.claude/skills/meridian -> /Users/mattjaikaran/dev/meridian` should **stay** for passive skill loading (the top-level SKILL.md provides background context). The new commands in `~/.claude/commands/meridian/` handle explicit invocation.

## Sources

- Direct inspection of `~/.claude/skills/` (32 installed skills)
- Direct inspection of `~/.claude/commands/gsd/` (30+ commands) -- the reference implementation for Claude Code subcommand routing
- Direct inspection of `~/.claude/skills/skill-creator/SKILL.md` -- Anthropic's official skill authoring guide
- Direct inspection of `~/.claude/skills/writing-skills/SKILL.md` -- TDD-based skill creation methodology
- Meridian codebase analysis from `.planning/codebase/STACK.md` and `.planning/codebase/CONCERNS.md`
- Python sqlite3 documentation (stdlib `connection.backup()` method)
- Claude Code skill system: folder-based discovery with YAML frontmatter `name` and `description` fields

---

*Stack research: 2026-03-10*
