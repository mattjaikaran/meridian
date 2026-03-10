# Requirements: Meridian Hardening

**Defined:** 2026-03-10
**Core Value:** Deterministic workflow state that survives context resets — every resume produces the exact same prompt from the same database state.

## v1 Requirements

### Command Routing

- [ ] **ROUT-01**: All 13 subcommands are discoverable as `/meridian:*` slash commands in Claude Code
- [ ] **ROUT-02**: Each command is a thin `.md` wrapper in `~/.claude/commands/meridian/` referencing existing SKILL.md procedures
- [ ] **ROUT-03**: A Python generator script produces command `.md` files from skill definitions
- [ ] **ROUT-04**: Root SKILL.md provides passive project context without conflicting with command routing

### Database Reliability

- [ ] **DBRL-01**: `open_project()` context manager replaces all manual connect/try/finally/close patterns
- [ ] **DBRL-02**: `PRAGMA busy_timeout=5000` is set on every connection for concurrent write tolerance
- [ ] **DBRL-03**: Retry decorator with exponential backoff handles `sqlite3.OperationalError` ("database is locked")
- [ ] **DBRL-04**: `connection.backup()` creates hot snapshot of state.db before schema migrations
- [ ] **DBRL-05**: All existing scripts updated to use `open_project()` instead of manual connection management

### Error Handling & Logging

- [ ] **ERRL-01**: `MeridianError` base class with `StateTransitionError`, `DatabaseBusyError`, `NeroUnreachableError` subclasses
- [ ] **ERRL-02**: All state transition failures raise `StateTransitionError` instead of generic `ValueError`
- [ ] **ERRL-03**: Structured logging via stdlib `logging` module to stderr, replacing ad-hoc `print()` calls
- [ ] **ERRL-04**: Nero HTTP dispatch/sync calls retry with exponential backoff (3 attempts, 1s/2s/4s)
- [ ] **ERRL-05**: Failed Nero calls raise `NeroUnreachableError` after retry exhaustion instead of returning None

### Security

- [ ] **SECR-01**: Dynamic SQL column interpolation replaced with safe_update helper validating against schema
- [ ] **SECR-02**: `add_priority()` table name interpolation replaced with explicit mapping dict
- [ ] **SECR-03**: `_run_pm_command` in axis_sync uses proper list arguments instead of `command.split()`

### Testing

- [ ] **TEST-01**: `pyproject.toml` has `[tool.pytest.ini_options]` with `pythonpath = ["."]`
- [ ] **TEST-02**: All `sys.path.insert` hacks removed from test files
- [ ] **TEST-03**: Test coverage for `scripts/dispatch.py` (payload construction, error handling, connection creation)
- [ ] **TEST-04**: Test coverage for `scripts/export.py` (JSON format, file I/O, nested entity export)
- [ ] **TEST-05**: Test coverage for `scripts/axis_sync.py` (command construction, ticket parsing, status mapping)
- [ ] **TEST-06**: Test coverage for `scripts/context_window.py` (token estimation, checkpoint thresholds)
- [ ] **TEST-07**: Test coverage for `check_auto_advance()` (milestone readiness, edge cases, empty plans)
- [ ] **TEST-08**: Test coverage for schema migration path (v1→v2 upgrade, idempotency)

### Code Quality

- [ ] **QUAL-01**: N+1 queries in `generate_resume_prompt()` replaced with single JOIN query
- [ ] **QUAL-02**: N+1 queries in `compute_progress()` replaced with single aggregated query
- [ ] **QUAL-03**: N+1 queries in `export_state()` replaced with bulk fetch + Python assembly
- [ ] **QUAL-04**: `check_auto_advance()` milestone_ready flag only true when phase is actually complete
- [ ] **QUAL-05**: `update_nero_dispatch()` uses `if status is not None:` instead of truthiness check
- [ ] **QUAL-06**: Inline `timedelta` import in `forecast_completion()` moved to module level

## v2 Requirements

### Observability

- **OBSV-01**: Structured JSON log output option for machine parsing
- **OBSV-02**: Performance metrics for database operations (query timing)

### Resilience

- **RESL-01**: Database WAL checkpoint scheduling
- **RESL-02**: Automatic state.db integrity checks on startup

### Features

- **FEAT-01**: Review result persistence in database (currently ephemeral)
- **FEAT-02**: Stall detection with configurable thresholds
- **FEAT-03**: Workflow templates for common project types
- **FEAT-04**: Decision log enhancement with outcome tracking

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI / API server | Claude Code is the interface — no server needed |
| PostgreSQL migration | SQLite sufficient for single-user scale |
| Multi-user auth | Single-developer local tool |
| Plugin system | Over-engineering for current use case |
| AI auto-planning | Keep human in the loop for planning decisions |
| tiktoken integration | Rough estimation sufficient for checkpoint triggers |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROUT-01 | TBD | Pending |
| ROUT-02 | TBD | Pending |
| ROUT-03 | TBD | Pending |
| ROUT-04 | TBD | Pending |
| DBRL-01 | TBD | Pending |
| DBRL-02 | TBD | Pending |
| DBRL-03 | TBD | Pending |
| DBRL-04 | TBD | Pending |
| DBRL-05 | TBD | Pending |
| ERRL-01 | TBD | Pending |
| ERRL-02 | TBD | Pending |
| ERRL-03 | TBD | Pending |
| ERRL-04 | TBD | Pending |
| ERRL-05 | TBD | Pending |
| SECR-01 | TBD | Pending |
| SECR-02 | TBD | Pending |
| SECR-03 | TBD | Pending |
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| TEST-03 | TBD | Pending |
| TEST-04 | TBD | Pending |
| TEST-05 | TBD | Pending |
| TEST-06 | TBD | Pending |
| TEST-07 | TBD | Pending |
| TEST-08 | TBD | Pending |
| QUAL-01 | TBD | Pending |
| QUAL-02 | TBD | Pending |
| QUAL-03 | TBD | Pending |
| QUAL-04 | TBD | Pending |
| QUAL-05 | TBD | Pending |
| QUAL-06 | TBD | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 0
- Unmapped: 31 ⚠️

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after initial definition*
