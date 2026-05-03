# /meridian:revert — Revert Completed Plan

Revert a completed plan back to pending status.

## Arguments
- `--plan <id>` — Plan ID to revert (required)
- `--reason <text>` — Reason for reverting

## Procedure

### Step 1: Verify Plan Status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.state import get_plan
with open_project('.') as conn:
    plan = get_plan(conn, <plan_id>)
    print(json.dumps(plan, indent=2, default=str))
"
```

Confirm the plan is in `complete` status before proceeding.

### Step 2: Revert Plan
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.state import revert_plan
with open_project('.') as conn:
    result = revert_plan(conn, <plan_id>, reason='<reason>')
    print(json.dumps(result, indent=2, default=str))
"
```

### Step 3: Confirm
Display the reverted plan showing status=pending with cleared fields.

## Output
Show the plan before and after revert, confirming commit_sha, error_message, and completed_at are cleared.
