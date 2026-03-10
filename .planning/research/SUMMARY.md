# Research Summary: Meridian Hardening

**Domain:** Claude Code skill/workflow engine (CLI-driven Python tool with SQLite backend)
**Researched:** 2026-03-10
**Updated:** 2026-03-10 (architecture dimension -- corrected routing, database patterns, error handling)
**Overall confidence:** HIGH

## Executive Summary

Meridian's routing problem has a clear root cause: Claude Code has two separate command systems, and Meridian uses the wrong one. **Skills** (`~/.claude/skills/`) are passive, description-matched, and auto-loaded -- designed for background knowledge. **Commands** (`~/.claude/commands/<namespace>/`) are explicit, user-invoked via `/namespace:cmd` -- designed for procedural workflows. Meridian needs commands for its 13 subcommands and should keep the skill for passive project context. The fix is 13 thin command `.md` files that reference existing SKILL.md procedures via `@` paths, following the proven GSD pattern (30+ working commands on this machine).

The database layer needs a `open_project()` context manager to replace the 12+ copies of `connect(); try; finally; close()` boilerplate. It also needs `PRAGMA busy_timeout=5000` to handle concurrent subagent writes (WAL mode alone does not prevent `SQLITE_BUSY` on concurrent writers). The `connection.backup()` API provides hot backups before migrations.

Error handling should shift from ad-hoc `ValueError`/`None` returns to a structured `MeridianError` hierarchy. Logging should use stdlib `logging` to stderr, keeping stdout clean for data that command snippets parse.

All fixes are stdlib-only. No new dependencies.

## Key Findings

**Stack:** Python stdlib only. New modules: `scripts/errors.py`, `scripts/logging_config.py`, `scripts/generate_commands.py`. No external dependencies.
**Architecture:** Dual registration -- `~/.claude/commands/meridian/*.md` for explicit invocation, `~/.claude/skills/meridian/SKILL.md` for passive context. Command files are thin wrappers referencing existing skill procedures.
**Critical pitfall:** Fixing routing before the database layer means rewriting command snippets twice. Do database and errors first.

## Implications for Roadmap

Based on research, suggested phase structure:

1. **Database Foundation** - Context manager, retry logic, transaction cleanup, backup API
   - Addresses: connection boilerplate, SQLITE_BUSY crashes, scattered commits, no backup
   - Avoids: touching command/skill snippets that will change again later
   - Includes: pytest config fix (pythonpath) so new tests don't copy sys.path hack

2. **Error Infrastructure** - Structured errors, logging, HTTP retry, SQL injection fix
   - Addresses: ad-hoc error handling, print-based output, silent Nero failures, entity_type injection
   - Avoids: writing command error handling before error types exist

3. **Command Routing** - Generate 13 command .md files, update SKILL.md frontmatter, update snippets
   - Addresses: broken subcommand discovery -- all 13 commands become `/meridian:*`
   - This is the primary user-visible deliverable

4. **Test Coverage and Hardening** - New tests, N+1 fixes, known bug fixes
   - Addresses: untested modules (dispatch, export, axis_sync, auto-advance), performance
   - Avoids: blocking the routing fix on optimization work

**Phase ordering rationale:**
- Phase 1 before 2: Error module imports from db.py patterns
- Phase 2 before 3: Command procedures need error handling patterns defined
- Phase 3 before 4: Routing is the primary user-visible fix; hardening is optimization
- Phase 4 last: Tests and N+1 fixes are nice-to-haves that don't block functionality

**Research flags for phases:**
- Phase 1: Standard patterns, no additional research needed
- Phase 3: Needs end-to-end testing in Claude Code to verify all 13 commands are discoverable
- Phase 4: N+1 fix complexity depends on query patterns in resume.py and metrics.py

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Stdlib-only, no new dependencies, verified against existing code |
| Architecture (routing) | HIGH | Verified from GSD's 30+ working commands at ~/.claude/commands/gsd/ |
| Architecture (database) | HIGH | Standard Python stdlib patterns (contextlib, sqlite3 pragmas) |
| Architecture (errors) | MEDIUM | Standard pattern; specific error names are best-guess |
| Pitfalls | HIGH | Identified from direct code inspection and codebase analysis docs |

## Gaps to Address

- Exact behavior of `allowed-tools` in command frontmatter (does it restrict or suggest?)
- How many subagents Claude can spawn simultaneously (affects busy_timeout tuning)
- Whether `@` references in command files support relative paths or require absolute
- Whether the root SKILL.md passive loading conflicts with command invocation

---

*Research summary: 2026-03-10*
