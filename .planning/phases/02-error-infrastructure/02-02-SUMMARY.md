---
phase: 02-error-infrastructure
plan: 02
subsystem: errors
tags: [sql-injection, state-transitions, column-allowlist, safe-update]

requires:
  - phase: 02-error-infrastructure
    provides: "StateTransitionError from Plan 01 error hierarchy"
provides:
  - "safe_update() with ALLOWED_COLUMNS column validation for all 6 tables"
  - "_PRIORITY_SQL mapping eliminating dynamic table interpolation"
  - "StateTransitionError usage in all 4 transition functions"
affects: [03-cli-infrastructure]

tech-stack:
  added: []
  patterns: [column-allowlist-validation, explicit-sql-mapping]

key-files:
  created: []
  modified:
    - scripts/state.py
    - tests/test_state.py

key-decisions:
  - "Both per-function allowed sets and ALLOWED_COLUMNS serve different purposes: kwargs filtering vs security validation"
  - "Entity-not-found errors remain as ValueError (not StateTransitionError) since they are argument validation, not transition errors"

patterns-established:
  - "Column allowlist: all dynamic UPDATE statements go through safe_update() with ALLOWED_COLUMNS validation"
  - "Explicit SQL mapping: table names in SQL never come from user input (_PRIORITY_SQL pattern)"

requirements-completed: [ERRL-02, SECR-01, SECR-02]

duration: 3min
completed: 2026-03-10
---

# Phase 2 Plan 2: State Error Handling and SQL Safety Summary

**safe_update() with column allowlists preventing SQL injection, _PRIORITY_SQL eliminating table interpolation, and StateTransitionError for typed transition errors**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T02:17:22Z
- **Completed:** 2026-03-11T02:20:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- ALLOWED_COLUMNS dict covering all 6 tables with column allowlists, preventing invalid column injection
- safe_update() function with validation used by all 8 update/transition functions
- _PRIORITY_SQL mapping replacing f-string table interpolation in add_priority()
- StateTransitionError replacing ValueError in 4 transition functions for typed error catching
- 9 new tests (TestSafeUpdate: 5, TestAddPriority: 4), all 117 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for safe_update and add_priority** - `8bbd8c6` (test)
2. **Task 1 (GREEN): safe_update(), ALLOWED_COLUMNS, _PRIORITY_SQL, refactor all updates** - `04ad61e` (feat)
3. **Task 2: Replace ValueError with StateTransitionError** - `65f0a49` (feat)

_TDD task with RED/GREEN commits for Task 1._

## Files Created/Modified
- `scripts/state.py` - Added ALLOWED_COLUMNS, safe_update(), _PRIORITY_SQL, StateTransitionError import; refactored all update/transition functions
- `tests/test_state.py` - Added TestSafeUpdate (5 tests), TestAddPriority (4 tests), updated 3 transition tests to expect StateTransitionError

## Decisions Made
- Both per-function allowed sets (kwargs filtering) and ALLOWED_COLUMNS (security validation) kept as separate layers serving different purposes
- Entity-not-found errors remain as ValueError since they are argument validation, not state transition errors

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All SQL injection surfaces in state.py eliminated via safe_update() and _PRIORITY_SQL
- StateTransitionError available for typed error handling in CLI layer (Phase 3)
- Plan 03 (dispatch/sync retry) can build on same error patterns

---
*Phase: 02-error-infrastructure*
*Completed: 2026-03-10*
