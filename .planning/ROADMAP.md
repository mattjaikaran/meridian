# Roadmap: Meridian

## Milestones

- ✅ **v1.0 Meridian Hardening** — Phases 1-4 (shipped 2026-03-11)
- 🚧 **v1.1 Polish & Reliability** — Phases 5-7 (in progress)

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
- [ ] **Phase 6: Nyquist Compliance** - Fill validation gaps so every phase has accurate pass/fail frontmatter
- [ ] **Phase 7: Roadmap Automation** - Auto-sync ROADMAP.md checkboxes and requirement traceability from DB state

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
**Plans**: TBD

### Phase 7: Roadmap Automation
**Goal**: ROADMAP.md and REQUIREMENTS.md stay in sync with DB state without manual edits
**Depends on**: Nothing (independent of other v1.1 phases)
**Requirements**: ROAD-01, ROAD-02
**Success Criteria** (what must be TRUE):
  1. When a plan or phase status changes in the DB, the corresponding ROADMAP.md checkbox updates automatically (no manual `[x]` editing)
  2. When a requirement's phase completes in the DB, the REQUIREMENTS.md traceability table status updates automatically
  3. After any state transition, `ROADMAP.md` progress table reflects current DB state without human intervention
**Plans**: TBD

## Progress

**Execution Order:**
Phases 5, 6, 7 are independent and can execute in any order.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Database Foundation | v1.0 | 2/2 | Complete | 2026-03-10 |
| 2. Error Infrastructure | v1.0 | 3/3 | Complete | 2026-03-11 |
| 3. Command Routing | v1.0 | 2/2 | Complete | 2026-03-11 |
| 4. Test Coverage & Hardening | v1.0 | 4/4 | Complete | 2026-03-11 |
| 5. Lint Cleanup | v1.1 | 1/1 | Complete | 2026-03-14 |
| 6. Nyquist Compliance | v1.1 | 0/0 | Not started | - |
| 7. Roadmap Automation | v1.1 | 0/0 | Not started | - |
