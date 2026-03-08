# Meridian State Machine

## Hierarchy

```
Project (1) → Milestone (N) → Phase (N) → Plan (N)
```

## Milestone States

```
planned → active → complete → archived
```

- Only one milestone can be `active` at a time
- Must be `active` before phases can be worked on
- All phases must be `complete` before milestone can be completed

## Phase States

```
planned → context_gathered → planned_out → executing → verifying → reviewing → complete
   ↕           ↕                  ↕            ↕           ↕           ↕
blocked     blocked           blocked      blocked     blocked     blocked
```

### Transition Rules

| From | To | Trigger |
|------|----|---------|
| planned | context_gathered | Context gathering subagent completes |
| context_gathered | planned_out | Plans created and wave-assigned |
| planned_out | executing | First plan begins execution |
| executing | verifying | All plans complete/skipped |
| verifying | reviewing | Acceptance criteria verified |
| reviewing | complete | Two-stage review passes |
| any | blocked | External blocker identified |
| blocked | previous | Blocker resolved |
| executing | planned_out | Re-planning needed (all plans failed) |
| verifying | executing | Verification fails, more work needed |
| reviewing | executing | Review finds issues requiring fixes |

### Constraints
- Phase proceeds in sequence order within a milestone
- Phase cannot start until previous phase is `complete`
- `started_at` set on first transition to `executing`
- `completed_at` set on transition to `complete`

## Plan States

```
pending → executing → complete
                   → failed → pending (retry)
                            → executing (direct retry)
                   → paused → executing (resume)
                            → skipped
pending → skipped
```

### Transition Rules

| From | To | Trigger |
|------|----|---------|
| pending | executing | Plan picked up by subagent/Nero |
| pending | skipped | Plan no longer needed |
| executing | complete | Tests pass, review passes |
| executing | failed | Tests fail or error occurs |
| executing | paused | Context limit or manual pause |
| failed | pending | Reset for retry |
| failed | executing | Direct retry |
| paused | executing | Resume execution |
| paused | skipped | Abandoned |

### Wave Rules
- Plans in the same wave CAN execute in parallel
- Wave N+1 plans cannot start until all wave N plans are complete/skipped
- Failed plans in wave N block wave N+1

## Checkpoint Triggers

| Trigger | When |
|---------|------|
| manual | User runs `/meridian:checkpoint` |
| auto_context_limit | Token estimation exceeds 150k |
| plan_complete | Each plan finishes (auto) |
| phase_complete | Phase transitions to complete |
| error | Unrecoverable error during execution |
| pause | User pauses work |

## Next Action Computation

Priority order:
1. Failed plans → fix or skip
2. Pending plans in current wave → execute
3. Wave complete, next wave pending → execute
4. All plans done → verify phase
5. Phase verified → review phase
6. Phase reviewed → complete phase
7. All phases complete → complete milestone
8. No phases → create plans
9. No milestones → create milestone
