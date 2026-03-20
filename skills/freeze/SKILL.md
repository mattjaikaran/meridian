# /meridian:freeze — Edit Scope Lock

Lock edits to a specific directory during focused work. Advisory safety net to prevent accidental edits outside scope.

## Arguments
- `<directory>` — Directory to lock edits to
- `--status` — Show current freeze state
- `--clear` — Remove edit lock (alias: /meridian:unfreeze)

## Keywords
freeze, lock, scope, restrict, directory, unfreeze, guard, safety

## Procedure

### Step 1: Route by argument

**If `--status`**: Show freeze state:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import open_project
from scripts.freeze import format_freeze_status
with open_project('.') as conn:
    print(format_freeze_status(conn))
"
```

**If `--clear`**: Remove freeze:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import open_project
from scripts.freeze import clear_freeze
with open_project('.') as conn:
    cleared = clear_freeze(conn)
    print('Edit lock removed' if cleared else 'No active edit lock')
"
```

### Step 2: Set Freeze

```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
import json
from scripts.db import open_project
from scripts.freeze import set_freeze
with open_project('.') as conn:
    result = set_freeze(conn, '<directory>')
    print(json.dumps(result, indent=2))
"
```

### Step 3: Confirm

Display: "Edit lock active: `<directory>`. Edits outside this directory will trigger a warning."

## Advisory Behavior

When freeze is active, before editing any file:
1. Check if the file is within the frozen directory
2. If OUTSIDE: warn the user and ask for confirmation before proceeding
3. If INSIDE: proceed normally
4. This is advisory — user can always override

## When to Use
- Debugging a specific module (lock to that module's directory)
- Focused refactoring of one package
- Preventing accidental cross-module edits during implementation

## When NOT to Use
- Broad refactoring across multiple directories
- Initial project setup
