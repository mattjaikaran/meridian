# /meridian:secure-phase — Security Phase Type

Spawns 3 parallel subagents (OWASP threat modeler, auth analyst, data exposure analyst)
for a phase that involves any user-facing surface, auth flows, or data handling.
Produces `SECURITY.md` in the phase artifact directory. The plan phase soft-gates on
this artifact for phases tagged as security-sensitive.

**Position in workflow:** `secure-phase → spec-phase → discuss-phase → plan-phase → execute-phase`

## Arguments

- (no args) — analyze the current pending/planned phase
- `--phase <id>` — specify a phase by ID
- `--skip-data` — skip the data exposure subagent (faster, 2 subagents only)
- `--skip-security` — bypass gate warning in /meridian:plan (emergency only)

## Keywords

security, owasp, threat model, auth, authentication, authorization, data exposure,
pii, encryption, injection, xss, csrf, sql injection, secrets, tokens, pre-plan

## Procedure

### Step 1: Find Target Phase

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from scripts.db import connect, get_db_path
from scripts.secure_phase import get_secure_context
conn = connect(get_db_path('.'))
ctx = get_secure_context(conn, phase_id=<phase_id_or_None>)
print(json.dumps(ctx, indent=2, default=str))
conn.close()
"
```

Pass the `--phase <id>` value as `phase_id`, or `None` if not specified.

If result contains `"error"`, display it and stop — tell the user to run `/meridian:plan` first.

Store: `phase_id`, `phase_name`, `description`, `acceptance_criteria`, `tech_stack`,
`phase_dir`, `slug`.

### Step 2: Check for Existing SECURITY.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.secure_phase import check_security_artifact
result = check_security_artifact(Path('<phase_dir>'))
print('exists' if result else 'missing')
"
```

If `exists`: ask the user — "SECURITY.md already exists for this phase. Re-run and overwrite? (y/N)". If No, print the path and exit.

### Step 3: Scout the Codebase

Before spawning subagents, read the codebase for security-relevant patterns:

1. Auth layer — check for middleware, guards, JWT/session handling, OAuth providers
2. Database access — ORM usage, raw queries, parameterization patterns
3. Input validation — request validation, sanitization, schema libraries
4. Secrets management — env vars, config files, `.env` patterns
5. Existing security controls — CORS config, rate limiting, CSP headers, HTTPS enforcement
6. Prior phase artifacts in `<phase_dir>` if present (RESEARCH.md, SPEC.md)

Synthesize into a 2-3 sentence brief of the current security posture. Pass as context to each subagent.

### Step 4: Spawn Security Subagents (parallel)

Launch all subagents in a **single parallel batch** (same message). Use
`subagent_type: Explore` for each.

**Agent 1 — OWASP Threat Modeler:**
```
Perform an OWASP Top 10 threat assessment for the following phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current security posture: <2-3 sentence brief from Step 3>

For each applicable OWASP category, determine:
1. Whether this phase introduces or touches this attack surface
2. Specific threat scenarios (concrete, not generic)
3. Severity: Critical / High / Medium / Low
4. Likelihood: High / Medium / Low (given the tech stack and phase scope)
5. Recommended mitigation with concrete implementation guidance

OWASP Top 10 categories to assess:
- A01 Broken Access Control
- A02 Cryptographic Failures
- A03 Injection (SQL, command, LDAP, XPath)
- A04 Insecure Design
- A05 Security Misconfiguration
- A06 Vulnerable and Outdated Components
- A07 Identification and Authentication Failures
- A08 Software and Data Integrity Failures
- A09 Security Logging and Monitoring Failures
- A10 Server-Side Request Forgery

Output a threat table: | Threat | Severity | Likelihood | Mitigation |
Then list the top 3 most critical findings with detailed remediation steps.
Read the codebase. Quote file paths and line numbers for relevant patterns.
```

**Agent 2 — Auth & Access Control Auditor:**
```
Audit authentication and authorization flows for the following phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current security posture: <2-3 sentence brief from Step 3>

Analyze:
1. Authentication mechanisms — what auth method is in use (JWT, session, OAuth, API key)?
   Where are tokens issued, validated, and revoked? Quote file paths and line numbers.
2. Authorization model — RBAC, ABAC, or ad-hoc? Where are permission checks enforced?
   Are there any missing authorization checks this phase must add?
3. Session management — token expiry, refresh flow, logout invalidation, concurrent sessions.
4. Privilege escalation vectors — can a lower-privilege user access higher-privilege resources?
   Enumerate any gaps this phase introduces.
5. Token/secret handling — are secrets stored securely? Any risk of leakage in logs, errors, or responses?
6. Recommendations — for this specific phase, list auth/authz requirements with concrete code guidance.

Read the codebase. Be specific — name exact files, functions, and line numbers.
```

**Agent 3 — Data Exposure Analyst (skip if `--skip-data`):**
```
Analyze data exposure risks for the following phase.

Phase: <phase_name>
Description: <description>
Tech stack: <tech_stack>
Acceptance criteria:
<formatted list>

Current security posture: <2-3 sentence brief from Step 3>

Cover:
1. PII and sensitive data — what personal or sensitive data does this phase handle?
   (names, emails, passwords, payment info, health data, location, etc.)
2. Data at rest — is sensitive data stored? Is it encrypted? What encryption scheme?
   Quote file paths for model/schema definitions.
3. Data in transit — is TLS enforced for all endpoints this phase touches?
   Are there any internal service calls without TLS?
4. API response exposure — do API responses leak fields that shouldn't be public?
   Check serializer/schema definitions for over-exposure.
5. Logging and monitoring — does logging inadvertently capture sensitive fields?
   Are there redaction controls in place?
6. Third-party data sharing — does this phase send data to external services?
   What data, under what conditions, and is it documented?
7. Remediation checklist — list specific changes required for this phase to handle
   data safely, with file paths and implementation notes.

Read the codebase. Quote exact file paths and line numbers.
```

Collect all results (or 2 if `--skip-data`).

### Step 5: Write SECURITY.md

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
from pathlib import Path
from scripts.db import connect, get_db_path
from scripts.secure_phase import write_security_md, mark_security_complete
conn = connect(get_db_path('.'))
path = write_security_md(
    phase_dir=Path('<phase_dir>'),
    phase_name='<phase_name>',
    phase_id=<phase_id>,
    threat_model='''<threat_model_findings_verbatim>''',
    auth_analysis='''<auth_findings_verbatim>''',
    data_exposure='''<data_exposure_findings_verbatim_or_empty_string>''',
)
mark_security_complete(conn, <phase_id>)
conn.close()
print(str(path))
"
```

Paste verbatim findings from each subagent.

### Step 6: Display Summary

```
## Security Analysis Complete: <Phase Name>

Artifact: <phase_dir>/SECURITY.md
Subagents: threat-model ✓  auth ✓  data-exposure ✓ (or skipped)

### Critical Findings

<top 3 most critical threats with severity tags>

### Remediation Checklist

<10-15 specific, actionable items from all 3 subagents>

Next: /meridian:spec-phase --phase <phase_id>
  spec-phase will incorporate security requirements into acceptance criteria.
```

## Gate Behavior

`/meridian:plan` and `/meridian:execute` can check for SECURITY.md using `security_gate()`:

```bash
PYTHONPATH=$MERIDIAN_HOME uv run --project $MERIDIAN_HOME -- python -c "
import json
from pathlib import Path
from scripts.secure_phase import security_gate
result = security_gate(Path('<phase_dir>'))
print(json.dumps(result, indent=2))
"
```

- `passed: true` → proceed normally
- `passed: false` → print the `warning` string; user can bypass with `--skip-security`

This is a **soft gate** — it warns but does not block execution.

## What Each Subagent Covers

| Subagent | Focus | Reads codebase? |
|---|---|---|
| OWASP Threat Modeler | Top 10 categories, threat table, severity/likelihood | Yes |
| Auth & Access Control | Auth mechanisms, authz model, session, privilege escalation | Yes |
| Data Exposure Analyst | PII, encryption, API over-exposure, logging, 3rd-party | Yes |

## Output Artifact Structure

```
.planning/phases/<slug>/
└── SECURITY.md          ← written by this skill
    ├── Threat Model
    ├── Auth & Access Control Analysis
    └── Data Exposure Analysis
```
