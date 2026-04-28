# /meridian:review — Two-Stage Code Review

Run spec compliance + code quality review on completed work.

## Arguments
- `--phase <id>` — Review specific phase (default: current phase)
- `--stage <1|2>` — Run only one stage
- `--files <paths>` — Review specific files instead of full phase
- `--cross-model` — Run independent review from a secondary AI model after Stage 2
- `--persona <name>` — Apply role-typed review lens (pm, architect, ux, qa, security)

## Procedure

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
