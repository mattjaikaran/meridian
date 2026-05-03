# /meridian:ui-phase — UI Phase Type

Spawns 3 parallel subagents (design, components, UX/accessibility) for a phase that
involves frontend or UI work. Produces `UI_SPEC.md` in the phase artifact directory.
The plan phase soft-gates on this artifact being present for UI phases.

**Position in workflow:** `ui-phase → spec-phase → discuss-phase → plan-phase → execute-phase`

## Arguments

- (no args) — spec the current pending/planned phase
- `--phase <id>` — specify a phase by ID
- `--skip-ux` — skip UX/accessibility subagent (faster, 2 subagents only)
- `--skip-ui` — bypass gate warning in /meridian:plan (emergency only)

## Keywords

ui, frontend, component, design system, design contract, visual, accessibility,
ux, component spec, props, variants, css, tailwind, shadcn, radix, pre-plan

## Procedure

### Step 1: Find Target Phase

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.ui_phase import get_ui_context
conn = connect(get_db_path('.'))
ctx = get_ui_context(conn, phase_id=<phase_id_or_None>)
print(json.dumps(ctx, indent=2, default=str))
conn.close()
"
```

Pass the `--phase <id>` value as `phase_id`, or `None` if not specified.

If result contains `"error"`, display it and stop — tell the user to run `/meridian:plan` first.

Store: `phase_id`, `phase_name`, `description`, `acceptance_criteria`, `tech_stack`,
`phase_dir`, `slug`.

### Step 2: Check for Existing UI_SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.ui_phase import check_ui_artifact
result = check_ui_artifact(Path('<phase_dir>'))
print('exists' if result else 'missing')
"
```

If `exists`: ask the user — "UI_SPEC.md already exists for this phase. Re-run and overwrite? (y/N)". If No, print the path and exit.

### Step 3: Scout the Codebase

Before spawning subagents, read the codebase to understand current UI state:

1. Check if a component library is in use: look for `components/ui/`, `shadcn`, `radix-ui`, `@headlessui`, Tailwind config
2. Read existing component files most relevant to the phase goal
3. Check `tailwind.config.*` for design tokens (colors, spacing, fonts)
4. Note any existing patterns for forms, modals, tables, navigation, etc.
5. Read prior phase artifacts in `<phase_dir>` if present (RESEARCH.md, SPEC.md)

Synthesize current state into a 2-3 sentence brief. Pass this as context into each subagent prompt.

### Step 4: Spawn UI Subagents (parallel)

Launch all subagents in a **single parallel batch** (same message). Use
`subagent_type: Explore` for each. Customize with the variables below.

**Agent 1 — Design Researcher:**
```
Analyze the design system and visual language for the following UI phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current codebase state: <2-3 sentence brief from Step 3>

Research the following:
1. Design tokens in use — color palette, typography scale, spacing scale, border radius, shadows.
   Quote exact values from tailwind.config or CSS variables.
2. Component library — which library is in use (shadcn/ui, radix, headlessui, custom)?
   What existing primitive components are available (Button, Input, Dialog, etc.)?
3. Visual patterns — what existing UI patterns are established? Forms, tables, modals,
   navigation, cards? Quote file paths and line numbers.
4. Theming — dark/light mode? CSS variables? Class-based theming?
5. Recommendations — for this specific phase, what design tokens and primitives will be
   most relevant? What visual consistency constraints must be respected?

Read the codebase. Be specific — quote file paths and token values.
```

**Agent 2 — Component Analyst:**
```
Define the component contracts needed for the following UI phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current codebase state: <2-3 sentence brief from Step 3>

Analyze the following:
1. Component inventory — what new components are needed for this phase? List each one.
2. Component contracts — for each new component, define:
   - Props interface (name, type, required/optional, default)
   - Variants (size, color, state variants if applicable)
   - Composition pattern (children, slots, render props, etc.)
   - Where it lives in the component tree (page, layout, feature, shared)
3. Reuse opportunities — which existing components can be reused or extended vs built from scratch?
   Quote file paths of relevant existing components.
4. State requirements — which components need local state? Server state (react-query, SWR)?
   What loading/error/empty states must each component handle?
5. Integration points — how do these components connect to API endpoints, stores, or parent state?

Read the codebase. Be precise — this output becomes the implementation contract.
```

**Agent 3 — UX & Accessibility Auditor (skip if `--skip-ux`):**
```
Define UX flows and accessibility requirements for the following UI phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current codebase state: <2-3 sentence brief from Step 3>

Cover the following:
1. User flows — step-by-step happy path for the primary use case. Note branching points
   (errors, empty states, loading, permission denied).
2. Error states — what can go wrong? How should each error be communicated to the user?
   (toast, inline, modal, redirect?)
3. Loading states — what shows while data loads? Skeleton, spinner, optimistic UI?
4. Empty states — what shows when there is no data? Is there a CTA?
5. Keyboard navigation — which interactions require keyboard support? Tab order, focus
   trapping (modals, drawers), escape key behavior.
6. ARIA requirements — which components need ARIA roles, labels, or live regions?
   Minimum: dialogs need role=dialog, aria-modal; form fields need aria-label or htmlFor.
7. Responsive behavior — which breakpoints matter? Mobile-first? Any layout shifts?
8. Visual audit checklist — list 5-8 specific things a reviewer should visually verify
   before the phase is marked complete.

Be specific — generic UX advice is useless. Everything must be tied to the actual phase deliverable.
```

Collect all results (or 2 if `--skip-ux`).

### Step 5: Write UI_SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.ui_phase import write_ui_spec_md, mark_ui_complete
conn = connect(get_db_path('.'))
path = write_ui_spec_md(
    phase_dir=Path('<phase_dir>'),
    phase_name='<phase_name>',
    phase_id=<phase_id>,
    design='''<design_findings_verbatim>''',
    components='''<component_findings_verbatim>''',
    ux='''<ux_findings_verbatim_or_empty_string>''',
)
mark_ui_complete(conn, <phase_id>)
conn.close()
print(str(path))
"
```

Paste verbatim findings from each subagent.

### Step 6: Display Summary

```
## UI Spec Complete: <Phase Name>

Artifact: <phase_dir>/UI_SPEC.md
Subagents: design ✓  components ✓  ux/accessibility ✓ (or skipped)

### Component Inventory

<bullet list of new components identified>

### Visual Audit Checklist

<5-8 items from UX subagent>

Next: /meridian:spec-phase --phase <phase_id>
  spec-phase will detect UI_SPEC.md and focus on behavioral requirements only.
```

## Gate Behavior

`/meridian:plan` and `/meridian:execute` can check for UI_SPEC.md using `ui_gate()`:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.ui_phase import ui_gate
result = ui_gate(Path('<phase_dir>'))
print(json.dumps(result, indent=2))
"
```

- `passed: true` → proceed normally
- `passed: false` → print the `warning` string; user can bypass with `--skip-ui`

This is a **soft gate** — it warns but does not block execution.

## What Each Subagent Covers

| Subagent | Focus | Reads codebase? |
|---|---|---|
| Design | Design tokens, component library, visual patterns | Yes |
| Components | Component contracts, props, variants, state | Yes |
| UX/Accessibility | User flows, ARIA, keyboard, responsive, visual checklist | Yes |

## Output Artifact Structure

```
.planning/phases/<slug>/
└── UI_SPEC.md          ← written by this skill
    ├── Design System & Visual Language
    ├── Component Contracts
    └── UX & Accessibility Requirements
```
