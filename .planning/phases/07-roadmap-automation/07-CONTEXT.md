# Phase 7: Roadmap Automation - Context

**Gathered:** 2026-03-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Auto-sync ROADMAP.md checkboxes and REQUIREMENTS.md traceability table from DB state. No manual edits needed after state transitions. DB is the source of truth for plan/phase status.

</domain>

<decisions>
## Implementation Decisions

### Sync trigger mechanism
- Hook into state.py's transition_plan and transition_phase functions (same pattern as Phase 6 nyquist hooks)
- Trigger on plan completion/skip and phase transitions (executing, verifying, complete)
- New module: scripts/roadmap_sync.py — state.py calls it, keeps concerns separated
- state.py is already 1150+ lines, new module avoids bloating it further

### Markdown update strategy
- Regex find-replace on specific lines — target checkboxes, table rows, status fields
- Preserve manual formatting and comments — minimal diff
- Do NOT regenerate entire sections from scratch

### Scope of auto-sync
- ROADMAP.md: plan checkboxes `[x]`/`[ ]`, phase status in progress table, completion dates
- REQUIREMENTS.md: traceability table status column (Pending → Complete)
- Core fields only — no plan counts, no progress percentages, no wave details

### Error handling / drift
- DB is source of truth — sync always overwrites markdown to match DB state
- No drift detection or warnings — just overwrite
- If regex can't find the target line, log a warning but don't crash

### Claude's Discretion
- Exact regex patterns for matching checkboxes and table rows
- How to identify which plan/phase lines to update (by name, number, or both)
- Whether to commit the markdown changes automatically or leave them staged
- Test strategy for regex-based file updates

</decisions>

<specifics>
## Specific Ideas

- Phase 6 established the pattern: hook side effects into state.py transition functions, keep logic in a separate module (nyquist.py)
- Standard library only — no new dependencies (consistent with Phase 6 decision)
- ROADMAP.md has two formats to handle: the checkbox list (`- [x] **Phase N: Name**`) and the progress table (`| Phase | Status | Completed |`)
- REQUIREMENTS.md traceability table: `| ROAD-01 | Phase 7 | Pending |` → `| ROAD-01 | Phase 7 | Complete |`

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- state.py: transition_plan() and transition_phase() are the hook points. check_auto_advance() shows the pattern for calling external modules after transitions.
- nyquist.py: Reference implementation of the "state.py calls external module on transition" pattern.
- _parse_frontmatter() in nyquist.py: Regex-based YAML parsing without PyYAML — similar approach needed for markdown parsing.

### Established Patterns
- Side effects as informational, non-blocking (Phase 6 decision carried forward)
- Separate module for file I/O logic, called from state.py hooks
- Standard library only, no new dependencies

### Integration Points
- state.py transition_plan() → call roadmap_sync after plan status change
- state.py transition_phase() → call roadmap_sync after phase status change
- .planning/ROADMAP.md and .planning/REQUIREMENTS.md as target files

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-roadmap-automation*
*Context gathered: 2026-03-16*
