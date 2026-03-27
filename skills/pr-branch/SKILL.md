# /meridian:pr-branch — Create Clean PR Branch

Create a PR-ready branch with only code-relevant commits, filtering out `.planning/` and `.meridian/` changes.

## Arguments
- `<slug>` (required) — Feature name for the branch (creates `pr/<slug>`)
- `--base <branch>` — Base branch to diff against (default: `main`)

## Procedure

### Step 1: Identify Code Commits
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.pr_branch import filter_commits
commits = filter_commits('main')
print(f'{len(commits)} code commits found')
for sha in commits:
    print(sha)
"
```

If no code commits found, warn user and stop.

### Step 2: Create PR Branch
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from scripts.pr_branch import create_pr_branch
branch = create_pr_branch('<slug>', 'main')
print(f'Created branch: {branch}')
"
```

### Step 3: Verify Branch
```bash
git log --oneline main..pr/<slug>
git diff --stat main..pr/<slug>
```

### Step 4: Push (optional)
```bash
git push -u origin pr/<slug>
```

## Notes
- Original branch is preserved — this is non-destructive
- Uses cherry-pick internally, so conflicts are possible on divergent histories
- If cherry-pick fails, the partial branch is cleaned up automatically
