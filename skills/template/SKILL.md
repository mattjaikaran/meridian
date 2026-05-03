# /meridian:template — Workflow Templates

Apply or list workflow templates for rapid project scaffolding.

## Arguments
- `--list` — List available templates
- `--apply <name>` — Apply a template to create milestone structure
- `--milestone <id>` — Target milestone ID (required with --apply)

## Procedure

### If --list:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json, glob
from pathlib import Path
templates_dir = Path('$MERIDIAN_HOME/templates').expanduser()
templates = []
for f in sorted(templates_dir.glob('*.json')):
    data = json.loads(f.read_text())
    templates.append({'file': f.name, 'name': data['name'], 'description': data.get('description', '')})
print(json.dumps(templates, indent=2))
"
```

### If --apply:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.state import create_milestone, create_phase, create_plan

template_path = Path('$MERIDIAN_HOME/templates/<name>.json').expanduser()
template = json.loads(template_path.read_text())

with open_project('.') as conn:
    milestone_id = '<milestone_id>'
    create_milestone(conn, milestone_id, template['name'])
    for phase_data in template['phases']:
        phase = create_phase(conn, milestone_id, phase_data['name'], phase_data.get('description'))
        for plan_data in phase_data.get('plans', []):
            create_plan(conn, phase['id'], plan_data['name'], plan_data['description'],
                       wave=plan_data.get('wave', 1),
                       tdd_required=plan_data.get('tdd_required', True))
    print(f'Applied template: {template[\"name\"]} to milestone {milestone_id}')
"
```

## Output
For --list: table of available templates with name and description.
For --apply: confirmation of created milestone, phases, and plans.
