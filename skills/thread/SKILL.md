# /meridian:thread — Persistent Discussion Threads

Lightweight, phase-independent threads for capturing ongoing context, decisions, or
explorations. Lighter than `/meridian:pause` — no checkpoint, no phase coupling.
Can be promoted to backlog items when ready.

## Arguments
- `create <title> [body]` — Open a new thread (slug derived from title)
- `list` — Show all threads (open + resolved)
- `list --open` — Show only open threads
- `list --resolved` — Show only resolved threads
- `status <slug>` — Show a single thread's full body and metadata
- `resume <slug>` — Re-open a resolved thread
- `close <slug>` — Mark a thread as resolved
- `promote <slug>` — Export thread to .planning/backlog/ and close it

## Keywords
thread, discussion, context, exploration, capture, idea, ongoing, track, promote

## Procedure

### Subcommand: create
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.threads import create_thread
with open_project('.') as conn:
    t = create_thread(conn, '<title>', '<body>')
    print(json.dumps(t, indent=2))
"
```

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.threads import list_threads
with open_project('.') as conn:
    threads = list_threads(conn, status=<'open'|'resolved'|None>)
    for t in threads:
        marker = '[open]' if t['status'] == 'open' else '[resolved]'
        print(f\"{marker} {t['slug']} — {t['updated_at']}\")
"
```

### Subcommand: status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.threads import get_thread
with open_project('.') as conn:
    t = get_thread(conn, '<slug>')
    if t:
        print(json.dumps(t, indent=2))
    else:
        print('Thread not found')
"
```

### Subcommand: resume
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.threads import reopen_thread
with open_project('.') as conn:
    t = reopen_thread(conn, '<slug>')
    print(json.dumps(t, indent=2))
"
```

### Subcommand: close
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.threads import close_thread
with open_project('.') as conn:
    t = close_thread(conn, '<slug>')
    print(json.dumps(t, indent=2))
"
```

### Subcommand: promote
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.threads import promote_to_backlog
with open_project('.') as conn:
    result = promote_to_backlog(conn, '<slug>', Path('.'))
    print(json.dumps(result, indent=2))
"
```

## Display Format

After any write operation, show:
```
Thread: <slug>
Status: open|resolved
Updated: <timestamp>

<body>
```

After list, show a compact table:

| Status | Slug | Updated |
|--------|------|---------|
| [open] | ... | ... |

## When to Use
- Capture a multi-sentence thought that doesn't fit in a note
- Track an ongoing decision or exploration across sessions
- Hold context for a feature you're not ready to plan yet
- Bridge between ad-hoc thinking and formal backlog items

## When NOT to Use
- Quick one-liners → use `/meridian:note`
- Suspending active work with state → use `/meridian:pause`
- Formal task tracking → use `/meridian:quick` or `/meridian:plan`
