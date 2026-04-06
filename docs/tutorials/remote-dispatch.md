# Tutorial: Remote Agent Dispatch

This tutorial covers dispatching plans to a self-hosted AI agent running on a secondary machine. The agent picks up tasks, implements them autonomously, and creates PRs.

## Overview

The standard Meridian workflow executes plans locally via Claude Code subagents. Remote dispatch adds an alternative: send plans to an agent running elsewhere for fully autonomous execution.

This works with any agent that implements the dispatch protocol — Nero, OpenClaw, Hermes, or your own custom agent.

```
Meridian (your machine)  --->  HTTP POST  --->  Agent (remote machine)
         |                                            |
         | dispatches plan                            | implements plan
         | tracks status                              | creates branch + PR
         |                                            |
         +--- pull status <--- HTTP GET <---  returns commit SHA + PR URL
```

### When to Use Remote Dispatch

- **Parallel development** — dispatch multiple plans while you continue working
- **Long-running tasks** — let the agent work overnight on large implementations
- **Dedicated build machine** — offload heavy work to more powerful hardware

## Step 1: Configure the Endpoint

During `/meridian:init`, set the agent endpoint for your project:

```python
from scripts.state import update_project
from scripts.db import open_project

with open_project(".") as conn:
    update_project(conn, "default", nero_endpoint="http://agent-host:7655")
```

The field is called `nero_endpoint` for historical reasons — it works with any agent.

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

All plans dispatch simultaneously. The agent creates separate branches for each. You review and merge PRs in order.

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

Meridian can pull status updates from the remote agent to sync local state:

```python
from scripts.sync import pull_dispatch_status
from scripts.db import open_project

with open_project(".") as conn:
    updates = pull_dispatch_status(conn)
    # [{"dispatch_id": 1, "old_status": "running", "new_status": "completed",
    #   "pr_url": "https://github.com/.../pull/42"}]
```

When the agent reports a plan as `completed`:
- Local plan transitions to `complete`
- Commit SHA is recorded
- Phase auto-advances if all plans are done

## Step 5: Push State

Export pending plans so the agent can schedule work:

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

## Implementing Your Own Agent

Your agent needs to expose two JSON-RPC methods over HTTP:

### `dispatch_task`

Receives a plan and starts implementation:

```json
{
    "method": "dispatch_task",
    "params": {
        "type": "implement",
        "project": { "name": "MyApp", "repo_url": "https://github.com/..." },
        "plan": { "name": "Add auth", "description": "...", "tdd_required": true }
    }
}
```

Returns: `{"task_id": "your-task-uuid"}`

### `get_task_status`

Returns current status of a dispatched task:

```json
{"method": "get_task_status", "params": {"task_id": "your-task-uuid"}}
```

Returns: `{"status": "completed", "pr_url": "...", "commit_sha": "..."}`

### Optional: Webhooks

Instead of polling, your agent can push events to Meridian:

```python
from scripts.sync import handle_webhook
from scripts.db import open_project

with open_project(".") as conn:
    result = handle_webhook(conn, {
        "event_type": "task.completed",
        "task_id": "your-task-uuid",
        "commit_sha": "abc123",
        "pr_url": "https://github.com/user/repo/pull/42",
    })
```

## Error Handling

- **Agent unreachable**: Dispatch fails gracefully, status cached locally
- **Task fails on agent**: Plan transitions to `failed`, eligible for node repair
- **Network timeout**: 30s timeout on all HTTP calls, logged but non-blocking

---

## Next Steps

- [Remote Agent Protocol](../../references/remote-agent.md) — full HTTP/webhook spec
- [Workflow Tutorial](workflow-walkthrough.md) — end-to-end project walkthrough
- [Board Integration Tutorial](board-integration.md) — kanban sync setup
