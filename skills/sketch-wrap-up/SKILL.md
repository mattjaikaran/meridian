# /meridian:sketch-wrap-up — Pick Winner and Close Sketch

Concludes a sketch session: records the winning variant, archives losers, and closes the gate
so a linked UI phase can proceed.

## Arguments
- `<slug> <variant>` — Pick winner (`variant-a`, `variant-b`, or `variant-c`) and close
- `<slug> <variant> --ui-phase <id>` — Also link the winner to a specific UI phase

## Keywords
sketch, wrap-up, close, winner, pick, archive, design, handoff

## Procedure

### Step 1: Load Sketch Details
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.sketch import get_sketch
with open_project('.') as conn:
    s = get_sketch(conn, '<slug>')
    if s:
        print(json.dumps(s, indent=2))
    else:
        print('not found')
"
```

If not found: display error and stop.
If already closed: display current winner and stop.

Store: `variants` list, `title`, `phase_id`.

### Step 2: Validate Winner Variant

Confirm the chosen variant exists as a file:
```
.planning/sketches/<slug>/<variant>.html
```

If the file does not exist, show:
> ✗ Variant `<variant>.html` not found in .planning/sketches/<slug>/. Available: <list files>.
> Stop.

### Step 3: Wrap Up
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.sketch import wrap_up_sketch
with open_project('.') as conn:
    result = wrap_up_sketch(
        conn,
        '<slug>',
        '<winner_variant>',
        Path('.'),
        ui_phase_id=<ui_phase_id_or_None>,
    )
    print(json.dumps(result, indent=2))
"
```

### Step 4: Display Summary

```
Sketch wrapped up: <slug>
Status: closed
Winner: <variant>.html
Archived: <loser1>.html, <loser2>.html → .planning/sketches/<slug>/archived/

Phase link: <ui_phase_id or "(none)">
Next: run /meridian:ui-phase --phase <ui_phase_id> (passes the winning design as context)
```

## What Happens on Wrap-Up

1. Winner variant stays in `.planning/sketches/<slug>/`
2. All other variant HTML files move to `.planning/sketches/<slug>/archived/`
3. MANIFEST.md updated with winner notation
4. DB record: `status = 'closed'`, `winner_variant` set, `closed_at` set
5. Gate clears — `/meridian:ui-phase` can now reference the winner as design context

## When to Use
- After reviewing the variant HTML files and agreeing on an approach
- Before starting `/meridian:ui-phase` on the same feature
- After stakeholder review selects a direction

## Notes
- Once closed, a sketch cannot be re-opened (create a new sketch instead)
- The winning variant should be referenced in the UI phase SKILL prompt as starting design context
- Archived variants are preserved — not deleted — for reference
