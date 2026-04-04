# /meridian:complete-milestone — Complete Milestone

Audit, complete, and optionally archive the active milestone with a git tag.

## Arguments

- `--archive` — Also archive after completion.

## Keywords

complete, milestone, finish, archive, git tag, ship

## Procedure

1. **Audit milestone readiness:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.milestone_lifecycle import audit_milestone
from scripts.state import get_status
with open_project('.') as conn:
    status = get_status(conn)
    ms = status.get('active_milestone')
    result = audit_milestone(conn, ms['id'])
    print(json.dumps(result, default=str, indent=2))
"
```

2. **Complete if ready:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.milestone_lifecycle import complete_milestone
from scripts.state import get_status
with open_project('.') as conn:
    status = get_status(conn)
    ms = status.get('active_milestone')
    result = complete_milestone(conn, ms['id'])
    print(json.dumps(result, default=str, indent=2))
"
```

3. **Create git tag:**

```bash
git tag -a "$GIT_TAG" -m "Milestone $MILESTONE_ID completed"
```

4. **Generate summary:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.milestone_lifecycle import generate_milestone_summary
with open_project('.') as conn:
    print(generate_milestone_summary(conn, '$MILESTONE_ID'))
"
```

## Output

Audit results, completion confirmation with stats, git tag name, and milestone summary.
