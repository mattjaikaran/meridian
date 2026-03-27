# /meridian:do — Freeform Command Router

Route natural language to the correct /meridian:* command. Just describe what you want to do.

## Arguments
- `<text>` — Freeform description of what you want to do

## Keywords
do, run, execute, help, what, how, route, find command

## Procedure

### Step 1: Route the Input
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.router import route_freeform
result = route_freeform('<text>')
print(json.dumps(result, indent=2))
"
```

### Step 2: Handle Result
- **exact/confident match**: Show the matched command and confirm before executing
- **ambiguous**: Show top 3 candidates and ask user to pick
- **none**: Suggest /meridian:help

### Step 3: Execute
Run the matched /meridian:* command with appropriate arguments.

## Examples
- "check what's next" → routes to /meridian:next
- "add a note about auth" → routes to /meridian:note
- "fix a typo" → routes to /meridian:fast
- "create a plan for the API" → routes to /meridian:plan

## When to Use
- When you don't remember the exact command name
- As a shortcut for common workflows
- When describing intent rather than a specific command
