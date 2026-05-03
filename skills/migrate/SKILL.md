# /meridian:migrate — Cross-Project Migration

Export a milestone's structure as a reusable template for use in other projects.

## Arguments
- `--export <milestone_id>` — Milestone to export (required)
- `--output <filename>` — Output filename (default: exported-<milestone_id>.json)

## Procedure

### Step 1: Export Template
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import open_project
from scripts.export import export_as_template

with open_project('.') as conn:
    template = export_as_template(conn, '<milestone_id>')
    output_path = '$MERIDIAN_HOME/templates/<output_filename>'
    from pathlib import Path
    path = Path(output_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(template, indent=2))
    print(f'Template exported to {path}')
    print(json.dumps(template, indent=2))
"
```

## Output
Show the exported template structure and the file path where it was saved.
