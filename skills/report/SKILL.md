# /meridian:report — Session Report

Generate an end-of-session summary with work done, token estimate, and next action.

## Arguments

- `--since <timestamp>` — Report from this ISO timestamp (default: last 24h).

## Keywords

report, session, summary, token usage, work done, progress

## Procedure

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.session_reports import (
    generate_session_report,
    estimate_token_usage,
    format_session_report,
)
with open_project('.') as conn:
    report = generate_session_report(conn)
    tokens = estimate_token_usage(report['events'])
    print(format_session_report(report, tokens))
"
```

## Output

Formatted markdown with summary stats, event timeline, token usage estimate, and suggested next action.
