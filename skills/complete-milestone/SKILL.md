# /meridian:complete-milestone — Complete Milestone

Audit readiness, mark the milestone complete, create a git tag, persist a summary,
and optionally archive.

## Prerequisites

- `MERIDIAN_HOME` set to the repo root (default: current directory)
- `uv` installed with project dependencies synced
- Clean or committed working tree (for git tag)

## Arguments

- `--archive` — Also archive after completion
- `--no-uat` — Skip UAT debt check in audit
- `--no-stubs` — Skip stub detection in audit
- `--force` — Complete even if UAT/stub issues exist (phase/plan checks still enforced)

## Keywords

complete, milestone, finish, archive, git tag, ship

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

Save the milestone `id` as `MILESTONE_ID` and `name` as `MILESTONE_NAME`.

### Step 2: Run audit

Run `/meridian:audit-milestone` first and confirm `ready` is `true`.

For `--force` mode, set `check_uat=False, check_stubs=False` in Step 3.

### Step 3: Complete the milestone

```bash
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
import json
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.milestone_lifecycle import complete_milestone
conn = connect(get_db_path('.'))
result = complete_milestone(
    conn,
    '$MILESTONE_ID',
    repo_path=Path('.'),
    planning_dir=Path('.planning'),
    check_uat=True,
    check_stubs=True,
    persist_summary=True,
)
print(json.dumps(result, indent=2, default=str))
conn.close()
"
```

Save `result['git_tag']` as `GIT_TAG` and `result['summary_path']` as `SUMMARY_PATH`.

### Step 4: Create git tag

```bash
git tag -a "$GIT_TAG" -m "Milestone $MILESTONE_ID ($MILESTONE_NAME) completed"
```

Verify: `git tag -l "milestone/*"`

### Step 5: Display summary

```bash
cat "$SUMMARY_PATH"
```

Or generate on demand:

```bash
PYTHONPATH="$MERIDIAN_HOME" uv run --project "$MERIDIAN_HOME" python -c "
from scripts.db import connect, get_db_path
from scripts.milestone_lifecycle import generate_milestone_summary
conn = connect(get_db_path('.'))
print(generate_milestone_summary(conn, '$MILESTONE_ID'))
conn.close()
"
```

### Step 6 (optional): Archive

If `--archive` was requested:

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

## Output Format

```
# Milestone Complete — {milestone_name}

Status: complete
Git tag: milestone/{id}
Summary: .planning/milestones/{id}-SUMMARY.md

## Stats
  Phases:   {n}
  Plans:    {n}
  Duration: {n} days

→ Run: git push origin milestone/{id}
→ Start next milestone with /meridian:roadmap
```

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `not ready for completion` | Incomplete phases or failed plans | Resolve issues from audit |
| `Milestone not found` | Wrong milestone ID | Check active milestone in Step 1 |
| `git tag already exists` | Tag was created before | Delete with `git tag -d $GIT_TAG` then retry |

## Notes for non-Claude LLMs

- All bash blocks are self-contained; substitute `$MILESTONE_ID` / `$GIT_TAG` with actual values
- Steps 2-6 depend on the `id` from Step 1 — execute sequentially
- `check_uat=False, check_stubs=False` disables optional checks (equivalent to `--force`)
- If the milestone has no `completed_at` after Step 3, the transition failed — check DB state
