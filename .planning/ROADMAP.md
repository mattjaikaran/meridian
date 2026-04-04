# Roadmap: Meridian

## Milestones

- ✅ **M1: Foundation** — Phases 1-4 (shipped 2026-03-11)
- ✅ **M2: Polish & Reliability** — Phases 5-7 (shipped 2026-03-20)
- ✅ **M3: Feature Parity** — Phases 8-11 (shipped 2026-03-20)
- ✅ **M4: Advanced Capabilities** — Phases 12-14 (shipped 2026-03-20)
- ✅ **M5: Feature Expansion** — Phases 15-20 (shipped 2026-03-20)
- ✅ **M6: Integration & Polish** — Phases 21-26 (shipped 2026-03-20)
- 🔄 **M7: GSD Parity & Workflow Maturity** — Phases 27-35

## Phases

<details>
<summary>✅ M1: Foundation (Phases 1-4) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Database Foundation (2/2 plans) — completed 2026-03-10
- [x] Phase 2: Error Infrastructure (3/3 plans) — completed 2026-03-11
- [x] Phase 3: Command Routing (2/2 plans) — completed 2026-03-11
- [x] Phase 4: Test Coverage & Hardening (4/4 plans) — completed 2026-03-11

See: `.planning/milestones/v1.0-ROADMAP.md` for full details

</details>

<details>
<summary>✅ M2: Polish & Reliability (Phases 5-7) — SHIPPED 2026-03-20</summary>

- [x] **Phase 5: Lint Cleanup** - Fix all E501 violations in SQL schema and command generator
- [x] **Phase 6: Nyquist Compliance** - Fill validation gaps so every phase has accurate pass/fail frontmatter
- [x] **Phase 7: Roadmap Automation** - Auto-sync ROADMAP.md checkboxes and requirement traceability from DB state

</details>

<details>
<summary>✅ M3: Feature Parity (Phases 8-11) — SHIPPED 2026-03-20</summary>

- [x] **Phase 8: Quick Workflow** — `/fast`, `/do`, `/note`, `/next` lightweight commands
- [x] **Phase 9: Quality Gates** — Regression gate, requirements coverage, stub detection, UAT audit
- [x] **Phase 10: Session Intelligence** — Structured handoff, debug knowledge base, decision IDs
- [x] **Phase 11: Security & PR Hygiene** — Centralized security module, `/pr-branch`

</details>

<details>
<summary>✅ M4: Advanced Capabilities (Phases 12-14) — SHIPPED 2026-03-20</summary>

- [x] **Phase 12: Developer Experience** — `/profile`, `/seed`, discussion log
- [x] **Phase 13: Execution Resilience** — Interactive executor, node repair
- [x] **Phase 14: Agent Intelligence** — MCP discovery, context awareness

</details>

<details>
<summary>✅ M5: Feature Expansion (Phases 15-20) — SHIPPED 2026-03-20</summary>

- [x] **Phase 15: Execution Learning** — `/meridian:learn` (learning table, auto-capture, prompt injection)
- [x] **Phase 16: Edit Scope Lock** — `/meridian:freeze` (directory lock via settings, advisory safety)
- [x] **Phase 17: Structured Retrospective** — `/meridian:retro` (velocity trends, shipping streaks, action items)
- [x] **Phase 18: Deep Discovery Mode** — `--deep` flag on `/meridian:plan` (5 forcing questions)
- [x] **Phase 19: Session Awareness** — PID-based concurrent session detection
- [x] **Phase 20: Cross-Model Review** — `--cross-model` flag on `/meridian:review` (secondary AI CLI)

</details>

<details>
<summary>✅ M6: Integration & Polish (Phases 21-26) — SHIPPED 2026-03-20</summary>

- [x] **Phase 21: Learnings Auto-Capture** — Auto-suggest from failures and review rejections
- [x] **Phase 22: HTML Dashboard** — `/meridian:dashboard --html` standalone dark-themed report
- [x] **Phase 23: Freeze Integration** — Check freeze state before subagent file edits
- [x] **Phase 24: Test Coverage Audit** — Scripts vs tests coverage mapping
- [x] **Phase 25: Context Bridge** — matt-stack + external context import
- [x] **Phase 26: Retro Auto-Scheduling** — Prompt for retro every N completed phases

</details>

### M7: GSD Parity & Workflow Maturity

- [ ] **Phase 27: Discuss Phase** — Adaptive questioning before planning (`--auto`, `--chain`, `--batch`)
- [ ] **Phase 28: Model Profiles** — Dynamic model assignment per agent type (quality/balanced/budget/inherit)
- [ ] **Phase 29: Config System** — User-facing `/meridian:config` for workflow preferences
- [ ] **Phase 30: Autonomous Mode** — Hands-free discuss→plan→execute per phase (`--from`, `--to`, `--only`)
- [ ] **Phase 31: Gap Closure** — `--gaps-only` flag to re-execute only failed/skipped plans
- [ ] **Phase 32: Phase Manipulation** — Insert decimal phases (7.1), remove + renumber
- [ ] **Phase 33: Milestone Lifecycle** — Audit, complete with git tag, archive
- [ ] **Phase 34: Session Reports** — End-of-session token usage, work summary, outcomes
- [ ] **Phase 35: Codebase Mapping** — Parallel multi-agent codebase analysis (7 structured docs)

## Phase Details

<details>
<summary>Phase details for M1-M6 (completed)</summary>

### Phase 5: Lint Cleanup
**Goal**: All Python source files pass ruff E501 checks with zero violations
**Depends on**: Nothing
**Plans:** 1 plan
- [x] 05-01-PLAN.md — Fix all E501 line-length violations in db.py and generate_commands.py

### Phase 6: Nyquist Compliance
**Goal**: VALIDATION.md accurately reflects execution results for every phase
**Depends on**: Nothing
**Plans:** 2 plans
- [x] 06-01-PLAN.md — Build Nyquist validation engine
- [x] 06-02-PLAN.md — Retroactive gap fill and /meridian:verify-phase skill

### Phase 7: Roadmap Automation
**Goal**: ROADMAP.md and REQUIREMENTS.md stay in sync with DB state without manual edits
**Depends on**: Nothing
**Plans:** 2 plans
- [x] 07-01-PLAN.md — Build and test roadmap_sync.py with TDD
- [x] 07-02-PLAN.md — Wire sync hooks into state.py transition functions

### Phase 8: Quick Workflow
**Goal**: Four lightweight commands for common quick actions
**Depends on**: Nothing
**Plans:** 4 plans (wave 1: fast, do, note | wave 2: next)
- [x] 08-01-PLAN.md — `/meridian:fast` inline task execution
- [x] 08-02-PLAN.md — `/meridian:do` freeform text router
- [x] 08-03-PLAN.md — `/meridian:note` zero-friction idea capture
- [x] 08-04-PLAN.md — `/meridian:next` auto-advance workflow step

### Phase 9: Quality Gates
**Goal**: Automated quality checks that catch regressions, coverage gaps, and placeholder code
**Depends on**: Phase 6
**Plans:** 4 plans
- [x] 09-01-PLAN.md — Cross-phase regression gate
- [x] 09-02-PLAN.md — Requirements coverage gate
- [x] 09-03-PLAN.md — Stub/placeholder detection
- [x] 09-04-PLAN.md — `/meridian:audit-uat` verification debt tracking

### Phase 10: Session Intelligence
**Goal**: Richer context preservation across sessions and traceable decisions
**Depends on**: Nothing
**Plans:** 3 plans
- [x] 10-01-PLAN.md — Structured session handoff (HANDOFF.json)
- [x] 10-02-PLAN.md — Persistent debug knowledge base
- [x] 10-03-PLAN.md — Decision IDs with discuss→plan traceability

### Phase 11: Security & PR Hygiene
**Goal**: Centralized input validation and clean PR branches
**Depends on**: Nothing
**Plans:** 2 plans
- [x] 11-01-PLAN.md — Centralized security module
- [x] 11-02-PLAN.md — `/meridian:pr-branch` clean PR branch creation

### Phase 12: Developer Experience
**Goal**: Developer profiling, backlog management, and discussion audit trail
**Depends on**: Phase 10
**Plans:** 3 plans
- [x] 12-01-PLAN.md — `/meridian:profile` developer preference profiling
- [x] 12-02-PLAN.md — `/meridian:seed` backlog parking lot with triggers
- [x] 12-03-PLAN.md — Discussion audit trail with decision ID linking

### Phase 13: Execution Resilience
**Goal**: Interactive execution mode and automatic recovery from plan failures
**Depends on**: Nothing
**Plans:** 2 plans
- [x] 13-01-PLAN.md — Interactive executor mode
- [x] 13-02-PLAN.md — Node repair operators (RETRY/DECOMPOSE/PRUNE)

### Phase 14: Agent Intelligence
**Goal**: MCP tool awareness and context window optimization for subagents
**Depends on**: Nothing
**Plans:** 2 plans
- [x] 14-01-PLAN.md — MCP tool discovery and relevance scoring
- [x] 14-02-PLAN.md — Context window awareness and prompt sizing

### Phase 15-26
All shipped. See CHANGELOG.md for details.

</details>

### Phase 27: Discuss Phase
**Goal**: Structured context gathering and decision-making before planning, replacing the current jump-straight-to-brainstorm approach
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:plan` routes through a discuss step that asks adaptive questions about scope, approach, and constraints
  2. `--auto` flag skips interactive questions and picks recommended defaults
  3. `--chain` flag runs discuss→plan automatically (no manual `/meridian:plan` after discuss)
  4. `--batch` flag dumps all questions to a file for offline answering
  5. Discussion decisions are persisted in DB and injected into plan generation context
**Plans:** TBD

### Phase 28: Model Profiles
**Goal**: Dynamic model selection per agent type for cost optimization and non-Anthropic provider support
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:config set profile balanced` sets the active profile (quality/balanced/budget/inherit)
  2. Each agent type (planner, executor, reviewer, researcher, verifier) maps to a model per profile
  3. `inherit` profile uses the current session model for all agents (required for non-Anthropic runtimes)
  4. Profile stored in DB settings table, readable by all skill commands
**Plans:** TBD

### Phase 29: Config System
**Goal**: User-facing configuration command for workflow preferences
**Depends on**: Phase 28 (model profiles stored in config)
**Success Criteria** (what must be TRUE):
  1. `/meridian:config` shows current settings (profile, discuss mode, interactive mode, etc.)
  2. `/meridian:config set <key> <value>` persists preferences to DB settings table
  3. `/meridian:config reset` restores defaults
  4. Config values respected by plan, execute, and review commands
**Plans:** TBD

### Phase 30: Autonomous Mode
**Goal**: Hands-free execution of multiple phases without manual intervention
**Depends on**: Phase 27 (discuss phase), Phase 29 (config for auto-discuss preference)
**Success Criteria** (what must be TRUE):
  1. `/meridian:execute --autonomous` runs discuss→plan→execute for each remaining phase
  2. `--from N` and `--to N` flags constrain the phase range
  3. `--only N` runs a single phase autonomously
  4. Failures stop the autonomous loop with a clear error and resumable state
**Plans:** TBD

### Phase 31: Gap Closure
**Goal**: Re-execute only failed or skipped plans without re-running successful ones
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:execute --gaps-only` filters to failed/skipped plans and re-executes them
  2. Previously completed plans are untouched
  3. Works with wave ordering (respects wave dependencies even for partial re-execution)
**Plans:** TBD

### Phase 32: Phase Manipulation
**Goal**: Insert urgent work mid-milestone and remove/renumber phases
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:insert-phase --after 7 "urgent fix"` creates Phase 7.1 in DB and ROADMAP
  2. `/meridian:remove-phase 8` removes the phase and renumbers subsequent phases
  3. Decimal phases sort correctly in status, dashboard, and execution order
**Plans:** TBD

### Phase 33: Milestone Lifecycle
**Goal**: Structured milestone completion with audit, archival, and git tagging
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:audit-milestone` checks all phases complete, no outstanding UAT debt, no stubs
  2. `/meridian:complete-milestone` archives the milestone, creates a git tag, updates ROADMAP
  3. Milestone summary with stats (phases, plans, velocity, duration) persisted
**Plans:** TBD

### Phase 34: Session Reports
**Goal**: End-of-session summary with work done, outcomes, and next steps
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:report` generates a session summary (plans completed, files changed, tests run)
  2. Report includes estimated token usage for the session
  3. Report suggests next action based on current workflow state
**Plans:** TBD

### Phase 35: Codebase Mapping
**Goal**: Parallel multi-agent codebase analysis producing structured documentation
**Depends on**: Nothing (independent)
**Success Criteria** (what must be TRUE):
  1. `/meridian:scan --deep` launches parallel agents analyzing: architecture, stack, structure, testing, conventions, integrations, concerns
  2. Each agent writes a structured doc to `.meridian/codebase/`
  3. Results are consumable by `/meridian:plan` for context enrichment
**Plans:** TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | M1 | 2/2 | Complete | 2026-04-04 |
| 2. Error Infrastructure | M1 | 3/3 | Complete | 2026-04-04 |
| 3. Command Routing | M1 | 2/2 | Complete | 2026-04-04 |
| 4. Test Coverage & Hardening | M1 | 4/4 | Complete | 2026-03-11 |
| 5. Lint Cleanup | M2 | 1/1 | Complete | 2026-03-14 |
| 6. Nyquist Compliance | M2 | 2/2 | Complete | 2026-03-20 |
| 7. Roadmap Automation | M2 | 2/2 | Complete | 2026-03-16 |
| 8. Quick Workflow | M3 | 4/4 | Complete | 2026-03-20 |
| 9. Quality Gates | M3 | 4/4 | Complete | 2026-03-20 |
| 10. Session Intelligence | M3 | 3/3 | Complete | 2026-03-20 |
| 11. Security & PR Hygiene | M3 | 2/2 | Complete | 2026-03-20 |
| 12. Developer Experience | M4 | 3/3 | Complete | 2026-03-20 |
| 13. Execution Resilience | M4 | 2/2 | Complete | 2026-03-20 |
| 14. Agent Intelligence | M4 | 2/2 | Complete | 2026-03-20 |
| 15. Execution Learning | M5 | 1/1 | Complete | 2026-03-20 |
| 16. Edit Scope Lock | M5 | 1/1 | Complete | 2026-03-20 |
| 17. Structured Retrospective | M5 | 1/1 | Complete | 2026-03-20 |
| 18. Deep Discovery Mode | M5 | 1/1 | Complete | 2026-03-20 |
| 19. Session Awareness | M5 | 1/1 | Complete | 2026-03-20 |
| 20. Cross-Model Review | M5 | 1/1 | Complete | 2026-03-20 |
| 21. Learnings Auto-Capture | M6 | 1/1 | Complete | 2026-03-20 |
| 22. HTML Dashboard | M6 | 1/1 | Complete | 2026-03-20 |
| 23. Freeze Integration | M6 | 1/1 | Complete | 2026-03-20 |
| 24. Test Coverage Audit | M6 | 1/1 | Complete | 2026-03-20 |
| 25. Context Bridge | M6 | 1/1 | Complete | 2026-03-20 |
| 26. Retro Auto-Scheduling | M6 | 1/1 | Complete | 2026-03-20 |
| 27. Discuss Phase | M7 | — | Planned | — |
| 28. Model Profiles | M7 | — | Planned | — |
| 29. Config System | M7 | — | Planned | — |
| 30. Autonomous Mode | M7 | — | Planned | — |
| 31. Gap Closure | M7 | — | Planned | — |
| 32. Phase Manipulation | M7 | — | Planned | — |
| 33. Milestone Lifecycle | M7 | — | Planned | — |
| 34. Session Reports | M7 | — | Planned | — |
| 35. Codebase Mapping | M7 | — | Planned | — |
