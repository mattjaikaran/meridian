# Meridian — Unified Workflow Engine

Meridian is a SQLite-backed state machine for managing complex development workflows with deterministic resume, fresh-context subagents, and engineering discipline protocols.

## Commands

- `/meridian:init` — Initialize Meridian in current project (creates `.meridian/`)
- `/meridian:plan` — Brainstorm → context gather → generate plans with wave assignments
- `/meridian:execute` — Run plans via fresh subagents with TDD enforcement and 2-stage review
- `/meridian:resume` — Generate deterministic resume prompt from SQLite state
- `/meridian:status` — Show progress, phase state, blockers, next action
- `/meridian:dashboard` — Rich project dashboard: health, velocity, stalls, Nero dispatches
- `/meridian:roadmap` — Cross-milestone roadmap with progress and ETAs
- `/meridian:dispatch` — Send plans to Nero for autonomous execution (PR factory)
- `/meridian:review` — Two-stage code review (spec compliance → quality)
- `/meridian:ship` — Commit + push + create PR via gh CLI
- `/meridian:debug` — 4-phase systematic debugging with decision logging
- `/meridian:quick` — Lightweight task, no phase overhead, still tracked
- `/meridian:checkpoint` — Manual save point with notes

## Architecture

State is stored in `.meridian/state.db` (SQLite) in each project directory. The state machine enforces valid transitions and computes the next action deterministically.

### Hierarchy
```
Project → Milestone → Phase → Plan
```

### Phase Lifecycle
```
planned → context_gathered → planned_out → executing → verifying → reviewing → complete
                                                                     ↕
                                                                   blocked
```

### Plan Lifecycle
```
pending → executing → complete
                   → failed → pending (retry)
                   → paused → executing
```

## Scripts (Python, stdlib only)
- `scripts/db.py` — Schema init + migrations (v2: priority column)
- `scripts/state.py` — CRUD + transitions + next-action + auto-advancement + priority
- `scripts/resume.py` — Deterministic resume prompt generator
- `scripts/export.py` — SQLite → JSON export for Nero
- `scripts/dispatch.py` — Nero HTTP dispatch client (push only)
- `scripts/sync.py` — Bidirectional Nero sync (pull status + push state)
- `scripts/metrics.py` — PM metrics: velocity, cycle times, stalls, forecasts, progress
- `scripts/axis_sync.py` — Axis PM ticket sync
- `scripts/context_window.py` — Token estimation + checkpoint triggers

## References
- `references/state-machine.md` — State transitions + rules + auto-advancement + priority
- `references/discipline-protocols.md` — TDD, debugging, verification, review
- `references/nero-integration.md` — Dispatch + bidirectional sync protocol
- `references/axis-integration.md` — PM sync protocol
