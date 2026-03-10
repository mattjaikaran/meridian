# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** SQLite-backed state machine with command-driven workflow orchestration

**Key Characteristics:**
- All state lives in a single SQLite database per project (`.meridian/state.db`)
- Deterministic state transitions enforced by Python transition maps
- Claude Code Skills framework provides slash-command routing via `SKILL.md` files
- Subagent architecture: each plan executes in a fresh 200k-token context via Claude's Agent tool
- Stdlib-only Python (no third-party dependencies) — uses `sqlite3`, `json`, `pathlib`, `subprocess`, `urllib`
- Two-machine model: MacBook Pro (interactive, Meridian) dispatches work to Mac Mini (autonomous, Nero)

## Layers

**Command Layer (Skills):**
- Purpose: Route user slash commands to procedures; define step-by-step execution instructions
- Location: `skills/*/SKILL.md` (13 skill files), `SKILL.md` (root entry point)
- Contains: Markdown-defined procedures with embedded Python code snippets that Claude executes
- Depends on: Scripts layer (all Python functions), Prompts layer (subagent instructions)
- Used by: Claude Code runtime — each `/meridian:*` command loads the corresponding `SKILL.md`

**Scripts Layer (Core Logic):**
- Purpose: All business logic — CRUD, state transitions, metrics, sync, export
- Location: `scripts/`
- Contains: 8 Python modules, stdlib-only
- Depends on: SQLite database (`sqlite3` stdlib module)
- Used by: Command layer (via `uv run --project ~/dev/meridian python -c "..."`)

**Prompts Layer (Subagent Templates):**
- Purpose: Instruction templates for fresh-context subagents
- Location: `prompts/`
- Contains: 5 markdown files — implementer, spec-reviewer, code-quality-reviewer, context-gatherer, resume-template
- Depends on: Nothing (pure templates with `{placeholder}` variables)
- Used by: Command layer — `/meridian:execute` fills templates and dispatches via Claude's Agent tool

**Reference Layer (Documentation):**
- Purpose: Detailed protocol specifications for state machines, discipline enforcement, and integrations
- Location: `references/`
- Contains: 4 markdown files — state-machine, discipline-protocols, nero-integration, axis-integration
- Depends on: Nothing (pure documentation)
- Used by: Command layer and prompts layer reference these for protocol details

**Data Layer (SQLite):**
- Purpose: Single source of truth for all workflow state
- Location: `.meridian/state.db` (per-project, created by `/meridian:init`)
- Contains: 8 tables — `project`, `milestone`, `phase`, `plan`, `checkpoint`, `decision`, `nero_dispatch`, `quick_task` + `schema_version`
- Depends on: Nothing
- Used by: Scripts layer exclusively (all access through `scripts/db.py` connection helpers)

## Data Flow

**Plan Execution Flow:**

1. User invokes `/meridian:execute` — Claude loads `skills/execute/SKILL.md`
2. `compute_next_action()` in `scripts/state.py` queries SQLite to determine the next pending plan
3. Phase transitions to `executing` via `transition_phase()` in `scripts/state.py`
4. Plan transitions to `executing` via `transition_plan()` in `scripts/state.py`
5. Claude spawns a subagent with `prompts/implementer.md` template filled with plan details
6. Subagent implements code, runs tests, commits
7. On success: `transition_plan(conn, plan_id, "complete", commit_sha=...)` in `scripts/state.py`
8. `check_auto_advance()` in `scripts/state.py` evaluates if all plans are done — auto-advances phase to `verifying`
9. Two-stage review via spec-reviewer and code-quality-reviewer subagents
10. Phase transitions through `reviewing` to `complete`
11. `export_state()` in `scripts/export.py` writes `.meridian/meridian-state.json` for Nero consumption

**Resume Flow (Context Recovery):**

1. User invokes `/meridian:resume` after context reset
2. `generate_resume_prompt()` in `scripts/resume.py` queries SQLite
3. Builds deterministic markdown prompt from discrete DB queries (position, phases, plans, decisions, git state, next action)
4. Same database state always produces identical resume prompt — no LLM-generated prose

**Bidirectional Nero Sync Flow:**

1. `pull_dispatch_status()` in `scripts/sync.py` polls Nero's `/rpc` endpoint for all active dispatches
2. When Nero reports `completed`, auto-transitions local plan to `complete` via `transition_plan()`
3. When Nero reports `failed`, marks local plan as `failed`
4. `push_state_to_nero()` in `scripts/sync.py` exports pending work as tickets to Nero's scheduler
5. `sync_all()` combines both operations in a single call

**State Management:**
- All state in SQLite with WAL mode and foreign keys enforced
- State transitions validated by Python dicts (`PHASE_TRANSITIONS`, `PLAN_TRANSITIONS`, `MILESTONE_TRANSITIONS`) in `scripts/state.py`
- Invalid transitions raise `ValueError` — no silent failures
- Timestamps (`started_at`, `completed_at`) set automatically on relevant transitions
- JSON fields (lists stored as JSON strings) for `tech_stack`, `acceptance_criteria`, `files_to_create`, `files_to_modify`, `decisions`, `blockers`

## Key Abstractions

**Entity Hierarchy:**
- Purpose: Organizes work into a tree: Project > Milestone > Phase > Plan
- Examples: `scripts/state.py` (CRUD for all entities), `scripts/db.py` (schema definition)
- Pattern: Each entity has its own state machine with enforced transitions. Phases have 8 states, plans have 6 states, milestones have 4 states.

**Wave System:**
- Purpose: Group plans within a phase for parallel/sequential execution
- Examples: `get_plans_by_wave()` in `scripts/state.py`, wave ordering in `compute_next_action()`
- Pattern: Plans in the same wave execute in parallel. Wave N+1 blocks until all wave N plans are complete/skipped. Failed plans in wave N block wave N+1.

**Next Action Computation:**
- Purpose: Deterministically compute what should happen next from current state
- Examples: `compute_next_action()` in `scripts/state.py` (lines 634-808)
- Pattern: Priority-ordered evaluation — finds active milestone, finds current phase, routes based on phase status, within executing phase finds next pending plan respecting wave order. Returns a dict with `action` type and context.

**Checkpoint System:**
- Purpose: Save points for context recovery after session resets
- Examples: `create_checkpoint()` in `scripts/state.py`, checkpoint triggers in `references/state-machine.md`
- Pattern: Captures current position (milestone, phase, plan), git state (branch, SHA, dirty), decisions, blockers, and estimated token usage. Six trigger types: manual, auto_context_limit, plan_complete, phase_complete, error, pause.

## Entry Points

**Skill Router (`SKILL.md`):**
- Location: `SKILL.md` (root)
- Triggers: Any `/meridian:*` command in Claude Code
- Responsibilities: Lists all available commands and routes to specific `skills/*/SKILL.md` files

**Individual Skills (`skills/*/SKILL.md`):**
- Location: `skills/init/SKILL.md`, `skills/plan/SKILL.md`, `skills/execute/SKILL.md`, etc. (13 total)
- Triggers: Specific `/meridian:<name>` slash command
- Responsibilities: Step-by-step procedures with embedded Python snippets that Claude executes via `uv run --project ~/dev/meridian python -c "..."`

**Script CLI Entry Points:**
- Location: `if __name__ == "__main__":` blocks in `scripts/db.py`, `scripts/resume.py`, `scripts/export.py`, `scripts/dispatch.py`, `scripts/sync.py`, `scripts/axis_sync.py`, `scripts/context_window.py`
- Triggers: Direct Python execution (`uv run python scripts/db.py init`)
- Responsibilities: CLI wrappers around library functions for manual/debugging use

**Test Entry Point:**
- Location: `tests/test_state.py`, `tests/test_resume.py`, `tests/test_metrics.py`, `tests/test_sync.py`
- Triggers: `uv run pytest tests/ -v`
- Responsibilities: Verify state machine transitions, resume generation, metrics computation, sync behavior

## Error Handling

**Strategy:** Fail-fast with `ValueError` for invalid state transitions; graceful degradation for external services

**Patterns:**
- State transition validation: `transition_phase()`, `transition_plan()`, `transition_milestone()` raise `ValueError` if the requested transition is not in the valid transitions dict — e.g., `"Invalid phase transition: planned -> executing. Valid: ['context_gathered', 'blocked']"`
- External service failures (Nero RPC): `_nero_rpc()` in `scripts/sync.py` catches `URLError`, `TimeoutError`, `JSONDecodeError` and returns `None` — callers check for `None` and log "unreachable"
- Git helper failures: `_get_git_state()` in `scripts/state.py` wraps all subprocess calls in try/except, returns `(None, None, False)` on failure
- Database connection: `connect()` in `scripts/db.py` creates parent directories automatically (`mkdir parents=True, exist_ok=True`)
- Subagent failures: Plans transition to `failed` status with `error_message` recorded; can be retried via `failed -> pending` or `failed -> executing`

## Cross-Cutting Concerns

**Logging:** No formal logging framework. Output is via `print()` in CLI entry points and via Claude Code's conversation output from SKILL.md procedures.

**Validation:** State transition validation via Python dicts in `scripts/state.py`. Schema-level CHECK constraints in SQLite for status columns. `VALID_PRIORITIES` tuple for priority validation.

**Authentication:** No authentication layer. Nero RPC calls are unauthenticated HTTP POST to configured endpoint. Axis sync runs local shell commands via `pm.sh`.

**Serialization:** JSON used throughout for structured data. `json.dumps()` for storing lists in SQLite text columns. `json.loads()` for reading them back. `default=str` used in export for datetime handling.

**Time Handling:** UTC timestamps throughout. `_now()` helper in `scripts/state.py` returns `"%Y-%m-%dT%H:%M:%SZ"` format. SQLite `datetime('now')` for defaults. `_parse_ts()` in `scripts/metrics.py` handles multiple timestamp formats for robustness.

---

*Architecture analysis: 2026-03-10*
