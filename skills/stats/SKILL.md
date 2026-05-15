---
name: meridian:stats
description: "Display project statistics — phases, plans, git metrics, test counts, velocity, and timeline"
allowed-tools:
  - Read
  - Bash
---

<objective>
Display comprehensive project statistics: phase and plan completion rates, git commit history, test file counts, planning velocity, and project timeline.
</objective>

<process>

Run the stats command and present the output:

```bash
meridian stats
```

If `--json` output is needed for downstream processing:

```bash
meridian --json stats
```

The output covers:
- **Progress**: phase and plan completion bars with percentages
- **Milestones**: per-milestone status and phase counts
- **Velocity**: plans completed per day (rolling 7-day window)
- **Git**: commit count, total insertions/deletions, file count, last commit date
- **Tests**: test file count and test function count
- **Timeline**: project start date and age in days

If the project has no `.meridian/state.db`, instruct the user to run `meridian init` first.

</process>

<success_criteria>
- [ ] Stats gathered and displayed
- [ ] Output readable without additional context
</success_criteria>
