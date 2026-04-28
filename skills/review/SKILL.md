# /meridian:review — Two-Stage Code Review

Run spec compliance + code quality review on completed work.

## Arguments
- `--phase <id>` — Review specific phase (default: current phase)
- `--stage <1|2>` — Run only one stage
- `--files <paths>` — Review specific files instead of full phase
- `--cross-model` — Run independent review from a secondary AI model after Stage 2
- `--persona <name>` — Apply role-typed review lens (pm, architect, ux, qa, security)
- `--party` — Concurrent multi-perspective review: code quality, security, and UX in parallel

## Procedure

### Step 0A: Party Mode (if --party)

If `--party` is passed, skip the normal Stage 1/2 pipeline and run this instead.

#### 0A-1: Build reviewer prompts for all 3 perspectives
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.party_review import build_reviewer_prompt, list_perspectives
perspectives = list_perspectives()
print(json.dumps(perspectives, indent=2))
"
```

Get changed files (same as Step 2 below), then build one prompt per perspective:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.party_review import build_reviewer_prompt
prompt = build_reviewer_prompt(
    '<perspective_key>',
    changed_files=['<file1>', '<file2>'],
    phase_name='<name>',
    phase_description='<desc>',
)
print(prompt)
"
```

#### 0A-2: Launch 3 reviewers in parallel

Spawn 3 independent Agents (subagent_type: general-purpose) simultaneously — one per perspective.
Each agent receives ONLY its own prompt and is NOT aware of the other reviewers.

Perspectives: `code-quality`, `security`, `ux`

Each agent must return a JSON object matching:
```json
{
  "perspective": "<key>",
  "verdict": "PASS" | "PASS_WITH_NOTES" | "REQUEST_CHANGES",
  "findings": [...],
  "summary": "<assessment>"
}
```

Use `parse_json_from_output` to extract JSON from each agent response:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.party_review import parse_json_from_output
result = parse_json_from_output('''<agent_output>''')
import json; print(json.dumps(result, indent=2))
"
```

#### 0A-3: Synthesize findings
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.party_review import synthesize_findings
outputs = <list_of_three_parsed_dicts>
synthesis = synthesize_findings(outputs)
print(json.dumps(synthesis, indent=2))
"
```

#### 0A-4: Write unified REVIEW.md
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.party_review import synthesize_findings, format_review_md
outputs = <list_of_three_parsed_dicts>
synthesis = synthesize_findings(outputs)
md = format_review_md('<phase_name>', synthesis, outputs)
print(md)
" > .planning/phases/<phase_id>/REVIEW.md
```

Display the party review banner:
```
## Party Review — <Phase Name>
Reviewers: Code Quality [CODE] | Security [SEC] | UX [UX]
Overall: <verdict>
Findings: <total> total, <critical> critical/high
```

#### 0A-5: Log and store result
Store the overall verdict as a review record, then log a decision. Use `result` = overall_verdict
mapped to `pass`/`pass_with_notes`/`fail`. Then **exit** — do not run Steps 1-7.

### Step 0: Load Persona (if --persona)

If `--persona <name>` is passed, load the persona prompt and prepend it to both
Stage 1 and Stage 2 reviewer agent prompts.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.personas import load_persona
persona = load_persona('<persona_name>')
print(json.dumps({'label': persona['label'], 'content': persona['content']}, indent=2))
"
```

Display the active persona at the top of the review output:
```
## Review — <Phase Name>
Persona: <Persona Label>
```

Use `apply_persona(base_prompt, persona_name)` from `scripts/personas.py` to
combine the persona instructions with the existing spec-reviewer.md / code-quality-reviewer.md
templates when populating each reviewer agent.

### Step 1: Gather Review Context
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_phase, list_plans
conn = connect(get_db_path('.'))
phase = get_phase(conn, <phase_id>)
plans = list_plans(conn, <phase_id>)
print(json.dumps({'phase': phase, 'plans': plans}, indent=2, default=str))
conn.close()
"
```

### Step 2: Get Changed Files
```bash
git diff --name-only <base_branch>...HEAD
```

### Step 3: Stage 1 — Spec Compliance Review
Launch Agent (subagent_type: general-purpose) with `prompts/spec-reviewer.md`:
- Populate with phase description, acceptance criteria, completed plans
- Agent reads all changed files and verifies spec compliance
- Returns APPROVE or REQUEST CHANGES

If REQUEST CHANGES:
- Transition phase back to `executing`
- Log issues as decisions
- Show user what needs fixing

### Step 4: Stage 2 — Code Quality Review
Only runs if Stage 1 passes.

Launch Agent (subagent_type: general-purpose) with `prompts/code-quality-reviewer.md`:
- Populate with phase name, changed files, project conventions
- Agent reviews code quality, security, performance
- Returns APPROVE, PASS WITH NOTES, or REQUEST CHANGES

### Step 4.5: Cross-Model Review (if --cross-model)

Only runs if Stage 2 passes. Requires a secondary AI CLI installed.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.cross_review import detect_models
models = detect_models()
print(json.dumps(models, indent=2))
"
```

If models are available, build and run the cross-review:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.cross_review import build_review_prompt, run_external_review, parse_findings
prompt = build_review_prompt(<changed_files>, phase_name='<name>', phase_description='<desc>')
result = run_external_review('<model_id>', prompt)
if result['success']:
    findings = parse_findings(result['output'])
    import json
    print(json.dumps(findings, indent=2))
else:
    print(f'Cross-review failed: {result[\"error\"]}')
"
```

Compare with Claude's findings and display the comparison report.
Store the cross-review result:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.state import create_review
with open_project('.') as conn:
    create_review(conn, phase_id=<phase_id>, stage=2, result='<pass|fail>',
                  feedback='<cross_review_summary>', model='<model_id>')
"
```

If no secondary models are available, skip with a note: "No secondary AI CLI detected. Install codex, gemini, or aider for cross-model review."

### Step 5: Transition Phase
If both stages pass:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_phase
conn = connect(get_db_path('.'))
transition_phase(conn, <phase_id>, 'reviewing')
conn.close()
"
```

If either stage fails, log findings and keep phase in current state.

### Step 6: Log Review Decision
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, 'Review <passed|failed>: <summary>',
    category='approach', phase_id=<phase_id>)
conn.close()
"
```

### Step 7: Persist Review Result
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.state import create_review
with open_project('.') as conn:
    create_review(conn, phase_id=<phase_id>, stage=<stage>, result='<pass|pass_with_notes|fail>',
                  feedback='<review_feedback>')
"
```

## Output
Display review results in a clear format with PASS/FAIL per stage and specific feedback.
