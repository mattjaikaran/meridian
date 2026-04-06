# Tutorial: End-to-End Workflow

This tutorial walks through a complete project lifecycle — from initialization to shipping a PR — using a real-world example: adding user authentication to a web application.

## Prerequisites

- Meridian installed and registered as a Claude Code skill ([Getting Started](../getting-started.md))
- A project you want to work on (any git repository)

## Step 1: Initialize Meridian

Navigate to your project directory and initialize:

```
/meridian:init
```

Meridian will:
1. Create `.meridian/state.db` (SQLite database)
2. Add `.meridian/` to your `.gitignore`
3. Scan your project to detect tech stack, structure, and conventions
4. Create a project record and first milestone

You'll see output like:

```
## Meridian Initialized

Project: my-app
Tech stack: Python, FastAPI, PostgreSQL
Milestone: v1.0 (active)
State: .meridian/state.db
```

## Step 2: Plan the Work

Tell Meridian what you want to build:

```
/meridian:plan "Add user authentication with JWT tokens"
```

Meridian's planning pipeline:

1. **Phase brainstorm** — breaks the work into logical phases:
   - Phase 1: Database Models (User table, migrations)
   - Phase 2: Auth Service (JWT generation, password hashing)
   - Phase 3: API Routes (login, register, refresh)
   - Phase 4: Middleware (token validation, route protection)

2. **Context gathering** — for each phase, a subagent analyzes your codebase:
   - Existing models and DB patterns
   - Current route structure
   - Testing conventions
   - Dependencies and config

3. **Plan generation** — specific tasks grouped into parallel waves:
   - Phase 1, Wave 1: `Create User model` + `Add migration`
   - Phase 1, Wave 2: `Add user fixtures` (depends on wave 1)
   - Phase 2, Wave 1: `JWT service` + `Password hasher`
   - etc.

Each plan includes: files to create/modify, test strategy, acceptance criteria.

## Step 3: Review Before Executing

Check what Meridian planned:

```
/meridian:status
```

```
## Project: my-app
Milestone: v1.0 (active) — 0% complete

Phase 1/4: Database Models [planned_out]
  Plan 1.1: Create User model (wave 1) [pending]
  Plan 1.2: Add migration (wave 1) [pending]
  Plan 1.3: User fixtures (wave 2) [pending]

Phase 2/4: Auth Service [planned_out]
  ...

Next action: Execute Phase 1
```

If you want to discuss or adjust a phase before executing:

```
/meridian:discuss --phase 1
```

Meridian will ask targeted questions about your preferences (ORM choice, naming conventions, etc.) and update the plans accordingly.

## Step 4: Execute

```
/meridian:execute
```

For each plan, Meridian:

1. **Runs regression gate** — executes prior phases' tests (skipped for Phase 1)
2. **Checks requirements coverage** — every requirement maps to a plan
3. **Spawns a scoped subagent** (only the context it needs) with:
   - Plan details and acceptance criteria
   - Codebase context gathered in Step 2
   - Engineering discipline protocols (TDD enforced)
4. **Subagent executes** — writes tests first, then implementation
5. **Commits atomically** — one commit per plan
6. **Detects stubs** — scans for TODO/FIXME/NotImplementedError
7. **Auto-advances** �� when all wave 1 plans complete, starts wave 2

Plans in the same wave run in parallel. Different waves run sequentially.

## Step 5: Monitor Progress

```
/meridian:dashboard
```

```
## Project Dashboard — my-app
Health: ON TRACK

Milestone: v1.0 (active) — 25% complete, ETA Mar 15
Phase 1/4: Database Models [executing] — 2/3 plans done
Velocity: 3.1 plans/day (7d avg)

Next action: Execute plan "User fixtures" (wave 2)
```

Or use `/meridian:next` to auto-detect and advance:

```
/meridian:next
```

## Step 6: Handle Context Resets

When your Claude Code session resets (context limit, new window, etc.):

```
/meridian:resume
```

Meridian generates a deterministic resume prompt from SQLite:
- Active phase and plan
- What's been completed
- Current blockers
- Recent decisions
- Next action

The resume prompt is identical every time for the same database state.

### For Planned Stops

Before stepping away, create a structured handoff:

```
/meridian:pause --notes "Was working on the JWT refresh logic, need to handle token rotation"
```

This creates `HANDOFF.json` with full context. When you resume, Meridian reads both the handoff and the database for richer restoration.

## Step 7: Handle Failures

If a plan fails during execution, Meridian's node repair kicks in:

1. **RETRY** — re-executes with the error context injected
2. **DECOMPOSE** — splits into smaller sub-plans (if retry fails)
3. **PRUNE** — skips non-critical plans (budget exhausted)

For harder bugs, use systematic debugging:

```
/meridian:debug
```

This runs a 4-phase investigation (investigate, pattern match, hypothesize, implement) and persists the resolution to the debug knowledge base for future reference.

## Step 8: Ship

When all phases are complete:

```
/meridian:ship
```

This commits, pushes, and creates a PR. For a cleaner PR without internal commits:

```
/meridian:pr-branch auth-feature
```

Creates a `pr/auth-feature` branch with only code-relevant commits.

## Step 9: Retrospective

After shipping:

```
/meridian:retro
```

Review what went well, what didn't, and capture learnings as persistent rules via `/meridian:learn`.

---

## Quick Reference

| I want to... | Command |
|---------------|---------|
| Start a new project | `/meridian:init` |
| Plan work | `/meridian:plan "description"` |
| Execute plans | `/meridian:execute` |
| See what's next | `/meridian:next` |
| Check health | `/meridian:dashboard` |
| Resume after reset | `/meridian:resume` |
| Save before stopping | `/meridian:pause` |
| Fix a bug | `/meridian:debug` |
| Ship the code | `/meridian:ship` |
| Capture an idea | `/meridian:note append "idea"` |
| Quick one-liner | `/meridian:fast "fix typo"` |

---

## Next Steps

- [Command Reference](../command-reference.md) — all 39 commands
- [Board Integration Tutorial](board-integration.md) — sync with your kanban board
- [Remote Dispatch Tutorial](remote-dispatch.md) — set up remote agent dispatch
- [Architecture Guide](../architecture.md) — how it all works under the hood
