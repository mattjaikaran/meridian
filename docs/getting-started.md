# Getting Started with Meridian

This guide walks you through installing Meridian and using it on your first project.

## Prerequisites

- **Python 3.11+** — Check with `python3 --version`
- **[uv](https://docs.astral.sh/uv/)** — Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **git** — Check with `git --version`
- **Claude Code** — With skills support enabled

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/material-endeavors/meridian.git ~/dev/meridian
cd ~/dev/meridian
```

### 2. Install Dev Dependencies

```bash
uv sync
```

This installs pytest (the only dependency — everything else is stdlib).

### 3. Register as Claude Code Skill

```bash
# Create symlink so Claude Code can find the skill
ln -sfn ~/dev/meridian ~/.claude/skills/meridian

# Generate slash command wrappers
uv run python scripts/generate_commands.py --fix-symlink
uv run python scripts/generate_commands.py
```

### 4. Verify

```bash
# Should list 29 .md files
ls ~/.claude/commands/meridian/

# Should show 740 passed
uv run pytest tests/ -q
```

Open Claude Code and type `/meridian:` — you should see all 29 commands in autocomplete.

## Your First Project

### Step 1: Initialize

Navigate to any project and run:

```
/meridian:init
```

This creates:
- `.meridian/state.db` — SQLite database (source of truth)
- `.meridian/` entry in `.gitignore`
- Project and milestone records in the database

### Step 2: Plan

Tell Meridian what you want to build:

```
/meridian:plan "Add user authentication with JWT"
```

Meridian will:
1. **Brainstorm** phases (e.g., "Database Models", "API Routes", "Middleware")
2. **Gather context** — analyze your codebase for each phase
3. **Generate plans** — specific tasks grouped into parallel waves

### Step 3: Execute

Run the plans with fresh-context subagents:

```
/meridian:execute
```

For each plan, Meridian:
1. Spawns a subagent with 200k fresh tokens
2. Enforces TDD (red → green → refactor)
3. Commits atomically after each plan
4. Runs regression tests from prior phases
5. Auto-advances the state machine

### Step 4: Check Progress

```
/meridian:dashboard    # Health, velocity, stalls
/meridian:status       # Current state, blockers, next action
/meridian:next         # Auto-detect and advance
```

### Step 5: Handle Context Resets

When your Claude Code session resets (context limit, new window):

```
/meridian:resume
```

This generates a deterministic prompt from SQLite — you're back exactly where you left off.

### Step 6: Ship

```
/meridian:ship         # Commit + push + PR
```

Or create a clean branch without planning artifacts:

```
/meridian:pr-branch    # Filters out .planning/ and .meridian/ commits
```

## Quick Tasks

Not everything needs full planning. Use these for lightweight work:

```
/meridian:fast "fix typo in login.py"     # Inline, no DB records
/meridian:quick "add error handling"       # Tracked but no phase
```

## Capturing Ideas

Don't lose ideas between sessions:

```
/meridian:note append "should add caching to API responses"
/meridian:note list                        # See all notes
/meridian:note promote N001               # Convert to task

/meridian:seed plant "rate limiting" --trigger "after phase Auth"
```

Seeds automatically surface when their trigger condition is met.

## Pausing and Resuming

Before stepping away:

```
/meridian:pause        # Creates HANDOFF.json with full context
```

Next session:

```
/meridian:resume       # Reads HANDOFF.json + DB for rich restoration
```

## What's Next

- Read the [Command Reference](command-reference.md) for all 29 commands
- Read the [Architecture Guide](architecture.md) for how it all fits together
- Check `/meridian:dashboard` for project health metrics
