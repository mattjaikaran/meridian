# /meridian:insert-phase — Insert Phase Mid-Milestone

Insert an urgent phase between existing phases using decimal sequencing.

## Arguments

- `--after <sequence>` — Insert after this phase sequence number.
- `<name>` — Name of the new phase.
- `<description>` — Description of the new phase.

## Keywords

insert, add phase, urgent, decimal phase, mid-milestone, between

## Procedure

1. **Insert the phase:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json, sys
from scripts.db import open_project
from scripts.phase_manipulation import insert_phase
from scripts.state import get_status
after = int(sys.argv[1])
name = sys.argv[2]
desc = sys.argv[3] if len(sys.argv) > 3 else ''
with open_project('.') as conn:
    status = get_status(conn)
    ms = status.get('active_milestone')
    phase = insert_phase(conn, ms['id'], after, name, desc)
    print(json.dumps(phase, default=str, indent=2))
" "$AFTER" "$NAME" "$DESC"
```

2. **Show updated phase order:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.phase_manipulation import list_phases_ordered
from scripts.state import get_status
with open_project('.') as conn:
    status = get_status(conn)
    ms = status.get('active_milestone')
    phases = list_phases_ordered(conn, ms['id'])
    for p in phases:
        print(f\"  {p['sequence']:>5} | {p['name']} [{p['status']}]\")
"
```

## Output

Show the created phase with its decimal sequence number and the updated phase ordering.
