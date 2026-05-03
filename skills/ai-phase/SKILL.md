# /meridian:ai-phase — AI Integration Phase Type

Spawns 3 parallel subagents (domain researcher, framework selector, eval planner) for
a phase that integrates an LLM, AI model, or ML component. Produces `AI-SPEC.md` in
the phase artifact directory. The plan phase soft-gates on this artifact for AI phases.

**Position in workflow:** `ai-phase → spec-phase → discuss-phase → plan-phase → execute-phase`

## Arguments

- (no args) — spec the current pending/planned phase
- `--phase <id>` — specify a phase by ID
- `--skip-eval` — skip the eval planner subagent (faster, 2 subagents only)
- `--skip-ai` — bypass gate warning in /meridian:plan (emergency only)

## Keywords

ai, llm, model, claude, openai, anthropic, gpt, embeddings, rag, agents, tool use,
prompt engineering, eval, evaluation, guardrails, inference, fine-tuning, pre-plan

## Procedure

### Step 1: Find Target Phase

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.ai_phase import get_ai_context
conn = connect(get_db_path('.'))
ctx = get_ai_context(conn, phase_id=<phase_id_or_None>)
print(json.dumps(ctx, indent=2, default=str))
conn.close()
"
```

Pass the `--phase <id>` value as `phase_id`, or `None` if not specified.

If result contains `"error"`, display it and stop — tell the user to run `/meridian:plan` first.

Store: `phase_id`, `phase_name`, `description`, `acceptance_criteria`, `tech_stack`,
`phase_dir`, `slug`.

### Step 2: Check for Existing AI-SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.ai_phase import check_ai_artifact
result = check_ai_artifact(Path('<phase_dir>'))
print('exists' if result else 'missing')
"
```

If `exists`: ask the user — "AI-SPEC.md already exists for this phase. Re-run and overwrite? (y/N)". If No, print the path and exit.

### Step 3: Scout the Codebase

Before spawning subagents, read the codebase for AI-relevant patterns:

1. Existing AI/LLM usage — check for `anthropic`, `openai`, `langchain`, `llama_index` imports
2. SDK versions — check `pyproject.toml`, `package.json`, `requirements.txt` for pinned versions
3. Prompt patterns — look for prompt templates, system prompts, message construction
4. Tool use / function calling — any existing tool definitions?
5. Caching — prompt caching, response caching, embedding stores?
6. Prior phase artifacts in `<phase_dir>` if present (RESEARCH.md, SPEC.md)

Synthesize into a 2-3 sentence brief of the current AI integration state. Pass as context to each subagent.

### Step 4: Spawn AI Subagents (parallel)

Launch all subagents in a **single parallel batch** (same message). Use
`subagent_type: Explore` for each.

**Agent 1 — Domain Researcher:**
```
Research the business domain and real-world application context for the following AI phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current AI integration state: <2-3 sentence brief from Step 3>

Research:
1. Domain expert evaluation criteria — how would a practitioner in this field judge
   whether the AI output is good? What does "good" look like vs "acceptable" vs "bad"?
2. Industry conventions — are there established approaches to this problem?
   What do production systems in this domain typically do?
3. Common failure modes — what goes wrong in production for this type of AI feature?
   Hallucination, latency, cost overruns, prompt injection, context window issues?
4. Regulatory and compliance context — is there any legal, privacy, or ethical context
   that constrains how AI can be used here? (GDPR, HIPAA, content policies, etc.)
5. User expectations — what will users expect from this AI feature?
   What will cause frustration or loss of trust?
6. Success criteria — 3-5 measurable criteria that define success for this AI integration
   from a domain perspective (not just technical correctness).

Do NOT read the codebase — this is pure domain and business research.
```

**Agent 2 — Framework & Model Selector:**
```
Select the optimal AI framework and model for the following phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current AI integration state: <2-3 sentence brief from Step 3>

Produce a decision matrix covering:
1. Task classification — what type of AI task is this?
   (text generation, classification, extraction, RAG, agents, tool use, embeddings, etc.)
2. Model candidates — evaluate 2-4 models suitable for this task. For each:
   - Provider and model name (e.g. Anthropic claude-sonnet-4-6, OpenAI gpt-4o)
   - Strengths for this specific use case
   - Weaknesses and known limitations
   - Context window, output constraints, pricing tier
3. Framework candidates — evaluate 1-3 integration patterns:
   - Direct SDK (anthropic, openai, boto3)
   - Orchestration framework (LangChain, LlamaIndex, Haystack)
   - Agentic framework (Claude Code SDK, AutoGen, CrewAI)
   For each: integration complexity, flexibility, community support, maintenance burden
4. Recommendation — pick ONE model and ONE integration approach.
   Justify the choice in 3-5 sentences. Explain what you ruled out and why.
5. Implementation notes — key SDK usage patterns, prompt caching opportunities,
   streaming vs batch considerations, retry and error handling guidance.
   Quote the latest Anthropic model IDs: claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5-20251001.

Read the codebase to check for existing patterns. Quote file paths and line numbers.
```

**Agent 3 — Eval Planner (skip if `--skip-eval`):**
```
Design the evaluation strategy for the following AI phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current AI integration state: <2-3 sentence brief from Step 3>

Design:
1. Critical failure modes — list 5-8 ways this AI feature can fail silently or
   produce harmful output. Be concrete and specific to this use case.
2. Eval dimensions — for each failure mode, define a measurable rubric:
   - Dimension name
   - What it measures
   - How to measure it (LLM-as-judge prompt, regex, human review, automated test)
   - Pass/fail threshold
3. Test dataset — what examples should the eval set include?
   How many? Where will they come from? Any adversarial cases?
4. Tooling recommendation — pick one eval framework or approach:
   (pytest with LLM judge, Braintrust, LangSmith, PromptFoo, custom harness)
   Justify why it fits this phase.
5. Guardrails — what input/output guardrails are required?
   (content filtering, length limits, PII stripping, structured output validation)
   Give concrete implementation guidance with code snippets where possible.
6. Production monitoring — 3-5 metrics to track in production:
   (latency p50/p99, cost per call, error rate, user feedback, eval score drift)
   How to alert when these degrade?

Be specific — generic eval advice is useless. Tie everything to this phase's deliverable.
```

Collect all results (or 2 if `--skip-eval`).

### Step 5: Write AI-SPEC.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.ai_phase import write_ai_spec_md, mark_ai_complete
conn = connect(get_db_path('.'))
path = write_ai_spec_md(
    phase_dir=Path('<phase_dir>'),
    phase_name='<phase_name>',
    phase_id=<phase_id>,
    domain='''<domain_findings_verbatim>''',
    framework='''<framework_findings_verbatim>''',
    eval_strategy='''<eval_findings_verbatim_or_empty_string>''',
)
mark_ai_complete(conn, <phase_id>)
conn.close()
print(str(path))
"
```

Paste verbatim findings from each subagent.

### Step 6: Display Summary

```
## AI Spec Complete: <Phase Name>

Artifact: <phase_dir>/AI-SPEC.md
Subagents: domain ✓  framework ✓  eval ✓ (or skipped)

### Model & Framework Selection

**Recommended model:** <model name>
**Integration approach:** <framework/SDK choice>
**Rationale:** <1-2 sentences>

### Top Failure Modes

<3-5 most critical failure modes with severity>

### Eval Dimensions

<rubric table: dimension | measure | threshold>

Next: /meridian:spec-phase --phase <phase_id>
  spec-phase will incorporate AI requirements into acceptance criteria.
```

## Gate Behavior

`/meridian:plan` and `/meridian:execute` can check for AI-SPEC.md using `ai_gate()`:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.ai_phase import ai_gate
result = ai_gate(Path('<phase_dir>'))
print(json.dumps(result, indent=2))
"
```

- `passed: true` → proceed normally
- `passed: false` → print the `warning` string; user can bypass with `--skip-ai`

This is a **soft gate** — it warns but does not block execution.

## What Each Subagent Covers

| Subagent | Focus | Reads codebase? |
|---|---|---|
| Domain Researcher | Business context, practitioner criteria, failure modes, compliance | No |
| Framework Selector | Model/framework decision matrix, SDK patterns, implementation notes | Yes |
| Eval Planner | Failure modes, eval rubrics, test datasets, guardrails, monitoring | No |

## Output Artifact Structure

```
.planning/phases/<slug>/
└── AI-SPEC.md          ← written by this skill
    ├── Domain & Problem Framing
    ├── Framework & Model Selection
    └── Evaluation Strategy, Guardrails & Monitoring
```
