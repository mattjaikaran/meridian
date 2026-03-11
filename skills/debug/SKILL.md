# /meridian:debug — Systematic Debugging

4-phase systematic debugging with decision logging. Uses the protocol from `references/discipline-protocols.md`.

## Arguments
- `<description>` — Bug description or error message
- `--plan <id>` — Associate with a specific plan
- `--phase <id>` — Associate with a specific phase

## Procedure

### Phase 1: Investigation
1. Read the full error message and stack trace
2. Identify the exact file, line, and function
3. Check recent changes: `git log --oneline -10` and `git diff`
4. Reproduce the error by running the failing test/command
5. Record findings

### Phase 2: Pattern Recognition
1. Categorize the error type:
   - Import/module error
   - Type error / null reference
   - Logic error / wrong behavior
   - Race condition / timing
   - Configuration / environment
   - Data integrity
2. Search codebase for similar patterns
3. Check if this is a known issue pattern

### Phase 3: Hypothesis
1. Form a specific hypothesis: "The error occurs because X"
2. Identify evidence that would confirm/refute
3. Test with minimal change
4. Record hypothesis and result as a decision:

```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, '<hypothesis and result>', category='approach',
    rationale='<evidence>', phase_id=<phase_id_or_None>)
conn.close()
"
```

### Phase 4: Implementation
1. Fix at the source, not the symptom
2. Run the failing test — must pass now
3. Run full test suite — no regressions
4. Commit the fix with descriptive message

### Escalation Rule
After 3 failed fix attempts:
- STOP fixing
- Record a deviation decision
- Re-examine assumptions
- Consider if the problem is architectural
- May need to re-plan the current phase

```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_decision
conn = connect(get_db_path('.'))
create_decision(conn, 'Escalation: 3+ failed fixes on <issue>. Likely architectural.',
    category='deviation', rationale='<what was tried>')
conn.close()
"
```

## Output
Report:
- Root cause identified
- Fix applied (file:line)
- Tests passing
- Decision logged
