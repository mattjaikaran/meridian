# /meridian:analyze-deps — Dependency Analysis

Detect phase ordering constraints within a milestone. Analyzes file overlap, semantic
name references, and sequence gaps to suggest `depends_on` entries for phases that are
missing explicit ordering. Optionally writes suggestions back to the DB.

## Arguments
- (no args) — analyze active milestone, print findings, write report (read-only)
- `--apply` — write suggested `depends_on` entries back to the DB
- `--milestone <id>` — target a specific milestone by ID instead of the active one

## Keywords
dependencies, ordering, depends_on, phase ordering, file overlap, coupling, analysis

## Procedure

### Analyze (default — read-only)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.analyze_deps import run_analysis, write_report
report = run_analysis(Path('.'))
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

### Analyze and apply suggestions
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.analyze_deps import run_analysis, write_report
report = run_analysis(Path('.'), apply=True)
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

### Target a specific milestone
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.analyze_deps import run_analysis, write_report
report = run_analysis(Path('.'), milestone_id='<MILESTONE_ID>')
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

## Display Format

After running, present findings grouped by type:

```
## Meridian Dependency Analysis

Milestone: M7 — GSD Parity & Workflow Maturity
Status: suggestions  Warnings: 1  Notes: 4
Report written: .planning/deps/report-20260427T120000Z.md

### File Overlap Dependencies
  ℹ Phase 'Build API' modifies 'models/user.py' which is created by phase 'Create Models'
    → Suggested: Build API depends_on Create Models

### File Creation Conflicts
  ⚠ Phases 'Auth Setup' and 'User Module' both declare they create 'auth/models.py'
    → Review: only one phase should own this file

### Semantic Name References
  ℹ Phase 'Add Endpoints' plan text references phase 'Create Models' by name
    → Suggested: Add Endpoints depends_on Create Models

### Phases Without Explicit Ordering
  ℹ Phase 'Deploy Config' (seq=3) has no explicit depends_on
    → Run with --apply to set suggested ordering

### Suggested depends_on Entries
  Phase 2 (Build API) → [1] (Create Models)
  Phase 4 (Add Endpoints) → [1] (Create Models)

(Run /meridian:analyze-deps --apply to write these to the DB)
```

Icons: warning → ⚠  info → ℹ

If `status == "clean"`: print a single success line and the report path.
If `status == "no_db"`: tell the user to run `/meridian:init`.
If `status == "no_milestone"`: tell the user to run `/meridian:init`.
If `--apply` was used and `applied` is non-empty: show each phase that was updated.

## What Each Check Detects

| Check | What it finds |
|---|---|
| `file_overlap` | Phase B modifies a file that Phase A creates → B depends on A |
| `file_conflict` | Two phases both declare they create the same file → ownership conflict |
| `name_reference` | Phase B's plan descriptions mention Phase A by name → semantic coupling |
| `missing_explicit_dep` | Phase N (seq > 1) has no `depends_on` set at all |

## DB Write-Back

`--apply` merges suggestions into existing `depends_on` values (never overwrites).
Phases that already have the suggested dependency are skipped (no duplicate writes).
`depends_on` is stored as a JSON array of phase IDs: `[1, 3]`.

## Read-Only by Default

Without `--apply`, `/meridian:analyze-deps` never modifies the database.
It only writes to `.planning/deps/report-{timestamp}.md`.
