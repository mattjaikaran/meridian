# /meridian:health — DB and Artifact Health Check

Validate SQLite database integrity, artifact consistency, and detect stuck phases.
Optional `--repair` flag auto-advances stale states and prunes orphaned rows.

## Arguments
- (no args) — run all checks, report findings
- `--repair` — auto-repair repairable issues (stale states, orphaned rows)
- `--stuck-hours N` — override stuck phase threshold (default: 4 hours)

## Keywords
health, integrity, check, stuck, orphan, repair, artifacts, consistency, validate, preflight

## Procedure

### Run health check (read-only)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.health import run_health_check
result = run_health_check(Path('.'), do_repair=False)
print(json.dumps(result, indent=2))
"
```

### Run with --repair
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.health import run_health_check
result = run_health_check(Path('.'), do_repair=True)
print(json.dumps(result, indent=2))
"
```

### Run with custom stuck threshold (e.g. 8 hours)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.health import run_health_check
result = run_health_check(Path('.'), do_repair=False, stuck_threshold_hours=8)
print(json.dumps(result, indent=2))
"
```

## Display Format

After running, present findings grouped by check type:

```
## Meridian Health Check

Status: ok | warning | error

### DB Integrity
  [ok] integrity_check — passed
  [ok] schema_version — v8

### Orphaned Rows
  [warn] Plan id=12 references non-existent phase_id=99

### Artifact Consistency
  [warn] Phase 'Add auth' (id=3, executing) has no artifact dir

### Stuck Phases
  [warn] Phase 'Deploy' (id=5) executing for 6.2h (threshold: 4h)

### Repair Log  (only shown when --repair used)
  - Reverted stuck phase id=5 to 'planned_out'
  - Deleted orphaned plan id=12
```

Icons: ok → ✓  warning → ⚠  error → ✗

If `status == "ok"` and no repair log: print a single success line.
If `status == "no_db"`: tell the user to run `/meridian:init`.

## What Each Check Does

| Check | What it validates |
|---|---|
| `integrity_check` | SQLite page-level corruption via `PRAGMA integrity_check` |
| `foreign_key_check` | FK constraint violations via `PRAGMA foreign_key_check` |
| `schema_version` | DB schema version matches code expectation |
| `orphaned_rows` | Plans with no phase, phases with no milestone |
| `artifact_consistency` | `.planning/phases/` dirs vs DB phase records |
| `stuck_phases` | Phases in `executing` for longer than threshold |

## Repair Actions

| Finding | Repair |
|---|---|
| Orphaned plan | Delete plan row |
| Orphaned phase | Delete phase and its plans |
| Stuck phase | Revert to `planned_out`, clear `started_at` |

`--repair` is non-destructive for completed work — it only touches rows with no valid parent or phases that have been stuck with no heartbeat.

## Pre-flight in /meridian:resume

`/meridian:resume` runs a silent health check before generating the resume prompt.
If warnings or errors are found, they are surfaced before the resume output.
Pass `--skip-health` to bypass the pre-flight check.
