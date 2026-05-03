# /meridian:workstream — Multi-Track Parallel Work Management

Workstreams are named parallel tracks of development, each owning a set of milestones.
Use them when you're juggling multiple independent bodies of work (e.g., a backend rewrite
alongside a new mobile feature). Switching workstreams pauses the current one and resumes
the target.

## Arguments
- `create <name> [description]` — Create a new workstream
- `list` — Show all workstreams
- `list --active` — Show only active workstreams
- `list --paused` — Show only paused workstreams
- `status <slug>` — Show a single workstream's details and milestone progress
- `switch <slug>` — Make a workstream the active session track (pauses current)
- `progress` — Show progress across all workstreams
- `complete <slug>` — Mark a workstream complete
- `resume <slug>` — Re-activate a paused workstream without switching session
- `assign <milestone-id> <workstream-slug>` — Assign a milestone to a workstream

## Keywords
workstream, track, parallel, portfolio, multi-track, switch, stream

---

## Procedure

### Subcommand: create
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import create_workstream
with open_project('.') as conn:
    ws = create_workstream(conn, '<name>', '<description>')
    print(json.dumps(ws, indent=2))
"
```

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import list_workstreams
with open_project('.') as conn:
    workstreams = list_workstreams(conn, status=<'active'|'paused'|'complete'|'archived'|None>)
    for ws in workstreams:
        marker = f\"[{ws['status']}]\"
        print(f\"{marker} {ws['slug']} — {ws['name']}\")
"
```

### Subcommand: status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import get_workstream_progress
with open_project('.') as conn:
    prog = get_workstream_progress(conn, '<slug>')
    print(json.dumps(prog, indent=2))
"
```

### Subcommand: switch
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import switch_workstream, get_active_workstream
with open_project('.') as conn:
    ws = switch_workstream(conn, '<slug>')
    print(json.dumps(ws, indent=2))
"
```

### Subcommand: progress
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import get_all_workstreams_progress
with open_project('.') as conn:
    all_prog = get_all_workstreams_progress(conn)
    print(json.dumps(all_prog, indent=2))
"
```

### Subcommand: complete
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import complete_workstream
with open_project('.') as conn:
    ws = complete_workstream(conn, '<slug>')
    print(json.dumps(ws, indent=2))
"
```

### Subcommand: resume
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.workstreams import resume_workstream
with open_project('.') as conn:
    ws = resume_workstream(conn, '<slug>')
    print(json.dumps(ws, indent=2))
"
```

### Subcommand: assign
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.workstreams import assign_milestone
with open_project('.') as conn:
    assign_milestone(conn, '<milestone-id>', '<workstream-slug>')
    print('Milestone <milestone-id> assigned to workstream <workstream-slug>')
"
```

---

## Display Format

### After create / switch / complete / resume:
```
Workstream: <slug>
Name: <name>
Status: active|paused|complete|archived
Updated: <timestamp>

<description>
```

### After list:
| Status | Slug | Name | Updated |
|--------|------|------|---------|
| [active] | backend-rewrite | Backend Rewrite | 2026-04-28 |
| [paused] | mobile-app | Mobile App | 2026-04-20 |

### After status / progress:
```
## Workstream: <name> (<status>)
Overall: 42% (5/12 phases complete)

| Milestone | Status | Progress |
|-----------|--------|----------|
| v1.0 Auth | active | 3/4 phases |
| v1.1 API  | planned | 0/4 phases |
```

### After progress (all workstreams):
```
## Portfolio Progress

| Workstream | Status | Milestones | Phases | Progress |
|------------|--------|------------|--------|----------|
| backend-rewrite | active | 2 | 12 | 42% |
| mobile-app | paused | 1 | 4 | 75% |
```

---

## Session Awareness

`/meridian:workstream switch <slug>` persists the active workstream in project settings.
`/meridian:status --all-workstreams` shows progress across all tracks.

The dashboard (`/meridian:dashboard`) includes a workstream panel when any workstreams exist.

## When to Use
- Multiple independent features being developed in parallel
- Separating product tracks (frontend, backend, mobile) for a solo dev
- Managing a portfolio of milestones across different clients or areas

## When NOT to Use
- Single linear project with one milestone at a time → just use milestones
- Short explorations → use `/meridian:spike`
- Loose context capture → use `/meridian:thread`
