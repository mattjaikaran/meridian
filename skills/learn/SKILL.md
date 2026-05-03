# /meridian:learn — Execution Learning System

Capture patterns and mistakes as persistent rules injected into future subagent prompts.

## Arguments
- `<rule>` — The learning to capture (freeform text)
- `--list` — Show all learnings
- `--prune` — Remove stale/unused learnings
- `--delete <id>` — Remove a specific learning
- `--scope <global|project|phase>` — Scope for the learning (default: project)
- `--source <manual|execution|review|debug>` — How the learning was discovered (default: manual)
- `--extract [<phase-dir>]` — Extract structured learnings from phase artifacts
- `--extract --all` — Extract from all completed phases missing LEARNINGS.md
- `--extract --pending` — List phases that need extraction (dry-run, no writes)

## Keywords
learn, learning, rule, pattern, remember, lesson, mistake, capture, inject, extract

## Procedure

### Step 1: Route by argument

**If `--list`**: Show all learnings:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.learnings import list_learnings
with open_project('.') as conn:
    learnings = list_learnings(conn)
    print(json.dumps(learnings, indent=2, default=str))
"
```

Display grouped by scope (global → project → phase), showing ID, rule, source, category, and applied_count.

Also show extraction status:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.extract_learnings import check_extraction_pending
status = check_extraction_pending(Path('.'))
print(json.dumps(status, indent=2))
"
```

If `pending` list is non-empty, print:
```
Tip: {N} phase(s) have no LEARNINGS.md — run /meridian:learn --extract to capture them.
```

**If `--prune`**: Remove stale learnings:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.learnings import prune_stale
with open_project('.') as conn:
    count = prune_stale(conn)
    print(f'Pruned {count} stale learnings')
"
```

**If `--delete <id>`**: Remove specific learning:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.learnings import delete_learning
with open_project('.') as conn:
    deleted = delete_learning(conn, <id>)
    print('Deleted' if deleted else 'Not found')
"
```

---

### Step 1b: Route --extract variants

**If `--extract --pending`**: Show phases awaiting extraction, no writes:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.extract_learnings import check_extraction_pending
status = check_extraction_pending(Path('.'))
print(json.dumps(status, indent=2))
"
```

Display as a table:
```
Phase extraction status:
  Total phase dirs : N
  Already extracted: N
  Pending          : N

Pending phases:
  - 01-database-foundation
  - 03-command-routing
  ...
```

**If `--extract --all`**: Extract from all pending phase dirs:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.extract_learnings import (
    find_phases_without_learnings,
    extract_from_phase_dir,
    write_learnings_md,
    save_extracted_to_db,
)
with open_project('.') as conn:
    pending = find_phases_without_learnings(Path('.'))
    results = []
    for phase_dir in pending:
        extraction = extract_from_phase_dir(phase_dir)
        out_path = write_learnings_md(phase_dir, extraction)
        saved = save_extracted_to_db(conn, extraction, project_id='default')
        results.append({
            'phase': phase_dir.name,
            'artifacts': extraction['artifacts_read'],
            'saved_to_db': len(saved),
            'learnings_md': str(out_path),
        })
    print(json.dumps(results, indent=2))
"
```

Display summary per phase showing decisions/patterns/surprises/failures counts.

**If `--extract` with a phase dir argument** (e.g., `--extract 07-roadmap-automation`):

Resolve the phase dir:
- If argument looks like a path: use as-is
- Otherwise: look under `.planning/phases/` for a dir matching the slug (prefix or exact)

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.extract_learnings import (
    extract_from_phase_dir,
    write_learnings_md,
    save_extracted_to_db,
)
phase_dir = Path('.planning/phases/<resolved-dir>')
with open_project('.') as conn:
    extraction = extract_from_phase_dir(phase_dir)
    out_path = write_learnings_md(phase_dir, extraction)
    saved = save_extracted_to_db(conn, extraction, project_id='default')
    print(json.dumps({
        'phase_dir': str(phase_dir),
        'artifacts_read': extraction['artifacts_read'],
        'decisions': extraction['decisions'],
        'patterns': extraction['patterns'],
        'surprises': extraction['surprises'],
        'failures': extraction['failures'],
        'saved_to_db': len(saved),
        'learnings_md': str(out_path),
    }, indent=2))
"
```

**If `--extract` with no argument**: Extract from the most recently completed phase (most recent dir in `.planning/phases/` without LEARNINGS.md):

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.extract_learnings import find_phases_without_learnings
pending = find_phases_without_learnings(Path('.'))
if pending:
    print(str(pending[-1]))
else:
    print('none')
"
```

If result is 'none', print "All phase dirs already have LEARNINGS.md." and stop.

Otherwise use the returned path as the phase dir and run the single-phase extraction above.

---

### Step 2: Add New Learning (freeform rule, no --extract flag)

Check for duplicates first:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
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
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.learnings import add_learning
with open_project('.') as conn:
    learning = add_learning(conn, '<rule>', scope='<scope>', source='<source>')
    print(json.dumps(learning, indent=2, default=str))
"
```

### Step 3: Confirm

Display the stored learning with its ID, scope, and category (if set).

---

## Auto-Trigger: After Phase Completion

When `/meridian:next` or `/meridian:execute` transitions a phase to `complete`, check:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.extract_learnings import check_extraction_pending
status = check_extraction_pending(Path('.'))
print(json.dumps(status, indent=2))
"
```

If `pending` is non-empty, emit this suggestion (non-blocking):

```
Learning extraction available:
  Run /meridian:learn --extract to capture decisions, patterns, surprises, and failures
  from the completed phase artifacts into LEARNINGS.md and the project DB.
```

---

## Displaying Extracted Results

After extraction, display a structured summary:

```
Phase: 07-roadmap-automation
Artifacts read: 07-01-PLAN.md, 07-01-SUMMARY.md, VERIFICATION.md

Decisions (2):
  - We decided to use roadmap_sync.py for checkbox sync to keep state.py clean
  - Chose slug-based phase matching over ID-based for human readability

Patterns (1):
  - Always run roadmap sync as non-blocking side-effect in transition_phase

Surprises (1):
  - Turns out SQLite row_factory must be set before the first execute call

Failures (0):
  _None detected_

Saved to DB: 4 new learnings
Written: .planning/phases/07-roadmap-automation/LEARNINGS.md
```

## When to Use
- After fixing a recurring mistake
- After a review catches a pattern you want to avoid
- After debugging reveals a root cause pattern
- When you discover a project-specific convention
- After any phase completes — run `--extract` to capture artifact insights

## When NOT to Use
- For one-time fixes (just fix the code)
- For code style preferences (use linter config)
- On phases with no artifacts (empty dirs produce no signal)
