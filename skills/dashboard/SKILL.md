# /meridian:dashboard — Project Dashboard

Single-view status + metrics: health, progress, velocity, stalls, remote dispatches, and next action.

## Procedure

### Step 1: Load Metrics and State
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_status, compute_next_action
from scripts.metrics import compute_velocity, compute_progress, detect_stalls, forecast_completion
from scripts.sync import get_dispatch_summary

conn = connect(get_db_path('.'))
status = get_status(conn)
velocity = compute_velocity(conn)
progress = compute_progress(conn)
stalls = detect_stalls(conn)
forecast = forecast_completion(conn)
dispatches = get_dispatch_summary(conn)

print(json.dumps({
    'status': status,
    'velocity': velocity,
    'progress': progress,
    'stalls': stalls,
    'forecast': forecast,
    'dispatches': dispatches,
}, indent=2, default=str))
conn.close()
"
```

### Step 2: Determine Health

Compute project health from metrics:
- **ON TRACK**: No stalls, velocity > 0, milestone ETA exists
- **AT RISK**: 1-2 stalls OR velocity dropped to 0 recently
- **STALLED**: 3+ stalls OR no plans completed in 3+ days

### Step 3: Format Output

Display in this format:

```
# Project Dashboard — {project_name}
## Health: {ON TRACK | AT RISK | STALLED}

Milestone: {name} ({status}) — {pct}% complete{, ETA {date} if available}
Phase {N}/{total}: {name} [{status}] — {done}/{total} plans done
Velocity: {velocity} plans/day (7d avg)

### Stalls
- Plan "{name}" stuck in {status} for {hours}h
- Phase "{name}" stuck in {status} for {hours}h
(or "None" if no stalls)

### Nero Dispatches
- Plan "{name}" → Nero ({status}{, PR #N if available})
(or "None" if no dispatches)

### Next Action
→ {computed_next_action}
```

### Step 4: Priority Items (if any)

If any phases or plans have `priority` set, show a priority summary:

```
### Priority Items
- [critical] Plan: "{name}" — {status}
- [high] Phase: "{name}" — {status}
```

## Options
- `--json` — Output raw JSON instead of formatted dashboard
- `--html [path]` — Generate standalone HTML dashboard (default: .meridian/dashboard.html)
- `--no-sync` — Skip pulling Nero dispatch status before rendering

### HTML Dashboard

If `--html` is specified:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.html_dashboard import write_dashboard
with open_project('.') as conn:
    path = write_dashboard(conn, '<output_path>')
    print(f'Dashboard written to {path}')
"
```

Opens in browser automatically if on macOS: `open <output_path>`
