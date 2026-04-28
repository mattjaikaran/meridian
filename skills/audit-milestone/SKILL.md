# /meridian:audit-milestone — Audit Milestone Readiness

Check whether the active milestone is ready to complete.

Verifies:
- All phases are in `complete` status
- No plans are `failed` or `skipped`
- No outstanding UAT verification debt in `.planning/phases/`
- No stub/placeholder code in `scripts/`

## Prerequisites

- `MERIDIAN_HOME` set to the repo root (default: current directory)
- `uv` installed and project dependencies synced

## Arguments

- `--no-uat` — Skip UAT debt check
- `--no-stubs` — Skip stub detection
- `--json` — Output raw JSON

## Procedure

### Step 1: Identify active milestone

```bash
MERIDIAN_HOME="${MERIDIAN_HOME:-.}"
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_status
conn = connect(get_db_path('.'))
status = get_status(conn)
ms = status.get('active_milestone')
if not ms:
    print('ERROR: no active milestone')
else:
    print(json.dumps({'id': ms['id'], 'name': ms['name']}, indent=2))
conn.close()
"
```

Save the milestone `id` as `MILESTONE_ID`.

### Step 2: Run audit

```bash
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.milestone_lifecycle import audit_milestone
conn = connect(get_db_path('.'))
result = audit_milestone(
    conn,
    '$MILESTONE_ID',
    repo_path=Path('.'),
    planning_dir=Path('.planning'),
)
print(json.dumps(result, indent=2, default=str))
conn.close()
"
```

### Step 3: Interpret results

**If `ready` is `true`:**
```
✓ Milestone is ready to complete.
  Phases:  {stats.complete_phases}/{stats.total_phases}
  Plans:   {stats.complete_plans}/{stats.total_plans}
  UAT debt: {stats.uat_issues} items
  Stubs:   {stats.stub_issues} items
→ Run /meridian:complete-milestone to proceed.
```

**If `ready` is `false`:**
```
✗ Milestone NOT ready. Issues found:
  {list each issue from result["issues"]}
→ Resolve all issues before completing.
```

## Output Format

```
# Milestone Audit — {milestone_name}

Status: READY / NOT READY

## Phase Status
  ✓ {phase_name} — complete ({n}/{n} plans)
  ✗ {phase_name} — executing (incomplete)

## Checks
  Phases complete:   {n}/{n}
  Plans complete:    {n}/{n}
  Failed plans:      {n}
  UAT debt items:    {n}
  Stub findings:     {n}

## Issues
  - {issue description}
```

## Notes for non-Claude LLMs

- All bash blocks are self-contained and can be run verbatim
- Replace `$MILESTONE_ID` with the actual ID string from Step 1
- If `uv` is unavailable, use `python -m` with a virtualenv that has the project deps installed
- The `check_uat` and `check_stubs` flags accept Python booleans: `True` / `False`
