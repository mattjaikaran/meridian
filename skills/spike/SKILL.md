# /meridian:spike — Pre-Commitment Exploration

Time-boxed investigations that answer a specific question before planning begins.
A spike creates a structured artifact directory and blocks dependent plan phases until closed.

## Arguments
- `create <title> [question]` — Open a new spike (slug derived from title)
- `list` — Show all spikes (open + closed)
- `list --open` — Open spikes only
- `list --closed` — Closed spikes only
- `status <slug>` — Show spike details, question, outcome, and findings
- `add-finding <slug> <filename> <content>` — Add a finding file to the spike
- `frontier` — Scan existing spikes; propose next ones based on unspike'd phases

## Keywords
spike, explore, investigation, question, research, pre-commitment, experiment, frontier

## Procedure

### Subcommand: create
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.spikes import create_spike
with open_project('.') as conn:
    s = create_spike(conn, '<title>', '<question>', Path('.'))
    print(json.dumps(s, indent=2))
"
```

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.spikes import list_spikes
with open_project('.') as conn:
    spikes = list_spikes(conn, status=<'open'|'closed'|None>)
    for s in spikes:
        marker = '[open]' if s['status'] == 'open' else '[closed]'
        print(f\"{marker} {s['slug']} — {s['title']} ({s['updated_at']})\")
"
```

### Subcommand: status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.spikes import get_spike
with open_project('.') as conn:
    s = get_spike(conn, '<slug>')
    if s:
        print(json.dumps(s, indent=2))
    else:
        print('Spike not found')
"
```
Then read `.planning/spikes/<slug>/MANIFEST.md` and list files in `.planning/spikes/<slug>/findings/`.

### Subcommand: add-finding
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from pathlib import Path
from scripts.spikes import add_finding
path = add_finding('<slug>', '<filename>', '''<content>''', Path('.'))
print(f'Written: {path}')
"
```

### Subcommand: frontier
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.spikes import frontier_scan
with open_project('.') as conn:
    result = frontier_scan(conn, Path('.'))
    print(json.dumps(result, indent=2))
"
```

## Display Format

After create/status, show:
```
Spike: <slug>
Status: open|closed
Question: <question>
Updated: <timestamp>
Artifact: .planning/spikes/<slug>/

<outcome if closed>
```

After list:
| Status | Slug | Title | Updated |
|--------|------|-------|---------|
| [open] | ... | ... | ... |

After frontier:
```
## Open Spikes (<N>)
  - slug: question summary

## Proposed Next Spikes
  - Phase <id>: <suggested_title>

## Orphaned Dirs
  - <dirname>
```

## Gate Behavior

Before `/meridian:plan` starts on a phase, run:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.spikes import check_spike_gate
with open_project('.') as conn:
    blockers = check_spike_gate(conn, <phase_id>)
    print(json.dumps(blockers, indent=2))
"
```
If blockers is non-empty, warn the user:
> ⚠ Phase has {N} open spike(s). Close them with `/meridian:spike-wrap-up` before planning.

## When to Use
- Architecture decision with meaningful unknowns
- New tech integration where complexity is unclear
- Security-sensitive flows before spec/plan
- Performance-critical paths needing profiling first

## When NOT to Use
- You already know the answer → go straight to `/meridian:plan`
- Pure task tracking → use `/meridian:quick`
- Capturing a thought → use `/meridian:note` or `/meridian:thread`
