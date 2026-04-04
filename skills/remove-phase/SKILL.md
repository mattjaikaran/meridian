# /meridian:remove-phase — Remove Phase

Remove a planned phase and renumber subsequent phases.

## Arguments

- `<phase_id>` — ID of the phase to remove (must be in 'planned' status).

## Keywords

remove, delete, phase, renumber, cleanup

## Procedure

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json, sys
from scripts.db import open_project
from scripts.phase_manipulation import remove_phase
phase_id = int(sys.argv[1])
with open_project('.') as conn:
    result = remove_phase(conn, phase_id)
    print(result['message'])
" "$PHASE_ID"
```

## Output

Confirmation of removal with count of deleted plans and renumbered phases.
