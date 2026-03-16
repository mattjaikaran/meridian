# /meridian:verify-phase -- Nyquist Compliance Check

Check VALIDATION.md frontmatter presence and currency for phases. Does NOT re-run tests -- only reads existing frontmatter.

## Procedure

### Step 1: Check compliance (all phases or specific phase)

If a phase number argument is provided, check only that phase. Otherwise check all phases.

```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from pathlib import Path
from scripts.nyquist import parse_validation_md

phases_dir = Path('.planning/phases')
results = []
for phase_dir in sorted(phases_dir.iterdir()):
    if not phase_dir.is_dir():
        continue
    parsed = parse_validation_md(phase_dir)
    if parsed is None:
        continue
    results.append({
        'phase': parsed.get('phase', '?'),
        'slug': parsed.get('slug', phase_dir.name),
        'compliant': parsed.get('nyquist_compliant', False),
        'status': parsed.get('status', 'unknown'),
        'wave_0': parsed.get('wave_0_complete', False),
        'validated_at': parsed.get('wave_0_validated', 'never'),
        'failure_reason': parsed.get('failure_reason'),
    })
print(json.dumps(results, indent=2))
"
```

### Step 2: Display Results

Format output as a table:

| Phase | Name | Status | Compliant | Issues |
|-------|------|--------|-----------|--------|
| 1     | database-foundation | validated | [x] | -- |
| 2     | error-infrastructure | failed | [ ] | Tests failed |

Rules:
- Compliant phases: show `[x]` checkmark
- Non-compliant phases: show `[ ]` with reason
  - `status: draft` -> "Not validated yet"
  - `status: failed` -> "Tests failed" (include failure_reason if present)
- Non-compliant phases are **warnings**, not errors (per project decision)

### Step 3: Offer backfill (if gaps found)

If any phases are non-compliant, suggest running the backfill command:

```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from pathlib import Path
from scripts.nyquist import backfill_validation
results = backfill_validation(Path('.planning'))
print(json.dumps(results, indent=2))
"
```

This will re-run tests for all non-compliant phases and update their VALIDATION.md frontmatter with actual results.

## Output

Summary table of phase compliance status. Non-compliant phases are warnings, not blockers.
