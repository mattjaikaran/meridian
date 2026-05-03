# /meridian:roadmap — Cross-Milestone Roadmap

Display a high-level roadmap view across all milestones with phase progress and ETA.

## Procedure

### Step 1: Load State
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import list_milestones, list_phases, list_plans
from scripts.metrics import compute_progress, forecast_completion

conn = connect(get_db_path('.'))
milestones = list_milestones(conn)
progress = compute_progress(conn)
forecast = forecast_completion(conn)

result = {'milestones': [], 'progress': progress, 'forecast': forecast}
for ms in milestones:
    phases = list_phases(conn, ms['id'])
    phase_data = []
    for ph in phases:
        plans = list_plans(conn, ph['id'])
        done = sum(1 for p in plans if p['status'] in ('complete', 'skipped'))
        phase_data.append({
            'name': ph['name'],
            'status': ph['status'],
            'done': done,
            'total': len(plans),
            'priority': ph.get('priority'),
        })
    result['milestones'].append({
        'id': ms['id'],
        'name': ms['name'],
        'status': ms['status'],
        'phases': phase_data,
    })

print(json.dumps(result, indent=2, default=str))
conn.close()
"
```

### Step 2: Format Output

Display in this format:

```
# Roadmap — {project_name}

## {milestone_name} ({status}) — {pct}%{  — ETA {date} if active}
  Phase 1: {name} [{status}] {checkmark if complete}
  Phase 2: {name} [{status}] {arrow if current}
  Phase 3: {name} [{status}]

## {milestone_name} ({status})
  Phase 1: {name} [{status}]
  Phase 2: {name} [{status}]
```

Use these markers:
- `[complete]` with checkmark for finished phases
- `[{status}]` with left-arrow `<-` for the current active phase
- `[planned]` for future phases
- Show plan counts as `({done}/{total})` after phase name if plans exist

### Step 3: Show Summary Stats

At the bottom, show:
```
---
Active velocity: {velocity} plans/day | Forecast: {eta_days} days remaining
```

## Options
- `--json` — Output raw JSON instead of formatted roadmap
- `--all` — Include archived milestones (hidden by default)
