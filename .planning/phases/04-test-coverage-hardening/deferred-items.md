# Deferred Items - Phase 04

## Pre-existing Test Failure

**Test:** `tests/test_state.py::TestNeroDispatch::test_update_with_empty_string_status_not_updated`
**Issue:** Test documents "buggy behavior" (QUAL-04 truthiness check on status=''), but commit `e5f9a54` (fix(04-04)) already fixed the bug in `state.py`. The test now fails because it expects the old buggy behavior.
**Fix needed:** Update test to expect the corrected behavior (status='' should be rejected by CHECK constraint, or the update function should validate status values before passing to SQL).
**Not caused by:** Plan 04-03 changes (N+1 query fixes).
