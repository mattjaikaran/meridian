# /meridian:validate — Git State Validation

Check that completed plans in the DB have valid commit SHAs in the git repo.

## Procedure

### Step 1: Run Validation
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.validate import validate_state

with open_project('.') as conn:
    result = validate_state(conn)
    print(json.dumps(result, indent=2))
"
```

### Step 2: Display Results
Format output:
- **Valid**: Plans with confirmed git commits
- **Missing**: Plans whose commit SHAs are not found in git (potential force-push or rebase)
- **Drift**: (reserved for future content-level validation)

If any plans are in the `missing` category, warn about potential git history rewrite.

## Output
Summary table of validation results with plan IDs and status.
