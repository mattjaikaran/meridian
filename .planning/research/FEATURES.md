# Feature Landscape

**Domain:** Production workflow state machine / Claude Code skill-based project management
**Researched:** 2026-03-10
**Mode:** Features dimension for hardening milestone

## Table Stakes

Features users expect from a production-quality workflow engine. Missing = the tool breaks under real use.

### Reliability & Error Handling

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Retry logic with exponential backoff (Nero HTTP) | Network transience is the norm, not the exception. A single failed HTTP call silently losing a dispatch is unacceptable. | Low | Missing | Use stdlib `time.sleep` + loop. 3 retries, 1s/2s/4s backoff. Already identified in CONCERNS.md. |
| SQLite write retry on SQLITE_BUSY | Multiple subagents writing concurrently will hit this. WAL mode helps reads but writes still serialize. | Low | Missing | Wrap `cursor.execute` in retry loop catching `sqlite3.OperationalError`. 5 retries, 100ms backoff. |
| Graceful error propagation | Functions return error dicts or silently swallow exceptions. Callers have no consistent way to distinguish success from failure. | Medium | Partial | Standardize on either exceptions (preferred for stdlib) or Result-type dicts. Pick one pattern and apply everywhere. |
| Transaction safety for multi-step state changes | Plan completion triggers auto-advance, checkpoint, and export. If export fails mid-way, state is inconsistent. | Medium | Partial | Wrap compound operations in `conn` transactions. Use `BEGIN IMMEDIATE` for write transactions. |

### Observability & Debugging

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Structured logging framework | No logging anywhere. When Nero dispatch fails, there is zero audit trail. `print()` is not logging. | Medium | Missing | Use stdlib `logging` module. File handler to `.meridian/meridian.log`. Rotate at 5MB. DEBUG/INFO/WARNING/ERROR levels. |
| Operation audit trail in DB | Know who changed what and when. Critical for debugging stale states after context resets. | Medium | Missing | Add `audit_log` table: `(id, timestamp, entity_type, entity_id, action, old_value, new_value)`. Write on every transition. |
| Debug command improvements | `/meridian:debug` exists but needs to surface more: last N transitions, failed dispatches, connection state, schema version. | Low | Partial | Enhance existing debug skill to query audit log and show recent activity. |

### Data Safety

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Database backup before destructive operations | Single SQLite file is the entire source of truth. Corruption or bad migration = total data loss. | Low | Missing | `shutil.copy2` of `state.db` to `.meridian/backups/state-{timestamp}.db` before migrations, bulk updates, or manual request. |
| Database restore from backup | Backups are useless without restore. | Low | Missing | Copy backup file back to `state.db`. Add to `/meridian:debug` as a restore subcommand. |
| Backup rotation | Don't fill disk with unlimited backups. | Low | Missing | Keep last 10 backups, delete older ones. Simple glob + sort + unlink. |

### Security Hardening

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Eliminate SQL injection surface | Dynamic f-string column/table interpolation is a ticking bomb. The `add_priority` function interpolates table names directly. | Medium | Identified | Use mapping dicts for table names. Validate column names against hardcoded allowlists in a centralized `safe_update()` helper. |
| Fix subprocess command construction | `command.split()` in axis_sync breaks on spaces in arguments. | Low | Identified | Pass args as proper list to `subprocess.run`. Never split formatted strings. |

### Testing & Quality

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Test coverage for dispatch.py | HTTP dispatch client is completely untested. Payload construction errors only caught in production. | Medium | Missing | Mock-based tests for `dispatch_plan`, `dispatch_phase`, `check_dispatch_status`. Test error handling paths. |
| Test coverage for export.py | Export format changes silently break Nero consumption. | Low | Missing | Test JSON structure, file I/O errors, empty state edge cases. |
| Test coverage for axis_sync.py | String splitting + subprocess = fragile. Needs mocked tests. | Medium | Missing | Mock `subprocess.run`, test ticket ID parsing, test space-in-name edge case. |
| Test coverage for auto-advance | `check_auto_advance` has the premature milestone_ready bug and no dedicated tests. | Medium | Missing | Test all edge cases: empty plans, mixed terminal states, milestone readiness timing. |
| Migration path tests | No test that v1 -> v2 upgrade actually works. Future migrations need regression testing. | Low | Missing | Create v1 database fixture, run migration, verify schema and data integrity. |
| Fix test infrastructure | `sys.path` hacking in every test file is fragile. | Low | Identified | Add `pythonpath = ["."]` to `pyproject.toml` pytest config. Remove `sys.path.insert` from all test files. |

### Code Quality

| Feature | Why Expected | Complexity | Status | Notes |
|---------|--------------|------------|--------|-------|
| Connection context manager | Same 10-line boilerplate in 10+ locations. Any connection setup change must be replicated everywhere. | Low | Missing | `@contextmanager def open_project(project_dir=None)` in `scripts/db.py` that yields `(conn, project)`. |
| Fix N+1 query patterns | `generate_resume_prompt`, `compute_progress`, `export_state` all iterate entities and query children in a loop. | Medium | Identified | Single JOIN queries with GROUP BY. Not critical at current scale but prevents future pain. |

## Differentiators

Features that make Meridian special compared to generic task management. These leverage the unique Claude Code + state machine + multi-machine architecture.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Deterministic resume from any state** | Already exists and is the core value prop. No other tool rebuilds exact context from DB state after a session reset. Harden this, don't replace it. | N/A (exists) | Ensure resume prompt generation is tested exhaustively for all state combinations. |
| **Wave-based parallel execution** | Plans in the same wave run in parallel via subagents. Wave N+1 blocks on wave N. This is genuine workflow orchestration, not just a task list. | N/A (exists) | Add wave-level status tracking and failure handling (what happens when 1 of 3 parallel plans fails?). |
| **Two-machine dispatch model** | MacBook Pro for interactive work, Mac Mini (Nero) for autonomous execution. Real distributed workflow, not just local scripting. | N/A (exists) | Needs retry logic and status reconciliation to be production-grade. |
| **Smart checkpoint triggers** | 6 trigger types including auto_context_limit based on token estimation. Proactive context management rather than reactive. | N/A (exists) | Could add 7th trigger: "time elapsed since last checkpoint" for long-running sessions. |
| **Integrated code review pipeline** | Two-stage review (spec compliance + code quality) as part of the workflow, not a separate tool. | N/A (exists) | Consider adding review result persistence — store review findings in DB, not just in conversation. |
| **Review result persistence** | Store spec review and code quality review findings in the database. Enables trend analysis (recurring issues), provides context on resume, and creates an audit trail of what was reviewed. | Medium | New `review_result` table: `(id, plan_id, review_type, verdict, findings_json, reviewer_prompt_hash, created_at)`. |
| **Stall detection and auto-recovery** | Detect when a phase or plan has been in `executing` state too long without progress. Surface it in status/dashboard. Optionally auto-checkpoint and suggest retry. | Medium | Use timestamps already tracked. Define "stale" threshold (e.g., 30 min no state change). |
| **Workflow templates** | Pre-built phase/plan structures for common project types (new feature, bug fix, refactor, library upgrade). Reduces planning overhead for repetitive project shapes. | Medium | JSON template files in `templates/`. `/meridian:init` offers template selection. Keep it simple — 3-4 templates max. |
| **Decision log with rationale** | The `decision` table exists but isn't well-utilized. Make it a first-class feature: every architectural decision recorded with context, alternatives considered, and rationale. Surfaces in resume prompts. | Low | Already has the table. Enhance `/meridian:plan` to prompt for decisions. Include in resume output. |
| **Dependency graph between plans** | Plans within a wave are independent, but sometimes plan B truly depends on plan A's output (e.g., "create API" before "write tests for API"). Explicit dependency declaration beyond wave ordering. | High | Would require DAG resolution in `compute_next_action`. Waves already handle 90% of cases — only add if wave ordering proves insufficient. |

## Anti-Features

Things to deliberately NOT build. These would add complexity without proportional value for a single-developer local tool.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Web UI / dashboard server** | Claude Code IS the interface. Building a separate web UI doubles the maintenance surface for no user. The dashboard and roadmap skills already render in the terminal. | Keep `/meridian:dashboard` and `/meridian:roadmap` as terminal-rendered views. If visualization is needed, export data and use an external tool. |
| **Multi-user / authentication** | Single-developer tool. Adding auth, permissions, and user management is massive complexity for zero value. | If sharing state is needed, share the SQLite file or the git repo. |
| **PostgreSQL backend** | SQLite is perfect for single-user, single-machine workflows. PostgreSQL adds a server dependency, connection management, and deployment complexity. | Optimize SQLite usage (WAL mode, retry logic, proper transactions). Only revisit if multi-machine concurrent writes become a real problem. |
| **Plugin / extension system** | Premature abstraction. The codebase has 8 scripts and 13 skills. A plugin architecture would add indirection without enough consumers to justify it. | Add features directly to the scripts. Refactor when there are 3+ instances of "I wish I could extend this." |
| **Real-time notifications / webhooks** | Polling Nero status via `/meridian:status` or sync is sufficient. Push notifications add complexity (what receives them? Claude Code doesn't have a listener). | Keep pull-based sync model. Enhance sync frequency if needed. |
| **Kanban board / visual workflow editor** | Terminal-based tool. Visual editors require a GUI framework or web server. The state machine transitions are well-defined in code. | Keep transitions code-defined. The `/meridian:roadmap` skill provides sufficient visual overview. |
| **AI-powered auto-planning** | Meridian orchestrates execution, it doesn't replace human judgment on what to build. Auto-generating plans from vague descriptions would produce low-quality plans that need manual correction anyway. | Keep planning as a human-guided process with `/meridian:plan`. The tool's job is to execute plans reliably, not generate them. |
| **tiktoken integration** | The rough 0.3 tokens/char estimate is good enough for checkpoint trigger heuristics. Exact token counting adds a dependency for marginal accuracy improvement. | Keep the heuristic. If it causes premature or late checkpoints, tune the constant. |
| **Undo / rollback for state transitions** | State machines are intentionally forward-only. Adding undo means every transition needs a reverse mapping, every side effect needs to be reversible. Massive complexity. | Use the `blocked` state as an escape hatch. Use DB backup/restore for catastrophic mistakes. |
| **Custom state machine definitions** | Letting users define their own states and transitions sounds flexible but creates untestable permutations. The current 8 phase states and 6 plan states cover real workflows well. | Keep states fixed. If a new state is genuinely needed, add it to the code with proper tests. |

## Feature Dependencies

```
Retry logic (Nero HTTP) ─┐
                          ├──> Reliable Nero dispatch (production-grade)
SQLite write retry ───────┘

Structured logging ──────> Audit trail in DB (logging provides the framework, audit provides queryable history)

DB backup ──────> DB restore (restore is useless without backup, backup is useful alone)

Connection context manager ──────> Cleaner test infrastructure (tests benefit from consistent connection handling)

SQL injection fix ──────> Safe update helper ──────> All update functions use it

Test infrastructure fix (pytest config) ──────> All new test files (write tests properly from the start)
```

## MVP Recommendation for Hardening Milestone

**Priority 1 — Reliability (blocks everything else):**
1. SQLite write retry on SQLITE_BUSY
2. Nero HTTP retry with exponential backoff
3. Transaction safety for compound operations
4. Database backup before migrations

**Priority 2 — Observability (needed to debug Priority 1):**
5. Structured logging framework (stdlib `logging`)
6. Enhanced `/meridian:debug` output

**Priority 3 — Security (known vulnerabilities):**
7. Eliminate SQL injection surface (safe_update helper)
8. Fix subprocess command construction in axis_sync

**Priority 4 — Test Coverage (proves everything works):**
9. Fix test infrastructure (pytest config)
10. Tests for dispatch.py, export.py, auto-advance
11. Migration path tests

**Priority 5 — Code Quality (reduces future maintenance):**
12. Connection context manager
13. N+1 query fixes

**Defer to next milestone:**
- Review result persistence
- Stall detection
- Workflow templates
- Dependency graph between plans
- Audit trail table (nice-to-have, not blocking)

## Sources

- Primary: Meridian codebase analysis (`.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/CONCERNS.md`)
- Domain knowledge: Production workflow engine patterns (Temporal, Airflow, Prefect, XState — adapted for single-user CLI context)
- Confidence: HIGH for table stakes and anti-features (well-established patterns). MEDIUM for differentiators (depends on actual usage patterns revealing what matters).

---

*Feature landscape: 2026-03-10*
