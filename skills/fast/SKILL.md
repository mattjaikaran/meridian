# /meridian:fast — Inline Fast Task

Execute a trivial task inline without phases or plans. For one-liner changes, typo fixes, and small tweaks.

## Arguments
- `<description>` — What to do (freeform text)

## Keywords
fast, quick, trivial, fix, typo, small, inline, one-liner, tweak, config

## Procedure

### Step 1: Estimate Complexity
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.fast import estimate_complexity
result = estimate_complexity('<description>')
print(json.dumps(result, indent=2))
"
```

If `is_trivial` is False, suggest `/meridian:quick` or `/meridian:plan` instead.

### Step 2: Execute Fast Task
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.fast import execute_fast_task
conn = connect(get_db_path('.'))
result = execute_fast_task(conn, '<description>')
print(json.dumps(result, default=str, indent=2))
conn.close()
"
```

### Step 3: Do the Work
Execute the task inline (no subagent):
- Make the changes
- Run tests if applicable
- Commit with `[meridian:fast]` prefix

### Step 4: Mark Complete
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import connect, get_db_path
from scripts.fast import complete_fast_task
conn = connect(get_db_path('.'))
complete_fast_task(conn, <task_id>, commit_sha='<sha>')
conn.close()
"
```

## When to Use
- Typo fixes
- Config changes
- Single-line bug fixes
- Small documentation updates
- Anything that doesn't need planning

## When NOT to Use
- Multi-file changes (3+ files) → use `/meridian:quick`
- Architectural decisions → use `/meridian:plan`
- Anything requiring design → use full pipeline
