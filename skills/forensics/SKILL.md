# /meridian:forensics — Workflow Forensics

Post-mortem analysis of failed or stuck workflow states. Reads git history, DB state,
and phase artifacts to detect stuck loops, missing artifacts, abandoned work, and crash
signatures. Always writes a report to `.planning/forensics/`. **Read-only** — never
modifies source files.

## Arguments
- (no args) — run all checks, print summary, write report
- `--stuck-hours N` — override stuck execution threshold (default: 4h)
- `--abandoned-days N` — override abandoned work threshold (default: 3 days)
- `--no-git` — skip git context gathering (faster, no subprocess calls)

## Keywords
forensics, postmortem, stuck, crash, abandoned, missing, artifact, investigation, debug, audit, analysis

## Procedure

### Run forensics (default — writes report automatically)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.forensics import run_forensics, write_report
report = run_forensics(Path('.'))
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

### Run with custom stuck threshold (e.g. 8 hours)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.forensics import run_forensics, write_report
report = run_forensics(Path('.'), stuck_threshold_hours=8)
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

### Run with custom abandoned threshold (e.g. 7 days)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.forensics import run_forensics, write_report
report = run_forensics(Path('.'), abandoned_threshold_days=7)
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

### Run without git context
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.forensics import run_forensics, write_report
report = run_forensics(Path('.'), include_git=False)
path = write_report(report, Path('.'))
report['report_path'] = str(path)
print(json.dumps(report, indent=2))
"
```

## Display Format

After running, present findings grouped by detection type, then git context:

```
## Meridian Workflow Forensics

Status: clean | notes | issues_found
Warnings: N  Notes: N
Report written: .planning/forensics/report-20260427T120000Z.md

### Stuck Execution Loops
  ⚠ Phase 'Deploy' (id=5) in milestone 'M7' has been executing for 6.2h
    → Run /meridian:health --repair to revert, or /meridian:resume to continue.

### Missing Artifacts
  ⚠ Phase 'Add auth' (status=executing) has no artifact dir at .planning/phases/03-add-auth/
    → Artifact directory was never created or was deleted.

### Abandoned Work
  ℹ Phase 'Refactor DB' (status=planned_out) started 5d ago with no recent git activity
    → Run /meridian:resume or /meridian:revert to reset state.

### Crash Signatures
  ⚠ 'PLAN.md' in '04-setup-ci/' is suspiciously small (12 bytes)
    → File may be truncated or a placeholder. Re-run the planning step.

### Git Context
  Branch: feature/auth
  Uncommitted changes: 3 files
  Recent commits:
    a1b2c3d feat: add login endpoint
    ...
```

Icons: warning → ⚠  info → ℹ

If `status == "clean"`: print a single success line and the report path.
If `status == "no_db"`: tell the user to run `/meridian:init`.

## What Each Check Detects

| Check | What it finds |
|---|---|
| `stuck_loop` | Phases in `executing` state longer than threshold |
| `missing_artifact` | Active phases with no artifact dir or missing PLAN.md |
| `abandoned_work` | Phases started N+ days ago with no recent git activity |
| `crash_signature` | Empty artifact dirs or suspiciously small key files |

## Read-Only Guarantee

`/meridian:forensics` never writes to source files, never modifies the database, and
never changes phase state. It only writes to `.planning/forensics/report-{timestamp}.md`.
To fix issues found, use `/meridian:health --repair` or `/meridian:resume`.
