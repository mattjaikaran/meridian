# /meridian:plan — Planning Pipeline

Brainstorm → Context Gather → Generate Plans with Wave Assignments.

## Arguments
- `<goal>` — What to build (required on first run, or creates milestone)
- `--milestone <id>` — Target milestone (default: active milestone)
- `--phase <id>` — Plan a specific phase (skip brainstorming)
- `--deep` — Office hours mode: force 5 strategic questions before brainstorming
- `--scale <small|medium|large>` — Override auto-detected scale (stored in DB)

## Procedure

### Step 1: Ensure Meridian is Initialized
Check for `.meridian/state.db`. If missing, run `/meridian:init` first.

### Step 2: Check Current State
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_status, compute_next_action
conn = connect(get_db_path('.'))
status = get_status(conn)
action = compute_next_action(conn)
print(json.dumps({'status': status, 'action': action}, indent=2, default=str))
conn.close()
"
```

### Step 2.5: Scale Detection

Detect project scale to auto-tune planning depth.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import list_phases
from scripts.scale import detect_scale, get_scale_override
conn = connect(get_db_path('.'))
override = get_scale_override(conn)
conn.close()
# Count phases in active milestone if known
scale = detect_scale('.', override=override)
print(json.dumps(scale, indent=2))
"
```

If `--scale <value>` was passed, persist the override first:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.scale import set_scale_override
conn = connect(get_db_path('.'))
set_scale_override(conn, '<scale_value>')
conn.close()
"
```

**Scale rules:**
- `small` (<5k LOC, ≤3 phases): skip context-gathering subagent, use fast planning. No --deep.
- `medium` (default): standard pipeline (Steps 4–6 as written).
- `large` (≥50k LOC or ≥10 phases): force --deep discovery (Step 3.5), run parallel research subagents before Step 5.

Display scale decision banner before proceeding:
```
## Scale: <SMALL|MEDIUM|LARGE> (<source>)
<rationale>
```

Log the scale decision:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, 'Scale: <scale> — <rationale>', category='approach')
conn.close()
"
```

### Step 3: Create Milestone (if needed)
If no active milestone exists, create one from the user's goal:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_milestone, transition_milestone
conn = connect(get_db_path('.'))
create_milestone(conn, '<id>', '<name>', description='<description>')
transition_milestone(conn, '<id>', 'active')
conn.close()
"
```

### Step 3.5: Deep Discovery (if --deep)

If `--deep` flag is present, ask these 5 forcing questions BEFORE brainstorming.
Use AskUserQuestion for each. Do NOT skip any.

1. **Who needs this?** — "Who is the specific user or persona that benefits? Not 'everyone' — name the person or role."
2. **What's the status quo?** — "How is this handled today without this feature? What workaround exists?"
3. **What's the narrowest wedge?** — "What is the absolute smallest version that delivers value? Strip it to bare minimum."
4. **What breaks without it?** — "What are the consequences of NOT building this? Who is hurt and how?"
5. **What does success look like?** — "Describe a concrete, measurable outcome. How do we know it worked?"

After collecting all 5 answers, store them as a decision:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, 'Deep Discovery: <goal summary>', category='constraint',
    rationale='''Who: <answer1>
Status Quo: <answer2>
Narrowest Wedge: <answer3>
Without It: <answer4>
Success: <answer5>''')
conn.close()
"
```

Feed these answers into Step 4 brainstorming and Step 5 context gathering.
Use the "narrowest wedge" answer to constrain scope.
Use the "success" answer to shape acceptance criteria.

### Step 4: Brainstorm Phases
Think through the work as an architect:
- What are the major work units?
- What depends on what?
- What can be parallelized?
- What are the acceptance criteria for each phase?

Create phases in sequence order:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_phase
conn = connect(get_db_path('.'))
create_phase(conn, '<milestone_id>', '<name>', description='<desc>',
    acceptance_criteria=['criterion 1', 'criterion 2'])
conn.close()
"
```

### Step 5: Context Gathering (per phase)

**Small scale**: skip this step — proceed directly to Step 6 with a brief inline context summary.

**Medium/Large scale**: dispatch a context-gatherer subagent.

Launch an Agent (subagent_type: Explore) with the prompt from `prompts/context-gatherer.md`, customized with:
- Phase name and description
- Project tech stack
- Acceptance criteria

**Large scale only**: also launch a second parallel Agent (subagent_type: general-purpose) focused on
cross-phase risk analysis — what dependencies, shared state, or integration points could break when
this phase is executed. Merge both agents' outputs before storing.

The subagent returns a context document. Store it:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import update_phase, transition_phase
conn = connect(get_db_path('.'))
update_phase(conn, <phase_id>, context_doc='''<gathered_context>''')
transition_phase(conn, <phase_id>, 'context_gathered')
conn.close()
"
```

### Step 6: Generate Plans
Based on the gathered context, break the phase into executable plans:
- Each plan = one subagent's worth of work
- Assign waves for parallelism (wave 1 first, wave 2 after wave 1 completes)
- Specify files to create/modify
- Set test commands
- Mark TDD required/not

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_plan, transition_phase
conn = connect(get_db_path('.'))
create_plan(conn, <phase_id>, '<name>', '<description>',
    wave=1, files_to_create=['path/file.py'], test_command='uv run pytest tests/')
# ... more plans ...
transition_phase(conn, <phase_id>, 'planned_out')
conn.close()
"
```

### Step 7: Export State
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.export import export_state
export_state('.')
"
```

### Step 8: Show Plan Summary
Display all phases and plans in a table, showing wave assignments and dependencies.

### Step 9: Record Decisions
Log any architectural or approach decisions made during planning:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, '<summary>', category='architecture', rationale='<why>')
conn.close()
"
```

## Output
Show the full plan breakdown with phase sequence, plan waves, and next action.
