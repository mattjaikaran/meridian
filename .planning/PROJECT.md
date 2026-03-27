# Meridian — Unified Workflow Engine

## What This Is

A SQLite-backed state machine for managing complex development workflows in Claude Code. Provides 32 slash commands (`/meridian:*`) for project initialization, planning, execution via fresh-context subagents, deterministic resume, code review, and autonomous dispatch to Nero. Built as a Claude Code skill with stdlib-only Python. Hardened with structured error handling, retry logic, SQL safety, and comprehensive test coverage.

## Core Value

Deterministic workflow state that survives context resets — every resume produces the exact same prompt from the same database state, so complex multi-phase projects never lose progress.

## Requirements

### Validated

- ✓ SQLite state machine with enforced transitions (Project > Milestone > Phase > Plan) — existing
- ✓ 13 slash command definitions as SKILL.md files — existing
- ✓ Fresh-context subagent execution for plans — existing
- ✓ Deterministic resume prompt generation from SQLite — existing
- ✓ Wave-based parallel/sequential plan execution — existing
- ✓ Two-stage code review (spec + quality) — existing
- ✓ Checkpoint system with 6 trigger types — existing
- ✓ Nero bidirectional sync (dispatch + status pull) — existing
- ✓ Axis PM ticket sync — existing
- ✓ PM metrics: velocity, cycle times, stalls, forecasts — existing
- ✓ JSON state export for Nero consumption — existing
- ✓ Schema migration system (v1→v2) — existing
- ✓ Context window token estimation — existing
- ✓ Dashboard and roadmap views — existing
- ✓ `open_project()` context manager with retry, backup, busy tolerance — v1.0
- ✓ `MeridianError` hierarchy (StateTransitionError, NeroUnreachableError, DatabaseBusyError) — v1.0
- ✓ Structured logging via stdlib `logging` to stderr — v1.0
- ✓ HTTP retry with exponential backoff for Nero communication — v1.0
- ✓ SQL injection elimination via `safe_update()` allowlists — v1.0
- ✓ 32 `/meridian:*` slash commands discoverable in Claude Code autocomplete — v1.0–v1.5
- ✓ Command generator script producing wrappers from SKILL.md definitions — v1.0
- ✓ Test coverage for all modules (928 tests, 45 test files) — v1.0–v1.5
- ✓ N+1 query fixes in resume, metrics, and export — v1.0
- ✓ Bug fixes: auto-advance false positive, nero dispatch truthiness, inline import — v1.0

### Shipped

All milestones v1.0 through v1.5 shipped (2026-03-11 to 2026-03-20):
- **v1.0** Meridian Hardening — DB foundation, error infrastructure, command routing, test coverage
- **v1.1** Polish & Reliability — lint cleanup, Nyquist compliance, roadmap automation
- **v1.2** Feature Parity — quick workflow, quality gates, session intelligence, security & PR hygiene
- **v1.3** Advanced Capabilities — developer experience, execution resilience, agent intelligence
- **v1.4** Feature Expansion — learnings, freeze, retro, deep discovery, sessions, cross-model review
- **v1.5** Integration & Polish — auto-learn, HTML dashboard, freeze integration, test coverage audit, context bridge, retro auto-scheduling

### Out of Scope

- Multi-user / authentication — single-developer local tool
- PostgreSQL migration — SQLite sufficient for single-user scale
- Web UI / API server — Claude Code is the interface
- tiktoken integration — rough estimation is good enough for checkpoint triggers
- Plugin system — over-engineering for current use case
- AI auto-planning — keep human in the loop for planning decisions

## Context

Shipped v1.0 through v1.5 (2026-03-11 to 2026-03-20). 26 phases across 6 milestones.
Tech stack: Python 3.12+ (stdlib-only), SQLite (WAL mode), pytest, uv.
928 tests passing across 45 test files. 42 Python modules in scripts/. 32 slash commands shipped.
Two-machine model: MacBook Pro (interactive) dispatches to Mac Mini (Nero) for autonomous execution.

## Constraints

- **Python stdlib only**: No external dependencies beyond pytest for tests
- **Claude Code skill system**: Commands use folder-based SKILL.md routing with generated `.md` wrappers
- **SQLite single-writer**: WAL mode + busy_timeout + retry_on_busy for concurrent writes
- **Package manager**: uv only (no pip)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stdlib-only Python | Zero dependency management, works everywhere Python does | ✓ Good |
| SQLite per-project | Simple, portable, no server needed for single-user tool | ✓ Good |
| SKILL.md-based commands | Leverages Claude Code's native skill system | ✓ Good — fixed with generated .md wrappers in ~/.claude/commands/ |
| Symlink into ~/.claude/skills/ | Quick registration approach | ✓ Good — works with wrapper pattern |
| open_project() as canonical DB access | Single reliable pattern with auto-commit/rollback/close | ✓ Good |
| MeridianError hierarchy | Structured errors replace silent None/generic ValueError | ✓ Good |
| safe_update() with ALLOWED_COLUMNS | Eliminates SQL injection from dynamic column interpolation | ✓ Good |
| defaultdict + plans_by_phase pattern | Consistent N+1 fix across resume, metrics, export | ✓ Good |
| Generated command wrappers | Thin .md files with @ references, regenerable from skills | ✓ Good |

---
*Last updated: 2026-03-27 after v1.5 completion*
