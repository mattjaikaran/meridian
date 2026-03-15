# Phase 6: Nyquist Compliance - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Ensure VALIDATION.md files accurately reflect execution results for every phase. Two requirements: (1) auto-update frontmatter with real pass/fail results during execution, (2) retroactively fill validation gaps for phases 1-4 that were executed before Nyquist existed.

</domain>

<decisions>
## Implementation Decisions

### Frontmatter update trigger
- Auto-update during execution — no manual step required
- Trigger on each wave completion (not per-plan, not per-phase)
- Actually run the VALIDATION.md test commands and record pass/fail results in frontmatter
- Logic lives in state.py, integrated into existing plan/phase transition hooks

### Retroactive gap filling
- Single command fills all gaps at once — scans all phases, finds nyquist_compliant: false, runs tests, updates all
- Run tests against current code — if they pass now, mark compliant
- If a retroactive test fails, mark failed + report the failure reason in frontmatter (don't block anything, don't create todos)
- Update frontmatter status field: draft -> validated (pass) or draft -> failed (fail)

### Pass/fail granularity
- Per-wave results in frontmatter: wave_0_complete: true/false, wave_1_complete: true/false, etc.
- Include validated_at timestamp per wave (e.g., wave_0_validated: 2026-03-14)
- nyquist_compliant: false until ALL waves pass — no partial state
- Test commands stay in VALIDATION.md body only (no duplication in frontmatter)

### Verify-phase behavior
- /meridian:verify-phase checks frontmatter presence + currency (non-draft status, wave results present)
- Does NOT re-run tests — just checks frontmatter state
- Optional phase arg: /meridian:verify-phase checks all, /meridian:verify-phase 3 checks just phase 3
- Output is a table summary: phase name, compliant status, last validated date, issues
- Non-compliant phases are warnings, not errors — informational only, doesn't block anything

### Claude's Discretion
- Exact YAML frontmatter field names and structure
- How to parse test commands from VALIDATION.md body
- Error handling for missing or malformed VALIDATION.md files
- How to integrate wave completion detection with state.py's existing lifecycle hooks

</decisions>

<specifics>
## Specific Ideas

- Nyquist concept explained: validation sampling at sufficient rate during execution to catch problems early
- Phase 5 is the reference implementation — already has nyquist_compliant: true, wave_0_complete: true
- Phases 1-4 all have VALIDATION.md with status: draft, nyquist_compliant: false — these are the gap targets

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- state.py: Has plan completion hooks and phase lifecycle transitions (executing -> verifying -> reviewing -> complete). Wave completion detection already triggers phase transition.
- validate.py: Git SHA validation — different purpose but similar pattern of checking state against reality.
- Existing VALIDATION.md files: All 5 phases already have templates with frontmatter and test command documentation.

### Established Patterns
- YAML frontmatter in VALIDATION.md: phase, slug, status, nyquist_compliant, wave_0_complete, created
- state.py update_row() with column allowlist validation for safe updates
- Phase auto-transition: all plans complete -> phase moves to 'verifying'

### Integration Points
- state.py wave/plan completion hooks — add validation runner here
- VALIDATION.md files in .planning/phases/XX-name/ directories
- /meridian:verify-phase skill — needs to read frontmatter and produce table output

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-nyquist-compliance*
*Context gathered: 2026-03-14*
