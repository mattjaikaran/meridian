# Architecture Patterns

**Domain:** Claude Code skill with 13 subcommands, SQLite-backed state machine
**Researched:** 2026-03-10
**Updated:** 2026-03-10 (corrected skill routing based on commands system discovery)

## Recommended Architecture

### Overview

Meridian has three architecture problems that compound each other:

1. **Command routing uses the wrong mechanism** -- Claude Code has two separate systems: **skills** (passive, description-matched, loaded automatically) and **commands** (`~/.claude/commands/<namespace>/<cmd>.md`, explicit `/namespace:cmd` invocation). Meridian uses skills for what should be commands. This is why subcommands are not discoverable.
2. **Database connections are manually managed** -- every module does `conn = connect(); try: ... finally: conn.close()` with no retry logic, no context manager, no protection against concurrent WAL writes from subagents.
3. **Error handling is ad-hoc** -- `ValueError` for transitions, `None` returns for Nero failures, `print()` for output, no structured error types, no logging.

These must be fixed in dependency order: database layer first (everything depends on it), then error handling (routing needs it), then command routing (user-facing surface).

---

## 1. Command Routing Architecture

### The Problem

Claude Code has two separate systems that Meridian conflates:

| System | Location | Trigger | Discovery |
|--------|----------|---------|-----------|
| **Skills** | `~/.claude/skills/<name>/SKILL.md` | Automatic (description-matched) | Claude reads description, loads SKILL.md when relevant |
| **Commands** | `~/.claude/commands/<namespace>/<cmd>.md` | Explicit (`/namespace:cmd`) | User types `/` and sees command list |

The current symlink `~/.claude/skills/meridian -> ~/dev/meridian` registers a single skill. The 13 subcommand SKILL.md files at `skills/*/SKILL.md` are invisible because skills do not support subcommand routing.

**Evidence:** GSD (Get Shit Done) uses `~/.claude/commands/gsd/*.md` for 30+ subcommands. Each `.md` file becomes `/gsd:<filename>`. This works reliably with full subcommand routing, argument passing, and tool restrictions. Verified by direct inspection of `~/.claude/commands/gsd/`.

### Recommended Solution: Dual Registration (Commands + Skill)

**Commands** for explicit invocation, **skill** for passive context.

#### Commands (new): `~/.claude/commands/meridian/`

Create 13 thin command wrapper files:

```
~/.claude/commands/meridian/
  init.md          -> /meridian:init
  plan.md          -> /meridian:plan
  execute.md       -> /meridian:execute
  resume.md        -> /meridian:resume
  status.md        -> /meridian:status
  dashboard.md     -> /meridian:dashboard
  roadmap.md       -> /meridian:roadmap
  dispatch.md      -> /meridian:dispatch
  review.md        -> /meridian:review
  ship.md          -> /meridian:ship
  debug.md         -> /meridian:debug
  quick.md         -> /meridian:quick
  checkpoint.md    -> /meridian:checkpoint
```

Each command file follows the GSD-verified format:

```markdown
---
name: meridian:execute
description: Run plans via fresh subagents with TDD enforcement and 2-stage review
argument-hint: "[--phase <id>] [--plan <id>] [--wave <n>] [--no-review] [--inline]"
allowed-tools:
  - Read
  - Bash
  - Write
  - Task
  - AskUserQuestion
---
<objective>
Execute the next pending plan (or specified plan/phase) via a fresh-context subagent.
Enforces TDD discipline and runs 2-stage code review on completion.
</objective>

<execution_context>
@/Users/mattjaikaran/dev/meridian/skills/execute/SKILL.md
@/Users/mattjaikaran/dev/meridian/references/state-machine.md
@/Users/mattjaikaran/dev/meridian/references/discipline-protocols.md
</execution_context>

<context>
Arguments: $ARGUMENTS
Working directory: $CWD
</context>

<process>
Execute the workflow from @/Users/mattjaikaran/dev/meridian/skills/execute/SKILL.md end-to-end.
</process>
```

**Key properties:**
- `name`: Command identifier shown in `/` menu
- `description`: Short text shown in command list
- `argument-hint`: Placeholder shown after command name
- `allowed-tools`: Restricts which tools the command can use
- `@` references: Pull in existing SKILL.md content by absolute path
- `$ARGUMENTS`: Passes user-provided arguments into context

#### Skill (keep): `~/.claude/skills/meridian/SKILL.md`

Keep the existing symlink and root SKILL.md for **passive context loading**. When Claude is working in a project that has `.meridian/`, it auto-loads the skill for background awareness of the state machine, entity hierarchy, and available commands. Add proper YAML frontmatter:

```markdown
---
name: meridian
description: Meridian workflow engine context. This skill provides background
  knowledge about the Meridian state machine, entity hierarchy (Project >
  Milestone > Phase > Plan), and available commands. Automatically relevant
  when working in projects with a .meridian/ directory.
---
```

#### Why This Architecture

- **Commands are the correct mechanism** for explicit `/meridian:execute` invocations. Verified from GSD's working implementation.
- **Skills are the correct mechanism** for passive context (Claude knowing about Meridian without explicit invocation).
- **Existing SKILL.md files stay as-is** -- they contain procedural knowledge. Command `.md` files are thin wrappers that reference them via `@` paths.
- **No namespace pollution** -- all 13 commands live under the `meridian` namespace, not as 13 separate top-level skills.

### Component Boundaries for Routing

```
User Input: "/meridian:execute --plan 3"
    |
    v
[Command: ~/.claude/commands/meridian/execute.md]
    |  Loads: @/path/to/skills/execute/SKILL.md (via @ reference)
    |  Passes: $ARGUMENTS = "--plan 3"
    v
[SKILL.md procedure] -- loaded into context
    |  Contains: step-by-step procedure with embedded Python
    |  Executes: uv run --project ~/dev/meridian python -c "..."
    v
[Scripts Layer] -- Python business logic
    |  Functions called: compute_next_action(), transition_phase(), etc.
    v
[SQLite Database] -- .meridian/state.db
```

### Command Generation Strategy

Write a script (`scripts/generate_commands.py`) that reads existing `skills/*/SKILL.md` files and generates the corresponding command `.md` files. This ensures commands stay in sync with skills and makes regeneration trivial after skill changes.

---

## 2. Database Access Architecture

### Current Problems

1. **No context manager** -- every caller manually does `connect() / try / finally / close()`. This is 6 lines of boilerplate repeated ~12 times across modules.
2. **No retry on SQLITE_BUSY** -- WAL mode helps with concurrent reads, but when a subagent writes while the main agent writes, `sqlite3.OperationalError: database is locked` will crash with no recovery.
3. **Connections not scoped to operations** -- some functions accept `conn` as a parameter (good), some create their own connection internally (bad -- no caller control over transaction boundaries).
4. **Commits scattered inside CRUD functions** -- `create_project()` calls `conn.commit()` internally. This prevents callers from batching operations in a single transaction.

### Recommended Pattern: Connection Context Manager with Retry

Add to `scripts/db.py`:

```python
import contextlib
import time
import sqlite3
from pathlib import Path

@contextlib.contextmanager
def open_project(
    project_dir: str | Path | None = None,
    *,
    readonly: bool = False,
):
    """Context manager for SQLite connections with automatic cleanup.

    Usage:
        with open_project() as conn:
            create_project(conn, ...)
            create_milestone(conn, ...)
            # auto-commits on exit, auto-rollbacks on exception
    """
    db_path = get_db_path(project_dir)
    conn = connect(db_path)
    conn.execute("PRAGMA busy_timeout = 5000")  # 5 second retry on lock

    if readonly:
        conn.execute("PRAGMA query_only = ON")

    try:
        yield conn
        if not readonly:
            conn.commit()
    except sqlite3.OperationalError as e:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### Retry Decorator for Write Operations

Separate from the context manager -- wraps entire operations that may need retry:

```python
def retry_on_busy(max_retries: int = 5, base_delay: float = 0.1, max_delay: float = 2.0):
    """Retry decorator for sqlite3.OperationalError (database locked)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = base_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "database is locked" not in str(e) or attempt == max_retries - 1:
                        raise
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
        return wrapper
    return decorator
```

### Transaction Boundaries

**Rule: Functions that accept `conn` must NOT call `conn.commit()`.**

Currently `create_project()`, `create_milestone()`, etc. all call `conn.commit()` internally. This prevents batching multiple creates in a single transaction.

**Refactoring approach:**
1. Remove `conn.commit()` from all CRUD functions
2. Let the context manager handle commit/rollback
3. For backward compatibility, the context manager auto-commits on clean exit

### Connection Patterns by Module Type

| Module Type | Pattern | Example |
|------------|---------|---------|
| CRUD functions (`state.py`) | Accept `conn` parameter, no commit | `create_project(conn, ...)` |
| Entry points (`export.py`, `resume.py`) | Use `open_project()` | `with open_project() as conn:` |
| Command snippets | Use `open_project()` in the Python `-c` string | See below |
| Tests | Create in-memory connection in fixture | `conn = sqlite3.connect(":memory:")` |

### Command Snippet Pattern (after refactoring)

```python
# Before (current):
from scripts.db import connect, get_db_path
conn = connect(get_db_path('.'))
result = some_function(conn)
conn.close()

# After (recommended):
from scripts.db import open_project
with open_project() as conn:
    result = some_function(conn)
```

### SQLite Concurrent Access Strategy

Subagents spawned by `/meridian:execute` may write to the database concurrently:

1. **WAL mode** (already enabled) -- allows concurrent reads during writes
2. **busy_timeout pragma** (5000ms) -- SQLite retries internally before raising
3. **Short transactions** -- commit frequently, don't hold connections open during subagent execution
4. **Application-level retry** -- `retry_on_busy` decorator for operations that open their own connections

### SQL Injection Surface

The `update_*` functions build `SET` clauses dynamically with column names from hardcoded allowlists -- this is safe. However, `set_priority()` in `state.py` line 621 interpolates `entity_type` directly into the table name:

```python
conn.execute(f"UPDATE {entity_type} SET priority = ? WHERE id = ?", ...)
```

**Fix:** Validate against a whitelist:
```python
VALID_ENTITIES = {"phase", "plan"}
if entity_type not in VALID_ENTITIES:
    raise ValueError(f"Invalid entity type: {entity_type}")
```

### Database Backup via Online Backup API

```python
def backup_database(src_path: Path, dst_path: Path) -> None:
    """Hot backup using SQLite's online backup API (stdlib, Python 3.7+)."""
    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dst_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
```

Call before migrations and on explicit `/meridian:checkpoint` requests.

---

## 3. Error Handling Architecture

### Current State

- State transitions: `ValueError` with descriptive message
- Nero RPC: catches exceptions, returns `None`
- Git helpers: catches exceptions, returns tuple of `None`s
- No logging framework -- all output via `print()`
- No structured error types -- callers can't distinguish error categories

### Recommended Pattern: Structured Error Hierarchy

```python
# scripts/errors.py (new module)

class MeridianError(Exception):
    """Base error for all Meridian operations."""
    def __init__(self, message: str, context: dict | None = None):
        super().__init__(message)
        self.context = context or {}

class StateTransitionError(MeridianError):
    """Invalid state transition attempted."""
    def __init__(self, entity: str, entity_id: str | int,
                 current: str, requested: str, valid: list[str]):
        self.entity = entity
        self.entity_id = entity_id
        self.current = current
        self.requested = requested
        self.valid = valid
        super().__init__(
            f"Invalid {entity} transition: {current} -> {requested}. "
            f"Valid: {valid}",
            {"entity": entity, "entity_id": entity_id,
             "current": current, "requested": requested}
        )

class DatabaseBusyError(MeridianError):
    """SQLite database is locked by another writer."""

class NeroUnreachableError(MeridianError):
    """Cannot communicate with Nero endpoint."""

class ProjectNotFoundError(MeridianError):
    """Project not initialized in this directory."""

class EntityNotFoundError(MeridianError):
    """Requested entity does not exist."""
```

### Why Structured Errors Matter Here

Command procedures execute Python via `python -c "..."`. When an error occurs, the traceback appears in Claude's context. Structured errors with clear messages let Claude:
1. Understand what went wrong without parsing raw tracebacks
2. Decide whether to retry (`DatabaseBusyError`) or report (`StateTransitionError`)
3. Provide the user with actionable information

### Logging Strategy

**Use `logging` stdlib module, not `print()`.** Configure to output to stderr so it doesn't interfere with stdout which command snippets use for return values.

```python
# scripts/logging_config.py (new module)
import logging
import sys

def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("meridian")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S"
        ))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level))
    return logger
```

**Key principle:** `print()` to stdout for values command snippets need to capture. `logging` to stderr for diagnostic information.

---

## 4. Suggested Refactoring Order

The dependencies between improvements dictate the build order:

```
Phase 1: Database Layer (foundation -- everything depends on this)
    |
    +-- 1a. Add open_project() context manager to db.py
    +-- 1b. Add busy_timeout pragma, retry_on_busy decorator
    +-- 1c. Remove conn.commit() from CRUD functions
    +-- 1d. Fix entity_type SQL injection in set_priority()
    +-- 1e. Add backup_database() using online backup API
    +-- 1f. Fix pytest config (pythonpath in pyproject.toml)
    +-- 1g. Update tests to use new connection pattern
    |
Phase 2: Error Handling (depends on Phase 1 patterns)
    |
    +-- 2a. Create scripts/errors.py with error hierarchy
    +-- 2b. Replace ValueError in transition functions with StateTransitionError
    +-- 2c. Replace None returns in sync.py with NeroUnreachableError
    +-- 2d. Add logging_config.py, replace print() calls
    +-- 2e. Add HTTP retry wrapper for Nero communication
    +-- 2f. Update tests for new error types
    |
Phase 3: Command Routing (depends on Phase 1+2 for clean snippets)
    |
    +-- 3a. Create ~/.claude/commands/meridian/ directory
    +-- 3b. Write generate_commands.py script
    +-- 3c. Generate 13 command .md files from existing SKILL.md files
    +-- 3d. Add YAML frontmatter to root SKILL.md (passive context)
    +-- 3e. Update SKILL.md snippets to use open_project() pattern
    +-- 3f. Test all 13 commands end-to-end in Claude Code
    |
Phase 4: Test Coverage & Hardening (builds on Phase 1-3 foundation)
    |
    +-- 4a. Add tests for dispatch.py, export.py, axis_sync.py
    +-- 4b. Add tests for auto-advance edge cases
    +-- 4c. Add migration path tests (v1 -> v2)
    +-- 4d. Fix N+1 queries in resume.py, metrics.py, export.py
    +-- 4e. Fix known bugs (premature milestone_ready, empty status skip, command.split)
```

### Why This Order

1. **Database first:** Every module imports from `db.py`. Changing connection patterns is a foundational change. If you fix routing first, you write command snippets with the old connection pattern and then rewrite them.

2. **Errors before routing:** Command procedures need to handle errors gracefully. If error types aren't defined yet, the procedures will have ad-hoc error handling that needs rewriting.

3. **Routing after infrastructure:** The command files reference SKILL.md procedures. Those procedures should use clean patterns (context managers, structured errors) before being wrapped in commands.

4. **Tests and hardening last:** Proving everything works and optimizing performance builds on the foundation but doesn't block user-visible features.

---

## Patterns to Follow

### Pattern 1: Connection-per-Operation in Commands

**What:** Each Python `-c` snippet in a command/skill gets its own connection via context manager.
**When:** Always, for embedded Python snippets.
**Why:** Skill/command steps are independent operations. Holding a connection across steps (which span Claude's thinking time) would hold a WAL write lock for seconds or minutes.

```python
from scripts.db import open_project
import json
with open_project() as conn:
    result = do_something(conn)
    print(json.dumps(result))
# Connection released immediately
```

### Pattern 2: Whitelist Validation for Dynamic SQL

**What:** Any value interpolated into SQL structure (table/column names) must be validated against a hardcoded whitelist.
**When:** Whenever building dynamic SQL (as opposed to parameterized values which use `?`).

```python
VALID_TABLES = {"phase", "plan"}

def set_priority(conn, entity_type, entity_id, priority):
    if entity_type not in VALID_TABLES:
        raise ValueError(f"Invalid entity type: {entity_type}")
    conn.execute(
        f"UPDATE {entity_type} SET priority = ? WHERE id = ?",
        (priority, entity_id)
    )
```

### Pattern 3: Stdout for Data, Stderr for Diagnostics

**What:** Command snippets print structured data (JSON) to stdout. Logging/errors go to stderr.
**When:** All scripts that produce output consumed by command procedures.

### Pattern 4: Command as Thin Wrapper, Skill as Procedure

**What:** Command `.md` files define invocation interface (name, args, tool restrictions) and reference skill files via `@` paths. Skill files contain the actual procedural knowledge.
**When:** For all 13 subcommands.
**Why:** Separation of concerns. Commands handle routing; skills handle execution logic. A change to the procedure only touches the skill file. A change to the invocation interface only touches the command file.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Long-Lived Connections

**What:** Opening a connection at the start of a procedure and keeping it open across multiple steps.
**Why bad:** Claude's thinking time between steps can be 5-30 seconds. Holding a WAL write lock blocks subagents.
**Instead:** Open and close a connection for each discrete database operation.

### Anti-Pattern 2: Commits Inside CRUD Functions

**What:** Calling `conn.commit()` inside `create_project()`, `transition_phase()`, etc.
**Why bad:** Prevents transaction batching. A multi-step operation like "create milestone + 5 phases + 15 plans" makes 21 separate transactions instead of 1.
**Instead:** Let the caller (context manager) control commits.

### Anti-Pattern 3: Returning None for Errors

**What:** `_nero_rpc()` returns `None` on failure.
**Why bad:** `None` is ambiguous -- did the call fail, or did it return no data? Callers that forget the check silently proceed with `None`.
**Instead:** Raise `NeroUnreachableError`. Callers that want graceful degradation can catch it explicitly.

### Anti-Pattern 4: Using Skills for Explicit Commands

**What:** Putting procedural slash-command workflows in `~/.claude/skills/`.
**Why bad:** Skills are passive/description-matched. They load when Claude thinks they're relevant, not when the user explicitly invokes `/meridian:execute`. This is why subcommand routing is broken.
**Instead:** Use `~/.claude/commands/<namespace>/` for explicit invocations. Keep skills for passive context.

### Anti-Pattern 5: sys.path Hacking in Tests

**What:** `sys.path.insert(0, str(Path(__file__).parent.parent))` at the top of every test file.
**Why bad:** Fragile, non-standard, breaks IDE tooling.
**Instead:** Add `pythonpath = ["."]` to `pyproject.toml` `[tool.pytest.ini_options]`.

---

## Component Boundaries (Final State)

```
scripts/
  errors.py          NEW  -- Error hierarchy (MeridianError, StateTransitionError, ...)
  logging_config.py  NEW  -- Logging setup (stderr handler, formatters)
  generate_commands.py NEW -- Generates ~/.claude/commands/meridian/*.md from skills
  db.py              MOD  -- Add open_project(), busy_timeout, backup_database()
  state.py           MOD  -- Use structured errors, remove conn.commit() from CRUD
  resume.py          MOD  -- Use open_project(), fix N+1 queries
  export.py          MOD  -- Use open_project(), fix N+1 queries
  sync.py            MOD  -- Use structured errors, HTTP retry for Nero
  dispatch.py        MOD  -- Use open_project(), structured errors
  metrics.py         MOD  -- Use open_project(), fix N+1 queries
  axis_sync.py       MOD  -- Use open_project(), fix command.split()
  context_window.py  MOD  -- Use open_project()

~/.claude/commands/meridian/
  init.md            NEW  -- Thin wrapper -> skills/init/SKILL.md
  plan.md            NEW  -- Thin wrapper -> skills/plan/SKILL.md
  execute.md         NEW  -- Thin wrapper -> skills/execute/SKILL.md
  ... (13 total)     NEW

SKILL.md             MOD  -- Add YAML frontmatter for passive context
skills/*/SKILL.md    MOD  -- Update Python snippets to use open_project()

tests/
  conftest.py        NEW  -- Shared fixtures, eliminate sys.path hacking
  test_errors.py     NEW  -- Error hierarchy tests
  test_db.py         NEW  -- Connection manager, retry, migration tests
  test_dispatch.py   NEW  -- HTTP dispatch tests (mocked)
  test_export.py     NEW  -- Export format tests
  test_axis_sync.py  NEW  -- Axis sync tests (mocked subprocess)
```

### Module Dependency Graph

```
errors.py (no dependencies)
    ^
    |
logging_config.py (no dependencies)
    ^
    |
db.py (depends on: errors.py)
    ^
    |
state.py (depends on: db.py, errors.py)
    ^         ^         ^
    |         |         |
resume.py  export.py  sync.py  dispatch.py  metrics.py  axis_sync.py  context_window.py
```

**Key insight:** `errors.py` and `logging_config.py` have zero dependencies. They can be created first without touching anything else. Then `db.py` gets the context manager. Then `state.py` gets structured errors. Then all leaf modules are updated. This minimizes the blast radius of each change.

---

## Scalability Considerations

| Concern | Current (1 user, 1 project) | At 5 concurrent subagents | At 50+ plans per phase |
|---------|----------------------------|--------------------------|----------------------|
| SQLite contention | No issue | SQLITE_BUSY without retry | Same as 5 subagents |
| Connection management | Works (leaked connections rare) | Must retry or queue | Same |
| N+1 queries | Imperceptible | Imperceptible | Noticeable latency in resume/export |
| State.py size (880 lines) | Manageable | Same | Consider splitting CRUD from transitions |

---

## Confidence Assessment

| Area | Confidence | Basis |
|------|-----------|-------|
| Command routing (commands vs skills) | HIGH | Verified from GSD's 30+ working commands at `~/.claude/commands/gsd/` |
| Command .md format | HIGH | Directly inspected GSD command files (frontmatter, @ references, $ARGUMENTS) |
| SQLite context manager pattern | HIGH | Standard Python stdlib pattern |
| Retry on SQLITE_BUSY | HIGH | Standard SQLite concurrent access pattern, `busy_timeout` is documented pragma |
| Error hierarchy design | MEDIUM | Standard Python pattern; specific error names are best-guess for this domain |
| Logging strategy (stdout/stderr split) | HIGH | Unix convention; verified command snippets parse stdout |
| Refactoring order | HIGH | Derived from dependency analysis of actual codebase imports |

## Sources

- `~/.claude/commands/gsd/new-project.md` -- verified command format with frontmatter, @ references, $ARGUMENTS
- `~/.claude/commands/gsd/` -- 32 command files demonstrating the working subcommand pattern
- `~/.claude/skills/skill-creator/SKILL.md` -- Anthropic's official skill authoring guide (skills vs commands distinction)
- `~/.claude/skills/meridian/SKILL.md` -- current broken routing
- Current codebase: `scripts/db.py`, `scripts/state.py`, `scripts/sync.py`, `scripts/export.py`
- Python `sqlite3` stdlib module (WAL mode, busy_timeout pragma, connection.backup())
- Python `contextlib` stdlib module (contextmanager decorator)

---

*Architecture research: 2026-03-10 (updated with commands system discovery)*
