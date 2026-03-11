---
phase: 04-test-coverage-hardening
plan: 04
subsystem: testing
tags: [bugfix, truthiness, state-management, metrics]

# Dependency graph
requires:
  - phase: 04-02
    provides: "Baseline tests capturing buggy behavior for QUAL-04/05/06"
provides:
  - "Fixed check_auto_advance milestone_ready false positive"
  - "Fixed update_nero_dispatch truthiness bug (is not None)"
  - "Module-level timedelta import in metrics.py"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use 'is not None' for optional parameter checks (not truthiness)"
    - "Re-fetch DB state after mutations before computing derived values"

key-files:
  created: []
  modified:
    - scripts/state.py
    - scripts/metrics.py
    - tests/test_state.py

key-decisions:
  - "Empty string status on nero_dispatch correctly reaches DB and fails CHECK constraint (explicit error vs silent no-op)"
  - "milestone_ready only True when all phases genuinely complete (verifying treated as incomplete)"

patterns-established:
  - "is not None guards: use for optional kwargs where empty string is meaningful"

requirements-completed: [QUAL-04, QUAL-05, QUAL-06]

# Metrics
duration: 3min
completed: 2026-03-11
---

# Phase 04 Plan 04: Bug Fixes Summary

**Fixed three correctness bugs: milestone_ready false positive, nero_dispatch truthiness, and inline timedelta import**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T15:12:46Z
- **Completed:** 2026-03-11T15:15:52Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Fixed check_auto_advance: milestone_ready=False when current phase is "verifying" (not "complete")
- Fixed update_nero_dispatch: `is not None` checks allow empty strings through to DB layer
- Moved timedelta import to module level in metrics.py
- Updated 5 tests covering new correct behaviors

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix check_auto_advance milestone_ready false positive (QUAL-04)** - `e5f9a54` (fix)
2. **Task 2: Fix update_nero_dispatch truthiness bug and move timedelta import (QUAL-05, QUAL-06)** - `5f77ba6` (fix)

## Files Created/Modified
- `scripts/state.py` - Fixed milestone_ready logic (re-fetch after transition, remove phase_id exclusion) and nero_dispatch truthiness checks
- `scripts/metrics.py` - Moved timedelta to module-level import
- `tests/test_state.py` - Updated TestAutoAdvance and TestNeroDispatch with correct assertions
- `tests/test_metrics.py` - Verified no regression from timedelta import move

## Decisions Made
- Empty string status on nero_dispatch now reaches the DB and is rejected by the CHECK constraint, which is correct behavior -- callers get an explicit error instead of a silent no-op
- milestone_ready is only True when all phases including the current one have status="complete"; a phase in "verifying" is correctly treated as incomplete

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Adjusted empty-string test for DB CHECK constraint**
- **Found during:** Task 2 (QUAL-05 test)
- **Issue:** Plan specified asserting status="" updates DB, but nero_dispatch.status has a CHECK constraint limiting values to dispatched/accepted/running/completed/failed/rejected
- **Fix:** Changed test to assert that empty string reaches DB and triggers IntegrityError (explicit error vs silent no-op)
- **Files modified:** tests/test_state.py
- **Verification:** Test passes, confirms fix works correctly with DB constraints
- **Committed in:** 5f77ba6

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Test adjusted to match DB schema constraints. The core fix (is not None) is correct.

## Issues Encountered
- Linter/pre-commit reverted in-progress edits to source files between Task 1 commit and Task 2 editing. Re-applied edits successfully.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All three QUAL bugs fixed with tests proving correct behavior
- Full test suite passes (217 tests)
- Phase 04 bug fix work complete

---
*Phase: 04-test-coverage-hardening*
*Completed: 2026-03-11*
