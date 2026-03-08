# Nero Integration Protocol

## Overview

Nero is an autonomous coding daemon running on Mac Mini (192.168.1.230). Meridian on MacBook Pro dispatches tasks to Nero, which uses Crush (its coding agent) to implement and create PRs.

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
