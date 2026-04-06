# Tutorial: Remote Agent Dispatch (Nero)

This tutorial covers setting up Nero ��� Meridian's remote autonomous execution agent. Nero runs on a secondary machine, picks up dispatched plans, implements them, and creates PRs.

## Overview

The standard Meridian workflow executes plans locally via Claude Code subagents. Nero adds an alternative: dispatch plans to a remote machine for fully autonomous execution.

```
Meridian (your machine)  --->  HTTP POST  --->  Nero (remote machine)
         |                                            |
         | dispatches plan                            | implements plan
         | tracks status                              | creates branch + PR
         |                                            |
         +--- pull status <--- HTTP GET <---  returns commit SHA + PR URL
```

### When to Use Nero

- **Parallel development** — dispatch multiple plans while you continue working
- **Long-running tasks** — let Nero work overnight on large implementations
- **Dedicated build machine** — offload heavy work to more powerful hardware

## Step 1: Configure the Endpoint

During `/meridian:init`, set the Nero endpoint for your project:

```python
from scripts.state import update_project
from scripts.db import open_project

with open_project(".") as conn:
    update_project(conn, "default", nero_endpoint="http://nero-host:7655")
```

Or configure it later via the database.

## Step 2: Dispatch a Plan

After planning (via `/meridian:plan`), dispatch individual plans or entire phases:

### Single Plan
```
/meridian:dispatch --plan 5
```

### All Plans in a Phase (Wave-Ordered)
```
/meridian:dispatch --phase 2
```

Plans are dispatched in wave order — wave 1 plans go first, then wave 2 after wave 1 completes.

### Swarm Mode (All Parallel)
```
/meridian:dispatch --phase 2 --swarm
```

All plans dispatch simultaneously. Nero creates separate branches for each. You review and merge PRs in order.

## Step 3: Check Status

```
/meridian:dispatch --status 1        # Check specific dispatch
/meridian:dispatch --check-all       # Check all active dispatches
```

Or use the dashboard:
```
/meridian:dashboard
```

Dispatch statuses:
```
dispatched --> accepted --> running --> completed (with PR URL)
                                   --> failed (with error message)
                        --> rejected
```

## Step 4: Pull Updates

Meridian can pull status updates from Nero to sync local state:

```python
from scripts.sync import pull_dispatch_status
from scripts.db import open_project

with open_project(".") as conn:
    updates = pull_dispatch_status(conn)
    # [{"dispatch_id": 1, "old_status": "running", "new_status": "completed",
    #   "pr_url": "https://github.com/.../pull/42"}]
```

When Nero reports a plan as `completed`:
- Local plan transitions to `complete`
- Commit SHA is recorded
- Phase auto-advances if all plans are done

## Step 5: Push State to Nero

Export pending plans as tickets so Nero can schedule work:

```python
from scripts.sync import push_state_to_nero
from scripts.db import open_project

with open_project(".") as conn:
    result = push_state_to_nero(conn)
    # {"status": "ok", "tickets_pushed": 3}
```

### Full Bidirectional Sync

```python
from scripts.sync import sync_all
from scripts.db import open_project

with open_project(".") as conn:
    result = sync_all(conn)
    # {"pull_results": [...], "push_result": {...}}
```

## Dispatch Payload Format

What Meridian sends to Nero:

```json
{
    "method": "dispatch_task",
    "params": {
        "type": "implement",
        "project": {
            "name": "MyApp",
            "repo_path": "/path/to/repo",
            "repo_url": "https://github.com/user/repo",
            "tech_stack": ["python", "fastapi"]
        },
        "phase": {
            "name": "API Routes",
            "description": "Implement REST endpoints"
        },
        "plan": {
            "name": "Add auth endpoints",
            "description": "Full implementation instructions...",
            "files_to_create": ["src/routes/auth.py"],
            "files_to_modify": ["src/app.py"],
            "test_command": "uv run pytest tests/",
            "tdd_required": true
        },
        "context": "Gathered context document..."
    }
}
```

## Webhooks (Optional)

Instead of polling, Nero can push events to Meridian:

```python
from scripts.sync import handle_webhook
from scripts.db import open_project

with open_project(".") as conn:
    result = handle_webhook(conn, {
        "event_type": "task.completed",
        "task_id": "nero-task-uuid",
        "commit_sha": "abc123",
        "pr_url": "https://github.com/user/repo/pull/42",
    })
```

Event types:
| Event | Effect |
|-------|--------|
| `task.completed` | Plan -> complete, dispatch -> completed |
| `task.failed` | Plan -> failed, dispatch -> failed |
| `task.progress` | Dispatch status updated (running, etc.) |

## State Export

Meridian exports its full state to JSON for Nero to read:

```python
from scripts.export import export_state
export_state(".")  # Creates .meridian/meridian-state.json
```

This runs automatically after every state change (plan complete, phase transition, etc.).

## Error Handling

- **Nero unreachable**: Dispatch fails gracefully, status cached locally
- **Task fails on Nero**: Plan transitions to `failed`, eligible for node repair
- **Network timeout**: 30s timeout on all HTTP calls, logged but non-blocking

## Architecture Diagram

```
                Meridian                         Nero
                ---------                       ------
1. /dispatch    ---- dispatch_plan() -------->  Accept task
                     creates nero_dispatch       nero_task_id returned
                     plan -> executing

2. (later)      ---- pull_dispatch_status() -->  get_task_status
                     checks nero_dispatch         returns completed/failed
                     plan -> complete/failed <--

3. Auto-advance      check_auto_advance()
                     phase -> verifying (if all plans done)

4. /dashboard        get_dispatch_summary()
                     renders dispatch status

5. push_state() ---- push_state_to_nero() ---->  sync_tickets
                      sends pending plans         Nero schedules work
```

---

## Next Steps

- [Nero Protocol Reference](../../references/nero-integration.md) — full HTTP/webhook spec
- [Workflow Tutorial](workflow-walkthrough.md) — end-to-end project walkthrough
- [Board Integration Tutorial](board-integration.md) — kanban sync setup
