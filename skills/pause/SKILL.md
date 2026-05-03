# /meridian:pause — Session Handoff

Create a structured HANDOFF.json before ending a session. The next `/meridian:resume` will incorporate this context for richer restoration.

## Arguments
- `[notes]` — Optional freeform notes about what you were working on

## Procedure

### Step 1: Create Handoff
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.handoff import create_handoff
handoff = create_handoff('.', user_notes='<notes>')
print(json.dumps(handoff, indent=2))
"
```

### Step 2: Create Checkpoint
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_checkpoint
conn = connect(get_db_path('.'))
cp = create_checkpoint(conn, trigger='pause', notes='<notes>')
print(f'Checkpoint created: {cp[\"id\"]}')
conn.close()
"
```

### Step 3: Confirm
Report to user:
- Handoff saved to `.meridian/HANDOFF.json`
- Checkpoint recorded in DB
- Next session will auto-load this context via `/meridian:resume`

## When to Use
- End of a work session
- Before context window fills up
- Switching between projects
- Any time you want richer resume context

## When NOT to Use
- Quick breaks (just use `/meridian:checkpoint`)
- If you haven't made meaningful progress to capture
