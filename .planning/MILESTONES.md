# Milestones

## v1.0 Meridian Hardening (Shipped: 2026-03-11)

**Phases completed:** 4 phases, 11 plans, 0 tasks

**Key accomplishments:**
- Built `open_project()` context manager with WAL, busy_timeout, retry, and backup — all 5 scripts migrated
- Created `MeridianError` hierarchy with `StateTransitionError`, `NeroUnreachableError`, HTTP retry decorator
- Eliminated SQL injection surface with `safe_update()` column allowlists and `_PRIORITY_SQL` mapping
- Built command generator that produces 13 `/meridian:*` slash commands from SKILL.md definitions
- Added 217 tests (10 test files) covering all modules including dispatch, export, axis_sync, context_window
- Fixed 3 N+1 query patterns, auto-advance false positive, nero dispatch truthiness bug

**Stats:**
- Timeline: 4 days (Mar 7-11, 2026)
- Commits: 71
- Files: 84 modified, 6,227 lines Python
- Tests: 217 passing

---

