# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**Nero (Autonomous Coding Daemon):**
- Purpose: Dispatches implementation tasks to a secondary machine running the Crush coding agent. Nero executes plans, creates branches/PRs autonomously.
- SDK/Client: Custom HTTP client using `urllib.request` (stdlib) in `scripts/dispatch.py` and `scripts/sync.py`
- Protocol: JSON-RPC over HTTP POST to `<nero_endpoint>/rpc`
- Auth: None detected (plain HTTP, endpoint stored in `project.nero_endpoint` DB column)
- Configuration: Set during `/meridian:init`, stored in SQLite `project` table

**Nero RPC Methods:**
- `dispatch_task` - Send a plan for implementation (`scripts/dispatch.py` `dispatch_plan()`)
- `get_task_status` - Poll task status (`scripts/dispatch.py` `check_dispatch_status()`, `scripts/sync.py` `pull_dispatch_status()`)
- `sync_tickets` - Push pending work items for Nero's PM agent scheduling (`scripts/sync.py` `push_state_to_nero()`)

**Nero Dispatch Payload Structure** (from `scripts/dispatch.py` lines 46-76):
```python
{
    "method": "dispatch_task",
    "params": {
        "type": "implement",
        "project": {"name", "repo_path", "repo_url", "tech_stack"},
        "phase": {"name", "description"},
        "plan": {"name", "description", "files_to_create", "files_to_modify", "test_command", "tdd_required"},
        "context": "<phase context_doc>"
    }
}
```

**Nero Status Flow:**
```
dispatched -> accepted -> running -> completed (with pr_url, commit_sha)
                                  -> failed (with error)
                       -> rejected
```

**Axis (PM Kanban Board):**
- Purpose: Syncs Meridian phase status to a kanban board at `https://axis.mattjaikaran.com`
- SDK/Client: Shell script execution via `subprocess.run()` calling `~/zeroclaw/skills/kanban/pm.sh`
- Auth: Handled by the `pm.sh` script (external to this codebase)
- Configuration: `axis_project_id` stored in SQLite `project` table
- Implementation: `scripts/axis_sync.py`

**Axis Commands Used:**
- `pm.sh ticket move <ticket_id> <status>` - Update ticket status (`scripts/axis_sync.py` line 79)
- `pm.sh ticket add <project> "<name>" --description "<desc>"` - Create new tickets (`scripts/axis_sync.py` line 131-133)

**Axis Status Mapping** (from `scripts/axis_sync.py` lines 12-32):
| Meridian Phase Status | Axis Status |
|---|---|
| planned, context_gathered | backlog |
| planned_out | todo |
| executing, verifying | in_progress |
| reviewing | in_review |
| complete | done |
| blocked | blocked |

## Data Storage

**Databases:**
- SQLite3 (embedded, per-project)
  - Connection: File path `<project_dir>/.meridian/state.db`
  - Client: Python stdlib `sqlite3` module via `scripts/db.py` `connect()`
  - Schema: 9 tables, version 2 with migration support
  - Config: WAL mode, foreign keys ON, row_factory enabled

**File Storage:**
- Local filesystem only
  - `.meridian/state.db` - SQLite database per project
  - `.meridian/meridian-state.json` - JSON state export for git tracking

**Caching:**
- None. All state reads hit SQLite directly.

## Authentication & Identity

**Auth Provider:**
- None. Meridian is a local CLI tool. No user authentication.
- Nero endpoint has no auth (plain HTTP POST)
- Axis auth is delegated to external `pm.sh` script

## Monitoring & Observability

**Error Tracking:**
- None. Errors are returned as dict values or raised as `ValueError` exceptions.

**Logs:**
- No logging framework. Functions return result dicts with status/error messages.
- Nero dispatch failures are captured in `nero_dispatch` table (status field).

## CI/CD & Deployment

**Hosting:**
- Local CLI tool. Not deployed as a service.
- Consumed by Claude Code as a skill/command set.

**CI Pipeline:**
- None detected. No GitHub Actions, no CI config files.

## Environment Configuration

**Required env vars:**
- None. All configuration is in SQLite database.

**Runtime configuration (in SQLite `project` table):**
- `nero_endpoint` - URL for Nero daemon (optional, enables dispatch features)
- `axis_project_id` - Axis kanban project ID (optional, enables PM sync)
- `repo_path` - Local path to the project repository
- `repo_url` - Remote git URL (optional)
- `tech_stack` - JSON array of tech stack tags (optional)

## Webhooks & Callbacks

**Incoming:**
- None. Meridian is a client/CLI tool, not a server.

**Outgoing:**
- Nero RPC dispatch (HTTP POST to `<nero_endpoint>/rpc`) - `scripts/dispatch.py`, `scripts/sync.py`
- Axis PM commands (shell subprocess) - `scripts/axis_sync.py`

## Git Integration

**Git CLI Usage:**
- `scripts/state.py` `_get_git_state()` - Reads branch, SHA, dirty status via `git rev-parse` and `git status --porcelain`
- `scripts/resume.py` `_get_git_log()`, `_get_git_branch()`, `_get_git_sha()` - Reads git history for resume prompt generation
- Git operations are read-only within Meridian scripts (write operations like commit/push are handled by skill prompts)

## Integration Error Handling

**Nero:**
- `urllib.error.URLError` caught on all HTTP calls
- Unreachable Nero returns cached local status, no crash
- Timeouts: 30s for dispatch, 10s for status checks
- Failed dispatches recorded in `nero_dispatch` table

**Axis:**
- `FileNotFoundError` if `pm.sh` script missing at `~/zeroclaw/skills/kanban/pm.sh`
- Generic `Exception` caught per-ticket, failures logged in results but don't block other syncs
- 30s subprocess timeout

**Both integrations are optional** - Meridian works fully without Nero or Axis configured.

---

*Integration audit: 2026-03-10*
