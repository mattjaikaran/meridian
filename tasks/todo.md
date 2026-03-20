# Meridian TODO

## v1.1 Polish & Reliability (shipped 2026-03-20)
- [x] Phase 5: Lint Cleanup
- [x] Phase 6: Nyquist Compliance — fix filename mismatch, harden tests
- [x] Phase 7: Roadmap Automation — sync hooks wired into state.py
- [ ] Close v1.1 milestone — update STATE.md, ROADMAP.md checkboxes

## v1.2 Feature Parity (GSD catch-up)

### Phase 8: Quick Workflow (4 commands) — DONE
- [x] 08-01: `/meridian:fast` — trivial inline tasks, skip planning entirely
- [x] 08-02: `/meridian:do` — freeform text router, NL → right command
- [x] 08-03: `/meridian:note` — zero-friction idea capture (append/list/promote)
- [x] 08-04: `/meridian:next` — auto-detect and advance to next workflow step

### Phase 9: Quality Gates (4 features) — DONE
- [x] 09-01: Cross-phase regression gate — run prior phases' test suites before advancing
- [x] 09-02: Requirements coverage gate — verify all phase reqs covered in plans
- [x] 09-03: Stub detection — catch placeholder/TODO code in verifier and executor
- [x] 09-04: `/meridian:audit-uat` — cross-phase UAT/verification debt tracking

### Phase 10: Session Intelligence (3 features) — DONE
- [x] 10-01: Structured session handoff — HANDOFF.json for `/meridian:resume` enrichment
- [x] 10-02: Persistent debug knowledge base — append resolved sessions to `.meridian/debug-kb.md`
- [x] 10-03: Decision IDs — traceable discuss→plan decision references

### Phase 11: Security & PR Hygiene (2 features) — DONE
- [x] 11-01: Centralized security module — path traversal prevention, injection detection, safe JSON, field validation
- [x] 11-02: `/meridian:pr-branch` — create clean PR branch filtering `.planning/` and `.meridian/` commits

## Stats
- Tests: 580 passing (202 new in v1.2)
- New modules: 10 (fast, router, notes, next_action, gates, audit, handoff, debug_kb, security, pr_branch)
- New skills: 7 (fast, do, note, next, audit-uat, pause, pr-branch)
