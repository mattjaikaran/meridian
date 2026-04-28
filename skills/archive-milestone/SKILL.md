# /meridian:archive-milestone — Archive Milestone

Transition a completed milestone to `archived` status, marking it as historical record.

Archiving is a one-way operation. Use after completion when the milestone is stable
and you want to keep it out of active views.

## Prerequisites

- Milestone must already be in `complete` status
- Run `/meridian:complete-milestone` first if not yet complete

## Arguments

None. Operates on the most recently completed milestone.

## Procedure

### Step 1: Identify the milestone to archive

```bash
MERIDIAN_HOME="${MERIDIAN_HOME:-.}"
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_status, list_milestones
conn = connect(get_db_path('.'))
milestones = list_milestones(conn)
complete = [m for m in milestones if m['status'] == 'complete']
print(json.dumps(complete, indent=2, default=str))
conn.close()
"
```

Pick the milestone `id` to archive. Save as `MILESTONE_ID`.

### Step 2: Archive

```bash
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from scripts.db import connect, get_db_path
from scripts.milestone_lifecycle import archive_milestone
conn = connect(get_db_path('.'))
result = archive_milestone(conn, '$MILESTONE_ID')
print(json.dumps(result, indent=2))
conn.close()
"
```

### Step 3: Confirm

```bash
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from scripts.db import connect, get_db_path
from scripts.state import get_milestone
conn = connect(get_db_path('.'))
ms = get_milestone(conn, '$MILESTONE_ID')
print(f'Milestone {ms[\"id\"]} status: {ms[\"status\"]}')
conn.close()
"
```

Expected output: `Milestone {id} status: archived`

## Output Format

```
# Milestone Archived — {milestone_name}

Milestone ID: {id}
Status: archived

→ Archived milestones are excluded from active views.
→ Summary is preserved at .planning/milestones/{id}-SUMMARY.md
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid transition` | Milestone not in `complete` status | Complete it first with `/meridian:complete-milestone` |
| `Milestone not found` | Wrong ID | List milestones in Step 1 |

## Notes for non-Claude LLMs

- Replace `$MILESTONE_ID` with the actual string ID from Step 1
- This is a state transition only — no files are deleted
- The git tag created at completion is unaffected by archival
