# Meridian TODO

## v3.0 Harness Compatibility & CLI (CURRENT)

### Phase 44: Standalone CLI Entrypoint — START HERE
Build a `meridian` CLI so the tool works from any harness (Cursor, Aider, CI/CD, shell scripts).
- [ ] Create `scripts/cli.py` with `argparse` subcommands matching all major skills
- [ ] Register entrypoint in `pyproject.toml`: `[project.scripts] meridian = "scripts.cli:main"`
- [ ] Subcommands: `status`, `next`, `execute`, `plan`, `resume`, `ship`, `note`, `fast`, `dashboard`
- [ ] Subcommands: `init`, `checkpoint`, `pause`, `review`, `validate`, `config`, `workstream`
- [ ] `--json` flag for machine-readable output on all commands
- [ ] `--project-dir` flag on all commands (default: cwd)
- [ ] Tests: `tests/test_cli.py` covering all subcommands
- [ ] Update README install section with `meridian` binary usage

### Phase 45: MCP Server Mode
Expose Meridian as an MCP server so Claude.ai, Cursor, Windsurf, and Copilot can use it natively.
- [ ] Create `scripts/mcp_server.py` using `mcp` Python SDK (add as optional dep)
- [ ] Tools: `meridian_status`, `meridian_next`, `meridian_plan`, `meridian_execute`, `meridian_resume`
- [ ] Tools: `meridian_note`, `meridian_checkpoint`, `meridian_fast`, `meridian_review`
- [ ] Resources: current project state, active phase, pending plans
- [ ] Register in `pyproject.toml`: `[project.scripts] meridian-mcp = "scripts.mcp_server:main"`
- [ ] Optional dep: `[project.optional-dependencies] mcp = ["mcp>=1.0"]`
- [ ] Document MCP setup in `docs/harness-compatibility.md`
- [ ] Tests: `tests/test_mcp_server.py`

### Phase 46: SKILL.md Harness-Agnostic Fallbacks
Every skill that calls `Agent tool`, `AskUserQuestion`, or `subagent_type` must include harness-agnostic fallbacks.
- [ ] Audit all 50 Claude Code-specific references across 15 skills
- [ ] `execute/SKILL.md` — Agent tool dispatch step
- [ ] `plan/SKILL.md` — context-gatherer and AskUserQuestion deep discovery steps
- [ ] `review/SKILL.md` — 3-parallel-agent party mode
- [ ] `scan/SKILL.md` — 4 parallel agents
- [ ] `spec-phase/SKILL.md` — AskUserQuestion interview rounds
- [ ] `ai-phase`, `ui-phase`, `secure-phase`, `research-phase`, `sketch`, `discuss`, `autonomous`
- [ ] Standardize fallback format: `**[Claude Code]** ... **[Other harnesses]** ...`

### Phase 47: Cursor & Aider Adapter Files
- [ ] Create `.cursorrules` with Meridian workflow conventions and skill routing
- [ ] Create `docs/harness/cursor.md` — Cursor-specific setup and usage
- [ ] Create `docs/harness/aider.md` — `! meridian <cmd>` pattern, aider conventions
- [ ] Create `docs/harness/copilot.md` — `#file:` convention guide
- [ ] Create `docs/harness/windsurf.md` — Cascade agent integration
- [ ] Create `docs/harness-compatibility.md` — master compatibility matrix

## v3.0 Bug Fixes & Tech Debt

### Phase 48: Known Bug Fixes (from CONCERNS.md 2026-03-10)
- [ ] Fix `check_auto_advance` premature `milestone_ready=True` — requires phase `complete`, not `verifying` (`scripts/state.py:589-596`)
- [ ] Fix `update_nero_dispatch` silent skip on empty string — `if status is not None:` not `if status:` (`scripts/state.py:528-529`)
- [ ] Fix `_run_pm_command` string splitting — proper list args, not `command.split()` (`scripts/axis_sync.py:41,131-133`)
- [ ] Add retry logic to Nero HTTP calls — 3 retries with exponential backoff (`scripts/dispatch.py`, `scripts/sync.py`)
- [ ] Add optional Nero auth — `nero_api_key` field in project table, `Authorization: Bearer` header
- [ ] Add regression tests for all fixed bugs

### Phase 49: SQL & Performance
- [ ] Fix f-string table name in `add_priority` — use mapping dict (`scripts/state.py:621`)
- [ ] Fix N+1 in `generate_resume_prompt` — single JOIN query (`scripts/resume.py:162-168`)
- [ ] Fix N+1 in `compute_progress` — aggregated query (`scripts/metrics.py:252-253`)
- [ ] Fix N+1 in `export_state` — bulk fetch then assemble in Python (`scripts/export.py:38-44`)
- [ ] Fix `sys.path` hacking in tests — add `pythonpath = ["."]` to pyproject.toml pytest config
- [ ] Move `from datetime import timedelta` to module level (`scripts/metrics.py:217`)

### Phase 50: Refactor `compute_next_action`
- [ ] Extract each status handler into its own function (`_handle_executing`, `_handle_verifying`, etc.)
- [ ] Build `NEXT_ACTION_HANDLERS = {status: handler_fn}` dispatch table (`scripts/state.py:634-808`)
- [ ] Add missing edge case tests: multiple phases in non-terminal states simultaneously
- [ ] All existing `TestNextAction` tests must still pass

## v3.0 Documentation & Portfolio Polish

### Phase 51: README & Stats Update
- [ ] Update hero stats: "57 commands" (not 39), accurate test count, schema v14
- [ ] Add all 18 missing commands to the commands table
- [ ] Rewrite portfolio pitch — lead with deterministic resume, wave execution, quality gates
- [ ] Add "What makes this different" section vs GSD/BMAD/Hermes/Superpowers
- [ ] Add harness compatibility matrix

### Phase 52: Root SKILL.md Scripts Section
- [ ] Replace 10-item list with complete organized listing of all 75+ modules
- [ ] Group by category: Core / Execution / Workflow Modes / Review & Metrics / Integration / Utilities
- [ ] Update available skills list (missing: ai-phase, research-phase, spec-phase, sketch, ultraplan, etc.)

### Phase 53: CHANGELOG for M7/M8 (phases 27-43)
- [ ] v2.0 entry — thread, health, spike, forensics
- [ ] v2.1 entry — analyze-deps, learn --extract, milestone lifecycle, research-phase, spec-phase
- [ ] v2.2 entry — ui-phase, sketch, ai-phase, secure-phase, scale-adaptive planning, ultraplan, party review
- [ ] v2.3 entry — workstream system, schema v14
- [ ] Consistent version number across README, SKILL.md, pyproject.toml

### Phase 54: CONCERNS.md Refresh
- [ ] Re-audit each concern — mark resolved, update unresolved, document new ones from M7/M8
- [ ] Update analysis date to 2026-05-01

### Phase 55: Persona Prompt Enrichment
- [ ] Enrich `prompts/pm.md` — specific failure modes, product heuristics
- [ ] Enrich `prompts/architect.md` — system design anti-patterns, specific things to flag
- [ ] Enrich `prompts/qa.md` — edge case patterns, test type checklist
- [ ] Enrich `prompts/security.md` — OWASP top 10, specific vulnerability patterns
- [ ] Enrich `prompts/ux.md` — accessibility heuristics, interaction design patterns

## Stats (as of 2026-05-01)
- Tests: 1,058 passing
- Python modules: 75+ in scripts/
- Slash commands: 57
- Schema version: v14
- Milestones shipped: v1.0–v2.3 (7 milestones, 43 phases)
