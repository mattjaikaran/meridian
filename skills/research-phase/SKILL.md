# /meridian:research-phase — Research Phase Type

Spawns 3 parallel researcher subagents (domain, technical, competitive) for an upcoming
phase. Produces `RESEARCH.md` in the phase artifact directory. The plan phase soft-gates
on this artifact being present.

## Arguments
- (no args) — research the current pending/planned phase
- `--phase <id>` — research a specific phase by ID
- `--skip-competitive` — skip competitive research (faster, 2 subagents only)
- `--skip-research` — bypass gate warning in /meridian:plan (emergency only)

## Keywords
research, investigate, analyze, domain, technical, competitive, findings, pre-plan, context

## Procedure

### Step 1: Find Target Phase

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.research_phase import get_research_context
conn = connect(get_db_path('.'))
ctx = get_research_context(conn, phase_id=<phase_id_or_None>)
print(json.dumps(ctx, indent=2, default=str))
conn.close()
"
```

Pass the `--phase <id>` value as `phase_id`, or `None` if not specified.

If result contains `"error"`, display it and stop — tell the user to run `/meridian:plan` first.

Store: `phase_id`, `phase_name`, `description`, `acceptance_criteria`, `tech_stack`, `phase_dir`, `slug`.

### Step 2: Check for Existing RESEARCH.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from pathlib import Path
from scripts.research_phase import check_research_artifact
result = check_research_artifact(Path('<phase_dir>'))
print('exists' if result else 'missing')
"
```

If `exists`: ask the user — "RESEARCH.md already exists for this phase. Re-run and overwrite? (y/N)". If No, print the path and exit.

### Step 3: Spawn Researcher Subagents (parallel)

Launch all researcher agents in a **single parallel batch** (same message). Use
`subagent_type: Explore` for each. Read the `prompts/research-phase.md` template and
customize each call with the variables below. Pass absolute paths when referencing files.

**Agent 1 — Domain Researcher:**
```
focus_area: domain
focus_label: Domain & Business Context
phase_name: <phase_name>
phase_description: <description>
tech_stack: <tech_stack>
acceptance_criteria: <formatted list>
focus_instructions: |
  Research the real-world problem domain this phase addresses.
  Cover: what users/operators expect from this feature, industry conventions and
  best practices, common failure modes in production, regulatory or compliance
  context (if any), and what "done well" looks like from a practitioner's perspective.
  Do NOT read the codebase — this is pure domain research.
```

**Agent 2 — Technical Researcher:**
```
focus_area: technical
focus_label: Technical Implementation
phase_name: <phase_name>
phase_description: <description>
tech_stack: <tech_stack>
acceptance_criteria: <formatted list>
focus_instructions: |
  Research technical implementation options for this phase in the context of the
  project's tech stack. Read the codebase to find existing patterns, naming conventions,
  and analogous implementations. Cover: relevant libraries/APIs (with versions), known
  pitfalls, integration patterns, performance considerations, and security surface area.
  Quote file paths and line numbers for patterns you find in the codebase.
```

**Agent 3 — Competitive Researcher (skip if `--skip-competitive`):**
```
focus_area: competitive
focus_label: Competitive & Reference
phase_name: <phase_name>
phase_description: <description>
tech_stack: <tech_stack>
acceptance_criteria: <formatted list>
focus_instructions: |
  Research how similar tools, frameworks, and open-source projects implement equivalent
  features. Identify 2-3 reference implementations worth studying. Surface design
  decisions worth borrowing and anti-patterns worth deliberately avoiding.
  Focus on publicly known systems — no codebase access needed.
```

Collect all 3 results (or 2 if `--skip-competitive`).

### Step 4: Write RESEARCH.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.research_phase import write_research_md, mark_research_complete
conn = connect(get_db_path('.'))
path = write_research_md(
    phase_dir=Path('<phase_dir>'),
    phase_name='<phase_name>',
    phase_id=<phase_id>,
    domain='''<domain_findings_verbatim>''',
    technical='''<technical_findings_verbatim>''',
    competitive='''<competitive_findings_or_empty_string>''',
)
mark_research_complete(conn, <phase_id>)
conn.close()
print(str(path))
"
```

Paste the verbatim findings blocks from each subagent.

### Step 5: Display Summary

```
## Research Complete: <Phase Name>

Artifact: <phase_dir>/RESEARCH.md
Subagents: domain ✓  technical ✓  competitive ✓ (or skipped)

### Key Findings

**Domain:** <1-2 sentence summary of domain findings>
**Technical:** <1-2 sentence summary of technical findings>
**Competitive:** <1-2 sentence summary, or "Skipped (--skip-competitive)">

Next: /meridian:plan --phase <phase_id>
```

## Gate Behavior

`/meridian:plan` and `/meridian:execute` should check for RESEARCH.md using `research_gate()`:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.research_phase import research_gate
result = research_gate(Path('<phase_dir>'))
print(json.dumps(result, indent=2))
"
```

- `passed: true` → proceed normally
- `passed: false` → print the `warning` string and ask the user to confirm skip with `--skip-research`

This is a **soft gate** — it warns but does not block execution by default.

## What Each Researcher Covers

| Researcher | Focus | Reads codebase? |
|---|---|---|
| Domain | Real-world problem context, user expectations, failure modes | No |
| Technical | Stack-specific options, libraries, existing patterns, pitfalls | Yes |
| Competitive | Reference implementations, design decisions to borrow/avoid | No |

## Output Artifact Structure

```
.planning/phases/<slug>/
└── RESEARCH.md          ← written by this skill
    ├── Domain & Business Context
    ├── Competitive & Reference Analysis (if run)
    └── Technical Implementation
```
