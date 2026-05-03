# /meridian:discuss — Phase Discussion

Structured context gathering and decision-making before planning. Identifies gray areas in phase scope and presents focused questions to capture implementation decisions.

## Arguments

- `<phase_id>` — (optional) Phase ID to discuss. Defaults to current active phase.
- `--auto` — Skip interactive questions, apply recommended defaults.
- `--chain` — Run discuss then automatically advance to plan.
- `--batch` — Dump all questions to output for offline answering.
- `--persona <name>` — Frame context-gathering through a role lens (pm, architect, ux, qa, security)

## Keywords

discuss, context, gray areas, questions, decisions, scope, approach, before planning

## Persona Support

If `--persona <name>` is passed, load the persona and use it to frame the
context-gathering questions. The persona shapes which gray areas are surfaced and
how questions are phrased.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.personas import load_persona
persona = load_persona('<persona_name>')
print(json.dumps({'label': persona['label'], 'content': persona['content']}, indent=2))
"
```

Inject the persona content into the context-gatherer prompt before calling `run_discuss`.
Show the active persona in the discuss banner:

```
## Discuss — <Phase Name>
Persona: <Persona Label>
Gray areas will be framed from the <label> perspective.
```

Available personas: `pm`, `architect`, `ux`, `qa`, `security`

## Procedure

1. **Load phase** — Read phase from DB, parse acceptance criteria.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json, sys
from scripts.db import open_project
from scripts.state import get_status
with open_project('.') as conn:
    status = get_status(conn)
    print(json.dumps(status, default=str))
"
```

2. **Run discuss** — Identify gray areas, generate questions, optionally auto-apply.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json, sys
from pathlib import Path
from scripts.db import open_project
from scripts.discuss_phase import run_discuss
mode = sys.argv[1] if len(sys.argv) > 1 else 'interactive'
phase_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
chain = '--chain' in sys.argv
with open_project('.') as conn:
    if not phase_id:
        from scripts.state import get_status
        status = get_status(conn)
        active = status.get('active_phase')
        phase_id = active['id'] if active else None
    if not phase_id:
        print('ERROR: No active phase found. Specify phase_id.')
        sys.exit(1)
    result = run_discuss(conn, phase_id, 'default', Path('.'), mode=mode, chain=chain)
    print(json.dumps(result, default=str, indent=2))
" -- "$MODE" "$PHASE_ID"
```

3. **Interactive flow** — If mode is interactive:
   - Present each gray area with options
   - Ask the user to choose (or accept defaults)
   - After all questions answered, call `apply_answers()` to persist
   - Write CONTEXT.md to `.meridian/phases/`

4. **Apply answers** — Persist decisions and generate context doc.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json, sys
from pathlib import Path
from scripts.db import open_project
from scripts.discuss_phase import apply_answers
phase_id = int(sys.argv[1])
answers_json = sys.argv[2]
gray_areas_json = sys.argv[3]
answers = json.loads(answers_json)
gray_areas = json.loads(gray_areas_json)
with open_project('.') as conn:
    result = apply_answers(conn, phase_id, 'default', gray_areas, answers, Path('.'))
    print(result['context_doc'])
"
```

5. **Transition phase** — Move phase to `context_gathered` state.

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
from scripts.state import transition_phase
phase_id = int('$PHASE_ID')
with open_project('.') as conn:
    transition_phase(conn, phase_id, 'context_gathered')
    print(f'Phase {phase_id} transitioned to context_gathered')
"
```

6. **Chain advance** — If `--chain` was passed, automatically invoke `/meridian:plan` for this phase.

## Output

Display gray areas as numbered list with options. After decisions are made, show the generated CONTEXT.md summary. If `--auto`, show applied defaults.
