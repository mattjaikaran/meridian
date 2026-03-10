# Codebase Structure

**Analysis Date:** 2026-03-10

## Directory Layout

```
meridian/
├── SKILL.md                          # Root skill entry point — command router
├── pyproject.toml                    # uv project config, ruff settings
├── README.md                         # Full documentation with architecture, commands, schema
├── LICENSE                           # MIT license
├── .gitignore                        # Excludes .meridian/, .venv/, etc.
├── scripts/                          # Core Python modules (all business logic)
│   ├── __init__.py                   # Empty package init
│   ├── db.py                         # Schema, migrations, connection helpers
│   ├── state.py                      # CRUD, transitions, next-action, auto-advance
│   ├── resume.py                     # Deterministic resume prompt generator
│   ├── export.py                     # SQLite → JSON export
│   ├── dispatch.py                   # Nero HTTP dispatch client (push)
│   ├── sync.py                       # Bidirectional Nero sync (pull + push)
│   ├── metrics.py                    # PM metrics: velocity, stalls, forecasts, progress
│   ├── axis_sync.py                  # Axis PM ticket sync
│   └── context_window.py            # Token estimation + checkpoint triggers
├── prompts/                          # Subagent instruction templates
│   ├── implementer.md                # TDD implementation agent
│   ├── spec-reviewer.md              # Spec compliance review agent
│   ├── code-quality-reviewer.md      # Code quality review agent
│   ├── context-gatherer.md           # Project analysis agent
│   └── resume-template.md           # Resume prompt structure reference
├── references/                       # Protocol specifications
│   ├── state-machine.md              # State transitions, rules, auto-advance, priority
│   ├── discipline-protocols.md       # TDD, debugging, verification, review protocols
│   ├── nero-integration.md           # Dispatch + bidirectional sync protocol
│   └── axis-integration.md          # PM sync protocol
├── skills/                           # Individual slash command definitions
│   ├── init/SKILL.md                 # /meridian:init
│   ├── plan/SKILL.md                 # /meridian:plan
│   ├── execute/SKILL.md              # /meridian:execute
│   ├── resume/SKILL.md               # /meridian:resume
│   ├── status/SKILL.md               # /meridian:status
│   ├── dashboard/SKILL.md            # /meridian:dashboard
│   ├── roadmap/SKILL.md              # /meridian:roadmap
│   ├── dispatch/SKILL.md             # /meridian:dispatch
│   ├── review/SKILL.md               # /meridian:review
│   ├── ship/SKILL.md                 # /meridian:ship
│   ├── debug/SKILL.md                # /meridian:debug
│   ├── quick/SKILL.md                # /meridian:quick
│   └── checkpoint/SKILL.md           # /meridian:checkpoint
├── tests/                            # pytest test suite
│   ├── __init__.py                   # Empty package init
│   ├── test_state.py                 # 33 tests — CRUD, transitions, next-action
│   ├── test_resume.py                # 9 tests — deterministic prompt generation
│   ├── test_metrics.py               # 18 tests — velocity, stalls, forecasts, progress
│   └── test_sync.py                 # 15 tests — pull, push, sync, dispatch summary
└── .planning/                        # GSD planning documents (this directory)
    └── codebase/                     # Codebase analysis docs
```

## Directory Purposes

**`scripts/`:**
- Purpose: All Python business logic — the only executable code in the project
- Contains: 8 Python modules + `__init__.py`
- Key files: `scripts/state.py` (largest, ~880 lines — all CRUD, transitions, next-action), `scripts/db.py` (schema + migrations), `scripts/metrics.py` (PM metrics engine)

**`skills/`:**
- Purpose: Claude Code skill definitions — one SKILL.md per slash command
- Contains: 13 subdirectories, each with a single `SKILL.md` file
- Key files: `skills/execute/SKILL.md` (most complex procedure), `skills/init/SKILL.md` (project setup), `skills/plan/SKILL.md` (planning workflow)

**`prompts/`:**
- Purpose: Template markdown files filled with plan/phase data and passed to Claude subagents
- Contains: 5 markdown files with `{placeholder}` variables
- Key files: `prompts/implementer.md` (TDD implementation instructions), `prompts/context-gatherer.md` (deep project analysis)

**`references/`:**
- Purpose: Detailed protocol specifications that skills and prompts reference
- Contains: 4 markdown files
- Key files: `references/state-machine.md` (canonical state transition rules), `references/discipline-protocols.md` (TDD, debugging, review enforcement)

**`tests/`:**
- Purpose: pytest test suite with in-memory SQLite databases
- Contains: 4 test files + `__init__.py`
- Key files: `tests/test_state.py` (33 tests, most comprehensive), `tests/test_metrics.py` (18 tests)

**`.meridian/` (per-project, not in this repo):**
- Purpose: Runtime data directory created by `/meridian:init` in target projects
- Contains: `state.db` (SQLite database), `meridian-state.json` (exported state for Nero)
- Generated: Yes, by `scripts/db.py:init()`
- Committed: No — added to `.gitignore`

## Key File Locations

**Entry Points:**
- `SKILL.md`: Root skill entry point, lists all `/meridian:*` commands and routes to individual skills
- `skills/*/SKILL.md`: Individual command procedures with embedded Python snippets

**Configuration:**
- `pyproject.toml`: Python project config — requires Python 3.11+, ruff lint settings (line-length 100, py311 target, rules E/F/I/N/W/UP)
- `.gitignore`: Excludes `.meridian/`, `.venv/`, `__pycache__/`, `*.pyc`

**Core Logic:**
- `scripts/state.py`: Central module — all entity CRUD, state transition validation, next-action computation, auto-advancement, priority management, git helpers
- `scripts/db.py`: Database schema (SQL string), migrations, connection factory (`connect()`), schema versioning
- `scripts/resume.py`: Deterministic resume prompt generator — queries SQLite, builds markdown
- `scripts/metrics.py`: PM metrics — velocity (plans/day), cycle times, stall detection, forecasting, progress computation
- `scripts/sync.py`: Bidirectional Nero sync — pull dispatch status, push state as tickets, dispatch summary
- `scripts/dispatch.py`: One-way Nero dispatch — send individual plans or entire phases
- `scripts/export.py`: SQLite to JSON export — full state tree and human-readable status summary
- `scripts/axis_sync.py`: Axis PM kanban sync — status mapping, ticket creation
- `scripts/context_window.py`: Token estimation utilities — checkpoint threshold (150k), subagent budget (200k)

**Testing:**
- `tests/test_state.py`: CRUD operations, valid/invalid transitions, next-action computation, auto-advance, priority
- `tests/test_resume.py`: Deterministic prompt generation, edge cases (no project, no milestone)
- `tests/test_metrics.py`: Velocity, cycle times, stall detection, forecasting, progress computation
- `tests/test_sync.py`: Pull status, push state, full sync, dispatch summary (uses mocked HTTP)

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` — e.g., `axis_sync.py`, `context_window.py`
- Skill directories: `lowercase` single-word — e.g., `skills/init/`, `skills/dashboard/`
- Prompt templates: `kebab-case.md` — e.g., `code-quality-reviewer.md`, `context-gatherer.md`
- Reference docs: `kebab-case.md` — e.g., `state-machine.md`, `discipline-protocols.md`
- Test files: `test_<module>.py` — mirrors the module they test

**Directories:**
- Flat structure: no nested directories within `scripts/`, `prompts/`, `references/`
- Skill directories: one level deep — `skills/<command>/SKILL.md`
- Test directory: flat — all test files at `tests/` root

**Functions:**
- Public functions: `snake_case` — e.g., `create_project()`, `transition_phase()`, `compute_velocity()`
- Private helpers: `_snake_case` with leading underscore — e.g., `_now()`, `_row_to_dict()`, `_nero_rpc()`, `_get_git_state()`
- CRUD pattern: `create_*()`, `get_*()`, `list_*()`, `update_*()`, `transition_*()` for each entity

**Variables:**
- Constants: `UPPER_SNAKE_CASE` — e.g., `SCHEMA_VERSION`, `PHASE_TRANSITIONS`, `AUTO_CHECKPOINT_TOKENS`, `VALID_PRIORITIES`
- SQL strings: `UPPER_SNAKE_CASE` — e.g., `SCHEMA_SQL`, `MIGRATION_V2`

**Types:**
- All functions use type hints — `str | Path | None`, `dict | None`, `list[dict]`, `sqlite3.Connection`
- Union syntax uses `|` (Python 3.10+ style) not `Union[]`

## Where to Add New Code

**New Script Module:**
- Place at: `scripts/<module_name>.py`
- Import convention: `from scripts.<module> import <function>`
- All modules are called via `uv run --project ~/dev/meridian python -c "from scripts.<module> import ..."` from SKILL.md procedures
- Add corresponding tests at: `tests/test_<module_name>.py`

**New Slash Command:**
- Create directory: `skills/<command>/SKILL.md`
- Add command to root `SKILL.md` command list
- Follow the step-by-step procedure pattern from existing skills (embedded Python snippets using `uv run --project ~/dev/meridian python -c "..."`)
- Add to README.md command table

**New Subagent Prompt:**
- Place at: `prompts/<agent-name>.md`
- Use `{placeholder}` syntax for variables filled at dispatch time
- Follow structure from `prompts/implementer.md`: task description, project context, rules, output format

**New Reference Document:**
- Place at: `references/<topic>.md`
- Reference from relevant SKILL.md files and prompts

**New Database Table:**
- Add to `SCHEMA_SQL` in `scripts/db.py`
- Create a migration function `_migrate_vN_to_vN+1()` in `scripts/db.py`
- Increment `SCHEMA_VERSION` and add migration call to `init_schema()`
- Add CRUD functions in `scripts/state.py` following existing patterns
- Add tests in `tests/test_state.py`

**New Metric:**
- Add function to `scripts/metrics.py`
- Follow pattern: pure function taking `sqlite3.Connection` and `project_id`, returning a dict
- Add tests in `tests/test_metrics.py`
- Wire into `skills/dashboard/SKILL.md` display logic

## Special Directories

**`.meridian/` (per target project):**
- Purpose: Runtime state directory created in projects that use Meridian
- Generated: Yes, by `/meridian:init` command
- Committed: No — excluded by `.gitignore` in target projects
- Contains: `state.db` (SQLite, WAL mode), `meridian-state.json` (exported JSON for Nero)

**`.venv/`:**
- Purpose: Python virtual environment managed by `uv`
- Generated: Yes, by `uv sync`
- Committed: No

**`.planning/`:**
- Purpose: GSD planning and codebase analysis documents
- Generated: Yes, by GSD mapping commands
- Committed: Yes (committed to git for reference)

---

*Structure analysis: 2026-03-10*
