# Roadmap: Meridian

## Milestones

- ✅ **v1.0 Meridian Hardening** — Phases 1-4 (shipped 2026-03-11)
- ✅ **v1.1 Polish & Reliability** — Phases 5-7 (shipped 2026-03-20)
- 🚧 **v1.2 Feature Parity** — Phases 8-11 (in progress)
- 📋 **v1.3 Advanced Capabilities** — Phases 12-14 (planned)

## Phases

<details>
<summary>✅ v1.0 Meridian Hardening (Phases 1-4) — SHIPPED 2026-03-11</summary>

- [x] Phase 1: Database Foundation (2/2 plans) — completed 2026-03-10
- [x] Phase 2: Error Infrastructure (3/3 plans) — completed 2026-03-11
- [x] Phase 3: Command Routing (2/2 plans) — completed 2026-03-11
- [x] Phase 4: Test Coverage & Hardening (4/4 plans) — completed 2026-03-11

See: `.planning/milestones/v1.0-ROADMAP.md` for full details

</details>

### v1.1 Polish & Reliability

- [x] **Phase 5: Lint Cleanup** - Fix all E501 violations in SQL schema and command generator
- [x] **Phase 6: Nyquist Compliance** - Fill validation gaps so every phase has accurate pass/fail frontmatter
- [x] **Phase 7: Roadmap Automation** - Auto-sync ROADMAP.md checkboxes and requirement traceability from DB state

### v1.2 Feature Parity

- [ ] **Phase 8: Quick Workflow** — `/fast`, `/do`, `/note`, `/next` lightweight commands
- [ ] **Phase 9: Quality Gates** — Regression gate, requirements coverage, stub detection, UAT audit
- [ ] **Phase 10: Session Intelligence** — Structured handoff, debug knowledge base, decision IDs
- [ ] **Phase 11: Security & PR Hygiene** — Centralized security module, `/pr-branch`

## Phase Details

### Phase 5: Lint Cleanup
**Goal**: All Python source files pass ruff E501 checks with zero violations
**Depends on**: Nothing (independent of other v1.1 phases)
**Requirements**: QUAL-01, QUAL-02
**Success Criteria** (what must be TRUE):
  1. `ruff check scripts/db.py --select E501` returns zero violations
  2. `ruff check scripts/generate_commands.py --select E501` returns zero violations
  3. No functional behavior changes in either file (tests still pass)
**Plans:** 1 plan
Plans:
- [x] 05-01-PLAN.md — Fix all E501 line-length violations in db.py and generate_commands.py

### Phase 6: Nyquist Compliance
**Goal**: VALIDATION.md accurately reflects execution results for every phase
**Depends on**: Nothing (independent of other v1.1 phases)
**Requirements**: COMP-01, COMP-02
**Success Criteria** (what must be TRUE):
  1. After plan execution completes, VALIDATION.md frontmatter contains actual pass/fail results (not stale placeholders)
  2. Every previously-executed phase that skipped validation has its VALIDATION.md gap filled with retroactive results
  3. Running `/meridian:verify-phase` on any completed phase finds a VALIDATION.md with current, accurate frontmatter
**Plans:** 2 plans
Plans:
- [x] 06-01-PLAN.md — Build Nyquist validation engine (parse, run, update VALIDATION.md frontmatter)
- [x] 06-02-PLAN.md — Retroactive gap fill and /meridian:verify-phase skill

### Phase 7: Roadmap Automation
**Goal**: ROADMAP.md and REQUIREMENTS.md stay in sync with DB state without manual edits
**Depends on**: Nothing (independent of other v1.1 phases)
**Requirements**: ROAD-01, ROAD-02
**Success Criteria** (what must be TRUE):
  1. When a plan or phase status changes in the DB, the corresponding ROADMAP.md checkbox updates automatically (no manual `[x]` editing)
  2. When a requirement's phase completes in the DB, the REQUIREMENTS.md traceability table status updates automatically
  3. After any state transition, `ROADMAP.md` progress table reflects current DB state without human intervention
**Plans:** 2 plans
Plans:
- [x] 07-01-PLAN.md — Build and test roadmap_sync.py with TDD (pure text transformations)
- [x] 07-02-PLAN.md — Wire sync hooks into state.py transition functions

### Phase 8: Quick Workflow
**Goal**: Four lightweight commands for common quick actions without full planning overhead
**Depends on**: Nothing (independent)
**Requirements**: QUICK-01, QUICK-02, QUICK-03, QUICK-04
**Success Criteria** (what must be TRUE):
  1. `/meridian:fast` executes trivial tasks inline without creating DB records for phases/plans
  2. `/meridian:do` routes freeform text to the correct `/meridian:*` command
  3. `/meridian:note` captures, lists, and promotes ideas to tasks
  4. `/meridian:next` auto-detects workflow state and advances to the next logical step
**Plans:** 4 plans (wave 1: fast, do, note | wave 2: next)
Plans:
- [x] 08-01-PLAN.md — `/meridian:fast` inline task execution with complexity check
- [x] 08-02-PLAN.md — `/meridian:do` freeform text router
- [x] 08-03-PLAN.md — `/meridian:note` zero-friction idea capture
- [x] 08-04-PLAN.md — `/meridian:next` auto-advance workflow step

### Phase 9: Quality Gates
**Goal**: Automated quality checks that catch regressions, coverage gaps, and placeholder code
**Depends on**: Phase 6 (uses VALIDATION.md for regression gate)
**Requirements**: GATE-01, GATE-02, GATE-03, GATE-04
**Success Criteria** (what must be TRUE):
  1. Phase execution is blocked if prior phases' tests fail (regression gate)
  2. Plan execution warns if phase requirements aren't fully covered by plans
  3. Post-execution stub scan detects TODO/FIXME/NotImplementedError patterns
  4. `/meridian:audit-uat` produces a cross-phase verification debt report
**Plans:** 4 plans (wave 1: regression + coverage gates | wave 2: stubs + audit)
Plans:
- [x] 09-01-PLAN.md — Cross-phase regression gate
- [x] 09-02-PLAN.md — Requirements coverage gate
- [x] 09-03-PLAN.md — Stub/placeholder detection
- [x] 09-04-PLAN.md — `/meridian:audit-uat` verification debt tracking

### Phase 10: Session Intelligence
**Goal**: Richer context preservation across sessions and traceable decision making
**Depends on**: Nothing (independent)
**Requirements**: SESS-01, SESS-02, SESS-03
**Success Criteria** (what must be TRUE):
  1. `/meridian:pause` creates a structured HANDOFF.json consumed by `/meridian:resume`
  2. Debug sessions append findings to a persistent knowledge base
  3. Decisions get unique IDs and link to the plans they informed
**Plans:** 3 plans (wave 1: handoff + debug KB | wave 2: decision IDs)
Plans:
- [x] 10-01-PLAN.md — Structured session handoff (HANDOFF.json)
- [x] 10-02-PLAN.md — Persistent debug knowledge base
- [x] 10-03-PLAN.md — Decision IDs with discuss→plan traceability

### Phase 11: Security & PR Hygiene
**Goal**: Centralized input validation and clean PR branches without planning artifacts
**Depends on**: Nothing (independent)
**Requirements**: SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. All path, JSON, field name, and shell arg validation goes through `scripts/security.py`
  2. `/meridian:pr-branch` creates a code-only branch filtering `.planning/` and `.meridian/` commits
**Plans:** 2 plans (wave 1: both parallel)
Plans:
- [x] 11-01-PLAN.md — Centralized security module
- [x] 11-02-PLAN.md — `/meridian:pr-branch` clean PR branch creation

### Phase 12: Developer Experience
**Goal**: Developer profiling, backlog management, and discussion audit trail
**Depends on**: Phase 10 (uses decision IDs)
**Requirements**: DX-01, DX-02, DX-03
**Success Criteria** (what must be TRUE):
  1. `/meridian:profile` generates a USER-PROFILE.md from project analysis
  2. `/meridian:seed` captures ideas with trigger conditions that surface automatically
  3. Discussion decisions are logged in DISCUSSION-LOG.md with decision ID links
**Plans:** 3 plans (wave 1: all parallel)
Plans:
- [ ] 12-01-PLAN.md — `/meridian:profile` developer preference profiling
- [ ] 12-02-PLAN.md — `/meridian:seed` backlog parking lot with triggers
- [ ] 12-03-PLAN.md — Discussion audit trail with decision ID linking

### Phase 13: Execution Resilience
**Goal**: Interactive execution mode and automatic recovery from plan failures
**Depends on**: Nothing (independent)
**Requirements**: EXEC-01, EXEC-02
**Success Criteria** (what must be TRUE):
  1. `--interactive` flag pauses execution after each task for user review
  2. Failed plans trigger auto-recovery (RETRY/DECOMPOSE/PRUNE) within a configurable budget
**Plans:** 2 plans (wave 1: both parallel)
Plans:
- [ ] 13-01-PLAN.md — Interactive executor mode for pair-programming
- [ ] 13-02-PLAN.md — Node repair operators (RETRY/DECOMPOSE/PRUNE)

### Phase 14: Agent Intelligence
**Goal**: MCP tool awareness and context window optimization for subagents
**Depends on**: Nothing (independent)
**Requirements**: AGENT-01, AGENT-02
**Success Criteria** (what must be TRUE):
  1. Subagent prompts include relevant MCP tools when available
  2. Prompt sizing adapts to available context window (1M vs 200k)
**Plans:** 2 plans (wave 1: both parallel)
Plans:
- [ ] 14-01-PLAN.md — MCP tool discovery and relevance scoring
- [ ] 14-02-PLAN.md — Context window awareness and prompt sizing

## Progress

**Execution Order:**
- v1.1: Phases 5, 6, 7 — independent. All complete.
- v1.2: Phases 8-11 — independent. All complete.
- v1.3: Phases 12-14 — independent. Within phases, waves enforce ordering.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | v1.0 | 2/2 | Complete | 2026-03-20 |
| 2. Error Infrastructure | v1.0 | 3/3 | Complete | 2026-03-20 |
| 3. Command Routing | v1.0 | 2/2 | Complete | 2026-03-11 |
| 4. Test Coverage & Hardening | v1.0 | 4/4 | Complete | 2026-03-11 |
| 5. Lint Cleanup | v1.1 | 1/1 | Complete | 2026-03-14 |
| 6. Nyquist Compliance | v1.1 | 2/2 | Complete | 2026-03-20 |
| 7. Roadmap Automation | v1.1 | 2/2 | Complete | 2026-03-16 |
| 8. Quick Workflow | v1.2 | 4/4 | Complete | 2026-03-20 |
| 9. Quality Gates | v1.2 | 4/4 | Complete | 2026-03-20 |
| 10. Session Intelligence | v1.2 | 3/3 | Complete | 2026-03-20 |
| 11. Security & PR Hygiene | v1.2 | 2/2 | Complete | 2026-03-20 |
| 12. Developer Experience | v1.3 | 0/3 | Not started | - |
| 13. Execution Resilience | v1.3 | 0/2 | Not started | - |
| 14. Agent Intelligence | v1.3 | 0/2 | Not started | - |
