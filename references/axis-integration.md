# Axis Integration Protocol

## Overview

Axis is the PM kanban board (https://axis.mattjaikaran.com). Meridian syncs phase status to Axis tickets for visibility.

## Status Mapping

| Meridian Phase | Axis Status |
|----------------|-------------|
| planned | backlog |
| context_gathered | backlog |
| planned_out | todo |
| executing | in_progress |
| verifying | in_progress |
| reviewing | in_review |
| complete | done |
| blocked | blocked |

## Sync Operations

### Phase → Axis Ticket
- When phase status changes, update corresponding Axis ticket
- Uses `pm.sh ticket move <ticket_id> <status>`
- Graceful when Axis is unreachable (skip sync, no error)

### Create Tickets
- `/meridian:plan` can auto-create Axis tickets for new phases
- Stores `axis_ticket_id` in phase record
- Ticket title = phase name, description = phase description

### Axis → Meridian
- Manual sync only (not automatic)
- If ticket moved in Axis, user can run sync to update Meridian
- Respects Meridian's stricter state transition rules

## Configuration
- `axis_project_id` set on project record during `/meridian:init`
- PM script at `~/zeroclaw/skills/kanban/pm.sh`
- Axis auth handled by existing sync infrastructure

## Notes
- Axis sync is optional — Meridian works fine without it
- Sync failures are logged but don't block workflow
- Phase changes are the source of truth; Axis is a view
