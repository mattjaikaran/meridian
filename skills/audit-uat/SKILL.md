# /meridian:audit-uat — Cross-Phase Verification Debt Audit

Scan all phases for outstanding verification items and produce a summary report.

## Arguments
- None (scans all phases automatically)

## Procedure

### Step 1: Run UAT Audit
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.audit import audit_uat
result = audit_uat()
print(result['report'])
print()
print(json.dumps({
    'total_debt': result['total_debt'],
    'has_debt': result['has_debt'],
    'phase_count': len(result['phases']),
}, indent=2))
"
```

### Step 2: Review Results
- If `has_debt` is `true`, review unchecked sign-off items and pending human verifications
- Each phase section shows actionable items that need attention
- Prioritize items in earlier phases (regression risk)

### Step 3: Address Debt (if needed)
For each outstanding item:
- **Unchecked sign-off**: Verify the condition and check it off in VALIDATION.md
- **Pending human verification**: Perform the manual test and update VERIFICATION.md

## When to Use
- Before marking a milestone complete
- During periodic quality reviews
- Before releases to verify no verification debt remains
- When onboarding to understand outstanding work

## When NOT to Use
- For automated regression testing (use `/meridian:execute` regression gate instead)
- For individual phase verification (use `/meridian:verify-work` instead)
