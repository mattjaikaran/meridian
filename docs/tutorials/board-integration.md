# Tutorial: Board Integration

This tutorial shows how to connect Meridian to an external kanban board so phase transitions automatically sync ticket status.

## Overview

Meridian's board sync is:
- **Optional** — Meridian works standalone without any board
- **Pluggable** — use the built-in CLI provider or write your own
- **Graceful** — sync failures are logged but never block your workflow
- **Automatic** — phase transitions trigger syncs without manual intervention

## Option 1: CLI Provider (Built-in)

The CLI provider shells out to any board tool that has a command-line interface.

### Step 1: Create or Locate Your Board CLI

Your CLI script needs two subcommands:

```bash
# Create a ticket — must print a ticket ID in output
my-board-cli.sh ticket add <project_id> <name> --description <description>
# Example output: "Created ticket PROJ-123"

# Move a ticket to a new status
my-board-cli.sh ticket move <ticket_id> <status>
# Statuses: backlog, todo, in_progress, in_review, done, blocked
```

### Step 2: Configure the Environment

```bash
# Point to your CLI script
export BOARD_PM_SCRIPT=~/tools/my-board-cli.sh

# Add to ~/.zshrc or ~/.bashrc to persist
echo 'export BOARD_PM_SCRIPT=~/tools/my-board-cli.sh' >> ~/.zshrc
```

### Step 3: Configure Your Project

During `/meridian:init`, or manually:

```python
# In a Claude Code session:
from scripts.state import set_setting, update_project
from scripts.db import open_project

with open_project(".") as conn:
    update_project(conn, "default", board_project_id="YOUR-PROJECT-ID")
    set_setting(conn, "board_provider", "cli")
```

### Step 4: Verify

Create a phase and watch it sync:

```
/meridian:plan "Test board sync"
```

Check your board — you should see tickets created for each phase.

When phases transition:
```
planned       --> board: backlog
planned_out   --> board: todo
executing     --> board: in_progress
reviewing     --> board: in_review
complete      --> board: done
```

## Option 2: Custom Provider (API-based)

For boards with REST APIs (Linear, Jira, GitHub Projects), write a Python provider.

### Step 1: Create the Provider Module

Create `scripts/board/linear.py` (or any name):

```python
"""Linear board provider."""

from __future__ import annotations

import json
import logging
import os
import urllib.request

from scripts.board.provider import register_provider

logger = logging.getLogger(__name__)

LINEAR_API_KEY = os.environ.get("LINEAR_API_KEY", "")
LINEAR_API_URL = "https://api.linear.app/graphql"

# Map Meridian statuses to your Linear workflow state IDs
STATUS_MAP = {
    "backlog": "your-backlog-state-id",
    "todo": "your-todo-state-id",
    "in_progress": "your-in-progress-state-id",
    "in_review": "your-in-review-state-id",
    "done": "your-done-state-id",
    "blocked": "your-blocked-state-id",
}


def _linear_request(query: str, variables: dict | None = None) -> dict | None:
    """Make a GraphQL request to Linear."""
    if not LINEAR_API_KEY:
        logger.warning("LINEAR_API_KEY not set — skipping board sync")
        return None

    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        LINEAR_API_URL,
        data=payload,
        headers={
            "Authorization": LINEAR_API_KEY,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        logger.error("Linear API request failed: %s", e)
        return None


class LinearProvider:
    """Linear issue tracking integration."""

    def create_ticket(
        self,
        project_id: str,
        name: str,
        description: str = "",
    ) -> str | None:
        query = """
        mutation CreateIssue($teamId: String!, $title: String!, $description: String) {
            issueCreate(input: {teamId: $teamId, title: $title, description: $description}) {
                issue { identifier }
            }
        }
        """
        result = _linear_request(query, {
            "teamId": project_id,
            "title": name,
            "description": description,
        })
        if not result:
            return None
        return result.get("data", {}).get("issueCreate", {}).get("issue", {}).get("identifier")

    def move_ticket(
        self,
        ticket_id: str,
        status: str,
    ) -> str | None:
        state_id = STATUS_MAP.get(status)
        if not state_id:
            logger.warning("No Linear state mapping for status: %s", status)
            return None

        query = """
        mutation UpdateIssue($id: String!, $stateId: String!) {
            issueUpdate(id: $id, input: {stateId: $stateId}) {
                issue { identifier }
            }
        }
        """
        result = _linear_request(query, {"id": ticket_id, "stateId": state_id})
        if not result:
            return None
        return ticket_id


register_provider("linear", LinearProvider)
```

### Step 2: Register the Import

Add your module to `scripts/board/sync.py`:

```python
# Import built-in providers to trigger register_provider calls
import scripts.board.cli  # noqa: F401
import scripts.board.linear  # noqa: F401  # <-- Add this
```

### Step 3: Configure

```bash
export LINEAR_API_KEY=lin_api_xxxxx
```

Set the provider in your project:
```python
set_setting(conn, "board_provider", "linear")
```

### Step 4: Add Tests

```python
# tests/test_linear_provider.py
from scripts.board.linear import LinearProvider
from scripts.board.provider import BoardProvider

def test_satisfies_protocol():
    assert isinstance(LinearProvider(), BoardProvider)

def test_registered():
    from scripts.board.provider import get_provider
    provider = get_provider("linear")
    assert isinstance(provider, LinearProvider)
```

## Status Mapping Reference

| Meridian Phase | Board Status |
|----------------|-------------|
| `planned` | `backlog` |
| `context_gathered` | `backlog` |
| `planned_out` | `todo` |
| `executing` | `in_progress` |
| `verifying` | `in_progress` |
| `reviewing` | `in_review` |
| `complete` | `done` |
| `blocked` | `blocked` |

## Troubleshooting

### Tickets not being created
1. Check `board_provider` setting: is it set to the right provider name?
2. Check `board_project_id`: does your project have it configured?
3. Check env vars: is `BOARD_PM_SCRIPT` or your API key set?
4. Check logs: board sync errors are logged but don't raise exceptions

### Sync not triggering on phase transitions
Board sync is called automatically by `transition_phase()` in `scripts/state.py`. If you're modifying phase status directly in the DB, sync won't fire — always use the state transition functions.

### Provider not found
Make sure your module is imported in `scripts/board/sync.py`. The `register_provider()` call runs at import time, so the import must happen before any sync operations.

---

## Next Steps

- [Board Protocol Reference](../../references/board-integration.md) — full API contract
- [Workflow Tutorial](workflow-walkthrough.md) — end-to-end project walkthrough
- [Remote Dispatch Tutorial](remote-dispatch.md) — Nero autonomous execution
