# Command Reference

All 39 `/meridian:*` commands organized by category.

---

## Core Workflow

### `/meridian:init`
Initialize Meridian in the current project.

Creates `.meridian/state.db`, gathers project context (tech stack, repo structure), and creates the first milestone.

```
/meridian:init
```

**Creates:** `.meridian/` directory with `state.db`

---

### `/meridian:plan`
Planning pipeline — brainstorm phases, gather context, generate plans.

```
/meridian:plan "Build user authentication"
/meridian:plan --phase 3              # Plan a specific phase
```

**Flow:** Brainstorm phases -> Dispatch context-gatherer subagents -> Generate wave-assigned plans

---

### `/meridian:execute`
Run plans via fresh-context subagents with TDD enforcement and 2-stage review.

```
/meridian:execute                     # Execute next pending work
/meridian:execute --phase 2           # Execute specific phase
/meridian:execute --interactive       # Pause after each plan for review
/meridian:execute --skip-regression   # Skip regression gate (emergency)
```

**Quality gates run automatically:**
1. Regression gate (prior phase tests)
2. Requirements coverage check
3. Post-execution stub detection
4. Auto-advancement on completion

---

### `/meridian:next`
Auto-detect workflow state and advance to the next logical step.

```
/meridian:next
```

**Maps state to action:**
- No project -> suggests `/meridian:init`
- Active milestone, no phases -> suggests `/meridian:plan`
- Phases planned -> starts `/meridian:execute`
- All complete -> suggests closing milestone

---

### `/meridian:resume`
Deterministic resume from SQLite state. Same state = same prompt, always.

```
/meridian:resume
```

**Incorporates:** HANDOFF.json (if exists from `/meridian:pause`), active phase/plan, blockers, recent decisions, git state.

---

### `/meridian:status`
Show current project status — progress, phase state, blockers, next action.

```
/meridian:status
```

---

### `/meridian:ship`
Commit, push, and create a PR via `gh` CLI.

```
/meridian:ship
```

---

## Quick Actions

### `/meridian:fast`
Execute a trivial task inline without creating DB records.

```
/meridian:fast "fix typo in README"
/meridian:fast "add .env to gitignore"
```

**Complexity check:** If the task looks non-trivial (3+ files, keywords like "refactor"), warns and suggests `/meridian:quick` or `/meridian:plan`.

---

### `/meridian:quick`
Lightweight task — no phase overhead, still tracked in the DB.

```
/meridian:quick "add error handling to API routes"
```

---

### `/meridian:do`
Freeform text router — routes natural language to the right command.

```
/meridian:do "check what's next"          # -> /meridian:next
/meridian:do "show me the dashboard"      # -> /meridian:dashboard
/meridian:do "add a note about caching"   # -> /meridian:note
```

If ambiguous, shows top 3 candidates and asks you to pick.

---

### `/meridian:note`
Zero-friction idea capture with subcommands.

```
/meridian:note append "consider adding rate limiting"
/meridian:note list
/meridian:note promote N001              # Convert note to task
```

**Storage:** `.meridian/notes.md`

---

### `/meridian:seed`
Backlog parking lot — ideas with trigger conditions that surface automatically.

```
/meridian:seed plant "add caching layer" --trigger "after_phase:Auth"
/meridian:seed list
/meridian:seed promote S001              # Convert to phase
/meridian:seed dismiss S002              # Archive as not needed
```

**Trigger types:**
- `after_phase:<name>` — surface when phase completes
- `after_milestone:<name>` — surface at milestone boundary
- `manual` — only surfaces when listed

---

## Planning & Discussion

### `/meridian:discuss`
Gather phase context through adaptive questioning before planning.

```
/meridian:discuss --phase 1
/meridian:discuss --auto               # Skip questions, use defaults
/meridian:discuss --chain              # Discuss then auto plan+execute
/meridian:discuss --power              # Bulk questions to file-based UI
```

---

### `/meridian:insert-phase`
Insert a phase mid-milestone using decimal numbering (e.g., 2.1 between 2 and 3).

```
/meridian:insert-phase "Emergency hotfix" --after 2
```

---

### `/meridian:remove-phase`
Remove a future phase and renumber subsequent phases.

```
/meridian:remove-phase 5
```

---

### `/meridian:complete-milestone`
Archive a completed milestone and prepare for the next version.

```
/meridian:complete-milestone
```

---

### `/meridian:roadmap`
Cross-milestone roadmap with progress bars and ETAs.

```
/meridian:roadmap
```

---

## Quality & Review

### `/meridian:review`
Two-stage code review.

```
/meridian:review
```

**Stage 1 (Spec):** Does implementation match plans? Are acceptance criteria met?
**Stage 2 (Quality):** Code cleanliness, security, performance, conventions.

---

### `/meridian:audit-uat`
Cross-phase verification debt tracking.

```
/meridian:audit-uat
```

Scans all phases for unchecked sign-off items, pending human verification, and outstanding UAT.

---

### `/meridian:verify-phase`
Nyquist compliance check — verify VALIDATION.md frontmatter is accurate.

```
/meridian:verify-phase 3
```

---

### `/meridian:validate`
Git state validation — verify working tree and DB consistency.

```
/meridian:validate
```

---

### `/meridian:debug`
4-phase systematic debugging with persistent knowledge base.

```
/meridian:debug
```

**Phases:** Investigation -> Pattern -> Hypothesis -> Implementation

Resolved sessions are appended to `.meridian/debug-kb.md`. Future debug sessions search the KB for similar symptoms.

---

## Visibility & Metrics

### `/meridian:dashboard`
Project health dashboard with velocity, stalls, and dispatch status.

```
/meridian:dashboard
/meridian:dashboard --html             # Standalone HTML report
```

**Health levels:** ON TRACK -> AT RISK -> STALLED

---

### `/meridian:history`
Event timeline — all state transitions and activity log.

```
/meridian:history
/meridian:history --phase 2            # Filter by phase
```

---

### `/meridian:report`
Session summary with work completed, outcomes, and token usage.

```
/meridian:report
```

---

### `/meridian:profile`
Developer preference profiling from project analysis.

```
/meridian:profile
/meridian:profile --refresh            # Re-analyze
```

Generates `.meridian/USER-PROFILE.md` with patterns, tech choices, and commit style.

---

## Session Management

### `/meridian:pause`
Create structured handoff for rich context restoration.

```
/meridian:pause
/meridian:pause --notes "Was debugging the auth middleware timeout"
```

**Creates:** `.meridian/HANDOFF.json` — consumed by `/meridian:resume`.

---

### `/meridian:checkpoint`
Manual save point with notes.

```
/meridian:checkpoint
/meridian:checkpoint --notes "Before major refactor"
```

---

### `/meridian:pr-branch`
Create a clean PR branch filtering `.planning/` and `.meridian/` commits.

```
/meridian:pr-branch auth-feature
```

**Creates:** `pr/auth-feature` branch with only code-relevant commits.

---

## Execution Control

### `/meridian:autonomous`
Hands-free execution across all remaining phases. Runs discuss -> plan -> execute per phase automatically.

```
/meridian:autonomous
```

---

### `/meridian:freeze`
Lock edit scope to prevent unrelated file changes during focused work.

```
/meridian:freeze
```

---

### `/meridian:learn`
Capture execution patterns as persistent rules. Auto-suggested from failures and review rejections.

```
/meridian:learn
```

Rules are injected into future subagent prompts.

---

### `/meridian:retro`
Structured retrospective after milestone completion.

```
/meridian:retro
```

---

### `/meridian:config`
View and modify workflow configuration.

```
/meridian:config
/meridian:config set repair_budget 3
```

---

## Integration

### `/meridian:dispatch`
Send plans to Nero for remote autonomous execution.

```
/meridian:dispatch --plan 5            # Dispatch specific plan
/meridian:dispatch --phase 2           # Dispatch all plans in phase
/meridian:dispatch --swarm             # All plans in parallel
/meridian:dispatch --status 1          # Check dispatch status
/meridian:dispatch --check-all         # Check all active dispatches
```

See [Remote Dispatch Tutorial](tutorials/remote-dispatch.md) for setup.

---

### `/meridian:scan`
Codebase audit and work discovery. Identifies potential improvements and generates phase proposals.

```
/meridian:scan
```

---

### `/meridian:template`
Apply pre-built workflow templates for common project types.

```
/meridian:template api-service
```

---

### `/meridian:migrate`
Move Meridian state between projects or repos.

```
/meridian:migrate --to /path/to/new-project
```

---

### `/meridian:revert`
Revert a completed plan's changes via git.

```
/meridian:revert --plan 3
```
