# /meridian:profile — Developer Preference Profiling

Analyzes project history and structure to build a developer preference profile. Profile is saved to .meridian/USER-PROFILE.md for future session context.

## Arguments
- (no args) — Generate profile from project analysis
- `--refresh` — Regenerate profile even if one exists

## Keywords
profile, preferences, patterns, style, conventions, developer, analyze, history

## Procedure

### Generate Profile
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.profiler import analyze_project_patterns, generate_profile, save_profile
patterns = analyze_project_patterns(Path('.'))
content = generate_profile(patterns)
path = save_profile(Path('.'), content)
print(f'Profile saved to {path}')
print(content)
"
```

### Refresh Profile
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.profiler import analyze_project_patterns, generate_profile, save_profile
patterns = analyze_project_patterns(Path('.'))
content = generate_profile(patterns)
path = save_profile(Path('.'), content)
print(f'Profile refreshed at {path}')
print(content)
"
```

## When to Use
- At the start of a new project to capture dev preferences
- Before generating plans to inform style choices
- After major project structure changes

## When NOT to Use
- For project status → use /meridian:status
- For task tracking → use /meridian:quick
