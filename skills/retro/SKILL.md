# /meridian:retro — Structured Retrospective

Generate a metrics-driven retrospective for a time period or milestone.

## Arguments
- `--since <days>` — Look back N days (default: 7)
- `--milestone <id>` — Retro for entire milestone instead of time window

## Keywords
retro, retrospective, review, reflect, velocity, streak, what shipped, what went wrong

## Procedure

### Step 1: Generate Retro Data
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.retro import generate_retro
with open_project('.') as conn:
    retro = generate_retro(conn, since_days=<since_days>)
    print(json.dumps(retro, indent=2, default=str))
"
```

### Step 2: Format and Display
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.retro import generate_retro, format_retro
with open_project('.') as conn:
    retro = generate_retro(conn, since_days=<since_days>)
    print(format_retro(retro))
"
```

### Step 3: Suggest Action Items

Based on the retro data, suggest concrete action items:
- For stalls: investigate root causes, adjust thresholds
- For failures: check if learnings were captured, suggest pattern rules
- For review rejections: identify common rejection reasons
- For velocity changes: note what helped or hurt

### Step 4: Optionally Capture Learnings

If the retro surfaces patterns worth remembering, offer to save them via `/meridian:learn`.

## When to Use
- End of week check-in
- After completing a milestone
- When velocity feels off
- Before planning a new milestone

## When NOT to Use
- Mid-sprint (use `/meridian:status` instead)
- No completed work yet (nothing to retro on)
