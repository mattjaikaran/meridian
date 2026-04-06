# /meridian:dispatch — Remote Agent Dispatch

Send plans to a self-hosted AI agent for autonomous execution. The agent picks up the task, implements it, and creates a PR.

Compatible with any agent that implements the dispatch protocol (Nero, OpenClaw, Hermes, or custom).

## Arguments
- `--plan <id>` — Dispatch specific plan
- `--phase <id>` — Dispatch all pending plans in phase
- `--swarm` — Dispatch all pending plans at once (parallel PRs)
- `--status <dispatch_id>` — Check dispatch status
- `--check-all` — Check status of all active dispatches

## Prerequisites
- Project must have `nero_endpoint` configured (set during `/meridian:init`)
- Remote agent must be running and reachable
- Plans must be in `pending` status

## Procedure

### Dispatch a Plan
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.dispatch import dispatch_plan
result = dispatch_plan('.', plan_id=<plan_id>)
print(json.dumps(result, indent=2, default=str))
"
```

### Dispatch a Phase (Wave-Ordered)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.dispatch import dispatch_phase
results = dispatch_phase('.', phase_id=<phase_id>)
print(json.dumps(results, indent=2, default=str))
"
```

### Dispatch Phase Swarm (All Parallel)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.dispatch import dispatch_phase
results = dispatch_phase('.', phase_id=<phase_id>, swarm=True)
print(json.dumps(results, indent=2, default=str))
"
```

### Check Status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.dispatch import check_dispatch_status
result = check_dispatch_status('.', dispatch_id=<id>)
print(json.dumps(result, indent=2, default=str))
"
```

## Integration Notes
- Agent endpoint: configured per-project (e.g. `http://<agent-host>:7655`)
- Dispatches tracked in `nero_dispatch` table (name is historical)
- Agent returns a `task_id` for tracking
- Completed dispatches include `pr_url`
- Export state after dispatch so the agent can read `meridian-state.json`
- See `references/remote-agent.md` for the full protocol spec
