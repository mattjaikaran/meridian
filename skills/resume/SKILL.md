# /meridian:resume — Deterministic Resume

Generate and load a resume prompt from SQLite state. Start exactly where you left off.

## Arguments
- (no args) — run pre-flight health check then generate resume prompt
- `--skip-health` — skip the pre-flight health check

## Procedure

### Step 0: Pre-flight Health Check (skip if --skip-health)
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.health import run_health_check
result = run_health_check(Path('.'), do_repair=False)
print(json.dumps(result, indent=2))
"
```

If `status` is `"warning"` or `"error"`, surface the findings to the user before
continuing. Example output:

> ⚠ Health check found 2 warnings:
> - Phase 'Build API' (id=3) has been executing for 7.2h — may be stuck
> - Artifact dir '04-old-feature' has no DB phase record
>
> Run `/meridian:health --repair` to auto-fix, or continue with `--skip-health`.

If `status` is `"ok"`, proceed silently.

### Step 1: Generate Resume Prompt
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.resume import generate_resume_prompt
print(generate_resume_prompt('.'))
"
```

### Step 2: Display Resume
Print the full resume prompt so the agent can understand current state.

### Step 3: Determine Next Action
The resume prompt always ends with a computed next action. Follow it:

- `activate_milestone` → Activate the planned milestone
- `create_phases` → Run `/meridian:plan`
- `gather_context` → Dispatch context-gatherer subagent
- `create_plans` → Generate plans for the phase
- `execute` → Run `/meridian:execute`
- `execute_plan` → Execute the specific plan shown
- `verify_phase` → Run acceptance criteria verification
- `review_phase` → Run `/meridian:review`
- `complete_phase` → Mark phase complete
- `complete_milestone` → Mark milestone complete
- `fix_failed_plan` → Debug and retry the failed plan
- `unblock_phase` → Address the blocker

### Step 4: Announce Position
Tell the user where we are and what's next. Example:

> Resuming **MyApp** — Phase 2: Features (executing)
> 2/4 plans complete. Next: execute "Add API routes" (wave 2).
> Ready to continue?
