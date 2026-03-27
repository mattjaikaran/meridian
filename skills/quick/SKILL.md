# /meridian:quick — Lightweight Quick Task

Execute a small task without phase/plan overhead. Still tracked in SQLite.

## Arguments
- `<description>` — What to do

## Procedure

### Step 1: Create Quick Task
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import create_quick_task
conn = connect(get_db_path('.'))
qt = create_quick_task(conn, '<description>')
print(json.dumps(qt, default=str))
conn.close()
"
```

### Step 2: Mark Executing
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_quick_task
conn = connect(get_db_path('.'))
transition_quick_task(conn, <task_id>, 'executing')
conn.close()
"
```

### Step 3: Do the Work
Execute the task inline (no subagent needed for quick tasks).
- Make the changes
- Run tests if applicable
- Commit with `[meridian:quick]` prefix

### Step 4: Mark Complete
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import connect, get_db_path
from scripts.state import transition_quick_task
conn = connect(get_db_path('.'))
transition_quick_task(conn, <task_id>, 'complete', commit_sha='<sha>')
conn.close()
"
```

## When to Use
- Bug fixes that take < 10 minutes
- Typo corrections
- Config changes
- Small refactors
- Anything that doesn't need phase overhead

## When NOT to Use
- Multi-file features → use `/meridian:plan` + `/meridian:execute`
- Anything requiring design decisions → use `/meridian:plan`
- Work that needs review → use full pipeline
