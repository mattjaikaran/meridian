# Meridian -- Unified Workflow Engine

Meridian is a SQLite-backed state machine for managing
complex development workflows with deterministic resume,
fresh-context subagents, and engineering discipline protocols.

## Available Skills

- audit-uat -- uat — Cross-Phase Verification Debt Audit
- autonomous -- Hands-Free Execution
- checkpoint -- Manual Save Point
- complete-milestone -- milestone — Complete Milestone
- config -- Workflow Configuration
- dashboard -- Project Dashboard
- debug -- Systematic Debugging
- discuss -- Phase Discussion
- dispatch -- Nero Dispatch
- do -- Freeform Command Router
- execute -- Execution Engine
- fast -- Inline Fast Task
- freeze -- Edit Scope Lock
- history -- Event Timeline
- init -- Initialize Meridian in Current Project
- insert-phase -- phase — Insert Phase Mid-Milestone
- learn -- Execution Learning System
- migrate -- Cross-Project Migration
- next -- Advance to Next Workflow Step
- note -- Quick Note Capture
- pause -- Session Handoff
- plan -- Planning Pipeline
- pr-branch -- branch — Create Clean PR Branch
- profile -- Developer Preference Profiling
- quick -- Lightweight Quick Task
- remove-phase -- phase — Remove Phase
- report -- Session Report
- resume -- Deterministic Resume
- retro -- Structured Retrospective
- revert -- Revert Completed Plan
- review -- Two-Stage Code Review
- roadmap -- Cross-Milestone Roadmap
- scan -- Codebase Audit & Work Discovery
- seed -- Backlog Seed Management
- ship -- Commit + Push + PR
- status -- Show Project Status
- template -- Workflow Templates
- validate -- Git State Validation
- verify-phase -- phase -- Nyquist Compliance Check

## Architecture

State is stored in `.meridian/state.db` (SQLite) in each
project directory. The state machine enforces valid transitions
and computes the next action deterministically.

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
- `scripts/board/`          -- Pluggable board sync (kanban integration)
  - `provider.py`           -- BoardProvider protocol and registry
  - `cli.py`                -- CLI-based board provider (env-var configurable)
  - `sync.py`               -- Sync bridge (called from phase transitions)
- `scripts/context_window.py` -- Token estimation + checkpoint triggers
- `scripts/generate_commands.py` -- Generate Claude Code command wrappers from skills

## References
- `references/state-machine.md` -- State transitions + rules + auto-advancement + priority
- `references/discipline-protocols.md` -- TDD, debugging, verification, review
- `references/nero-integration.md` -- Dispatch + bidirectional sync protocol
- `references/board-integration.md` -- Pluggable board sync protocol
