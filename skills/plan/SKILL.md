# /meridian:plan — Planning Pipeline

Brainstorm → Context Gather → Generate Plans with Wave Assignments.

## Arguments
- `<goal>` — What to build (required on first run, or creates milestone)
- `--milestone <id>` — Target milestone (default: active milestone)
- `--phase <id>` — Plan a specific phase (skip brainstorming)

## Procedure

### Step 1: Ensure Meridian is Initialized
Check for `.meridian/state.db`. If missing, run `/meridian:init` first.

### Step 2: Check Current State
```bash
uv run --project ~/dev/meridian python -c "
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

### Step 3: Create Milestone (if needed)
If no active milestone exists, create one from the user's goal:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_milestone, transition_milestone
conn = connect(get_db_path('.'))
create_milestone(conn, '<id>', '<name>', description='<description>')
transition_milestone(conn, '<id>', 'active')
conn.close()
"
```

### Step 4: Brainstorm Phases
Think through the work as an architect:
- What are the major work units?
- What depends on what?
- What can be parallelized?
- What are the acceptance criteria for each phase?

Create phases in sequence order:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_phase
conn = connect(get_db_path('.'))
create_phase(conn, '<milestone_id>', '<name>', description='<desc>',
    acceptance_criteria=['criterion 1', 'criterion 2'])
conn.close()
"
```

### Step 5: Context Gathering (per phase)
For the current phase, dispatch a context-gatherer subagent:

Launch an Agent (subagent_type: Explore) with the prompt from `prompts/context-gatherer.md`, customized with:
- Phase name and description
- Project tech stack
- Acceptance criteria

The subagent returns a context document. Store it:
```bash
uv run --project ~/dev/meridian python -c "
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
uv run --project ~/dev/meridian python -c "
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
uv run --project ~/dev/meridian python -c "
from scripts.export import export_state
export_state('.')
"
```

### Step 8: Show Plan Summary
Display all phases and plans in a table, showing wave assignments and dependencies.

### Step 9: Record Decisions
Log any architectural or approach decisions made during planning:
```bash
uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, '<summary>', category='architecture', rationale='<why>')
conn.close()
"
```

## Output
Show the full plan breakdown with phase sequence, plan waves, and next action.
