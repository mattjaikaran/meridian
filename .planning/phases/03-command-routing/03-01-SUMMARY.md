---
phase: 03-command-routing
plan: 01
subsystem: tooling
tags: [cli, code-generation, slash-commands, pathlib, argparse]

requires:
  - phase: 01-database-foundation
    provides: "scripts/ directory pattern and project conventions"
provides:
  - "Command generator script (scripts/generate_commands.py)"
  - "Unit tests for generator (tests/test_generate_commands.py)"
  - "Functions: discover_skills, extract_metadata, generate_wrapper, write_commands"
  - "Functions: cleanup_orphans, verify_symlink, fix_symlink, uninstall, update_root_skill"
affects: [03-command-routing]

tech-stack:
  added: []
  patterns: ["TDD for I/O contract testing", "tmp_path fixtures for filesystem tests"]

key-files:
  created:
    - scripts/generate_commands.py
    - tests/test_generate_commands.py
  modified: []

key-decisions:
  - "Absolute paths in @ references (not tilde) matching GSD command pattern"
  - "argument-hint omitted from frontmatter when empty (cleaner output)"
  - "Root SKILL.md uses 'Available Skills' heading (not 'Commands') to avoid routing conflict"
  - "Generated marker as HTML comment before frontmatter for safe detection"

patterns-established:
  - "Generated file marker: <!-- meridian:generated --> as first line"
  - "Wrapper format: marker + frontmatter + description + @ reference to SKILL.md"
  - "Skills discovery via sorted pathlib iterdir on skills/ directory"

requirements-completed: [ROUT-01, ROUT-02, ROUT-03, ROUT-04]

duration: 2min
completed: 2026-03-11
---

# Phase 03 Plan 01: Command Generator Summary

**TDD command generator that auto-discovers 13 skills, produces .md wrappers with YAML frontmatter, and manages symlinks/orphans/uninstall**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-11T05:17:30Z
- **Completed:** 2026-03-11T05:19:49Z
- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 2

## Accomplishments
- Built complete command generator with 10 public functions covering full lifecycle
- 33 unit tests with 100% function coverage using tmp_path fixtures
- CLI with argparse: install (default), --uninstall, --fix-symlink, --all
- Full test suite (150 tests) green with zero regressions

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests** - `e4078b8` (test)
2. **GREEN: Implementation** - `827928c` (feat)

_TDD plan: tests first, then implementation to pass them._

## Files Created/Modified
- `scripts/generate_commands.py` - Command generator (294 lines, stdlib-only)
- `tests/test_generate_commands.py` - Unit tests (390 lines, 33 tests)

## Decisions Made
- Used absolute paths in @ references (`/Users/mattjaikaran/.claude/skills/meridian/...`) rather than tilde, matching GSD command pattern for reliability
- Omit `argument-hint` from frontmatter entirely when empty (rather than empty string)
- Root SKILL.md uses "Available Skills" section heading (not "Commands") to avoid routing conflict with explicit command files
- Generated marker (`<!-- meridian:generated -->`) placed as first line before frontmatter, detected by is_generated()

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Generator ready to run: `uv run python scripts/generate_commands.py`
- Plan 03-02 (if any) can use generator to produce actual command files
- End-to-end testing in Claude Code still needed (flagged in STATE.md)

---
*Phase: 03-command-routing*
*Completed: 2026-03-11*
