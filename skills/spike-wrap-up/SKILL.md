# /meridian:spike-wrap-up — Close a Spike and Extract Learnings

Concludes a spike: records the outcome, extracts learnings into the DB, and closes
the gate so dependent plan phases can proceed.

## Arguments
- `<slug> "<outcome>"` — Close spike and record outcome (no learnings)
- `<slug> "<outcome>" --learnings "<rule1>" "<rule2>" ...` — Also extract learnings

## Keywords
spike, wrap-up, close, conclude, outcome, learnings, findings, gate

## Procedure

### Wrap up without explicit learnings
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.spikes import wrap_up_spike
with open_project('.') as conn:
    result = wrap_up_spike(
        conn,
        '<slug>',
        '<outcome>',
        [],  # no explicit learnings
        Path('.'),
    )
    print(json.dumps(result, indent=2))
"
```

### Wrap up with learnings
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.spikes import wrap_up_spike
with open_project('.') as conn:
    result = wrap_up_spike(
        conn,
        '<slug>',
        '<outcome>',
        ['<learning rule 1>', '<learning rule 2>'],
        Path('.'),
    )
    print(json.dumps(result, indent=2))
"
```

## What Happens on Wrap-Up

1. Spike status → `closed`, `closed_at` set to now
2. Outcome written to DB and to `.planning/spikes/<slug>/MANIFEST.md`
3. Each learning rule inserted into the `learning` table (scope: project, source: execution)
4. Gate is now clear — `/meridian:plan` on the linked phase can proceed

## Display Format

```
Spike wrapped up: <slug>
Status: closed
Outcome: <outcome>

Learnings recorded: <N>
  1. <rule 1>
  2. <rule 2>

Gate cleared for phase: <phase_id or "(none)">
Next: run /meridian:plan on phase <phase_id>
```

## When to Use
- You've finished the exploration and have an answer
- Use before starting `/meridian:plan` on the phase that triggered the spike
- After adding finding files to `.planning/spikes/<slug>/findings/`

## Notes
- Learnings are stored with `source = 'execution'` and linked to the triggering phase
- The MANIFEST.md is updated in-place with the outcome section
- Once closed, a spike cannot be re-opened (create a new spike instead)
