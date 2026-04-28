# /meridian:spec-phase — Spec Phase Type

Clarifies WHAT a phase delivers through a Socratic interview loop with quantitative
ambiguity scoring. Produces `SPEC.md` in the phase artifact directory with falsifiable
requirements locked before implementation decisions begin.

**Position in workflow:** `spec-phase → discuss-phase → plan-phase → execute-phase`

## Arguments
- (no args) — spec the current pending/planned phase
- `--phase <id>` — spec a specific phase by ID
- `--auto` — skip interview if ambiguity already ≤ 0.20; otherwise Claude selects best answers
- `--skip-spec` — bypass gate warning in /meridian:plan (emergency only)

## Keywords
spec, specification, requirements, clarify, ambiguity, scope, boundaries, falsifiable,
what, deliverable, acceptance criteria, pre-plan, contract

## Ambiguity Model

| Dimension | Weight | Minimum | What it measures |
|-----------|--------|---------|-----------------|
| Goal Clarity | 35% | 0.75 | Is the outcome specific and measurable? |
| Boundary Clarity | 25% | 0.70 | What's in scope vs out of scope? |
| Constraint Clarity | 20% | 0.65 | Performance, compatibility, data requirements? |
| Acceptance Criteria | 20% | 0.70 | How do we know it's done? |

`ambiguity = 1.0 − (0.35×goal + 0.25×boundary + 0.20×constraint + 0.20×acceptance)`

**Gate:** ambiguity ≤ 0.20 AND all dimensions ≥ minimums → write SPEC.md.

## Procedure

### Step 1: Find Target Phase

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.spec_phase import get_spec_context
conn = connect(get_db_path('.'))
ctx = get_spec_context(conn, phase_id=<phase_id_or_None>)
print(json.dumps(ctx, indent=2, default=str))
conn.close()
"
```

Pass the `--phase <id>` value as `phase_id`, or `None` if not specified.

If result contains `"error"`, display it and stop — tell the user to run `/meridian:plan` first.

Store: `phase_id`, `phase_name`, `description`, `acceptance_criteria`, `tech_stack`,
`phase_dir`, `slug`, `initial_scores`, `initial_ambiguity`.

### Step 2: Check for Existing SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from pathlib import Path
from scripts.spec_phase import check_spec_artifact
result = check_spec_artifact(Path('<phase_dir>'))
print('exists' if result else 'missing')
"
```

If `exists`:
- `--auto`: proceed with "Update it" automatically. Log: `[auto] SPEC.md exists — updating.`
- Otherwise: use AskUserQuestion:
  - header: "Spec Phase"
  - question: "SPEC.md already exists for Phase <N>: <phase_name>. What do you want to do?"
  - options: ["Update it", "View it", "Skip (use existing)"]
  
  If "View": display the SPEC.md content, then offer ["Update it", "Skip"].
  If "Skip": print `Existing SPEC.md unchanged. Run /meridian:discuss --phase <id> to continue.` and exit.
  If "Update": continue.

### Step 3: Scout Codebase

Before any questioning, understand current state:

1. Read `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` (or check if they exist at those paths)
2. Read the phase's description and acceptance_criteria from context
3. Grep the codebase for code/files relevant to this phase goal — look for:
   - Existing implementations of similar functionality
   - Integration points where new code will connect
   - Test coverage gaps relevant to the phase
   - Prior phase artifacts (SUMMARY.md, VERIFICATION.md, RESEARCH.md) in `phase_dir`

Synthesize: what exists today vs what the phase must deliver. Hold this internally — use it to ask precise, grounded questions.

### Step 4: Initial Ambiguity Assessment

Use the `initial_scores` from Step 1 context. Display:

```
## Initial Ambiguity Assessment — Phase <N>: <phase_name>

<format_scores output>
```

**If `--auto` AND initial_ambiguity ≤ 0.20 AND all minimums met:**
Skip interview — derive SPEC.md from roadmap + requirements context.
Log: `[auto] Phase requirements are already sufficiently clear — generating SPEC.md.`
Jump to Step 7.

### Step 5: Socratic Interview Loop

Run up to 6 rounds. Each round: 2–3 focused questions. One AskUserQuestion call per round.

Track current scores (start from `initial_scores`). Track `round_number` (starts at 1).

**Interview perspectives by round:**
- Round 1: **Researcher** — ground in current reality
  - "What exists in the codebase today related to this phase?"
  - "What's the delta between today and the target state?"
  - "What triggers this work — what's broken or missing?"

- Round 2: **Researcher + Simplifier** — surface minimum viable scope
  - "What's the simplest version that solves the core problem?"
  - "If you had to cut 50%, what's the irreducible core?"

- Round 3: **Boundary Keeper** — lock the perimeter
  - "What explicitly will NOT be done in this phase?"
  - "What adjacent problems are tempting to solve but shouldn't be?"
  - "What does 'done' look like — what's the final deliverable?"

- Round 4: **Failure Analyst** — find invalidating edge cases
  - "What's the worst thing that could go wrong if we get requirements wrong?"
  - "What does a broken version of this look like?"
  - "What would cause a verifier to reject the output?"

- Rounds 5–6: **Seed Closer** — lock remaining undecided territory
  - Focus questions on the lowest-scoring dimensions
  - "We have <dimension> at <score> — what would make it completely clear?"

**For each round:**
1. Ask questions via AskUserQuestion:
   - header: "Spec Round <N> — <Perspective Name>"
   - question: "<2-3 focused questions formatted clearly>"
   - (free-text response — use the `freeText: true` option or plain question if AskUserQuestion doesn't support free text; display questions as text and await user response)

2. After user answers, update dimension scores based on what was clarified:
   - Each clear answer to a boundary question → increase `boundary_clarity`
   - Each clear constraint → increase `constraint_clarity`
   - Each testable AC → increase `acceptance_criteria`
   - Clearer goal statement → increase `goal_clarity`

3. Display updated scores:

```
After round <N>:
<format_scores output>
```

4. **Gate check:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.spec_phase import gate_passed, compute_ambiguity
scores = <current_scores_as_dict>
passed, failing = gate_passed(scores)
ambiguity = compute_ambiguity(scores)
print(json.dumps({'passed': passed, 'failing': failing, 'ambiguity': ambiguity}))
"
```

**If gate passes:**
- `--auto`: jump to Step 7.
- Otherwise: AskUserQuestion:
  - header: "Spec Gate Passed"
  - question: "Ambiguity is <score> — requirements are clear enough to write SPEC.md. Proceed?"
  - options: ["Yes — write SPEC.md", "One more round", "Done talking — write it"]

  If "Yes" or "Done talking": jump to Step 7.
  If "One more round": continue.

**If max rounds (6) reached and gate NOT passed:**
- `--auto`: proceed to Step 7, flagging unresolved dimensions in Ambiguity Report.
  Log: `[auto] Max rounds reached. Writing SPEC.md with <N> dimensions below minimum.`
- Otherwise: AskUserQuestion:
  - header: "Max Rounds Reached"
  - question: "After 6 rounds, ambiguity is <score>. Dimensions still below minimum: <list>. What would you like to do?"
  - options: ["Write SPEC.md anyway — flag gaps", "Keep talking", "Abandon"]
  
  If "Write": proceed to Step 7.
  If "Keep talking": continue (no round limit).
  If "Abandon": print `Spec abandoned. No SPEC.md written.` and exit.

### Step 6: Derive SPEC.md Content

Before writing, synthesize from everything gathered:

**Goal statement** (1-2 sentences, specific and measurable):
- Based on phase description + interview clarifications

**Requirements** (list of 3-8 items):
- Each must be: one specific testable statement
- Format: "Current state: X. Target state: Y. Verified by: Z."
- No vague requirements ("should be fast", "improve UX")
- Good: "CLI command exits code 1 + stderr on invalid input"
- Good: "API responds < 200ms p95 under 100 concurrent requests"

**In scope** (explicit list of what this phase produces):
- Concrete deliverables, not wishes

**Out of scope** (explicit list of what it does NOT do, with brief reasoning):
- At least 2-3 items per phase to prevent scope creep

**Constraints** (performance, compatibility, data, tooling):
- Empty list is acceptable if none apply

**Acceptance criteria** (pass/fail checkboxes):
- Must be objectively verifiable
- No "looks good", "feels right", "seems reasonable"

### Step 7: Write SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.spec_phase import write_spec_md, mark_spec_complete
conn = connect(get_db_path('.'))
path = write_spec_md(
    phase_dir=Path('<phase_dir>'),
    phase_name='<phase_name>',
    phase_id=<phase_id>,
    goal='''<goal_statement>''',
    requirements=<requirements_as_list>,
    in_scope=<in_scope_as_list>,
    out_of_scope=<out_of_scope_as_list>,
    acceptance_criteria=<ac_as_list>,
    constraints=<constraints_as_list>,
    final_scores=<scores_as_dict>,
    unresolved_dimensions=<unresolved_list_or_empty>,
)
mark_spec_complete(conn, <phase_id>, <ambiguity_score>, <requirement_count>)
conn.close()
print(str(path))
"
```

### Step 8: Display Summary

```
## Spec Complete: <Phase Name>

Artifact: <phase_dir>/SPEC.md
Requirements locked: <N>
Ambiguity: <final_score> (gate: ≤ 0.20) [PASS / PASS with gaps]

Next: /meridian:discuss --phase <phase_id>
  discuss-phase will detect SPEC.md and focus on implementation decisions only.
```

## Gate Behavior

`/meridian:plan` and `/meridian:execute` can check for SPEC.md using `spec_gate()`:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.spec_phase import spec_gate
result = spec_gate(Path('<phase_dir>'))
print(json.dumps(result, indent=2))
"
```

- `passed: true` → proceed normally
- `passed: false` → print the `warning` string; user can bypass with `--skip-spec`

This is a **soft gate** — it warns but does not block execution.

## Critical Rules

- Scout codebase BEFORE the first question — grounded questions only
- Max 2–3 questions per round — never frontload all questions at once
- SPEC.md is NEVER written if user selects "Abandon"
- Do NOT ask about HOW to implement — that is discuss-phase territory
- Every requirement must have current state, target state, and acceptance criterion
- Boundaries section is MANDATORY — cannot be empty
- Acceptance criteria must be pass/fail — no subjective criteria
