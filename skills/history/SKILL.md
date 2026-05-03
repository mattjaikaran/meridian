# /meridian:history — Event Timeline

Display state transition history for Meridian entities.

## Arguments
- `--type <entity_type>` — Filter by entity type (milestone, phase, plan, quick_task, dispatch, review)
- `--id <entity_id>` — Filter by entity ID
- `--limit <n>` — Max events to show (default: 50)

## Procedure

### Step 1: Query Events
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.state import list_events
with open_project('.') as conn:
    events = list_events(conn, entity_type=<type_or_None>, entity_id=<id_or_None>, limit=<limit>)
    print(json.dumps(events, indent=2, default=str))
"
```

### Step 2: Display Timeline
Format events as a timeline table:

| Time | Entity | Old → New | Metadata |
|------|--------|-----------|----------|

Show most recent events first. If metadata contains JSON, format it inline.

## Output
Display the event timeline in a readable table format.
