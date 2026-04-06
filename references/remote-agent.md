# Remote Agent Dispatch Protocol

## Overview

Meridian can dispatch plans to any self-hosted autonomous AI agent for execution on a separate machine. The agent picks up tasks, implements them, creates branches and PRs, and reports back via HTTP or webhooks.

This protocol is agent-agnostic — it works with any service that implements the JSON-RPC interface described below. Examples of compatible agents:

- **Nero** — autonomous coding daemon
- **OpenClaw / ZeroClaw** — open-source agent framework
- **Hermes** — self-hosted AI agent
- Any custom agent that speaks the dispatch protocol

## Communication

### State Sharing
- Meridian exports state to `.meridian/meridian-state.json` (git-tracked)
- The remote agent reads this file to understand project context
- Export happens after every state change (plan complete, phase transition, etc.)

### HTTP Dispatch
- Endpoint: `http://<agent-host>:<port>/rpc` (configured per-project as `nero_endpoint`)
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
        "task_id": "agent-task-uuid"
    }
}
```

### Response
```json
{
    "task_id": "agent-task-uuid",
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
When `--swarm` is used, all pending plans dispatch simultaneously. The agent creates separate branches and PRs for each. The user reviews and merges PRs in order.

## Error Handling
- If the agent is unreachable, dispatch fails gracefully with cached status
- Failed tasks can be retried or reassigned to local subagent execution
- Dispatch status is always available from local SQLite even if the agent is down

## Bidirectional Sync (`scripts/sync.py`)

### Pull: `pull_dispatch_status(conn)`

Polls all active dispatches and updates local state when the remote agent reports changes.

**Auto-transitions on pull:**
- Agent reports `completed` → local plan transitions to `complete` (with `commit_sha`)
- Agent reports `failed`/`rejected` → local plan transitions to `failed` (with error message)
- Agent unreachable → no change, logged as `unreachable`

```python
from scripts.sync import pull_dispatch_status
updates = pull_dispatch_status(conn)
```

### Push: `push_state_to_nero(conn)`

Exports all pending/failed plans from the active milestone as agent-compatible tickets.

```python
from scripts.sync import push_state_to_nero
result = push_state_to_nero(conn)
# {"status": "ok", "tickets_pushed": 3}
```

### Full Sync: `sync_all(conn)`

Runs pull then push in sequence.

```python
from scripts.sync import sync_all
result = sync_all(conn)
```

### Dispatch Summary: `get_dispatch_summary(conn)`

Returns all dispatches for the active milestone with plan/phase names attached.

```python
from scripts.sync import get_dispatch_summary
dispatches = get_dispatch_summary(conn)
```

## Webhooks

The remote agent can push events to Meridian via `handle_webhook()` instead of requiring Meridian to poll.

### Webhook Payload Format
```json
{
    "event_type": "task.completed",
    "task_id": "agent-task-uuid",
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

## Setting Up Your Agent

### 1. Configure the endpoint

Set `nero_endpoint` on your project (the field name is historical — it works with any agent):

```python
from scripts.state import update_project
from scripts.db import open_project

with open_project(".") as conn:
    update_project(conn, "default", nero_endpoint="http://your-agent:7655")
```

### 2. Implement the protocol

Your agent needs two JSON-RPC methods:

- `dispatch_task(params)` → returns `{"task_id": "..."}`
- `get_task_status(params)` → returns `{"status": "...", "pr_url": "...", "commit_sha": "..."}`

### 3. Dispatch

```
/meridian:dispatch --plan 5           # Single plan
/meridian:dispatch --phase 2          # All plans in phase
/meridian:dispatch --phase 2 --swarm  # All plans in parallel
```

## Sync Lifecycle

```
                Meridian                         Remote Agent
                ─────────                       ─────────────
1. /dispatch    ──── dispatch_plan() ────────→  Accept task
                     creates dispatch record     task_id returned
                     plan → executing

2. (later)      ──── pull_dispatch_status() ──→  get_task_status
                     checks dispatch records      returns completed/failed
                     plan → complete/failed ◄──

3. Auto-advance      check_auto_advance()
                     phase → verifying (if all plans done)

4. /dashboard        get_dispatch_summary()
                     renders dispatch status

5. push_state() ──── push_state_to_nero() ───→  sync_tickets
                      sends pending plans         Agent schedules work
```

## Notes
- The `nero_endpoint` and `nero_dispatch` names in the database are historical — they work with any agent that implements this protocol
- All dispatch communication uses standard HTTP POST with JSON payloads
- No authentication is required by default — add auth headers in a custom dispatch wrapper if needed
