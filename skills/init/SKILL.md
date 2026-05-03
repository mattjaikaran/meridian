# /meridian:init — Initialize Meridian in Current Project

Initialize Meridian state tracking in the current project directory.

## What This Does

1. Creates `.meridian/` directory in the project root
2. Initializes SQLite database with schema at `.meridian/state.db`
3. Gathers project context (repo info, tech stack, structure)
4. Creates the default project record
5. Optionally creates the first milestone

## Procedure

### Step 1: Find Project Root
Look for indicators of project root (`.git/`, `package.json`, `pyproject.toml`, `Cargo.toml`, etc.). If none found, use current directory.

### Step 2: Initialize Database
```bash
cd <project_root>
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import init
path = init('.')
print(f'Database initialized at {path}')
"
```

### Step 3: Gather Context
Use an Explore agent to analyze the project:
- Repository URL (from `git remote -v`)
- Tech stack (from config files)
- Directory structure overview
- Key patterns and conventions

### Step 4: Create Project Record
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_project
conn = connect(get_db_path('.'))
create_project(conn, name='<name>', repo_path='<path>', tech_stack=<stack>, repo_url='<url>')
conn.close()
"
```

### Step 5: Create First Milestone (if user provides goal)
Ask the user what the first milestone should be. If they provide one:
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_milestone, transition_milestone
conn = connect(get_db_path('.'))
create_milestone(conn, '<id>', '<name>', description='<desc>')
transition_milestone(conn, '<id>', 'active')
conn.close()
"
```

### Step 6: Add .meridian to .gitignore
Append `.meridian/` to `.gitignore` if not already present. The state DB is local — only the exported JSON is tracked.

### Step 7: Show Status
Run `/meridian:status` to confirm initialization.

## Output
Print a summary showing:
- Project name and path
- Tech stack detected
- Milestone (if created)
- Next recommended action
