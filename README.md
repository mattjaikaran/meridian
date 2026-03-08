# Meridian

Unified workflow engine for Claude Code. SQLite-backed state machine with deterministic resume, fresh-context subagents, and engineering discipline protocols.

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
/meridian:checkpoint    # Save state before context limit
  ... new session ...
/meridian:resume        # Deterministic restore — exact same position
/meridian:execute       # Continue where we left off
/meridian:ship          # Commit, push, PR
```

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
│   ├── db.py                            # Schema init + migrations
│   ├── state.py                         # CRUD + transitions + next-action
│   ├── resume.py                        # Deterministic resume prompt generator
│   ├── export.py                        # SQLite → JSON export
│   ├── dispatch.py                      # Nero HTTP dispatch client
│   ├── axis_sync.py                     # Axis PM ticket sync
│   └── context_window.py               # Token estimation + checkpoint triggers
├── prompts/
│   ├── implementer.md                   # Subagent: implement + TDD
│   ├── spec-reviewer.md                 # Subagent: spec compliance check
│   ├── code-quality-reviewer.md         # Subagent: code quality review
│   ├── context-gatherer.md              # Subagent: deep project analysis
│   └── resume-template.md              # Resume prompt structure reference
├── references/
│   ├── state-machine.md                 # State transitions + rules
│   ├── discipline-protocols.md          # TDD, debugging, verification, review
│   ├── nero-integration.md              # Dispatch protocol + state sharing
│   └── axis-integration.md             # PM sync protocol
├── skills/                              # Individual slash command SKILL.md files
│   ├── init/SKILL.md
│   ├── plan/SKILL.md
│   ├── execute/SKILL.md
│   ├── resume/SKILL.md
│   ├── status/SKILL.md
│   ├── dispatch/SKILL.md
│   ├── review/SKILL.md
│   ├── ship/SKILL.md
│   ├── debug/SKILL.md
│   ├── quick/SKILL.md
│   └── checkpoint/SKILL.md
└── tests/
    ├── test_state.py                    # 33 tests — CRUD, transitions, next-action
    └── test_resume.py                   # 9 tests — deterministic prompt generation
```

## Setup

```bash
# Install (symlink to Claude Code skills)
ln -sfn ~/dev/meridian ~/.claude/skills/meridian

# Run tests
cd ~/dev/meridian
uv run pytest tests/ -v
```

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

## License

MIT
