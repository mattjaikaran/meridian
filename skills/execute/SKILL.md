# /meridian:execute — Execution Engine

Run plans via fresh-context subagents with TDD enforcement and 2-stage review.

## Arguments
- `--phase <id>` — Execute specific phase (default: current phase)
- `--plan <id>` — Execute single plan
- `--wave <n>` — Execute specific wave only
- `--no-review` — Skip 2-stage review (not recommended)
- `--inline` — Execute in current context instead of subagent

## Procedure

### Step 1: Determine What to Execute
```bash
uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import compute_next_action, get_phase, list_plans
conn = connect(get_db_path('.'))
action = compute_next_action(conn)
print(json.dumps(action, indent=2, default=str))
conn.close()
"
```

If action is `execute` or `execute_plan`, proceed. Otherwise, show the required action.

### Step 2: Transition Phase to Executing
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_phase
conn = connect(get_db_path('.'))
transition_phase(conn, <phase_id>, 'executing')
conn.close()
"
```

### Step 3: Execute Plans by Wave

For each wave (starting from 1):

#### 3a. Get plans for current wave
```bash
uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_plans_by_wave
conn = connect(get_db_path('.'))
plans = get_plans_by_wave(conn, <phase_id>, <wave>)
print(json.dumps(plans, indent=2, default=str))
conn.close()
"
```

#### 3b. For each pending plan in the wave:

1. **Mark plan as executing**:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_plan
conn = connect(get_db_path('.'))
transition_plan(conn, <plan_id>, 'executing')
conn.close()
"
```

2. **Dispatch subagent** with the implementer prompt (`prompts/implementer.md`):
   - Use Agent tool with `subagent_type: "general-purpose"`
   - Include plan description, files to create/modify, test command
   - Include project context from phase's `context_doc`
   - If TDD required, include TDD protocol from discipline-protocols.md

3. **On success**: Mark plan complete with commit SHA:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_plan
conn = connect(get_db_path('.'))
transition_plan(conn, <plan_id>, 'complete', commit_sha='<sha>')
conn.close()
"
```

4. **On failure**: Mark plan failed:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_plan
conn = connect(get_db_path('.'))
transition_plan(conn, <plan_id>, 'failed', error_message='<error>')
conn.close()
"
```

#### 3c. Plans in the same wave CAN be dispatched in parallel using multiple Agent calls.

### Step 4: After All Plans Complete

Transition phase to verifying:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_phase
conn = connect(get_db_path('.'))
transition_phase(conn, <phase_id>, 'verifying')
conn.close()
"
```

### Step 5: Verify Acceptance Criteria
Check each acceptance criterion against the implemented code. Run tests.

### Step 6: Two-Stage Review (unless --no-review)

**Stage 1 — Spec Compliance**: Launch Agent with `prompts/spec-reviewer.md`
- Does implementation match plan descriptions?
- Are all acceptance criteria met?
- Are specified files created/modified?

**Stage 2 — Code Quality**: Launch Agent with `prompts/code-quality-reviewer.md`
- Code cleanliness and readability
- Security concerns
- Performance considerations
- Convention adherence

### Step 7: Complete Phase
If review passes:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_phase
conn = connect(get_db_path('.'))
transition_phase(conn, <phase_id>, 'reviewing')
transition_phase(conn, <phase_id>, 'complete')
conn.close()
"
```

If review fails, transition back to `executing` with notes on what needs fixing.

### Step 8: Checkpoint
Create automatic checkpoint after phase completion:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_checkpoint
conn = connect(get_db_path('.'))
create_checkpoint(conn, trigger='phase_complete', phase_id=<phase_id>)
conn.close()
"
```

### Step 9: Export and Show Next Action
```bash
uv run --project ~/dev/meridian python -c "
from scripts.export import export_state
from scripts.db import connect, get_db_path
from scripts.state import compute_next_action
export_state('.')
conn = connect(get_db_path('.'))
import json
print(json.dumps(compute_next_action(conn), indent=2, default=str))
conn.close()
"
```
