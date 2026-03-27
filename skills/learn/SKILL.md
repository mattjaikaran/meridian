# /meridian:learn — Execution Learning System

Capture patterns and mistakes as persistent rules injected into future subagent prompts.

## Arguments
- `<rule>` — The learning to capture (freeform text)
- `--list` — Show all learnings
- `--prune` — Remove stale/unused learnings
- `--delete <id>` — Remove a specific learning
- `--scope <global|project|phase>` — Scope for the learning (default: project)
- `--source <manual|execution|review|debug>` — How the learning was discovered (default: manual)

## Keywords
learn, learning, rule, pattern, remember, lesson, mistake, capture, inject

## Procedure

### Step 1: Route by argument

**If `--list`**: Show all learnings:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.learnings import list_learnings
with open_project('.') as conn:
    learnings = list_learnings(conn)
    print(json.dumps(learnings, indent=2, default=str))
"
```

Display grouped by scope (global → project → phase), showing ID, rule, source, and applied_count.

**If `--prune`**: Remove stale learnings:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.learnings import prune_stale
with open_project('.') as conn:
    count = prune_stale(conn)
    print(f'Pruned {count} stale learnings')
"
```

**If `--delete <id>`**: Remove specific learning:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.db import open_project
from scripts.learnings import delete_learning
with open_project('.') as conn:
    deleted = delete_learning(conn, <id>)
    print('Deleted' if deleted else 'Not found')
"
```

### Step 2: Add New Learning

Check for duplicates first:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.learnings import find_similar
with open_project('.') as conn:
    match = find_similar(conn, '<rule>')
    print(json.dumps(match, indent=2, default=str) if match else 'null')
"
```

If a similar learning exists (>70% match), show it and ask user whether to:
- **Update** the existing learning
- **Add anyway** as a separate learning
- **Skip** (already captured)

If no duplicate, add the learning:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.learnings import add_learning
with open_project('.') as conn:
    learning = add_learning(conn, '<rule>', scope='<scope>', source='<source>')
    print(json.dumps(learning, indent=2, default=str))
"
```

### Step 3: Confirm

Display the stored learning with its ID and scope.

## When to Use
- After fixing a recurring mistake
- After a review catches a pattern you want to avoid
- After debugging reveals a root cause pattern
- When you discover a project-specific convention

## When NOT to Use
- For one-time fixes (just fix the code)
- For code style preferences (use linter config)
