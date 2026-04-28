# /meridian:sketch — Multi-Variant HTML Mockup Generation

Generate 2–3 variant HTML mockups for a UI concept before committing to a design.
Loads spike findings and theme context; spawns a subagent per variant in parallel.
Produces `.planning/sketches/{slug}/variant-{a,b,c}.html`.

## Arguments
- `create <title> [description]` — Open a new sketch session
- `list` — Show all sketches (open + closed)
- `list --open` — Open sketches only
- `list --closed` — Closed sketches only
- `status <slug>` — Show sketch details and list variant files

## Keywords
sketch, mockup, wireframe, prototype, variant, design, HTML, UI, visual, layout

## Procedure

### Subcommand: create

#### Step 1: Create DB record
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from pathlib import Path
from scripts.db import open_project
from scripts.sketch import create_sketch
with open_project('.') as conn:
    s = create_sketch(conn, '<title>', '<description>', Path('.'))
    print(json.dumps(s, indent=2))
"
```

Store: `slug`, `title`, `description`, `phase_id`.

#### Step 2: Load Spike Findings (if any linked spike exists)

Check `.planning/spikes/` for any spikes linked to the triggering phase. If found, read their MANIFEST.md and findings/ files for context.

Also check `.planning/PROJECT.md` and any RESEARCH.md for the current phase.

#### Step 3: Spawn Variant Subagents (parallel)

Launch **2 or 3 variant subagents** in a single parallel batch. Each produces a complete, self-contained HTML mockup. Use `subagent_type: general-purpose`.

**For each variant, instruct the subagent:**

```
You are a UI designer producing a self-contained HTML mockup for:

Sketch title: <title>
Description: <description>

Spike context (if available): <spike_summary>

Your task: Write a complete, self-contained HTML file for variant <A/B/C>.

Variant guidance:
- Variant A: Conservative / minimal layout — prioritize clarity and scannability
- Variant B: Feature-rich / content-dense — show all key elements at once
- Variant C (optional): Experimental / unconventional — challenge assumptions about layout

Requirements:
- All CSS must be inline (no external stylesheets or CDN links)
- All JavaScript must be inline (no external scripts)
- Use realistic placeholder content (not "Lorem ipsum")
- Must render correctly when opened as a local HTML file in a browser
- Include a small `<header>` comment at the top naming the variant and approach

Return ONLY the raw HTML — no markdown code fences, no preamble.
```

Collect all variant HTML strings.

#### Step 4: Write Variant Files
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
from pathlib import Path
from scripts.db import open_project
from scripts.sketch import add_variant
with open_project('.') as conn:
    add_variant(conn, '<slug>', 'variant-a', '''<variant_a_html>''', Path('.'))
    add_variant(conn, '<slug>', 'variant-b', '''<variant_b_html>''', Path('.'))
    # add_variant(conn, '<slug>', 'variant-c', '''<variant_c_html>''', Path('.'))
"
```

#### Step 5: Display Summary

```
Sketch: <slug>
Status: open
Title: <title>
Artifact: .planning/sketches/<slug>/

Variants generated:
  - variant-a.html  ← Conservative / minimal
  - variant-b.html  ← Feature-rich / content-dense
  - variant-c.html  ← Experimental (if generated)

Next: review variants, then run /meridian:sketch-wrap-up <slug> variant-<x>
```

---

### Subcommand: list
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.sketch import list_sketches
with open_project('.') as conn:
    sketches = list_sketches(conn, status=<'open'|'closed'|None>)
    for s in sketches:
        marker = '[open]' if s['status'] == 'open' else '[closed]'
        winner = f\" → {s['winner_variant']}\" if s.get('winner_variant') else ''
        print(f\"{marker} {s['slug']} — {s['title']}{winner} ({s['updated_at']})\")
"
```

Display as a table:

| Status | Slug | Title | Winner | Updated |
|--------|------|-------|--------|---------|

---

### Subcommand: status
```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.sketch import get_sketch
with open_project('.') as conn:
    s = get_sketch(conn, '<slug>')
    if s:
        print(json.dumps(s, indent=2))
    else:
        print('Sketch not found')
"
```

Then read `.planning/sketches/<slug>/MANIFEST.md` and list files in `.planning/sketches/<slug>/`.

```
Sketch: <slug>
Status: open|closed
Title: <title>
Artifact: .planning/sketches/<slug>/

Variants:
  - variant-a.html
  - variant-b.html
  - variant-c.html

Winner: <winner or "(none yet)">
```

## Display Format (create)

```
Sketch: <slug>
Status: open
Variants generated: 2–3
Artifact: .planning/sketches/<slug>/

Next: /meridian:sketch-wrap-up <slug> variant-<x>
```

## Gate Behavior

Before `/meridian:ui-phase` starts on a phase, check for open sketches:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME python -c "
import json
from scripts.db import open_project
from scripts.sketch import check_sketch_gate
with open_project('.') as conn:
    blockers = check_sketch_gate(conn, <phase_id>)
    print(json.dumps(blockers, indent=2))
"
```

If blockers is non-empty, warn:
> ⚠ Phase has {N} open sketch(es). Close them with `/meridian:sketch-wrap-up` before UI phase.

This is a **soft gate** — warns but does not block.

## When to Use
- Before a UI phase when layout options are genuinely unclear
- When stakeholder alignment on visual approach is needed
- After a spike that surfaces multiple valid UI directions

## When NOT to Use
- You already know the layout → go straight to `/meridian:ui-phase`
- Backend-only phase — no UI work involved
- Pure bugfix or refactor
