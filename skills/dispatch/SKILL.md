# /meridian:dispatch — Nero Dispatch

Send plans to Nero (Mac Mini) for autonomous execution. Nero's Dev agent picks up the task, Crush executes, and a PR is created.

## Arguments
- `--plan <id>` — Dispatch specific plan
- `--phase <id>` — Dispatch all pending plans in phase
- `--swarm` — Dispatch all pending plans at once (parallel PRs)
- `--status <dispatch_id>` — Check dispatch status
- `--check-all` — Check status of all active dispatches

## Prerequisites
- Project must have `nero_endpoint` configured (set during `/meridian:init`)
- Nero must be running on Mac Mini
- Plans must be in `pending` status

## Procedure

### Dispatch a Plan
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.dispatch import dispatch_plan
result = dispatch_plan('.', plan_id=<plan_id>)
print(json.dumps(result, indent=2, default=str))
"
```

### Dispatch a Phase (Wave-Ordered)
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.dispatch import dispatch_phase
results = dispatch_phase('.', phase_id=<phase_id>)
print(json.dumps(results, indent=2, default=str))
"
```

### Dispatch Phase Swarm (All Parallel)
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.dispatch import dispatch_phase
results = dispatch_phase('.', phase_id=<phase_id>, swarm=True)
print(json.dumps(results, indent=2, default=str))
"
```

### Check Status
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.dispatch import check_dispatch_status
result = check_dispatch_status('.', dispatch_id=<id>)
print(json.dumps(result, indent=2, default=str))
"
```

## Nero Integration Notes
- Nero endpoint: configured per-project (e.g. `http://<nero-host>:7655`)
- Dispatches tracked in `nero_dispatch` table
- Nero returns a `task_id` for tracking
- Completed dispatches include `pr_url`
- Export state after dispatch so Nero can read `meridian-state.json`
