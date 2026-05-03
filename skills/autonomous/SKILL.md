# /meridian:autonomous — Hands-Free Execution

Run discuss→plan→execute for each remaining phase without manual intervention.

## Arguments

- `--from <phase_id>` — Start from this phase.
- `--to <phase_id>` — Stop after this phase.
- `--only <phase_id>` — Run a single phase autonomously.

## Keywords

autonomous, auto, hands-free, unattended, run all, batch execute

## Procedure

1. **Plan the run** — Determine which phases need processing.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.autonomous import plan_autonomous_run
from scripts.state import get_status
with open_project('.') as conn:
    status = get_status(conn)
    ms = status.get('active_milestone')
    if not ms:
        print('ERROR: No active milestone')
    else:
        result = plan_autonomous_run(conn, ms['id'])
        print(json.dumps(result, default=str, indent=2))
"
```

2. **For each phase**, determine the next step and dispatch:
   - `discuss` → Run `/meridian:discuss --auto` for the phase
   - `plan` → Run `/meridian:plan` for the phase
   - `execute` → Run `/meridian:execute` for the phase
   - `verify` → Transition to reviewing
   - `complete` → Skip (already done)

3. **On failure**, stop the loop and report which phase/step failed with error context. The state is resumable — running `/meridian:autonomous` again picks up where it left off.

## Output

Show progress per phase: phase name, current step, result. On completion, show summary of phases processed.
