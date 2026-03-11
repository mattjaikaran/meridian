# Phase 3: Command Routing - Research

**Researched:** 2026-03-11
**Domain:** Claude Code slash commands / skill routing
**Confidence:** HIGH

## Summary

Phase 3 creates 13 `/meridian:*` slash commands by placing `.md` wrapper files in `~/.claude/commands/meridian/`. The symlink at `~/.claude/skills/meridian` already points to the meridian repo, which means Claude Code already loads the root SKILL.md as passive context. The commands directory is separate and additive -- both can coexist.

A Python generator script (`scripts/generate_commands.py`) will auto-discover `skills/*/SKILL.md` files and produce thin wrapper `.md` files in `~/.claude/commands/meridian/`. The wrappers summarize what the command does, document its arguments, then reference the full SKILL.md procedure. The root SKILL.md must be updated to remove its Commands section (preventing conflict with explicit command routing).

**Primary recommendation:** Generate `.md` command files with YAML frontmatter (`name`, `description`, `argument-hint`) and a body that references the full SKILL.md via `@~/.claude/skills/meridian/skills/<name>/SKILL.md`. Use `<!-- meridian:generated -->` comment marker to distinguish generated files from custom ones.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Each command is a `.md` file in `~/.claude/commands/meridian/` (folder-based: `meridian/init.md` -> `/meridian:init`)
- Wrappers are "summary + reference" style: brief description + reference to full SKILL.md procedure
- Each wrapper documents accepted arguments/flags so Claude knows what to parse
- Wrappers reference SKILL.md via symlink path: `~/.claude/skills/meridian/skills/<name>/SKILL.md`
- Hardcoded `~/dev/meridian` path for `uv run --project` (personal tool)
- Generator lives at `scripts/generate_commands.py`
- Generator auto-discovers skills by scanning `skills/*/SKILL.md`
- Full install mode: creates `~/.claude/commands/meridian/` and writes all `.md` files directly
- Preserves custom (non-generated) files via comment marker -- only overwrites files it created
- Prints brief summary: "Created: init.md, plan.md, ..." and "Skipped: N custom files"
- Verifies `~/.claude/skills/meridian` symlink; warns if missing with `--fix-symlink` flag
- Creates directory automatically if missing (`mkdir -p`)
- Supports `--uninstall` flag to remove generated files (and optionally symlink with `--all`)
- Invoked as: `uv run python scripts/generate_commands.py`
- Stdlib-only Python
- Root SKILL.md becomes passive context only (Commands section removed)
- Generator also updates root SKILL.md from template
- Root SKILL.md should not conflict with `/meridian:*` command routing

### Claude's Discretion
- Whether to auto-extract descriptions from SKILL.md content or add frontmatter metadata
- Whether `/meridian` (no subcommand) shows help or stays passive
- Whether wrappers include a brief header line on invocation or go straight to SKILL.md procedure
- Comment marker format for tracking generated vs custom files

### Deferred Ideas (OUT OF SCOPE)
None
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ROUT-01 | All 13 subcommands discoverable as `/meridian:*` slash commands | Command files in `~/.claude/commands/meridian/` with proper frontmatter make them appear in autocomplete |
| ROUT-02 | Each command is thin `.md` wrapper referencing SKILL.md procedures | Wrapper format: frontmatter + summary + `@` reference to skill symlink path |
| ROUT-03 | Python generator script produces command `.md` files from skill definitions | `scripts/generate_commands.py` scans `skills/*/SKILL.md`, extracts metadata, writes wrappers |
| ROUT-04 | Root SKILL.md provides passive context without conflicting with command routing | Remove Commands section, keep Architecture/Scripts/References; generator regenerates from template |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib | 3.11+ | Generator script | Project constraint: no external deps |
| `pathlib` | stdlib | File/path operations | Standard for path manipulation |
| `argparse` | stdlib | CLI flags (`--uninstall`, `--fix-symlink`, `--all`) | Standard for CLI tools |
| `re` | stdlib | Parse SKILL.md frontmatter/content | Extract titles, arguments, descriptions |
| `textwrap` | stdlib | Template formatting | Clean multi-line string generation |

### Supporting
No external libraries needed. This phase is entirely stdlib Python + Markdown file generation.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `.claude/commands/meridian/` | `.claude/skills/meridian/skills/*/SKILL.md` (direct skill routing) | Skills already exist via symlink but don't get explicit `/meridian:*` namespace in commands menu; commands approach is locked decision |
| Python generator | Shell script | Python matches project conventions and is more maintainable for template logic |

## Architecture Patterns

### Command File Structure
```
~/.claude/commands/meridian/
  init.md          # /meridian:init
  plan.md          # /meridian:plan
  execute.md       # /meridian:execute
  resume.md        # /meridian:resume
  status.md        # /meridian:status
  dashboard.md     # /meridian:dashboard
  roadmap.md       # /meridian:roadmap
  dispatch.md      # /meridian:dispatch
  review.md        # /meridian:review
  ship.md          # /meridian:ship
  debug.md         # /meridian:debug
  quick.md         # /meridian:quick
  checkpoint.md    # /meridian:checkpoint
```

### Generator Script Structure
```
scripts/generate_commands.py
  main()                    # Entry point, argparse
  discover_skills()         # Scan skills/*/SKILL.md
  extract_metadata()        # Parse title, description, arguments from SKILL.md
  generate_wrapper()        # Produce .md content with frontmatter
  write_commands()          # Write to ~/.claude/commands/meridian/
  update_root_skill()       # Regenerate root SKILL.md
  verify_symlink()          # Check/fix ~/.claude/skills/meridian
  uninstall()               # Remove generated files
```

### Pattern: Command Wrapper Format
**What:** Each generated `.md` file has YAML frontmatter + body that references the full SKILL.md
**When to use:** Every generated command file follows this exact pattern

```markdown
<!-- meridian:generated -->
---
name: meridian:init
description: Initialize Meridian in current project
argument-hint: "[--milestone <name>]"
---

Initialize Meridian state tracking in the current project directory. Creates `.meridian/` directory, initializes SQLite database, gathers project context.

## Full Procedure

Follow the complete procedure in the skill definition:

@~/.claude/skills/meridian/skills/init/SKILL.md
```

**Key details about this format (verified from official docs):**
- The `@` file reference syntax loads the referenced file's content into context
- `name` field in frontmatter sets the slash command name
- `description` appears in autocomplete
- `argument-hint` shows expected arguments during autocomplete
- The comment marker `<!-- meridian:generated -->` MUST be the first line (before frontmatter) so the generator can identify its own files

### Pattern: Metadata Extraction from SKILL.md
**What:** Parse each skill's SKILL.md to extract description and arguments
**Recommendation:** Auto-extract from content (Claude's discretion item)

Each SKILL.md already follows a consistent pattern:
- Line 1: `# /meridian:<name> -- <description>`
- `## Arguments` section lists flags/params
- Procedure follows

Extract the title line for description and parse the Arguments section. No need for additional frontmatter metadata in skill files -- the content already contains everything needed.

### Pattern: Root SKILL.md Template
**What:** Generator produces root SKILL.md from a template string embedded in the script
**Content:** Architecture, Scripts, References sections (copied from current SKILL.md minus Commands)
**Dynamic:** List of available commands auto-generated from discovered skills (as informational, not routing)

### Anti-Patterns to Avoid
- **Duplicating SKILL.md content in wrappers:** Wrappers should reference, not copy. Copying creates maintenance burden and drift.
- **Using `context: fork` on command wrappers:** These commands run inline -- they need conversation context to understand the user's project state.
- **Adding `disable-model-invocation: true`:** Users want Claude to be able to suggest meridian commands when relevant.
- **Putting generated marker inside frontmatter:** YAML frontmatter is parsed by Claude Code. The marker must be an HTML comment outside frontmatter.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML frontmatter parsing | Custom regex parser | Simple line-by-line scan between `---` markers | SKILL.md files don't have YAML frontmatter currently; just parse the markdown heading and sections |
| Argument extraction | Complex AST parser | Regex on `## Arguments` section lines starting with `- ` | Arguments follow a consistent `- \`<flag>\` -- <description>` pattern |
| Template engine | Jinja2 or custom | Python f-strings / textwrap.dedent | Stdlib-only constraint; templates are simple enough |

## Common Pitfalls

### Pitfall 1: Comment Marker Position
**What goes wrong:** Putting `<!-- meridian:generated -->` after the frontmatter means Claude Code may parse and fail on it
**Why it happens:** Natural instinct to put markers at the end
**How to avoid:** First line of file, before the `---` frontmatter opener. Generator checks for this exact first line to identify its own files.
**Warning signs:** Custom files getting overwritten

### Pitfall 2: Symlink Resolution
**What goes wrong:** `~/.claude/skills/meridian` points to wrong path or is a broken symlink
**Why it happens:** Repo moved, or symlink never created
**How to avoid:** Generator verifies symlink target matches expected path (`/Users/mattjaikaran/dev/meridian`). The `--fix-symlink` flag recreates it.
**Warning signs:** Commands reference SKILL.md files that don't load

### Pitfall 3: Stale Command Files
**What goes wrong:** A skill gets renamed/deleted but its command file persists
**Why it happens:** Generator only writes new files, doesn't clean up
**How to avoid:** Generator should list all generated files (by marker), compare against discovered skills, and remove orphans. Print "Removed: old-name.md" in summary.
**Warning signs:** `/meridian:` autocomplete shows commands that don't work

### Pitfall 4: Root SKILL.md Commands Section Conflict
**What goes wrong:** Root SKILL.md still has a Commands section that Claude interprets as routing instructions, conflicting with the explicit command files
**Why it happens:** Forgot to update root SKILL.md, or generator didn't run after changes
**How to avoid:** Generator always regenerates root SKILL.md. The template has no Commands section. An informational "Available commands" list is fine but must not use `/meridian:*` invocation syntax that Claude would treat as routing.
**Warning signs:** Claude gets confused about which source to follow for command procedures

### Pitfall 5: @ Reference Path Resolution
**What goes wrong:** The `@~/.claude/skills/meridian/skills/<name>/SKILL.md` path doesn't resolve
**Why it happens:** Tilde expansion may not work in all contexts, or the symlink structure changes
**How to avoid:** Test that `@` references work with the symlink path in an actual Claude Code session. The `~` tilde works in `@` references per Claude Code behavior (confirmed by GSD commands using `@/Users/mattjaikaran/...` absolute paths).
**Warning signs:** Claude says it can't find the referenced file

**Recommendation on @ references:** Use absolute paths (`@/Users/mattjaikaran/.claude/skills/meridian/skills/<name>/SKILL.md`) rather than tilde, matching the pattern used by GSD commands. This is a personal tool with a hardcoded path, so absolute paths are acceptable and more reliable.

## Code Examples

### Command Wrapper Template (Generated Output)
```markdown
<!-- meridian:generated -->
---
name: meridian:init
description: Initialize Meridian in current project
argument-hint: "[--milestone <name>]"
---

Initialize Meridian state tracking in the current project directory. Creates `.meridian/` directory, initializes SQLite database, and gathers project context.

## Procedure

@/Users/mattjaikaran/.claude/skills/meridian/skills/init/SKILL.md
```

### Generator: Skill Discovery
```python
# Source: project convention (skills/*/SKILL.md pattern)
from pathlib import Path

def discover_skills(repo_root: Path) -> list[dict]:
    """Scan skills/ directory and extract metadata from each SKILL.md."""
    skills = []
    skills_dir = repo_root / "skills"
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if skill_dir.is_dir() and skill_md.exists():
            metadata = extract_metadata(skill_md)
            metadata["name"] = skill_dir.name
            skills.append(metadata)
    return skills
```

### Generator: Metadata Extraction
```python
import re

def extract_metadata(skill_md: Path) -> dict:
    """Extract description and arguments from a SKILL.md file."""
    content = skill_md.read_text()
    lines = content.splitlines()

    # Title line: # /meridian:<name> -- <description>
    description = ""
    if lines and lines[0].startswith("# "):
        match = re.search(r'[—–-]\s*(.+)$', lines[0])
        if match:
            description = match.group(1).strip()

    # Arguments section
    arguments = []
    in_args = False
    for line in lines:
        if line.strip().startswith("## Arguments"):
            in_args = True
            continue
        if in_args and line.strip().startswith("## "):
            break
        if in_args and line.strip().startswith("- "):
            arguments.append(line.strip()[2:])

    # Build argument-hint from parsed arguments
    arg_hint = ""
    if arguments:
        hints = []
        for arg in arguments:
            match = re.match(r'`([^`]+)`', arg)
            if match:
                hints.append(match.group(1))
        if hints:
            arg_hint = " ".join(hints)

    return {"description": description, "arguments": arguments, "argument_hint": arg_hint}
```

### Generator: Generated File Detection
```python
GENERATED_MARKER = "<!-- meridian:generated -->"

def is_generated(filepath: Path) -> bool:
    """Check if a command file was created by this generator."""
    try:
        first_line = filepath.read_text().splitlines()[0]
        return first_line.strip() == GENERATED_MARKER
    except (IndexError, OSError):
        return False
```

### Generator: Orphan Cleanup
```python
def cleanup_orphans(commands_dir: Path, valid_names: set[str]) -> list[str]:
    """Remove generated command files that no longer have a matching skill."""
    removed = []
    for md_file in commands_dir.glob("*.md"):
        if is_generated(md_file) and md_file.stem not in valid_names:
            md_file.unlink()
            removed.append(md_file.name)
    return removed
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `.claude/commands/*.md` | `.claude/skills/*/SKILL.md` (unified) | 2025 | Commands still work; skills are recommended for new setups. Both support same frontmatter. |
| Flat commands directory | Folder-based namespacing (`folder/cmd.md` -> `/folder:cmd`) | 2025 | Enables `/meridian:*` namespace via `~/.claude/commands/meridian/` directory |
| Manual command files | Generator-produced thin wrappers | This phase | Ensures all 13 commands stay in sync with skill definitions |

**Note:** The commands approach is used here (rather than converting to native skills) because:
1. Skills at `~/.claude/skills/meridian/` already exist via symlink for passive context
2. The `commands/meridian/` directory gives explicit namespace control
3. Commands and skills can coexist; command wrappers reference skill content via `@`

## Open Questions

1. **Does `@` file reference work with symlink paths?**
   - What we know: GSD commands use `@/Users/mattjaikaran/...` absolute paths successfully. The symlink at `~/.claude/skills/meridian` resolves to `/Users/mattjaikaran/dev/meridian`.
   - What's unclear: Whether `@/Users/mattjaikaran/.claude/skills/meridian/skills/init/SKILL.md` resolves through the symlink correctly.
   - Recommendation: Use the absolute path through the symlink. If it fails during testing, fall back to embedding the SKILL.md content directly (but this creates drift risk). End-to-end testing is flagged as a concern in STATE.md.

2. **Does the generated comment marker before frontmatter cause issues?**
   - What we know: Claude Code parses YAML frontmatter between `---` markers. HTML comments before frontmatter should be ignored.
   - What's unclear: Whether any Claude Code parser chokes on content before the first `---`.
   - Recommendation: Test with a single file first. If problematic, move marker to end of file or use a frontmatter field like `generator: meridian`.

3. **Root SKILL.md passive loading with skills symlink**
   - What we know: The symlink makes `~/.claude/skills/meridian/SKILL.md` the root skill file. Claude loads skill descriptions into context.
   - What's unclear: Whether removing the Commands section from root SKILL.md affects Claude's ability to discover the command files in `~/.claude/commands/meridian/`.
   - Recommendation: These are independent discovery mechanisms. Commands in `~/.claude/commands/` are discovered separately from skills in `~/.claude/skills/`. Removing Commands from root SKILL.md is safe.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (via uv) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_generate_commands.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ROUT-01 | All 13 skills discovered and commands generated | unit | `uv run pytest tests/test_generate_commands.py::test_discover_all_skills -x` | No -- Wave 0 |
| ROUT-02 | Wrapper format has correct frontmatter and @ reference | unit | `uv run pytest tests/test_generate_commands.py::test_wrapper_format -x` | No -- Wave 0 |
| ROUT-03 | Generator script end-to-end (discover, generate, write) | unit | `uv run pytest tests/test_generate_commands.py::test_generate_end_to_end -x` | No -- Wave 0 |
| ROUT-03 | Generator preserves custom files (no overwrite) | unit | `uv run pytest tests/test_generate_commands.py::test_preserve_custom_files -x` | No -- Wave 0 |
| ROUT-03 | Generator removes orphaned generated files | unit | `uv run pytest tests/test_generate_commands.py::test_cleanup_orphans -x` | No -- Wave 0 |
| ROUT-03 | Generator --uninstall removes generated files | unit | `uv run pytest tests/test_generate_commands.py::test_uninstall -x` | No -- Wave 0 |
| ROUT-03 | Generator --fix-symlink creates/updates symlink | unit | `uv run pytest tests/test_generate_commands.py::test_fix_symlink -x` | No -- Wave 0 |
| ROUT-04 | Root SKILL.md regenerated without Commands section | unit | `uv run pytest tests/test_generate_commands.py::test_root_skill_no_commands -x` | No -- Wave 0 |
| ROUT-01 | Manual: typing `/meridian:` shows all 13 commands in Claude Code | manual-only | N/A (requires Claude Code session) | N/A |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_generate_commands.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green + manual verification in Claude Code

### Wave 0 Gaps
- [ ] `tests/test_generate_commands.py` -- covers ROUT-01 through ROUT-04 (unit tests with tmp_path fixtures)
- [ ] Tests should use `tmp_path` for both skills source dir and commands output dir (no touching real `~/.claude/`)

## Sources

### Primary (HIGH confidence)
- [Claude Code Official Docs - Slash Commands / Skills](https://code.claude.com/docs/en/slash-commands) -- frontmatter format, folder-based namespacing, `@` file references, argument substitution, skill vs command behavior
- Project files: `skills/*/SKILL.md` (13 files) -- verified consistent format with title, arguments, procedure sections
- Project files: `~/.claude/commands/gsd/*.md` -- reference implementation of command frontmatter pattern

### Secondary (MEDIUM confidence)
- [WebSearch: Claude Code custom slash commands](https://code.claude.com/docs/en/slash-commands) -- confirmed folder-based namespace routing

### Tertiary (LOW confidence)
- `@` reference through symlink path -- untested in actual Claude Code session, flagged for manual validation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- stdlib Python, well-understood Markdown generation
- Architecture: HIGH -- command format verified from official docs and existing GSD examples
- Pitfalls: MEDIUM -- symlink resolution and comment marker behavior need manual testing

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- Claude Code command format is established)
