# /meridian:ultraplan — Cloud-Accelerated Planning

Deep planning with optional Claude Code cloud backend offload. Falls back to local
`/meridian:plan` automatically if cloud is unavailable or not configured.

**BETA** — Cloud backend requires Claude Code ≥ v2.1.91 and `ultraplan_enabled: true`
in project config.

## Arguments

- `<goal>` — What to build (same as /meridian:plan)
- `--phase <id>` — Plan a specific phase
- `--deep` — Force deep discovery questions before planning
- `--local` — Skip cloud check, run local planning directly
- `--cloud` — Require cloud backend; fail if unavailable instead of falling back
- `--dry-run` — Check cloud availability and print mode; do not plan

## Keywords

ultraplan, cloud plan, deep plan, accelerated, offload, v2.1

## Procedure

### Step 1: Check Cloud Availability

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.ultraplan import check_ultraplan_availability
result = check_ultraplan_availability('.')
print(json.dumps(result, indent=2))
"
```

**Result fields:**
- `available: bool` — cloud backend reachable and configured
- `version: str | null` — Claude Code version detected
- `mode: 'cloud' | 'local'` — resolved planning mode
- `reason: str` — human-readable explanation

If `--dry-run`: print the result and stop.

If `--local` flag: skip this step, set mode = `local`.

If `--cloud` flag and `available: false`: print reason and stop with error.

### Step 2: Display Mode Banner

Show the user which mode will be used:

```
## Ultraplan — <CLOUD | LOCAL> Mode

<reason>
```

For CLOUD mode:
```
## Ultraplan — CLOUD Mode

Offloading plan generation to Claude Code cloud backend.
Larger context window, parallel analysis, faster turnaround.
```

For LOCAL mode (fallback):
```
## Ultraplan — LOCAL Mode (fallback)

Cloud backend unavailable: <reason>
Running local planning pipeline.
```

### Step 3: Execute Planning

**If CLOUD mode:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.ultraplan import run_cloud_plan
result = run_cloud_plan('.', phase_id=<phase_id_or_None>, goal='<goal_or_empty>')
print(json.dumps(result, indent=2, default=str))
"
```

If result contains `error` or `status: 'failed'`: print the error, then fall back to local mode unless `--cloud` was passed.

If result `status: 'success'`: display the plan summary and artifact paths. Skip Step 3b.

**If LOCAL mode (or CLOUD fallback):**

Invoke `/meridian:plan` with the same arguments passed to ultraplan:
- Pass `--phase <id>` if specified
- Pass `--deep` if specified
- Pass `<goal>` if specified

This is a direct skill invocation — follow the full `/meridian:plan` procedure.

### Step 4: Log Mode Decision

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.state import create_decision
with open_project('.') as conn:
    create_decision(
        conn,
        'Ultraplan: used <cloud|local> mode — <reason>',
        category='approach',
    )
"
```

### Step 5: Display Summary

```
## Ultraplan Complete

Mode: <CLOUD | LOCAL>
Phase: <phase_name>
Plans generated: <N>

Next: /meridian:execute
```

## Cloud Backend Protocol

When `available: true`, Ultraplan sends the phase context to the cloud endpoint
and receives a structured plan response. The cloud backend:

- Has access to a larger context window for cross-phase analysis
- Runs multiple planning subagents in parallel server-side
- Returns plans in the same format as local planning (compatible with /meridian:execute)

Cloud endpoint is read from project config `ultraplan_endpoint`. If not set,
availability check returns `available: false`.

## Availability Matrix

| Condition | Mode |
|---|---|
| `--local` flag | LOCAL (always) |
| `--cloud` flag + cloud unavailable | ERROR (stop) |
| `ultraplan_enabled: false` in config | LOCAL |
| `ultraplan_endpoint` not configured | LOCAL |
| Claude Code < v2.1.91 | LOCAL |
| All conditions met | CLOUD |

## Fallback Guarantee

Ultraplan NEVER silently fails. If cloud is unavailable, it always falls back to
local planning (unless `--cloud` forces a hard failure). The user always gets a plan.
