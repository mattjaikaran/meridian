# Meridian -- Unified Workflow Engine

Meridian is a SQLite-backed state machine for managing complex development workflows with deterministic resume, fresh-context subagents, and engineering discipline protocols.

## Available Skills

- checkpoint -- Manual Save Point
- dashboard -- Project Dashboard
- debug -- Systematic Debugging
- dispatch -- Nero Dispatch
- execute -- Execution Engine
- init -- Initialize Meridian in Current Project
- plan -- Planning Pipeline
- quick -- Lightweight Quick Task
- resume -- Deterministic Resume
- review -- Two-Stage Code Review
- roadmap -- Cross-Milestone Roadmap
- ship -- Commit + Push + PR
- status -- Show Project Status

## Architecture

State is stored in `.meridian/state.db` (SQLite) in each project directory. The state machine enforces valid transitions and computes the next action deterministically.

### Hierarchy
```
Project -> Milestone -> Phase -> Plan
```

### Phase Lifecycle
```
planned -> context_gathered -> planned_out -> executing -> verifying -> reviewing -> complete
                                                                         |
                                                                       blocked
```

### Plan Lifecycle
```
pending -> executing -> complete
                     -> failed -> pending (retry)
                     -> paused -> executing
```

## Scripts (Python, stdlib only)
- `scripts/db.py` -- Schema init + migrations (v2: priority column)
- `scripts/state.py` -- CRUD + transitions + next-action + auto-advancement + priority
- `scripts/resume.py` -- Deterministic resume prompt generator
- `scripts/export.py` -- SQLite -> JSON export for Nero
- `scripts/dispatch.py` -- Nero HTTP dispatch client (push only)
- `scripts/sync.py` -- Bidirectional Nero sync (pull status + push state)
- `scripts/metrics.py` -- PM metrics: velocity, cycle times, stalls, forecasts, progress
- `scripts/axis_sync.py` -- Axis PM ticket sync
- `scripts/context_window.py` -- Token estimation + checkpoint triggers
- `scripts/generate_commands.py` -- Generate Claude Code command wrappers from skills

## References
- `references/state-machine.md` -- State transitions + rules + auto-advancement + priority
- `references/discipline-protocols.md` -- TDD, debugging, verification, review
- `references/nero-integration.md` -- Dispatch + bidirectional sync protocol
- `references/axis-integration.md` -- PM sync protocol
