# Phase 3: Command Routing - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Make all 13 Meridian workflows discoverable as `/meridian:*` slash commands in Claude Code. This involves creating command wrapper files in `~/.claude/commands/meridian/`, building a generator script to produce them from skill definitions, and updating root SKILL.md to passive context only.

</domain>

<decisions>
## Implementation Decisions

### Command Wrapper Format
- Each command is a `.md` file in `~/.claude/commands/meridian/` (folder-based: `meridian/init.md` → `/meridian:init`)
- Wrappers are "summary + reference" style: brief description of what the command does + reference to the full SKILL.md procedure
- Each wrapper documents accepted arguments/flags so Claude knows what to parse from user input
- Wrappers reference SKILL.md via the symlink path: `~/.claude/skills/meridian/skills/<name>/SKILL.md`
- Hardcoded `~/dev/meridian` path for `uv run --project` (personal tool, won't change)

### Generator Script
- Lives at `scripts/generate_commands.py` (alongside other scripts)
- Auto-discovers skills by scanning `skills/*/SKILL.md` directory — new skills get commands automatically
- Full install mode: creates `~/.claude/commands/meridian/` and writes all `.md` files directly
- Preserves custom (non-generated) files via a comment marker in generated files — only overwrites files it created
- Prints brief summary: "Created: init.md, plan.md, ..." and "Skipped: N custom files"
- Verifies the `~/.claude/skills/meridian` symlink exists; warns if missing with option to auto-fix (e.g., `--fix-symlink` flag)
- Creates `~/.claude/commands/meridian/` directory automatically if missing (`mkdir -p`)
- Supports `--uninstall` flag to remove generated command files (and optionally symlink with `--all`)
- Invoked as: `uv run python scripts/generate_commands.py`
- Stdlib-only Python (per project constraint)

### Root SKILL.md
- Becomes passive project context only — Commands section removed
- Keeps Architecture, Scripts, References sections as project context for Claude
- Generator also updates root SKILL.md (regenerates from template, keeping it in sync with skills/)
- Should not conflict with `/meridian:*` command routing

### Claude's Discretion
- Whether to auto-extract descriptions from SKILL.md content or add frontmatter metadata — pick whichever approach is cleaner
- Whether `/meridian` (no subcommand) shows help or stays passive
- Whether wrappers include a brief header line on invocation or go straight to SKILL.md procedure
- Comment marker format for tracking generated vs custom files

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `skills/*/SKILL.md`: 13 skill definition files already exist with full procedures
- Root `SKILL.md`: Current project context doc listing all commands, architecture, scripts
- `scripts/` directory: Established pattern for Python utility scripts (db.py, state.py, etc.)

### Established Patterns
- All Python scripts are stdlib-only (no external dependencies)
- Scripts invoked via `uv run --project ~/dev/meridian python -c "..."` or `uv run python scripts/<name>.py`
- Symlink at `~/.claude/skills/meridian` → `/Users/mattjaikaran/dev/meridian` already exists and works
- Claude Code `~/.claude/commands/` directory exists with `gsd/` subfolder already present

### Integration Points
- `~/.claude/skills/meridian` symlink — must continue working for SKILL.md passive context
- `~/.claude/commands/meridian/` — new directory for command routing
- Each SKILL.md references `uv run --project ~/dev/meridian` for Python execution
- Root SKILL.md is loaded by Claude Code when the meridian skill is active

</code_context>

<specifics>
## Specific Ideas

- Generator should be a single-file Python script that's self-contained
- The symlink auto-fix should handle the case where symlink points to a different (old) path
- After running the generator, typing `/meridian:` in Claude Code should show all 13 subcommands in autocomplete

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-command-routing*
*Context gathered: 2026-03-11*
