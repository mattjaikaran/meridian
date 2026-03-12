# /meridian:review — Two-Stage Code Review

Run spec compliance + code quality review on completed work.

## Arguments
- `--phase <id>` — Review specific phase (default: current phase)
- `--stage <1|2>` — Run only one stage
- `--files <paths>` — Review specific files instead of full phase

## Procedure

### Step 1: Gather Review Context
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
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

### Step 5: Transition Phase
If both stages pass:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
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
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
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
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import open_project
from scripts.state import create_review
with open_project('.') as conn:
    create_review(conn, phase_id=<phase_id>, stage=<stage>, result='<pass|pass_with_notes|fail>',
                  feedback='<review_feedback>')
"
```

## Output
Display review results in a clear format with PASS/FAIL per stage and specific feedback.
