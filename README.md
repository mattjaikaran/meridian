# Meridian

Unified workflow engine for Claude Code. SQLite-backed state machine with deterministic resume, fresh-context subagents, and engineering discipline protocols.

## Quick Start

1. **Prerequisites**: Python 3.11+, [uv](https://docs.astral.sh/uv/), git
2. **Install**:
   ```bash
   git clone <repo-url> ~/dev/meridian
   ln -sfn ~/dev/meridian ~/.claude/skills/meridian
   cd ~/dev/meridian && uv run python scripts/generate_commands.py --fix-symlink
   uv run python scripts/generate_commands.py
   ```
3. **Initialize a project**:
   ```bash
   # In any project directory:
   /meridian:init
   ```
4. **Plan work**:
   ```bash
   /meridian:plan "Build user authentication"
   ```
5. **Execute**:
   ```bash
   /meridian:execute
   ```

## Why Meridian

| Problem | Solution |
|---------|----------|
| GSD resume uses prose-based HANDOFF.md — breaks on context reset | SQLite-backed state with deterministic prompt generation |
| Superpowers has no state persistence | All state in `.meridian/state.db` |
| No integration between workflow systems and PM tools | Axis sync + Nero dispatch built in |
| Subagents share polluted context | Each plan gets 200k fresh tokens |
| No engineering discipline enforcement | TDD, debugging, review protocols embedded in prompts |

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ MacBook Pro (Matt interactive)                            │
│                                                           │
│  Claude Code + Meridian Skill                             │
│  ┌────────────────────────────────────────────┐           │
│  │ /meridian:* commands                        │           │
│  │ SQLite state.db (source of truth)           │           │
│  │ JSON export (git-tracked, Nero reads)       │           │
│  │ Subagent dispatch (200k fresh context each) │           │
│  │ TDD / Debug / Review protocols              │           │
│  └──────────────┬─────────────────────────────┘           │
│                  │ HTTP dispatch                          │
└──────────────────┼────────────────────────────────────────┘
                   │
┌──────────────────▼────────────────────────────────────────┐
│ Mac Mini (Nero autonomous)                                │
│                                                            │
│  Nero Daemon (Rust) → Crush agent → PRs                    │
│  Reads meridian-state.json for project context             │
│  Axis PM sync (kanban board)                               │
└────────────────────────────────────────────────────────────┘
```

## Data Model

```
Project
  └── Milestone (v1.0, v2.0)
        └── Phase (major work unit)
              └── Plan (one subagent's worth of work)
                    └── Wave (parallel execution group)
```

## State Machines

### Phase Lifecycle
```
planned → context_gathered → planned_out → executing → verifying → reviewing → complete
   ↕            ↕                 ↕            ↕           ↕           ↕
 blocked      blocked          blocked      blocked     blocked     blocked
```

### Plan Lifecycle
```
pending → executing → complete
                   → failed → pending (retry)
                   → paused → executing (resume)
pending → skipped
```

## Commands

| Command | Purpose |
|---------|---------|
| `/meridian:init` | Create `.meridian/`, init DB, gather project context |
| `/meridian:plan` | Brainstorm → context gather → generate plans with waves |
| `/meridian:execute` | Run plans via fresh subagents, TDD enforced, 2-stage review |
| `/meridian:resume` | Generate deterministic resume prompt from SQLite |
| `/meridian:status` | Show progress, phase state, blockers, next action |
| `/meridian:dashboard` | Rich project dashboard — health, velocity, stalls, Nero dispatches |
| `/meridian:roadmap` | Cross-milestone view with progress bars and ETAs |
| `/meridian:dispatch` | Send plans to Nero for autonomous execution (PR factory) |
| `/meridian:review` | Two-stage code review (spec compliance → quality) |
| `/meridian:ship` | Commit + push + create PR via gh CLI |
| `/meridian:debug` | 4-phase systematic debugging with decision logging |
| `/meridian:quick` | Lightweight task, no phase overhead, still tracked |
| `/meridian:checkpoint` | Manual save point with notes |

## Typical Workflow

```
/meridian:init          # Initialize in project
/meridian:plan          # Brainstorm phases, gather context, create plans
/meridian:execute       # Run plans (subagents, TDD, review)
/meridian:dashboard     # Check health, velocity, stalls
/meridian:checkpoint    # Save state before context limit
  ... new session ...
/meridian:resume        # Deterministic restore — exact same position
/meridian:execute       # Continue where we left off
/meridian:roadmap       # Cross-milestone progress view
/meridian:ship          # Commit, push, PR
```

## PM Visibility

Meridian computes metrics from existing SQLite timestamps — no extra instrumentation needed.

### Dashboard (`/meridian:dashboard`)

Single-view status with health indicator, velocity, stalls, and Nero dispatches:

```
# Project Dashboard — MyApp
## Health: ON TRACK

Milestone: v1.0 (active) — 67% complete, ETA Mar 9
Phase 2/3: Features [executing] — 3/5 plans done
Velocity: 2.4 plans/day (7d avg)

### Stalls
- Plan "Add auth" stuck in executing for 6h

### Nero Dispatches
- Plan "Setup CI" → Nero (running, 45min)
- Plan "Add tests" → Nero (completed, PR #12)

### Next Action
→ Execute plan: "Add API routes" (wave 2)
```

Health is computed from metrics:
- **ON TRACK** — No stalls, velocity > 0, ETA exists
- **AT RISK** — 1-2 stalls or velocity dropped to 0
- **STALLED** — 3+ stalls or no plans completed in 3+ days

### Roadmap (`/meridian:roadmap`)

Cross-milestone view with phase status and completion percentages:

```
# Roadmap — MyApp

## v1.0 (active) — 67% — ETA Mar 9
  Phase 1: Foundation [complete] (3/3) ✓
  Phase 2: Features [executing] (3/5) <-
  Phase 3: Polish [planned] (0/2)

## v1.1 (planned)
  Phase 1: Performance [planned]
  Phase 2: Mobile support [planned]

---
Active velocity: 2.4 plans/day | Forecast: 1.2 days remaining
```

### Metrics API

All metrics are pure functions on `sqlite3.Connection`:

```python
from scripts.metrics import (
    compute_velocity,       # plans/day over 7-day rolling window
    compute_cycle_times,    # avg hours per phase and plan
    detect_stalls,          # plans/phases stuck beyond threshold
    forecast_completion,    # ETA based on velocity + remaining work
    compute_progress,       # completion % at milestone/phase/plan levels
)

conn = connect(get_db_path("."))
velocity = compute_velocity(conn)        # {velocity: 2.4, completed_count: 17, window_days: 7}
stalls = detect_stalls(conn)             # [{entity_type: "plan", name: "Add auth", stuck_hours: 6.3}]
forecast = forecast_completion(conn)     # {remaining_plans: 3, eta_days: 1.2, eta_date: "2026-03-09"}
progress = compute_progress(conn)        # {milestone: {pct: 67}, phases: [{pct: 100}, {pct: 60}]}
```

## Bidirectional Nero Sync

Meridian now maintains a full sync loop with Nero instead of push-only dispatch:

```python
from scripts.sync import pull_dispatch_status, push_state_to_nero, sync_all

# Pull: check all active dispatches, auto-transition plans on completion/failure
updates = pull_dispatch_status(conn)

# Push: export pending work as Nero-ready tickets for scheduling
result = push_state_to_nero(conn)

# Both in one call
result = sync_all(conn)
```

When Nero reports a task completed, `pull_dispatch_status` auto-transitions the local plan to `complete` (with commit SHA) or `failed` (with error message). This triggers auto-advancement checks.

## Auto-Advancement

After plan completion, Meridian can auto-advance the state machine:

```python
from scripts.state import check_auto_advance

result = check_auto_advance(conn, phase_id)
# All plans complete → phase auto-transitions to "verifying"
# If all phases complete → milestone flagged for completion
```

This reduces manual state transitions — complete a plan and the phase automatically moves forward.

## Priority

Phases and plans support priority levels (`critical`, `high`, `medium`, `low`):

```python
from scripts.state import add_priority

add_priority(conn, "plan", plan_id, "critical")
add_priority(conn, "phase", phase_id, "high")
```

Priority is used by:
- `/meridian:dashboard` to highlight priority items
- `push_state_to_nero` to inform Nero's scheduler
- Future: priority-aware plan ordering in `compute_next_action`

## Discipline Protocols

Embedded in subagent prompts and enforced during execution:

1. **TDD Iron Law** — No production code without a failing test first. RED → GREEN → REFACTOR.
2. **Systematic Debugging** — 4-phase: Investigation → Pattern → Hypothesis → Implementation. 3+ failed fixes = architectural problem.
3. **Two-Stage Review** — Stage 1: spec compliance (did you build what was asked?). Stage 2: code quality (is it well-built?).
4. **Verification Before Completion** — Fresh evidence required. No claiming done without proving it works.
5. **Context Window Discipline** — Auto-checkpoint at 150k tokens. Subagents get 200k fresh context each.

## Project Structure

```
meridian/
├── SKILL.md                             # Skill entry point
├── pyproject.toml                       # uv-managed, stdlib only
├── scripts/
│   ├── db.py                            # Schema init + migrations (v2: priority)
│   ├── state.py                         # CRUD + transitions + next-action + auto-advance
│   ├── resume.py                        # Deterministic resume prompt generator
│   ├── export.py                        # SQLite → JSON export
│   ├── dispatch.py                      # Nero HTTP dispatch client (push)
│   ├── sync.py                          # Bidirectional Nero sync (pull + push)
│   ├── metrics.py                       # PM metrics — velocity, stalls, forecasts
│   ├── axis_sync.py                     # Axis PM ticket sync
│   └── context_window.py               # Token estimation + checkpoint triggers
├── prompts/
│   ├── implementer.md                   # Subagent: implement + TDD
│   ├── spec-reviewer.md                 # Subagent: spec compliance check
│   ├── code-quality-reviewer.md         # Subagent: code quality review
│   ├── context-gatherer.md              # Subagent: deep project analysis
│   └── resume-template.md              # Resume prompt structure reference
├── references/
│   ├── state-machine.md                 # State transitions + rules + auto-advance
│   ├── discipline-protocols.md          # TDD, debugging, verification, review
│   ├── nero-integration.md              # Dispatch + sync protocol
│   └── axis-integration.md             # PM sync protocol
├── skills/                              # Individual slash command SKILL.md files
│   ├── init/SKILL.md
│   ├── plan/SKILL.md
│   ├── execute/SKILL.md
│   ├── resume/SKILL.md
│   ├── status/SKILL.md
│   ├── dashboard/SKILL.md              # Project dashboard — health + metrics
│   ├── roadmap/SKILL.md                # Cross-milestone roadmap view
│   ├── dispatch/SKILL.md
│   ├── review/SKILL.md
│   ├── ship/SKILL.md
│   ├── debug/SKILL.md
│   ├── quick/SKILL.md
│   └── checkpoint/SKILL.md
└── tests/
    ├── test_state.py                    # 33 tests — CRUD, transitions, next-action
    ├── test_resume.py                   # 9 tests — deterministic prompt generation
    ├── test_metrics.py                  # 18 tests — velocity, stalls, forecasts, progress
    └── test_sync.py                     # 15 tests — pull, push, sync, dispatch summary
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- git
- Claude Code with skills support

### Installation

```bash
# Clone the repo
git clone <repo-url> ~/dev/meridian

# Symlink to Claude Code skills directory
ln -sfn ~/dev/meridian ~/.claude/skills/meridian

# Generate slash command wrappers
cd ~/dev/meridian
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py
```

### Running Tests

```bash
cd ~/dev/meridian
uv run pytest tests/ -v
```

### Verify Installation

After setup, open Claude Code in any project and run `/meridian:init`. You should see a `.meridian/` directory created with `state.db` inside.

## Schema

Current schema version: **2**

| Table | Purpose |
|-------|---------|
| `project` | One per project — name, repo, tech stack, nero endpoint |
| `milestone` | Versioned releases (v1.0, v2.0) with status |
| `phase` | Major work units — sequence, status, priority, acceptance criteria |
| `plan` | Subagent work items — wave, TDD flag, priority, executor type |
| `checkpoint` | Save points — git state, decisions, blockers |
| `decision` | Architecture/approach decisions with rationale |
| `nero_dispatch` | Async dispatch tracking — task ID, status, PR URL |
| `quick_task` | Lightweight tasks without phase overhead |

Migration history:
- **v1**: Initial schema (11 tables)
- **v2**: Added `priority` column to `phase` and `plan` tables

## Stack

- **Python 3.11+** — stdlib only (sqlite3, json, pathlib, subprocess, textwrap)
- **SQLite** — WAL mode, foreign keys enforced, per-project `.meridian/state.db`
- **Claude Code Skills** — SKILL.md routing with slash commands

## Key Innovation: Deterministic Resume

The resume prompt is generated entirely from SQLite queries:

```python
# Same state = same prompt. Always.
prompt1 = generate_resume_prompt("/path/to/project")
prompt2 = generate_resume_prompt("/path/to/project")
assert prompt1 == prompt2  # Guaranteed
```

Every field maps to a discrete DB query. No LLM-written prose. The `next_action` is computed from state transition rules, not guessed. This is what makes resume reliable across context resets.

## Commands Reference

| Command | Description |
|---------|-------------|
| `/meridian:init` | Initialize Meridian in current project — creates `.meridian/` and `state.db` |
| `/meridian:plan` | Planning pipeline — brainstorm, context gather, generate plans with waves |
| `/meridian:execute` | Execution engine — run plans via fresh subagents with TDD enforcement |
| `/meridian:resume` | Deterministic resume — regenerate exact state from SQLite for context restore |
| `/meridian:status` | Show project status — progress, phase state, blockers, next action |
| `/meridian:dashboard` | Project dashboard — health indicator, velocity, stalls, Nero dispatches |
| `/meridian:roadmap` | Cross-milestone roadmap — progress bars and ETAs across all milestones |
| `/meridian:dispatch` | Nero dispatch — send plans to Nero for autonomous execution |
| `/meridian:review` | Two-stage code review — spec compliance then code quality |
| `/meridian:ship` | Commit + push + PR via gh CLI |
| `/meridian:debug` | Systematic debugging — 4-phase investigation with decision logging |
| `/meridian:quick` | Lightweight quick task — no phase overhead, still tracked |
| `/meridian:checkpoint` | Manual save point — snapshot state with notes |
| `/meridian:history` | Event timeline — view state transitions and activity log |
| `/meridian:migrate` | Cross-project migration — move Meridian state between projects |
| `/meridian:revert` | Revert completed plan — undo a plan's changes |
| `/meridian:template` | Workflow templates — apply pre-built project templates |
| `/meridian:validate` | Git state validation — verify working tree and DB consistency |

## Troubleshooting

### "Module not found" or PYTHONPATH errors

Meridian scripts need the repo root on PYTHONPATH. Use the runner script:
```bash
~/dev/meridian/scripts/run.sh '<python code>'
```
Or set manually: `PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "..."`

### "Database is locked"

Multiple concurrent operations can lock SQLite. Meridian uses WAL mode and automatic retry with exponential backoff. If persistent, check for zombie processes:
```bash
lsof .meridian/state.db
```

### "State seems corrupted"

Meridian creates automatic backups before migrations in `.meridian/backups/`. Restore with:
```bash
cp .meridian/backups/state-<timestamp>.db .meridian/state.db
```

### Commands not showing in Claude Code

Regenerate command wrappers:
```bash
cd ~/dev/meridian
uv run python scripts/generate_commands.py
uv run python scripts/generate_commands.py --fix-symlink
```

## License

MIT
