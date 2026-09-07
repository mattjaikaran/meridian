# Meridian -- Unified Workflow Engine

Meridian is a SQLite-backed state machine for managing
complex development workflows with deterministic resume,
fresh-context subagents, and engineering discipline protocols.

## Available Skills

- ai-phase -- Use when you need Meridian to phase — AI Integration Phase Type.
- analyze-deps -- Use when you need Meridian to deps — Dependency Analysis.
- archive-milestone -- Use when you need Meridian to milestone — Archive Milestone.
- audit-milestone -- Use when you need Meridian to milestone — Audit Milestone Readiness.
- audit-uat -- Use when you need Meridian to uat — Cross-Phase Verification Debt Audit.
- autonomous -- Use when you need Meridian to hands-Free Execution.
- checkpoint -- Use when you need Meridian to manual Save Point.
- complete-milestone -- Use when you need Meridian to milestone — Complete Milestone.
- config -- Use when you need Meridian to workflow Configuration.
- dashboard -- Use when you need Meridian to project Dashboard.
- debug -- Use for systematic Debugging.
- discuss -- Use when you need Meridian to phase Discussion.
- dispatch -- Use when you need Meridian to remote Agent Dispatch.
- do -- Use when you need Meridian to freeform Command Router.
- execute -- Use when you need Meridian to execution Engine.
- fast -- Use when you need Meridian to inline Fast Task.
- forensics -- Use when you need Meridian to workflow Forensics.
- freeze -- Use when you need Meridian to edit Scope Lock.
- health -- Use when you need Meridian to dB and Artifact Health Check.
- history -- Use when you need Meridian to event Timeline.
- init -- Use when you need Meridian to initialize Meridian in Current Project.
- insert-phase -- Use when you need Meridian to phase — Insert Phase Mid-Milestone.
- learn -- Use when you need Meridian to execution Learning System.
- migrate -- Use when you need Meridian to cross-Project Migration.
- next -- Use when you need Meridian to advance to Next Workflow Step.
- note -- Use when you need Meridian to quick Note Capture.
- pause -- Use when you need Meridian to session Handoff.
- plan -- Use when you need Meridian to planning Pipeline.
- pr-branch -- Use when you need Meridian to branch — Create Clean PR Branch.
- profile -- Use when you need Meridian to developer Preference Profiling.
- quick -- Use when you need Meridian to lightweight Quick Task.
- remove-phase -- Use when you need Meridian to phase — Remove Phase.
- report -- Use when you need Meridian to session Report.
- research-phase -- Use when you need Meridian to phase — Research Phase Type.
- resume -- Use when you need Meridian to deterministic Resume.
- retro -- Use when you need Meridian to structured Retrospective.
- revert -- Use when you need Meridian to revert Completed Plan.
- review -- Use when you need Meridian to two-Stage Code Review.
- roadmap -- Use when you need Meridian to cross-Milestone Roadmap.
- scan -- Use when you need Meridian to codebase Audit & Work Discovery.
- secure-phase -- Use when you need Meridian to phase — Security Phase Type.
- seed -- Use when you need Meridian to backlog Seed Management.
- ship -- Use when you need Meridian to commit + Push + PR.
- sketch -- Use when you need Meridian to multi-Variant HTML Mockup Generation.
- sketch-wrap-up -- Use when you need Meridian to wrap-up — Pick Winner and Close Sketch.
- spec-phase -- Use when you need Meridian to phase — Spec Phase Type.
- spike -- Use when you need Meridian to pre-Commitment Exploration.
- spike-wrap-up -- Use when you need Meridian to wrap-up — Close a Spike and Extract Learnings.
- stats -- Use for project statistics, git metrics, test counts, velocity, and timelines.
- status -- Use when you need Meridian to show Project Status.
- template -- Use when you need Meridian to workflow Templates.
- thread -- Use when you need Meridian to persistent Discussion Threads.
- ui-phase -- Use when you need Meridian to phase — UI Phase Type.
- ultraplan -- Use when you need Meridian to cloud-Accelerated Planning.
- validate -- Use when you need Meridian to git State Validation.
- verify-phase -- Use when you need Meridian to phase -- Nyquist Compliance Check.
- workstream -- Use when you need Meridian to multi-Track Parallel Work Management.

## Architecture

State is stored in `.meridian/state.db` (SQLite) in each
project directory. The state machine enforces valid transitions
and computes the next action deterministically.

### Hierarchy
```
Project -> Workstream -> Milestone -> Phase -> Plan
                      (optional; milestones not in a workstream are ungrouped)
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
- `scripts/export.py` -- SQLite -> JSON export for remote agents
- `scripts/dispatch.py` -- Remote agent HTTP dispatch client
- `scripts/sync.py` -- Bidirectional remote agent sync (pull status + push state)
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
- `references/remote-agent.md` -- Remote agent dispatch protocol
- `references/board-integration.md` -- Pluggable board sync protocol
