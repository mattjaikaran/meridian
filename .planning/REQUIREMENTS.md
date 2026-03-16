# Requirements: Meridian

**Defined:** 2026-03-14
**Core Value:** Deterministic workflow state that survives context resets

## v1.1 Requirements

Requirements for v1.1 Polish & Reliability. Each maps to roadmap phases.

### Roadmap Automation

- [x] **ROAD-01**: ROADMAP.md checkboxes auto-update when phase/plan status changes in DB
- [x] **ROAD-02**: Requirement traceability status auto-syncs from DB state (no manual edits)

### Compliance

- [x] **COMP-01**: VALIDATION.md frontmatter updated post-execution with actual pass/fail results
- [x] **COMP-02**: Nyquist validation gaps filled for phases that skipped validation

### Code Quality

- [x] **QUAL-01**: All E501 lint violations fixed in SQL schema definitions
- [x] **QUAL-02**: All E501 lint violations fixed in generate_commands.py

## Future Requirements

None identified yet.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full CI/CD pipeline | Not needed for local-only tool |
| Automated test generation | Over-engineering for polish milestone |
| Dogfooding on external project | Process activity, not a code requirement -- do separately |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ROAD-01 | Phase 7 | Complete |
| ROAD-02 | Phase 7 | Complete |
| COMP-01 | Phase 6 | Complete |
| COMP-02 | Phase 6 | Complete |
| QUAL-01 | Phase 5 | Complete |
| QUAL-02 | Phase 5 | Complete |

**Coverage:**
- v1.1 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-03-14*
*Last updated: 2026-03-16 after 07-02 plan completion*
