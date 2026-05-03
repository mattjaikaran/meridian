# /meridian:seed — Backlog Seed Management

Capture forward-looking ideas with optional trigger conditions. Seeds are parked in .meridian/backlog.md and surface when their triggers are met.

## Arguments
- `plant <idea> [--trigger <trigger>]` — Plant a new seed with optional trigger
- `list` — Show all seeds with status and triggers
- `promote <id>` — Promote a seed for inclusion in planning
- `dismiss <id>` — Archive a seed as not needed
- `check` — Check which seeds have triggers met

## Trigger Types
- `after_phase:<name>` — Surface when named phase completes
- `after_milestone:<name>` — Surface at milestone boundary
- `manual` — Only surfaces when explicitly listed (default)

## Keywords
seed, idea, backlog, park, future, trigger, promote, dismiss, parking lot

## Procedure

### Subcommand: plant
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.backlog import plant_seed
result = plant_seed(Path('.'), '<idea>', trigger='<trigger>')
print(json.dumps(result, indent=2))
"
```

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.backlog import list_seeds
seeds = list_seeds(Path('.'))
for s in seeds:
    trigger = s['trigger']['type']
    if s['trigger']['value']:
        trigger += ':' + s['trigger']['value']
    print(f\"[{s['id']}] ({s['status']}) {s['idea']} — trigger: {trigger}\")
"
```

### Subcommand: promote
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.backlog import promote_seed
result = promote_seed(Path('.'), '<id>')
print(json.dumps(result, indent=2))
"
```

### Subcommand: dismiss
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.backlog import dismiss_seed
result = dismiss_seed(Path('.'), '<id>')
print(json.dumps(result, indent=2))
"
```

### Subcommand: check
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.backlog import check_triggers
triggered = check_triggers(Path('.'), completed_phases=['<phase1>', '<phase2>'])
for s in triggered:
    print(f\"[{s['id']}] {s['idea']} — trigger met!\")
"
```

## When to Use
- Capture ideas that aren't ready for planning yet
- Park features for after a specific phase completes
- Review backlog before starting a new milestone

## When NOT to Use
- For immediate tasks → use /meridian:quick
- For notes/thoughts → use /meridian:note
