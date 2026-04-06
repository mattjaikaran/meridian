# Nero Integration Protocol

## Overview

Nero is an autonomous coding daemon running on a secondary machine. Meridian dispatches tasks to Nero, which executes plans autonomously and creates PRs.

## Communication

### State Sharing
- Meridian exports state to `.meridian/meridian-state.json` (git-tracked)
- Nero reads this file to understand project context
- Export happens after every state change (plan complete, phase transition, etc.)

### HTTP Dispatch
- Endpoint: `http://<nero_endpoint>/rpc`
- Method: POST
- Content-Type: application/json

### Dispatch Payload
```json
{
    "method": "dispatch_task",
    "params": {
        "type": "implement",
        "project": {
            "name": "MyApp",
            "repo_path": "/path/to/repo",
            "repo_url": "https://github.com/...",
            "tech_stack": ["python", "fastapi"]
        },
        "phase": {
            "name": "Phase Name",
            "description": "What this phase achieves"
        },
        "plan": {
            "name": "Plan Name",
            "description": "Full implementation instructions",
            "files_to_create": ["path/file.py"],
            "files_to_modify": ["path/existing.py"],
            "test_command": "uv run pytest tests/",
            "tdd_required": true
        },
        "context": "Gathered context document..."
    }
}
```

### Status Check
```json
{
    "method": "get_task_status",
    "params": {
        "task_id": "nero-task-uuid"
    }
}
```

### Response
```json
{
    "task_id": "nero-task-uuid",
    "status": "completed",
    "pr_url": "https://github.com/.../pull/42",
    "commit_sha": "abc123"
}
```

## Status Flow
```
dispatched → accepted → running → completed
                                → failed
                     → rejected
```

## Swarm Mode
When `--swarm` is used, all pending plans dispatch simultaneously. Nero creates separate branches and PRs for each. The user reviews and merges PRs in order.

## Error Handling
- If Nero is unreachable, dispatch fails gracefully with cached status
- Failed Nero tasks can be retried or reassigned to subagent execution
- Dispatch status is always available from local SQLite even if Nero is down

## Bidirectional Sync (`scripts/sync.py`)

The original dispatch model was push-only: Meridian sends plans, checks status manually. The sync module closes the loop with automatic pull + push.

### Pull: `pull_dispatch_status(conn)`

Polls all active `nero_dispatch` records (status in `dispatched`, `accepted`, `running`) and updates local state when Nero reports changes.

**Auto-transitions on pull:**
- Nero reports `completed` → local plan transitions to `complete` (with `commit_sha`)
- Nero reports `failed`/`rejected` → local plan transitions to `failed` (with error message)
- Nero unreachable → no change, logged as `unreachable`
- Nero reports same status → no update

```python
from scripts.sync import pull_dispatch_status
updates = pull_dispatch_status(conn)
# Returns:
# [
#   {"dispatch_id": 1, "old_status": "running", "new_status": "completed",
#    "pr_url": "https://...", "plan_transitioned": "complete"},
#   {"dispatch_id": 2, "status": "unreachable", "message": "Could not reach Nero"}
# ]
```

### Push: `push_state_to_nero(conn)`

Exports all pending/failed plans from the active milestone as Nero-compatible tickets. This lets Nero's PM agent schedule and prioritize work.

**Ticket format pushed to Nero:**
```json
{
    "method": "sync_tickets",
    "params": {
        "project": "MyApp",
        "tickets": [
            {
                "type": "implement",
                "plan_id": 5,
                "name": "Add API routes",
                "description": "...",
                "priority": "high",
                "wave": 2,
                "tdd_required": true,
                "files_to_create": ["src/routes.py"],
                "files_to_modify": ["src/app.py"],
                "test_command": "uv run pytest tests/",
                "context": "Phase context doc..."
            }
        ]
    }
}
```

Priority flows from plan → phase → defaults to `"medium"`.

```python
from scripts.sync import push_state_to_nero
result = push_state_to_nero(conn)
# {"status": "ok", "tickets_pushed": 3, "nero_response": {...}}
```

### Full Sync: `sync_all(conn)`

Runs pull then push in sequence. Recommended for use before dashboard/status checks.

```python
from scripts.sync import sync_all
result = sync_all(conn)
# {"pull_results": [...], "push_result": {...}}
```

### Dispatch Summary: `get_dispatch_summary(conn)`

Returns all dispatches for the active milestone with plan/phase names attached. Used by `/meridian:dashboard`.

```python
from scripts.sync import get_dispatch_summary
dispatches = get_dispatch_summary(conn)
# [{"id": 1, "status": "completed", "plan_name": "Setup CI", "phase_name": "Foundation", ...}]
```

## Webhooks

Nero can push events to Meridian via `handle_webhook()` instead of requiring Meridian to poll.

### Webhook Payload Format
```json
{
    "event_type": "task.completed",
    "task_id": "nero-task-uuid",
    "status": "completed",
    "pr_url": "https://github.com/.../pull/42",
    "commit_sha": "abc123",
    "error": null
}
```

### Event Types

| Event | Description | Effect |
|-------|-------------|--------|
| `task.completed` | Task finished successfully | Dispatch → completed, Plan → complete |
| `task.failed` | Task failed | Dispatch → failed, Plan → failed |
| `task.progress` | Status update (running, etc.) | Dispatch status updated |

### Setup

1. Configure Nero to POST webhook events to your Meridian endpoint
2. Route incoming payloads to `handle_webhook(conn, payload)`

```python
from scripts.sync import handle_webhook
result = handle_webhook(conn, {
    "event_type": "task.completed",
    "task_id": "nero-123",
    "commit_sha": "abc123",
    "pr_url": "https://github.com/pr/1",
})
# {"status": "ok", "dispatch_id": 1, "plan_transitioned": "complete"}
```

All webhook events are logged to the `state_event` table for audit.

## Sync Lifecycle

```
                Meridian                         Nero
                ─────────                       ──────
1. /dispatch    ──── dispatch_plan() ────────→  Accept task
                     creates nero_dispatch       nero_task_id returned
                     plan → executing

2. (later)      ──── pull_dispatch_status() ──→  get_task_status
                     checks nero_dispatch         returns completed/failed
                     plan → complete/failed ◄──

3. Auto-advance      check_auto_advance()
                     phase → verifying (if all plans done)

4. /dashboard        get_dispatch_summary()
                     renders dispatch status

5. push_state()  ──── push_state_to_nero() ───→  sync_tickets
                      sends pending plans         Nero schedules work
```
