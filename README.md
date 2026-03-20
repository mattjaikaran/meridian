# Meridian

Unified workflow engine for Claude Code. SQLite-backed state machine with deterministic resume, fresh-context subagents, and engineering discipline protocols.

**740 tests | 29 commands | Python stdlib only | Schema v4**

## Quick Start

```bash
# 1. Clone
git clone https://github.com/material-endeavors/meridian.git ~/dev/meridian

# 2. Install as Claude Code skill
ln -sfn ~/dev/meridian ~/.claude/skills/meridian
cd ~/dev/meridian && uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py

# 3. Use in any project
/meridian:init              # Initialize
/meridian:plan "Build X"    # Plan phases + plans
/meridian:execute           # Run with fresh-context subagents
/meridian:next              # Auto-advance to next step
```

## Why Meridian

| Problem | Solution |
|---------|----------|
| Context rot degrades output as conversation grows | Fresh 200k-token subagents per plan |
| Resume after context reset loses progress | SQLite-backed deterministic resume — same state = same prompt |
| No workflow state persistence | All state in `.meridian/state.db` per project |
| Manual status tracking | Auto-advancing state machine with computed next-action |
| No quality enforcement | TDD, regression gates, stub detection, 2-stage review embedded |
| Ideas get lost between sessions | Notes, seeds, debug knowledge base persist across sessions |

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │         Claude Code + Meridian           │
                    │                                          │
  /meridian:*  ───> │  ┌──────────┐    ┌──────────────────┐   │
  commands          │  │ SKILL.md │───>│ scripts/*.py      │   │
                    │  │ routing  │    │ (state machine,   │   │
                    │  └──────────┘    │  gates, security)  │   │
                    │                  └────────┬───────────┘   │
                    │                           │               │
                    │              ┌─────────────┼───────────┐  │
                    │              │  .meridian/state.db      │  │
                    │              │  (SQLite, WAL mode)      │  │
                    │              └─────────────┼───────────┘  │
                    │                           │               │
                    │    ┌──────────────────────┼────────┐     │
                    │    │ Subagent Dispatch     │        │     │
                    │    │ (200k fresh context)  │        │     │
                    │    │ Plan 1 ──> Agent 1    │        │     │
                    │    │ Plan 2 ──> Agent 2    │ Wave 1 │     │
                    │    │ Plan 3 ──> Agent 3 ───┘        │     │
                    │    └────────────────────────────────┘     │
                    └─────────────────────┬────────────────────┘
                                          │ HTTP dispatch
                    ┌─────────────────────▼────────────────────┐
                    │  Nero (optional autonomous executor)      │
                    │  Reads meridian-state.json                │
                    │  Returns commit SHAs + PR URLs            │
                    └──────────────────────────────────────────┘
```

### Data Model

```
Project
  └── Milestone (v1.0, v2.0, ...)
        └── Phase (major work unit with acceptance criteria)
              └── Plan (one subagent's work, assigned to a wave)
                    └── Wave (parallel execution group)
```

### State Machines

```
Phase:   planned → context_gathered → planned_out → executing → verifying → reviewing → complete
                                                                                ↕
                                                                             blocked

Plan:    pending → executing → complete
                            → failed → pending (retry via node repair)
                            → paused → executing
         pending → skipped (pruned)
```

## Commands (29)

### Core Workflow

| Command | Purpose |
|---------|---------|
| `/meridian:init` | Initialize `.meridian/` and `state.db` in current project |
| `/meridian:plan` | Brainstorm phases, gather context, generate plans with waves |
| `/meridian:execute` | Run plans via fresh subagents — TDD enforced, 2-stage review |
| `/meridian:next` | Auto-detect workflow state and advance to next logical step |
| `/meridian:resume` | Deterministic resume from SQLite — same state = same prompt |
| `/meridian:status` | Show progress, phase state, blockers, next action |
| `/meridian:ship` | Commit + push + create PR via `gh` CLI |

### Quick Actions

| Command | Purpose |
|---------|---------|
| `/meridian:fast` | Inline trivial tasks — skip planning for one-liners |
| `/meridian:quick` | Lightweight task — no phase overhead, still tracked |
| `/meridian:do` | Freeform text router — natural language to right command |
| `/meridian:note` | Zero-friction idea capture — append, list, promote to task |
| `/meridian:seed` | Backlog parking lot — ideas with trigger conditions |

### Quality & Review

| Command | Purpose |
|---------|---------|
| `/meridian:review` | Two-stage code review — spec compliance then quality |
| `/meridian:audit-uat` | Cross-phase verification debt tracking |
| `/meridian:verify-phase` | Nyquist compliance check on VALIDATION.md |
| `/meridian:validate` | Git state validation — working tree + DB consistency |
| `/meridian:debug` | 4-phase systematic debugging with knowledge base |

### Visibility & Metrics

| Command | Purpose |
|---------|---------|
| `/meridian:dashboard` | Project health, velocity, stalls, Nero dispatches |
| `/meridian:roadmap` | Cross-milestone progress bars and ETAs |
| `/meridian:history` | Event timeline — state transitions and activity log |
| `/meridian:profile` | Developer preference profiling from project analysis |

### Session Management

| Command | Purpose |
|---------|---------|
| `/meridian:pause` | Structured handoff — HANDOFF.json for rich resume |
| `/meridian:checkpoint` | Manual save point with notes |
| `/meridian:pr-branch` | Create clean branch filtering `.planning/` commits |

### Advanced

| Command | Purpose |
|---------|---------|
| `/meridian:dispatch` | Send plans to Nero for autonomous execution |
| `/meridian:scan` | Codebase audit and work discovery |
| `/meridian:template` | Apply pre-built workflow templates |
| `/meridian:migrate` | Move Meridian state between projects |
| `/meridian:revert` | Revert a completed plan's changes |

## Typical Workflow

```
/meridian:init                    # 1. Initialize in project
/meridian:plan "Build user auth"  # 2. Create phases, gather context, generate plans
/meridian:execute                 # 3. Run plans (subagents, TDD, review)
/meridian:next                    # 4. Auto-advance to next step
/meridian:dashboard               # 5. Check health + velocity
/meridian:pause                   # 6. Save structured handoff before stopping

    ... new Claude Code session ...

/meridian:resume                  # 7. Deterministic restore — exact same position
/meridian:execute                 # 8. Continue where you left off
/meridian:ship                    # 9. Commit, push, PR
```

### Quick Tasks (Skip Full Planning)

```
/meridian:fast "fix typo in README"          # Inline, no DB records
/meridian:note append "add caching later"    # Capture idea for later
/meridian:seed plant "rate limiting" --trigger "after phase Auth"  # Future work
```

## Installation

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- git
- Claude Code with skills support

### Step-by-Step

```bash
# 1. Clone the repository
git clone https://github.com/material-endeavors/meridian.git ~/dev/meridian

# 2. Create symlink to Claude Code skills directory
ln -sfn ~/dev/meridian ~/.claude/skills/meridian

# 3. Install dependencies (dev only — pytest)
cd ~/dev/meridian
uv sync

# 4. Fix symlink if needed and generate command wrappers
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py
```

### Verify Installation

```bash
# Check commands are registered (should list 29 .md files)
ls ~/.claude/commands/meridian/

# Run tests (should show 740 passed)
cd ~/dev/meridian && uv run pytest tests/ -v

# In Claude Code, type /meridian: — autocomplete should show all commands
```

### Uninstall

```bash
cd ~/dev/meridian
uv run python scripts/generate_commands.py --uninstall
rm ~/.claude/skills/meridian
```

## Quality Gates

Meridian enforces quality at multiple stages:

### Regression Gate
Before executing a phase, prior phases' test suites run automatically. If any regress, execution blocks.

### Requirements Coverage Gate
Before execution, verifies every phase requirement has at least one plan covering it.

### Stub Detection
After plan execution, scans modified files for `TODO`, `FIXME`, `NotImplementedError`, and `pass`-only functions.

### Node Repair
When a plan fails, auto-recovery kicks in:
1. **RETRY** — re-execute with error context (first attempt)
2. **DECOMPOSE** — split into smaller sub-plans (if retry fails)
3. **PRUNE** — skip non-critical plan and continue (budget exhausted)

Configurable repair budget (default: 2 attempts per plan).

## Session Intelligence

### Deterministic Resume

Resume prompts are generated entirely from SQLite — no LLM prose. Same state = same prompt.

```python
from scripts.resume import generate_resume_prompt
prompt1 = generate_resume_prompt("/path/to/project")
prompt2 = generate_resume_prompt("/path/to/project")
assert prompt1 == prompt2  # Guaranteed identical
```

### Structured Handoff

`/meridian:pause` creates `.meridian/HANDOFF.json` with:
- Active phase/plan, blockers, recent decisions
- Modified files (git diff), next action
- User notes (freeform context)

`/meridian:resume` consumes it for richer restoration than DB-only resume.

### Debug Knowledge Base

Resolved debug sessions are appended to `.meridian/debug-kb.md`. Before starting a new debug session, the KB is searched for similar symptoms — surfacing prior resolutions as context.

### Decision Traceability

Every decision gets a unique ID (`DEC-001`, `DEC-002`, ...) and can be linked to plans. Discussion audit trail in `.meridian/DISCUSSION-LOG.md` captures the reasoning behind each decision.

## Security

Centralized validation in `scripts/security.py`:

| Function | Purpose |
|----------|---------|
| `validate_path()` | Reject path traversal (`../`) and symlink escapes |
| `safe_json_loads()` | JSON parsing with size limits, returns `None` on failure |
| `validate_field_name()` | SQL-safe identifiers only (`[a-zA-Z_][a-zA-Z0-9_]*`) |
| `sanitize_shell_arg()` | Reject shell metacharacters (`;`, `\|`, `&`, `$`) |

## PM Visibility

### Dashboard (`/meridian:dashboard`)

```
# Project Dashboard — MyApp
## Health: ON TRACK

Milestone: v1.0 (active) — 67% complete, ETA Mar 9
Phase 2/3: Features [executing] — 3/5 plans done
Velocity: 2.4 plans/day (7d avg)

### Stalls
- Plan "Add auth" stuck in executing for 6h

### Next Action
→ Execute plan: "Add API routes" (wave 2)
```

### Metrics API

```python
from scripts.metrics import (
    compute_velocity,       # plans/day over 7-day rolling window
    compute_cycle_times,    # avg hours per phase and plan
    detect_stalls,          # plans/phases stuck beyond threshold
    forecast_completion,    # ETA based on velocity + remaining work
    compute_progress,       # completion % at all levels
)
```

## Project Structure

```
meridian/
├── README.md
├── CHANGELOG.md
├── SKILL.md                          # Skill entry point (29 commands listed)
├── pyproject.toml                    # uv-managed, stdlib only
│
├── scripts/                          # 24 Python modules
│   ├── db.py                         # Schema v4, migrations, WAL mode
│   ├── state.py                      # CRUD, transitions, auto-advance, decisions
│   ├── resume.py                     # Deterministic resume + handoff integration
│   ├── security.py                   # Path, JSON, field, shell validation
│   ├── gates.py                      # Regression, coverage, stub detection
│   ├── audit.py                      # UAT verification debt tracking
│   ├── fast.py                       # Inline fast task execution
│   ├── router.py                     # Freeform text → command routing
│   ├── notes.py                      # Note capture (append/list/promote)
│   ├── next_action.py                # Auto-advance workflow detection
│   ├── handoff.py                    # Structured HANDOFF.json
│   ├── debug_kb.py                   # Persistent debug knowledge base
│   ├── discussion.py                 # Discussion audit trail
│   ├── backlog.py                    # Seed/backlog management
│   ├── profiler.py                   # Developer preference profiling
│   ├── node_repair.py                # RETRY/DECOMPOSE/PRUNE operators
│   ├── executor_modes.py             # Interactive executor mode
│   ├── mcp_discovery.py              # MCP tool discovery + relevance
│   ├── context_awareness.py          # Context window sizing
│   ├── pr_branch.py                  # Clean PR branch creation
│   ├── roadmap_sync.py               # Auto-sync ROADMAP.md from DB
│   ├── nyquist.py                    # VALIDATION.md engine
│   ├── metrics.py                    # Velocity, stalls, forecasts
│   ├── export.py                     # SQLite → JSON export
│   ├── dispatch.py                   # Nero HTTP dispatch
│   ├── sync.py                       # Bidirectional Nero sync
│   ├── axis_sync.py                  # PM ticket sync
│   ├── context_window.py             # Token estimation
│   ├── generate_commands.py          # Command wrapper generator
│   └── ...
│
├── skills/                           # 29 slash command definitions
│   ├── init/SKILL.md
│   ├── plan/SKILL.md
│   ├── execute/SKILL.md
│   ├── fast/SKILL.md
│   ├── do/SKILL.md
│   ├── note/SKILL.md
│   ├── next/SKILL.md
│   ├── seed/SKILL.md
│   ├── profile/SKILL.md
│   ├── pause/SKILL.md
│   ├── audit-uat/SKILL.md
│   ├── pr-branch/SKILL.md
│   └── ... (29 total)
│
├── tests/                            # 740 tests
│   ├── test_state.py                 # 94 tests
│   ├── test_security.py              # 48 tests
│   ├── test_gates.py                 # 25 tests
│   ├── test_backlog.py               # 31 tests
│   ├── test_context_awareness.py     # 28 tests
│   └── ... (24 test files)
│
├── prompts/                          # Subagent prompt templates
│   ├── implementer.md
│   ├── spec-reviewer.md
│   ├── code-quality-reviewer.md
│   └── context-gatherer.md
│
├── references/                       # Architecture docs
│   ├── state-machine.md
│   ├── discipline-protocols.md
│   ├── nero-integration.md
│   └── axis-integration.md
│
└── docs/                             # User guides
    ├── getting-started.md
    ├── command-reference.md
    └── architecture.md
```

## Schema

Current schema version: **4**

| Table | Purpose |
|-------|---------|
| `project` | Project metadata — name, repo, tech stack, Nero endpoint |
| `milestone` | Versioned releases with status lifecycle |
| `phase` | Major work units — sequence, priority, acceptance criteria |
| `plan` | Subagent work items — wave, TDD flag, executor type |
| `checkpoint` | Save points — git state, decisions, blockers |
| `decision` | Decisions with unique IDs (DEC-NNN) and rationale |
| `plan_decision` | Junction table linking plans to decisions |
| `nero_dispatch` | Async dispatch tracking — task ID, status, PR URL |
| `quick_task` | Lightweight tasks without phase overhead |
| `state_event` | Event log for all state transitions |
| `settings` | Key-value configuration |
| `review` | Code review records |

Migration history: v1 (initial) → v2 (priority) → v3 (settings, review) → v4 (decision IDs, plan_decision)

## Stack

- **Python 3.11+** — stdlib only (`sqlite3`, `json`, `pathlib`, `subprocess`, `re`, `hashlib`)
- **SQLite** — WAL mode, foreign keys, busy_timeout, automatic backups
- **Claude Code Skills** — SKILL.md routing with generated `.md` wrappers
- **pytest** — 740 tests, dev dependency only

## Troubleshooting

### Commands not showing in Claude Code
```bash
cd ~/dev/meridian
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py
```

### "Database is locked"
Meridian uses WAL mode with 5s busy_timeout and exponential backoff retry. If persistent:
```bash
lsof .meridian/state.db
```

### "Module not found" errors
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "from scripts.db import init; print('OK')"
```

### State seems corrupted
Automatic backups before migrations in `.meridian/backups/`:
```bash
cp .meridian/backups/state-<timestamp>.db .meridian/state.db
```

## License

MIT
