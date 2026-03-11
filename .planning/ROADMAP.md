# Roadmap: Meridian Hardening

## Overview

Harden Meridian from a working prototype into a reliable tool. The work flows bottom-up: database reliability first (everything depends on it), then structured error handling (builds on db patterns), then command routing (the primary user-visible fix), and finally test coverage and performance hardening (validates everything works and optimizes hot paths). Four phases, strict dependency order, no parallel phase execution.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3, 4): Planned milestone work
- Decimal phases (e.g., 2.1): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Database Foundation** - Context manager, retry logic, backup API, and pytest config so all subsequent phases build on solid DB patterns
- [x] **Phase 2: Error Infrastructure** - Structured error hierarchy, logging, HTTP retry, and SQL injection elimination (completed 2026-03-11)
- [x] **Phase 3: Command Routing** - All 13 subcommands discoverable as `/meridian:*` slash commands in Claude Code (completed 2026-03-11)
- [ ] **Phase 4: Test Coverage & Hardening** - Test coverage for untested modules, N+1 query fixes, and known bug fixes

## Phase Details

### Phase 1: Database Foundation
**Goal**: Every database interaction goes through a single reliable pattern with retry, busy tolerance, and backup capability
**Depends on**: Nothing (first phase)
**Requirements**: DBRL-01, DBRL-02, DBRL-03, DBRL-04, DBRL-05, TEST-01, TEST-02
**Success Criteria** (what must be TRUE):
  1. All scripts use `open_project()` context manager -- no manual connect/try/finally/close anywhere in codebase
  2. Concurrent subagent writes survive without `SQLITE_BUSY` crashes (busy_timeout + retry active)
  3. Running `python -m scripts.backup` (or equivalent) creates a hot snapshot of state.db
  4. `pytest` runs from repo root without any `sys.path.insert` hacks in test files
**Plans:** 1/2 plans executed

Plans:
- [ ] 01-01-PLAN.md -- Core db.py reliability layer (open_project, retry, backup) + test infrastructure
- [ ] 01-02-PLAN.md -- Migrate all scripts to open_project(), eliminate manual connection management

### Phase 2: Error Infrastructure
**Goal**: All failures produce structured, actionable errors instead of silent None returns or generic ValueErrors
**Depends on**: Phase 1
**Requirements**: ERRL-01, ERRL-02, ERRL-03, ERRL-04, ERRL-05, SECR-01, SECR-02, SECR-03
**Success Criteria** (what must be TRUE):
  1. State transition failures raise `StateTransitionError` with a message naming the invalid transition attempted
  2. Nero dispatch failures raise `NeroUnreachableError` after 3 retries -- never silently return None
  3. All log output goes to stderr via stdlib `logging` -- no `print()` calls remain for operational output
  4. Dynamic SQL interpolation is gone -- `safe_update()` validates columns against schema, `add_priority()` uses an explicit table mapping
**Plans:** 3/3 plans complete

Plans:
- [ ] 02-01-PLAN.md -- Error hierarchy, logging setup, and HTTP retry decorator in db.py
- [ ] 02-02-PLAN.md -- safe_update() with column allowlists and StateTransitionError in state.py
- [ ] 02-03-PLAN.md -- Nero retry integration in dispatch.py/sync.py and axis_sync command fix

### Phase 3: Command Routing
**Goal**: Users invoke all 13 Meridian workflows as `/meridian:*` slash commands in Claude Code
**Depends on**: Phase 2
**Requirements**: ROUT-01, ROUT-02, ROUT-03, ROUT-04
**Success Criteria** (what must be TRUE):
  1. Typing `/meridian:` in Claude Code shows all 13 subcommands in autocomplete
  2. Each command `.md` file in `~/.claude/commands/meridian/` is a thin wrapper referencing existing SKILL.md procedures
  3. Running the generator script regenerates all command files from skill definitions without manual editing
  4. Root SKILL.md provides passive project context without conflicting with command invocation
**Plans:** 2/2 plans complete

Plans:
- [ ] 03-01-PLAN.md -- Generator script with TDD (discover skills, generate wrappers, update root SKILL.md)
- [ ] 03-02-PLAN.md -- Run generator, install commands, verify in Claude Code

### Phase 4: Test Coverage & Hardening
**Goal**: Every module has test coverage, known bugs are fixed, and hot-path queries are optimized
**Depends on**: Phase 3
**Requirements**: TEST-03, TEST-04, TEST-05, TEST-06, TEST-07, TEST-08, QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05, QUAL-06
**Success Criteria** (what must be TRUE):
  1. `pytest` passes with tests covering dispatch, export, axis_sync, context_window, auto-advance, and migrations
  2. `check_auto_advance()` correctly returns `milestone_ready=False` when a phase has incomplete plans
  3. `generate_resume_prompt()`, `compute_progress()`, and `export_state()` each use a single query (or bulk fetch) instead of N+1 loops
  4. `update_nero_dispatch()` distinguishes between `status=None` (not provided) and `status=""` (empty string)
**Plans:** 3/4 plans executed

Plans:
- [ ] 04-01-PLAN.md -- New test files for dispatch.py, export.py, context_window.py
- [ ] 04-02-PLAN.md -- Expand existing tests for axis_sync, auto-advance, migrations
- [x] 04-03-PLAN.md -- N+1 query fixes in resume.py, metrics.py, export.py (completed 2026-03-11)
- [ ] 04-04-PLAN.md -- Bug fixes: auto-advance false positive, nero dispatch truthiness, inline import

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Database Foundation | 1/2 | In Progress|  |
| 2. Error Infrastructure | 3/3 | Complete   | 2026-03-11 |
| 3. Command Routing | 2/2 | Complete   | 2026-03-11 |
| 4. Test Coverage & Hardening | 3/4 | In Progress|  |
