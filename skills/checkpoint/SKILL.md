# /meridian:checkpoint — Manual Save Point

Create a structured checkpoint with notes for later resume.

## Arguments
- `<notes>` — Optional notes about current state
- `--blockers <list>` — Record blockers

## Procedure

### Step 1: Determine Current Position
```bash
uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import compute_next_action, get_status
conn = connect(get_db_path('.'))
status = get_status(conn)
action = compute_next_action(conn)
print(json.dumps({
    'milestone_id': status['active_milestone']['id'] if status.get('active_milestone') else None,
    'phase_id': status['current_phase']['id'] if status.get('current_phase') else None,
    'action': action
}, default=str))
conn.close()
"
```

### Step 2: Gather Recent Decisions
```bash
uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import list_decisions
conn = connect(get_db_path('.'))
decisions = list_decisions(conn, limit=10)
print(json.dumps(decisions, default=str))
conn.close()
"
```

### Step 3: Create Checkpoint
```bash
uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import create_checkpoint
conn = connect(get_db_path('.'))
create_checkpoint(conn,
    trigger='manual',
    milestone_id='<milestone_id>',
    phase_id=<phase_id>,
    notes='<user_notes>',
    blockers=<blockers_list_or_None>,
    decisions=<recent_decisions>,
    repo_path='.'
)
conn.close()
print('Checkpoint saved.')
"
```

### Step 4: Export State
```bash
uv run --project ~/dev/meridian python -c "
from scripts.export import export_state
export_state('.')
print('State exported to .meridian/meridian-state.json')
"
```

### Step 5: Confirm
Print checkpoint summary with timestamp, position, and notes.
