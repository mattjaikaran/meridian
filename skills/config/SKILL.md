# /meridian:config — Workflow Configuration

View and modify Meridian workflow preferences. Settings are stored in the SQLite settings table and respected by plan, execute, and review commands.

## Arguments

- (no args) — Show current settings.
- `set <key> <value>` — Set a configuration value.
- `reset` — Restore all settings to defaults.
- `profile <quality|balanced|budget|inherit>` — Shortcut to set model profile.

## Keywords

config, settings, preferences, profile, model, configure, setup

## Available Settings

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `model_profile` | quality, balanced, budget, inherit | balanced | Model assignment per agent type |
| `discuss_mode` | interactive, auto, batch | interactive | Default discuss phase mode |
| `auto_advance` | true, false | false | Auto-advance after phase completion |
| `interactive_execute` | true, false | false | Pause after each plan for review |
| `tdd_required` | true, false | true | Require TDD in execution |
| `cross_model_review` | true, false | false | Use secondary AI for review |

## Procedure

1. **Show current settings:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.state import list_settings
from scripts.model_profiles import get_profile_table, format_profile_display
with open_project('.') as conn:
    settings = list_settings(conn)
    profile = get_profile_table(conn)
    print('## Current Settings\n')
    if settings:
        print('| Key | Value |')
        print('|-----|-------|')
        for s in settings:
            print(f'| {s[\"key\"]} | {s[\"value\"]} |')
    else:
        print('No custom settings. Using defaults.')
    print()
    print(format_profile_display(profile))
"
```

2. **Set a value:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import sys
from scripts.db import open_project
from scripts.state import set_setting
key, value = sys.argv[1], sys.argv[2]
with open_project('.') as conn:
    set_setting(conn, key, value)
    print(f'Set {key} = {value}')
" "$KEY" "$VALUE"
```

3. **Set model profile** (shortcut):

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import sys
from scripts.db import open_project
from scripts.model_profiles import set_active_profile, format_profile_display
profile = sys.argv[1]
with open_project('.') as conn:
    result = set_active_profile(conn, profile)
    print(format_profile_display(result))
" "$PROFILE"
```

4. **Reset to defaults:**

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import open_project
with open_project('.') as conn:
    conn.execute('DELETE FROM settings WHERE project_id = ?', ('default',))
    print('All settings reset to defaults.')
"
```

## Output

Show settings as a formatted table with current values. For profile changes, display the full agent-to-model mapping.
