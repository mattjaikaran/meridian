# /meridian:next — Advance to Next Workflow Step

Auto-detect the current workflow state and advance to the next logical step.

## Arguments
None — automatically determines what to do based on project state.

## Keywords
next, advance, continue, what's next, proceed, step, forward, progress

## Procedure

### Step 1: Determine Next Step
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.next_action import determine_next_step, format_next_action
conn = connect(get_db_path('.'))
step = determine_next_step(conn)
print(format_next_action(step))
conn.close()
"
```

### Step 2: Confirm and Execute
- If non-destructive: show the action and proceed
- If destructive: ask for confirmation before executing
- Execute the mapped /meridian:* command

## State Mapping
| Current State | Action | Command |
|---|---|---|
| No project | Initialize | /meridian:init |
| No milestones | Create milestone | /meridian:init |
| Planned milestone | Activate | /meridian:plan |
| No phases | Create phases | /meridian:plan |
| Phase: planned | Gather context | /meridian:plan |
| Phase: context_gathered | Create plans | /meridian:plan |
| Phase: planned_out | Execute | /meridian:execute |
| Phase: executing | Continue execution | /meridian:execute |
| Phase: verifying | Review | /meridian:review |
| Phase: reviewing | Complete phase | /meridian:execute |
| All phases complete | Close milestone | /meridian:ship |
| Idle | Capture ideas | /meridian:note |

## When to Use
- When you don't know what to do next
- To continue a workflow after a break
- As a "what's the status" check

## When NOT to Use
- When you know exactly which command to run
- When you want to skip ahead or go back
