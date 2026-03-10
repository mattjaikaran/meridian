# Meridian — Unified Workflow Engine

## What This Is

A SQLite-backed state machine for managing complex development workflows in Claude Code. Provides slash commands for project initialization, planning, execution via fresh-context subagents, deterministic resume, code review, and autonomous dispatch to Nero. Built as a Claude Code skill with stdlib-only Python.

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

### Active

- [ ] Fix skill registration so all 13 commands work as Claude Code slash commands
- [ ] Fix known bugs (auto-advance premature flag, empty status silent skip, unsafe string splitting)
- [ ] Eliminate SQL injection surface (dynamic f-string column/table interpolation)
- [ ] Add test coverage for dispatch, export, axis_sync, context_window, auto-advance, migrations
- [ ] Add retry logic with backoff for Nero HTTP communication
- [ ] Add structured logging framework
- [ ] Extract duplicated connection boilerplate into context manager
- [ ] Fix sys.path hacking in tests with proper pytest config
- [ ] Add database backup/restore mechanism
- [ ] Fix N+1 query patterns in resume, metrics, and export

### Out of Scope

- Multi-user / authentication — single-developer local tool
- PostgreSQL migration — SQLite sufficient for single-user scale
- Web UI / API server — Claude Code is the interface
- tiktoken integration — rough estimation is good enough for checkpoint triggers

## Context

- Meridian is symlinked into `~/.claude/skills/meridian` which registers `/meridian` as a skill, but subcommands like `/meridian:init` aren't discoverable — Claude Code uses folder names for skill routing
- All Python is stdlib-only (explicit design choice), with pytest as the only dev dependency
- Two-machine model: MacBook Pro (interactive) dispatches to Mac Mini (Nero) for autonomous execution
- The codebase map at `.planning/codebase/` has 7 detailed analysis documents

## Constraints

- **Python stdlib only**: No external dependencies beyond pytest for tests — keeps the tool lightweight and portable
- **Claude Code skill system**: Commands must work within Claude Code's skill discovery mechanism (folder-based SKILL.md routing)
- **SQLite single-writer**: WAL mode helps but concurrent writes from subagents need retry logic
- **Package manager**: uv only (no pip)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stdlib-only Python | Zero dependency management, works everywhere Python does | ✓ Good |
| SQLite per-project | Simple, portable, no server needed for single-user tool | ✓ Good |
| SKILL.md-based commands | Leverages Claude Code's native skill system | ⚠️ Revisit — subcommand routing broken |
| Symlink into ~/.claude/skills/ | Quick registration approach | ⚠️ Revisit — doesn't support subcommands |

---
*Last updated: 2026-03-10 after initialization*
