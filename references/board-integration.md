# Board Integration Protocol

## Overview

Meridian supports pluggable kanban board sync. When a phase transitions, Meridian can automatically create or move tickets on an external board (Linear, Jira, a custom tool, etc.).

Board sync is **optional** — Meridian works standalone without any provider configured.

## Status Mapping

| Meridian Phase    | Board Status |
|-------------------|-------------|
| planned           | backlog     |
| context_gathered  | backlog     |
| planned_out       | todo        |
| executing         | in_progress |
| verifying         | in_progress |
| reviewing         | in_review   |
| complete          | done        |
| blocked           | blocked     |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BOARD_PM_SCRIPT` | `~/bin/pm.sh` | Path to your board CLI script |

### Project Settings

Set via `/meridian:init` or directly in the database:

- `board_provider` — which provider to use (`"cli"`, `"noop"`, or your custom name)
- `board_project_id` — your board's project identifier (e.g. `"PROJ"`, `"team-board"`)

### Quick Setup

```bash
# 1. Set your board CLI path
export BOARD_PM_SCRIPT=~/tools/my-board-cli.sh

# 2. Initialize a Meridian project with board sync
# During /meridian:init, set board_provider to "cli" and board_project_id to your project ID
```

## Sync Operations

### Phase → Board Ticket
- When phase status changes, update corresponding board ticket
- Graceful when board is unreachable (skip sync, no error)

### Create Tickets
- `/meridian:plan` can auto-create board tickets for new phases
- Stores `board_ticket_id` in phase record
- Ticket title = phase name, description = phase description

### Board → Meridian
- Manual sync only (not automatic)
- If ticket moved on board, user can run sync to update Meridian
- Respects Meridian's stricter state transition rules

## Built-in Providers

| Provider | Alias | Description |
|----------|-------|-------------|
| `cli`    | `axis` | CLI-based provider — shells out to `BOARD_PM_SCRIPT` |
| `noop`   | —     | Default — does nothing, Meridian works standalone |

### CLI Provider Script Contract

Your `BOARD_PM_SCRIPT` must support these subcommands:

```bash
# Create a ticket — must print ticket ID (e.g. "Created ticket PROJ-123")
my-board-cli.sh ticket add <project_id> <name> --description <description>

# Move a ticket to a new status
my-board-cli.sh ticket move <ticket_id> <status>
```

Statuses passed to your script: `backlog`, `todo`, `in_progress`, `in_review`, `done`, `blocked`.

## Writing a Custom Provider

Implement the `BoardProvider` protocol from `scripts/board/provider.py`:

```python
from scripts.board.provider import register_provider

class LinearProvider:
    """Example: sync to Linear via their API."""

    def create_ticket(self, project_id: str, name: str, description: str = "") -> str | None:
        # Call Linear API, return issue ID like "ENG-42"
        ...

    def move_ticket(self, ticket_id: str, status: str) -> str | None:
        # Update Linear issue status, return ticket ID
        ...

register_provider("linear", LinearProvider)
```

Then set `board_provider` to `"linear"` in your project settings.

## Notes
- Board sync is optional — Meridian works fine without any provider
- Sync failures are logged but don't block workflow
- Phase changes are the source of truth; board is a view
