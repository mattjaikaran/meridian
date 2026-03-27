# /meridian:note — Quick Note Capture

Zero-friction idea capture during work sessions. Notes persist in .meridian/notes.md.

## Arguments
- `append <text>` — Add a timestamped note
- `list` — Show all captured notes with IDs
- `promote <id>` — Convert a note into a tracked quick_task

## Keywords
note, idea, capture, remember, jot, thought, memo, append, promote

## Procedure

### Subcommand: append
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.notes import append_note
result = append_note(Path('.'), '<text>')
print(json.dumps(result, indent=2))
"
```

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.notes import list_notes
notes = list_notes(Path('.'))
for n in notes:
    status = ' [PROMOTED]' if n['promoted'] else ''
    print(f\"[{n['id']}] {n['timestamp']} — {n['text']}{status}\")
"
```

### Subcommand: promote
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.notes import promote_note
conn = connect(get_db_path('.'))
result = promote_note(Path('.'), '<id>', conn)
print(json.dumps(result, default=str, indent=2))
conn.close()
"
```

## When to Use
- Capture ideas without breaking flow
- Track thoughts that might become tasks later
- Promote ideas to tracked tasks when ready

## When NOT to Use
- For actual task execution → use /meridian:fast or /meridian:quick
- For planning → use /meridian:plan
