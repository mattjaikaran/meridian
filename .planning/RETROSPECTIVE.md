# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Meridian Hardening

**Shipped:** 2026-03-11
**Phases:** 4 | **Plans:** 11 | **Commits:** 71

### What Was Built
- Reliable DB layer: `open_project()` context manager with WAL, busy_timeout, retry, backup
- Error infrastructure: `MeridianError` hierarchy, structured logging, HTTP retry, SQL safety
- Command routing: Generator script producing 13 `/meridian:*` slash commands from SKILL.md
- Test hardening: 217 tests across 10 files, N+1 query elimination, 3 bug fixes

### What Worked
- Bottom-up phase ordering (DB → errors → routing → tests) meant each phase built cleanly on the last
- TDD approach in Phase 3 (generator script) caught bugs before integration
- Capturing buggy behavior as test baselines in Phase 4 Wave 1, then fixing in Wave 2 — clean regression safety
- Wave-based parallel execution: Plans 01+02 and 03+04 ran concurrently within each wave
- 4-day timeline from initial commit to fully shipped milestone

### What Was Inefficient
- ROADMAP.md tracking fell out of sync (Phase 1 showed "In Progress" despite being complete)
- Plan checkboxes not consistently updated during execution
- VALIDATION.md nyquist_compliant frontmatter never updated post-execution (administrative gap)
- Integration checker agent hit API connection error during audit — had to do manual check

### Patterns Established
- `defaultdict(list) + plans_by_phase` as canonical N+1 fix pattern
- `open_project()` as the only way to get a DB connection
- `safe_update()` with `ALLOWED_COLUMNS` for all dynamic SQL
- Generated `.md` wrappers with `<!-- meridian:generated -->` marker
- `is not None` guards instead of truthiness for optional string params

### Key Lessons
1. Test baselines before bug fixes — write tests capturing current (broken) behavior first, then fix
2. N+1 queries are mechanical: bulk fetch + group in Python, same pattern every time
3. ROADMAP tracking needs automated updates, not manual — tool should handle checkbox state
4. Cross-phase wiring is the highest-risk area — manual integration check was needed when agent failed

### Cost Observations
- Model mix: ~20% opus (orchestration), ~80% sonnet (research, execution, verification)
- Plan execution averaged 3 minutes per plan
- Total execution time: ~30 minutes across 11 plans
- Notable: Parallel wave execution cut wall-clock time roughly in half

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Commits | Phases | Key Change |
|-----------|---------|--------|------------|
| v1.0 | 71 | 4 | Initial hardening — established patterns |

### Cumulative Quality

| Milestone | Tests | Test Files | LOC |
|-----------|-------|------------|-----|
| v1.0 | 217 | 10 | 6,227 |

### Top Lessons (Verified Across Milestones)

1. Bottom-up dependency ordering prevents rework
2. Test baselines before fixes prevent regression
