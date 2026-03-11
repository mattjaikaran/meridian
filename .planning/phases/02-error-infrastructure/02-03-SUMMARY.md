---
phase: 02-error-infrastructure
plan: 03
subsystem: dispatch-sync-retry
tags: [retry, http, nero, subprocess, security, exceptions]

requires:
  - phase: 02-error-infrastructure
    plan: 01
    provides: "retry_on_http_error decorator, NeroUnreachableError exception"
provides:
  - "Retry-decorated _nero_rpc in sync.py with NeroUnreachableError on failure"
  - "Retry-decorated _send_to_nero helper in dispatch.py"
  - "Safe list-based subprocess args in axis_sync._run_pm_command"
affects: [03-cli-infrastructure]

tech-stack:
  added: []
  patterns: [retry-decorator-application, exception-propagation, safe-subprocess-args]

key-files:
  created:
    - tests/test_axis_sync.py
  modified:
    - scripts/dispatch.py
    - scripts/sync.py
    - scripts/axis_sync.py
    - tests/test_sync.py

key-decisions:
  - "_nero_rpc returns dict (never None) -- callers use try/except NeroUnreachableError"
  - "push_state_to_nero lets NeroUnreachableError propagate (push failure should be visible)"
  - "check_dispatch_status catches NeroUnreachableError silently (non-critical status poll)"

requirements-completed: [ERRL-04, ERRL-05, SECR-03]

duration: 3min
completed: 2026-03-10
---

# Phase 2 Plan 3: Dispatch/Sync Retry and Axis Command Injection Fix Summary

**HTTP retry decorator applied to all Nero RPC calls with NeroUnreachableError propagation; axis_sync command injection fixed with list-based subprocess args**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-11T02:17:19Z
- **Completed:** 2026-03-11T02:20:38Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- _nero_rpc in sync.py decorated with @retry_on_http_error, returns dict instead of dict|None
- _send_to_nero helper extracted in dispatch.py with @retry_on_http_error decorator
- pull_dispatch_status catches NeroUnreachableError per-dispatch, continues processing
- push_state_to_nero lets NeroUnreachableError propagate (no more silent error dict)
- check_dispatch_status catches NeroUnreachableError, falls back to cached status
- _run_pm_command changed from string splitting to list[str] args (eliminates command injection)
- All callers updated to pass list args, preserving values with spaces
- Full TDD: 6 new tests, all 117 tests green

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing retry tests** - `ac0381a` (test)
2. **Task 1 (GREEN): Retry decorator applied** - `cfa53e6` (feat)
3. **Task 2 (RED): Failing list args tests** - `3c5b078` (test)
4. **Task 2 (GREEN): List args implementation** - `05af105` (feat)

_TDD tasks with RED/GREEN commits._

## Files Created/Modified
- `scripts/dispatch.py` - Added _send_to_nero helper with @retry_on_http_error, removed try/except URLError
- `scripts/sync.py` - Decorated _nero_rpc with @retry_on_http_error, removed None returns
- `scripts/axis_sync.py` - Changed _run_pm_command(command: str) to _run_pm_command(args: list[str])
- `tests/test_sync.py` - Added TestNeroRpcRetry class, updated unreachable tests to use NeroUnreachableError
- `tests/test_axis_sync.py` - Created with TestRunPmCommand class (4 tests)

## Decisions Made
- _nero_rpc returns dict (never None) -- callers use try/except NeroUnreachableError
- push_state_to_nero lets NeroUnreachableError propagate (push failure should be visible to caller)
- check_dispatch_status catches NeroUnreachableError silently (non-critical status poll, same behavior as before)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All Nero HTTP calls now have retry + typed error handling
- axis_sync command injection risk eliminated
- Phase 2 error infrastructure complete (all 3 plans done)

---
*Phase: 02-error-infrastructure*
*Completed: 2026-03-10*
