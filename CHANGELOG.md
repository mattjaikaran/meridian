# Changelog

All notable changes to Meridian.

## v0.5.0 — 2026-03-27

### Breaking Changes
- All SKILL.md files now use `$MERIDIAN_HOME` instead of hardcoded `~/dev/meridian`. Set `export MERIDIAN_HOME=<path>` in your shell profile.

### Fixed
- Git commands (`_run_git`) now have 30s timeout — prevents indefinite hangs on network mounts
- DB corruption detected at connect time with actionable error message and backup guidance
- Shell injection vector removed — `shell=True` replaced with `shlex.split` in gates.py and nyquist.py
- `safe_update()` now validates `id_column` against allowlist, closing theoretical SQL injection

### Added
- Schema v6 migration: indexes on FK and status columns for query performance
- `generate_commands.py` warns if `$MERIDIAN_HOME` is unset or mismatched
- MERIDIAN_HOME documented in README, SKILL.md, and install instructions

### Updated
- PROJECT.md and ROADMAP.md reflect current state (928 tests, 42 modules, 32 commands, v1.0-v1.5 shipped)

### Stats
- 928 tests passing across 45 test files
- 42 Python modules, 32 slash commands
- Schema v6

---

## v1.5.0 — 2026-03-20

### Added
- **Learnings auto-capture** — auto-suggest from failures and review rejections
- **HTML dashboard** (`/meridian:dashboard --html`) — standalone dark-themed report
- **Freeze integration** — check freeze state before subagent file edits
- **Test coverage audit** — scripts vs tests coverage mapping
- **Context bridge** — matt-stack and external context import
- **Retro auto-scheduling** — prompt for retro every N completed phases

### Stats
- 928 tests passing (+88 new)
- 6 new Python modules

---

## v1.4.0 — 2026-03-20

### Added
- **Execution learning** (`/meridian:learn`) — persistent rules from patterns, injected into subagent prompts
- **Edit scope lock** (`/meridian:freeze`) — advisory directory lock via settings
- **Structured retrospective** (`/meridian:retro`) — velocity trends, shipping streaks, action items
- **Deep discovery** (`--deep` flag on `/meridian:plan`) — 5 forcing questions before brainstorming
- **Session awareness** — PID-based concurrent session detection
- **Cross-model review** (`--cross-model` on `/meridian:review`) — secondary AI CLI review pass
- **Schema v5** — learning table, review.model column

### Stats
- 840 tests passing (+100 new)
- 6 new Python modules, 3 new slash commands

---

## v1.3.0 — 2026-03-20

### Added
- **Developer profiling** (`/meridian:profile`) — analyze project patterns and generate USER-PROFILE.md
- **Backlog seeds** (`/meridian:seed`) — capture future ideas with trigger conditions (`after_phase`, `after_milestone`)
- **Discussion audit trail** — append-only DISCUSSION-LOG.md linking topics to decision IDs
- **Interactive executor** (`--interactive` flag) — pause after each plan for user review (approve/reject/modify)
- **Node repair operators** — automatic recovery when plans fail: RETRY → DECOMPOSE → PRUNE with configurable budget
- **MCP tool discovery** — scan available MCP servers, score relevance, include in subagent prompts
- **Context window awareness** — detect context size, allocate budget (system/plan/code/reserve), trim to fit

### Stats
- 740 tests passing (+160 new)
- 7 new Python modules
- 2 new slash commands (`/meridian:profile`, `/meridian:seed`)

---

## v1.2.0 — 2026-03-20

### Added
- **Fast tasks** (`/meridian:fast`) — inline trivial tasks that skip planning entirely, with complexity heuristic
- **Freeform router** (`/meridian:do`) — natural language to correct `/meridian:*` command with confidence scoring
- **Note capture** (`/meridian:note`) — append, list, and promote ideas to tasks in `.meridian/notes.md`
- **Auto-advance** (`/meridian:next`) — detect workflow state and advance to next logical step
- **Regression gate** — run prior phases' test suites before execution; blocks on failure
- **Requirements coverage gate** — verify all phase requirements covered by at least one plan
- **Stub detection** — scan for TODO, FIXME, NotImplementedError, pass-only functions after execution
- **UAT audit** (`/meridian:audit-uat`) — cross-phase verification debt report
- **Session handoff** (`/meridian:pause`) — structured HANDOFF.json consumed by `/meridian:resume`
- **Debug knowledge base** — append resolved sessions to `.meridian/debug-kb.md` with dedup and search
- **Decision IDs** — unique DEC-NNN identifiers with plan linking via junction table
- **Security module** — centralized `validate_path()`, `safe_json_loads()`, `validate_field_name()`, `sanitize_shell_arg()`
- **PR branch** (`/meridian:pr-branch`) — create clean branch filtering `.planning/` and `.meridian/` commits
- **Schema v4** — decision_id column, plan_decision junction table, backfill migration

### Stats
- 580 tests passing (+202 new)
- 10 new Python modules
- 7 new slash commands

---

## v1.1.0 — 2026-03-20

### Added
- **Roadmap automation** — auto-sync ROADMAP.md checkboxes and progress table from DB state transitions
- **Nyquist validation engine** — parse VALIDATION.md, run test commands, update frontmatter with results
- **Backfill validation** — retroactively fill validation gaps for phases that skipped validation
- **Verify-phase skill** (`/meridian:verify-phase`) — Nyquist compliance check on any phase

### Fixed
- VALIDATION.md filename mismatch — engine now globs for `*VALIDATION.md` matching `NN-VALIDATION.md` convention
- Tests hardened to use real `NN-VALIDATION.md` naming instead of plain `VALIDATION.md`
- E501 line-length violations in `db.py` and `generate_commands.py`

### Stats
- 378 tests passing (+161 new)
- 4 new Python modules

---

## v1.0.0 — 2026-03-11

### Added
- **Core state machine** — Project > Milestone > Phase > Plan hierarchy with enforced transitions
- **13 slash commands** — init, plan, execute, resume, status, dashboard, roadmap, dispatch, review, ship, debug, quick, checkpoint
- **Deterministic resume** — SQLite-backed prompt generation (same state = same prompt)
- **Fresh-context subagents** — 200k tokens per plan, no context rot
- **Wave-based execution** — parallel plans within waves, sequential waves
- **Two-stage code review** — spec compliance then code quality
- **TDD enforcement** — embedded in subagent prompts
- **PM metrics** — velocity, cycle times, stalls, forecasts, progress
- **Nero dispatch** — bidirectional sync with autonomous executor
- **Axis PM sync** — ticket creation and status sync
- **Auto-advancement** — plans completing auto-transitions phases
- **Priority system** — critical/high/medium/low on phases and plans
- **Context window monitoring** — token estimation with checkpoint triggers
- **Command generator** — auto-generates Claude Code wrappers from SKILL.md definitions
- **`open_project()` context manager** — WAL mode, retry, backup, busy tolerance
- **`MeridianError` hierarchy** — structured errors with specific subclasses
- **SQL injection prevention** — `safe_update()` with column allowlists

### Stats
- 217 tests across 10 test files
- 6,227 lines Python
- Schema v2
