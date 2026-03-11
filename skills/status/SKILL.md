# /meridian:status — Show Project Status

Display current Meridian state: progress, phase status, blockers, and computed next action.

## Procedure

### Step 1: Load State
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_status
conn = connect(get_db_path('.'))
status = get_status(conn)
print(json.dumps(status, indent=2, default=str))
conn.close()
"
```

### Step 2: Format Output

Display in this format:

```
# Meridian Status — {project_name}

## Milestone: {milestone_name} ({status})

### Phases
| # | Phase | Status | Plans |
|---|-------|--------|-------|
| 1 | Foundation | complete | 3/3 |
| 2 | Features | executing | 1/4 |
| 3 | Polish | planned | 0/0 |

### Current Phase: {phase_name}
Status: {phase_status}
Acceptance Criteria:
- [ ] criterion 1
- [x] criterion 2

### Plans (Phase {N})
| Wave | Plan | Status |
|------|------|--------|
| 1 | Setup DB | complete |
| 1 | Create models | executing |
| 2 | Add API routes | pending |

### Recent Decisions
- [{category}] {summary}

### Next Action
→ {computed_next_action}

### Last Checkpoint
{checkpoint_time} — {trigger}: {notes}
```

### Step 3: Show Git State
Include current branch, last commit, and dirty status.

## Options
- `--full` — Show all milestones, all phases, all decisions
- `--json` — Output raw JSON instead of formatted table
