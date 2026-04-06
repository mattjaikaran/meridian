# Meridian

**A unified workflow engine for AI-assisted development.** SQLite-backed state machine with deterministic resume, fresh-context subagents, pluggable board sync, and built-in engineering discipline.

**1055 tests | 39 commands | Zero external dependencies | Python stdlib only**

---

## The Problem

AI coding assistants lose context. Long conversations degrade output quality. Sessions reset and progress vanishes. There's no persistent state, no quality enforcement, and no way to resume exactly where you left off.

Meridian solves this by treating your development workflow as a **state machine** — every phase, plan, decision, and checkpoint is persisted in SQLite. When context resets, you get back to the exact same position with the exact same prompt. Every time.

## Key Features

### Deterministic Resume
All state lives in SQLite. Resume prompts are generated entirely from the database — no LLM prose. Same state = same prompt, guaranteed.

```python
prompt1 = generate_resume_prompt("/path/to/project")
prompt2 = generate_resume_prompt("/path/to/project")
assert prompt1 == prompt2  # Always identical
```

### Fresh-Context Subagents
Each plan executes in a fresh 200k-token subagent. No context rot. No degraded output from long conversations. Plans within the same wave run in parallel.

### Quality Gates
Automated enforcement at every stage:
- **Regression Gate** — prior phase tests run before new execution begins
- **Requirements Coverage** — every requirement must map to a plan
- **Stub Detection** — scans for `TODO`, `FIXME`, `NotImplementedError` after execution
- **Two-Stage Review** — spec compliance first, then code quality
- **Node Repair** — automatic retry, decomposition, or pruning on failure

### Pluggable Board Sync
Connect any kanban board (Linear, Jira, or your own) via the `BoardProvider` protocol. Phase transitions automatically sync ticket status. Works standalone without any board configured.

```bash
export BOARD_PM_SCRIPT=~/tools/my-board-cli.sh  # Point to your CLI
```

See [Board Integration Guide](references/board-integration.md) for details.

### Session Intelligence
- **Structured Handoff** — `/meridian:pause` captures full context as JSON
- **Debug Knowledge Base** — resolved bugs persist and inform future debugging
- **Decision Traceability** — every decision gets a unique ID and audit trail
- **Notes & Seeds** — capture ideas with trigger conditions that surface at the right time

### Remote Agent Dispatch
Optionally dispatch plans to a remote Nero agent for autonomous execution. Nero implements plans, creates branches and PRs, and reports back via HTTP or webhooks.

---

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/mattjaikaran/meridian.git ~/dev/meridian
cd ~/dev/meridian && uv sync

# 2. Register as Claude Code skill
ln -sfn ~/dev/meridian ~/.claude/skills/meridian
export MERIDIAN_HOME=~/dev/meridian  # Add to ~/.zshrc
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py

# 3. Use in any project
/meridian:init                    # Initialize state database
/meridian:plan "Build feature X"  # Create phases and plans
/meridian:execute                 # Run with fresh-context subagents
/meridian:next                    # Auto-advance to next step
```

See the [Getting Started Guide](docs/getting-started.md) for a full walkthrough.

---

## Architecture

```
                    +-------------------------------------------+
                    |         Claude Code + Meridian              |
                    |                                            |
  /meridian:*  ---> |  SKILL.md -----> scripts/*.py              |
  commands          |  routing         (state machine,           |
                    |                   gates, security)          |
                    |                      |                      |
                    |              .meridian/state.db             |
                    |              (SQLite, WAL mode)             |
                    |                      |                      |
                    |    Subagent Dispatch  |                     |
                    |    (200k fresh ctx)   |                     |
                    |    Plan 1 --> Agent 1 | Wave 1              |
                    |    Plan 2 --> Agent 2 |                     |
                    |    Plan 3 --> Agent 3-+                     |
                    +--------------------|-----------------------+
                                         | optional HTTP dispatch
                    +--------------------v-----------------------+
                    |  Nero (remote autonomous executor)          |
                    |  Returns commit SHAs + PR URLs              |
                    +--------------------|-----------------------+
                                         | optional board sync
                    +--------------------v-----------------------+
                    |  Board Provider (Linear, Jira, custom CLI)  |
                    |  Auto-syncs phase status to tickets          |
                    +--------------------------------------------+
```

### Data Model

```
Project
  +-- Milestone (v1.0, v2.0, ...)
        +-- Phase (major work unit with acceptance criteria)
              +-- Plan (one subagent's work, assigned to a wave)
                    +-- Wave (parallel execution group)
```

### State Machines

```
Phase:   planned --> context_gathered --> planned_out --> executing --> verifying --> reviewing --> complete
                                                                                         |
                                                                                      blocked

Plan:    pending --> executing --> complete
                              --> failed --> pending (retry via node repair)
                              --> paused --> executing
         pending --> skipped (pruned)
```

---

## Commands (39)

### Core Workflow

| Command | Description |
|---------|-------------|
| `/meridian:init` | Initialize `.meridian/` and `state.db` in current project |
| `/meridian:plan` | Brainstorm phases, gather context, generate wave-assigned plans |
| `/meridian:execute` | Run plans via fresh subagents with TDD and review |
| `/meridian:next` | Auto-detect state and advance to the next logical step |
| `/meridian:resume` | Deterministic resume from SQLite state |
| `/meridian:status` | Show progress, blockers, and next action |
| `/meridian:ship` | Commit + push + create PR via `gh` CLI |

### Quick Actions

| Command | Description |
|---------|-------------|
| `/meridian:fast` | Inline trivial tasks — no DB records |
| `/meridian:quick` | Lightweight tracked task — no phase overhead |
| `/meridian:do` | Natural language router — maps freeform text to commands |
| `/meridian:note` | Zero-friction idea capture (append, list, promote) |
| `/meridian:seed` | Backlog parking lot with trigger conditions |

### Planning & Discussion

| Command | Description |
|---------|-------------|
| `/meridian:discuss` | Gather phase context through adaptive questioning |
| `/meridian:insert-phase` | Insert a phase mid-milestone without renumbering |
| `/meridian:remove-phase` | Remove a future phase and renumber |
| `/meridian:complete-milestone` | Archive milestone and prepare next version |
| `/meridian:roadmap` | Cross-milestone progress bars and ETAs |

### Quality & Review

| Command | Description |
|---------|-------------|
| `/meridian:review` | Two-stage code review (spec compliance + quality) |
| `/meridian:audit-uat` | Cross-phase verification debt tracking |
| `/meridian:verify-phase` | Nyquist compliance check on validation artifacts |
| `/meridian:validate` | Git state + DB consistency validation |
| `/meridian:debug` | 4-phase systematic debugging with knowledge base |

### Visibility & Metrics

| Command | Description |
|---------|-------------|
| `/meridian:dashboard` | Project health, velocity, stalls, dispatch status |
| `/meridian:history` | Event timeline — all state transitions |
| `/meridian:report` | Session summary with work completed and outcomes |
| `/meridian:profile` | Developer preference profiling from project analysis |

### Session Management

| Command | Description |
|---------|-------------|
| `/meridian:pause` | Structured handoff with full context for rich resume |
| `/meridian:resume` | Restore from HANDOFF.json + DB state |
| `/meridian:checkpoint` | Manual save point with notes |
| `/meridian:pr-branch` | Create clean PR branch filtering internal commits |

### Execution Control

| Command | Description |
|---------|-------------|
| `/meridian:autonomous` | Hands-free execution across remaining phases |
| `/meridian:freeze` | Lock edit scope to prevent unrelated changes |
| `/meridian:learn` | Capture execution patterns as persistent rules |
| `/meridian:retro` | Structured retrospective after milestone completion |
| `/meridian:config` | View and modify workflow configuration |

### Integration

| Command | Description |
|---------|-------------|
| `/meridian:dispatch` | Send plans to Nero for remote autonomous execution |
| `/meridian:scan` | Codebase audit and work discovery |
| `/meridian:template` | Apply pre-built workflow templates |
| `/meridian:migrate` | Move Meridian state between projects |
| `/meridian:revert` | Revert a completed plan's changes |

---

## Typical Workflow

```bash
# 1. Initialize in your project
/meridian:init

# 2. Plan the work
/meridian:plan "Build user authentication with JWT"
# --> Creates phases: DB Models, API Routes, Middleware, Tests
# --> Each phase gets context-gathered plans in parallel waves

# 3. Execute with quality gates
/meridian:execute
# --> Spawns fresh 200k-token subagents per plan
# --> TDD enforced: red -> green -> refactor
# --> Regression gate blocks if prior phases break
# --> Auto-advances state machine on completion

# 4. Monitor progress
/meridian:dashboard          # Health, velocity, ETA
/meridian:next               # What should happen next?

# 5. Handle session boundaries
/meridian:pause              # Save context before stopping
# ... new session ...
/meridian:resume             # Deterministic restore

# 6. Ship it
/meridian:ship               # Commit + push + PR
```

### Quick Tasks (Skip Full Planning)

```bash
/meridian:fast "fix typo in README"                    # Inline, no tracking
/meridian:quick "add error handling to API routes"     # Tracked, no phase
/meridian:do "what's next"                             # Natural language routing
```

### Capturing Ideas

```bash
/meridian:note append "should add caching to API responses"
/meridian:note list
/meridian:note promote N001                            # Convert to task

/meridian:seed plant "rate limiting" --trigger "after_phase:Auth"
# --> Surfaces automatically when Auth phase completes
```

---

## Installation

### Prerequisites

- **Python 3.11+** — `python3 --version`
- **[uv](https://docs.astral.sh/uv/)** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **git** — `git --version`
- **Claude Code** — with skills support

### Install

```bash
# Clone
git clone https://github.com/mattjaikaran/meridian.git ~/dev/meridian
cd ~/dev/meridian

# Install dev dependencies (pytest only — everything else is stdlib)
uv sync

# Register as Claude Code skill
ln -sfn ~/dev/meridian ~/.claude/skills/meridian

# Set MERIDIAN_HOME (add to ~/.zshrc or ~/.bashrc)
export MERIDIAN_HOME=~/dev/meridian

# Generate command wrappers
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py
```

### Verify

```bash
# Should list 39 .md files
ls ~/.claude/commands/meridian/

# Should show 1055 passed
uv run pytest tests/ -q

# In Claude Code, type /meridian: — autocomplete shows all commands
```

### Uninstall

```bash
cd ~/dev/meridian
uv run python scripts/generate_commands.py --uninstall
rm ~/.claude/skills/meridian
```

---

## Board Integration

Meridian syncs phase status to external kanban boards via a pluggable provider system.

### Built-in Providers

| Provider | Description |
|----------|-------------|
| `noop` | Default — Meridian works standalone |
| `cli` | Shells out to any board CLI tool via `BOARD_PM_SCRIPT` env var |

### Using the CLI Provider

```bash
# Point to your board's CLI script
export BOARD_PM_SCRIPT=~/tools/my-board-cli.sh

# Set provider during project init
# board_provider = "cli"
# board_project_id = "YOUR-PROJECT"
```

Your script must support:
```bash
my-board-cli.sh ticket add <project_id> <name> --description <desc>
my-board-cli.sh ticket move <ticket_id> <status>
```

### Writing a Custom Provider

```python
from scripts.board.provider import register_provider

class LinearProvider:
    def create_ticket(self, project_id: str, name: str, description: str = "") -> str | None:
        # Call Linear API, return issue ID
        ...

    def move_ticket(self, ticket_id: str, status: str) -> str | None:
        # Update issue status
        ...

register_provider("linear", LinearProvider)
```

See [Board Integration Guide](references/board-integration.md) for the full protocol.

---

## Quality Gates

### Regression Gate
Before executing a phase, all prior phases' test suites run. If any regress, execution blocks.

### Requirements Coverage
Every phase requirement must map to at least one plan. Gaps trigger warnings.

### Stub Detection
After execution, scans modified files for `TODO`, `FIXME`, `NotImplementedError`, and `pass`-only functions.

### Node Repair
Automatic recovery when plans fail:
1. **RETRY** — re-execute with error context
2. **DECOMPOSE** — split into smaller sub-plans
3. **PRUNE** — skip non-critical plan and continue

### Two-Stage Review
1. **Spec compliance** — does implementation match the plan?
2. **Code quality** — security, performance, conventions

---

## Session Intelligence

### Deterministic Resume
Resume prompts are generated from SQLite — no LLM prose. Same state = same prompt.

### Structured Handoff
`/meridian:pause` creates `HANDOFF.json` with active phase, blockers, recent decisions, modified files, and user notes. `/meridian:resume` consumes it.

### Debug Knowledge Base
Resolved debug sessions are persisted to `debug-kb.md`. Future sessions search for similar symptoms before investigating.

### Decision Traceability
Decisions get unique IDs (`DEC-001`, `DEC-002`, ...) linked to plans. Full audit trail in `DISCUSSION-LOG.md`.

---

## Security

Centralized validation in `scripts/security.py`:

| Function | Purpose |
|----------|---------|
| `validate_path()` | Reject path traversal (`../`) and symlink escapes |
| `safe_json_loads()` | JSON parsing with size limits |
| `validate_field_name()` | SQL-safe identifiers only |
| `sanitize_shell_arg()` | Reject shell metacharacters |

---

## Project Structure

```
meridian/
|-- README.md
|-- LICENSE                          # Apache 2.0
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- SKILL.md                         # Skill entry point (39 commands)
|-- pyproject.toml                   # uv-managed, stdlib only
|
|-- scripts/                         # Python modules (stdlib only)
|   |-- db.py                        # Schema v7, migrations, WAL mode
|   |-- state.py                     # CRUD, transitions, auto-advance
|   |-- resume.py                    # Deterministic resume
|   |-- security.py                  # Path, JSON, field, shell validation
|   |-- gates.py                     # Regression, coverage, stub detection
|   |-- node_repair.py               # RETRY / DECOMPOSE / PRUNE
|   |-- metrics.py                   # Velocity, stalls, forecasts
|   |-- board/                       # Pluggable board sync
|   |   |-- provider.py              # BoardProvider protocol + registry
|   |   |-- cli.py                   # CLI-based provider (env var config)
|   |   +-- sync.py                  # Phase transition sync bridge
|   |-- dispatch.py                  # Nero HTTP dispatch
|   |-- sync.py                      # Bidirectional Nero sync
|   +-- ... (30+ modules)
|
|-- skills/                          # 39 slash command definitions
|   |-- init/SKILL.md
|   |-- plan/SKILL.md
|   |-- execute/SKILL.md
|   +-- ... (39 total)
|
|-- tests/                           # 1055 tests
|   |-- test_state.py
|   |-- test_security.py
|   |-- test_gates.py
|   +-- ... (24 test files)
|
|-- prompts/                         # Subagent prompt templates
|   |-- implementer.md
|   |-- spec-reviewer.md
|   +-- code-quality-reviewer.md
|
|-- references/                      # Architecture documentation
|   |-- state-machine.md             # State transitions + rules
|   |-- discipline-protocols.md      # TDD, debugging, review protocols
|   |-- nero-integration.md          # Remote agent dispatch protocol
|   +-- board-integration.md         # Pluggable board sync protocol
|
+-- docs/                            # User guides and tutorials
    |-- getting-started.md           # Installation + first project
    |-- command-reference.md         # All 39 commands
    |-- architecture.md              # System design + diagrams
    +-- tutorials/
        |-- workflow-walkthrough.md   # End-to-end project tutorial
        |-- board-integration.md      # Setting up board sync
        +-- remote-dispatch.md        # Nero setup guide
```

---

## Schema

Current version: **v7** (with automatic migrations from any prior version)

| Table | Purpose |
|-------|---------|
| `project` | Project metadata, repo path, tech stack, board config |
| `milestone` | Versioned releases with status lifecycle |
| `phase` | Work units with sequence, priority, acceptance criteria |
| `plan` | Subagent tasks with wave assignment and TDD flag |
| `checkpoint` | Save points with git state and blockers |
| `decision` | Decisions with unique IDs and rationale |
| `plan_decision` | Links plans to informing decisions |
| `nero_dispatch` | Remote dispatch tracking (task ID, status, PR URL) |
| `quick_task` | Lightweight tasks without phase overhead |
| `state_event` | Audit log for all state transitions |
| `settings` | Key-value project configuration |
| `review` | Code review records |
| `learning` | Execution patterns captured as persistent rules |

---

## Stack

- **Python 3.11+** — stdlib only (`sqlite3`, `json`, `pathlib`, `subprocess`, `re`, `hashlib`)
- **SQLite** — WAL mode, foreign keys, busy_timeout, automatic backups
- **Claude Code Skills** — SKILL.md routing with auto-generated command wrappers
- **pytest** — 1055 tests (dev dependency only)

---

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Installation and first project walkthrough |
| [Command Reference](docs/command-reference.md) | All 39 commands with usage and examples |
| [Architecture Guide](docs/architecture.md) | System design, data model, state machines |
| [Workflow Tutorial](docs/tutorials/workflow-walkthrough.md) | End-to-end project from init to ship |
| [Board Integration](docs/tutorials/board-integration.md) | Setting up kanban board sync |
| [Remote Dispatch](docs/tutorials/remote-dispatch.md) | Nero autonomous agent setup |
| [State Machine Reference](references/state-machine.md) | Phase and plan lifecycle rules |
| [Discipline Protocols](references/discipline-protocols.md) | TDD, debugging, review enforcement |
| [Board Protocol](references/board-integration.md) | BoardProvider API and custom providers |
| [Nero Protocol](references/nero-integration.md) | HTTP dispatch and webhook integration |

---

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
echo $MERIDIAN_HOME  # Should print your meridian clone path
export MERIDIAN_HOME=~/dev/meridian
```

### State seems corrupted
Automatic backups exist before every migration in `.meridian/backups/`:
```bash
cp .meridian/backups/state-<timestamp>.db .meridian/state.db
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and contribution guidelines.

## License

Apache License 2.0 — see [LICENSE](LICENSE) for details.
