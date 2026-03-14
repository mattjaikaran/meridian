# /meridian:scan — Codebase Audit & Work Discovery

Analyze a codebase with parallel agents to discover issues, tech debt, and work items. Produces a prioritized audit report and optionally creates a milestone with phases/plans from findings.

## Arguments
- `<focus>` — narrow scan to "security", "tests", "performance", "architecture", "deps", etc.
- `--create-milestone` — auto-create milestone with phases from findings
- `--milestone-name <name>` — custom milestone name (default: "Audit Remediation")

## Prerequisites
- Project must be initialized with `/meridian:init` (`.meridian/state.db` exists)
- Must be run from a project root with source code to analyze

## Procedure

### Step 1: Validate Project

Confirm `.meridian/state.db` exists. If not, tell the user to run `/meridian:init` first.

```bash
ls .meridian/state.db
```

### Step 2: Prepare Audit Directory

```bash
mkdir -p .meridian/audit
```

### Step 3: Parse Arguments

- If user provided `<focus>`, narrow all agents to that dimension only (spawn 1 agent instead of 4)
- If `--create-milestone` is present, set flag to create milestone after aggregation
- If `--milestone-name` is present, use that name; otherwise default to "Audit Remediation"

### Step 4: Launch Parallel Analysis Agents

Spawn **4 agents in parallel** using the Agent tool. Each agent writes its findings to `.meridian/audit/`. If `<focus>` is set, only spawn the relevant agent.

**IMPORTANT**: All agents must use the finding format defined below. Each agent should use Read, Grep, Glob, and Bash to thoroughly analyze its dimension.

#### Agent 1: Stack & Dependencies → `.meridian/audit/stack.md`
Analyze:
- Package manager files (`package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, etc.)
- Outdated or unused dependencies
- Build configuration issues
- Environment variable gaps (`.env.example` vs actual usage)
- Missing or misconfigured linters/formatters
- Dockerfile / docker-compose issues
- CI/CD configuration gaps

#### Agent 2: Architecture → `.meridian/audit/architecture.md`
Analyze:
- Module organization and coupling
- Dead code and unused exports/imports
- Oversized files (>500 lines)
- Inconsistent naming conventions
- Circular dependencies
- Missing abstractions or god objects
- API design issues (REST/GraphQL endpoint organization)

#### Agent 3: Quality & Tests → `.meridian/audit/quality.md`
Analyze:
- Test coverage gaps (directories/modules without tests)
- Missing type annotations (Python) or strict TypeScript issues
- TODO/FIXME/HACK/XXX comments
- Error handling gaps (bare except, unhandled promises)
- Code duplication patterns
- Missing input validation
- Logging gaps

#### Agent 4: Security & Ops → `.meridian/audit/security.md`
Analyze:
- Hardcoded secrets, API keys, tokens
- SQL injection or command injection risks
- XSS vulnerabilities (unescaped user input in templates)
- CORS/CSRF configuration issues
- Debug mode enabled in production configs
- Missing rate limiting
- Insecure dependencies (if lockfile available)
- Missing security headers
- File permission issues

### Agent Prompt Template

Each agent receives this prompt structure:
```
You are auditing a codebase. Write your findings to <output_file>.

Analyze the codebase for: <dimension description>

Use Read, Grep, Glob, and Bash tools to thoroughly examine the code.

Write every finding in this exact format:

### [SEVERITY] Finding Title
- **Category**: category-slug
- **Location**: file_path:line_number
- **Description**: What's wrong
- **Impact**: Why it matters
- **Suggested Fix**: What to do
- **Effort**: S/M/L

Severity levels:
- CRITICAL: Security vulnerabilities, data loss risks, broken core functionality
- HIGH: Significant bugs, major performance issues, missing critical tests
- MEDIUM: Code quality issues, moderate tech debt, missing non-critical tests
- LOW: Style issues, minor improvements, nice-to-haves

Start the file with:
# <Dimension> Audit
**Scanned**: <timestamp>
**Focus**: <focus or "full scan">

Then list all findings. End with:
## Summary
- Critical: N
- High: N
- Medium: N
- Low: N
```

### Step 5: Aggregate into REPORT.md

After all agents complete, read all 4 audit files and produce `.meridian/audit/REPORT.md`:

```markdown
# Codebase Audit Report
**Project**: <project name>
**Date**: <date>
**Focus**: <focus or "Full Scan">

## Summary
| Severity | Count |
|----------|-------|
| CRITICAL | N |
| HIGH | N |
| MEDIUM | N |
| LOW | N |
| **Total** | **N** |

## Critical Findings
<all CRITICAL findings from all agents>

## High Priority
<all HIGH findings from all agents>

## Medium Priority
<all MEDIUM findings from all agents>

## Low Priority
<all LOW findings from all agents>

## Recommended Phases
Based on findings, here is a suggested remediation plan:

### Phase 1: Critical Fixes (Wave 1)
<CRITICAL findings, Effort S first>

### Phase 2: Security Hardening (Wave 1-2)
<Security-related HIGH/MEDIUM findings>

### Phase 3: Test Coverage (Wave 2)
<Quality/test-related findings>

### Phase 4: Architecture Improvements (Wave 2-3)
<Architecture-related findings>

### Phase 5: Tech Debt Cleanup (Wave 3)
<Remaining LOW/MEDIUM findings>
```

### Step 6: Display Results

Print a summary to the user:
- Total findings by severity
- Top 5 most critical findings with locations
- Recommended next steps
- If `--create-milestone` was NOT set, suggest: "Run `/meridian:scan --create-milestone` to create a remediation milestone"

### Step 7: Create Milestone (if --create-milestone)

Only if `--create-milestone` flag is set:

1. **Create the milestone**:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_milestone, transition_milestone
conn = connect(get_db_path('.'))
create_milestone(conn, 'audit-remediation', '<milestone_name>', description='Auto-generated from codebase audit scan')
transition_milestone(conn, 'audit-remediation', 'active')
conn.close()
"
```

2. **Create phases** from the recommended groupings in REPORT.md:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_phase
conn = connect(get_db_path('.'))
# Phase for each recommended group
create_phase(conn, 'audit-remediation', 'Critical Fixes', description='Address all CRITICAL findings from audit')
create_phase(conn, 'audit-remediation', 'Security Hardening', description='Address security-related findings')
create_phase(conn, 'audit-remediation', 'Test Coverage', description='Fill test coverage gaps identified in audit')
create_phase(conn, 'audit-remediation', 'Architecture Improvements', description='Address structural and design issues')
create_phase(conn, 'audit-remediation', 'Tech Debt Cleanup', description='Address remaining low-priority findings')
conn.close()
"
```

3. **Create plans** within each phase for individual findings:
```bash
PYTHONPATH=~/dev/meridian uv run --project ~/dev/meridian python -c "
from scripts.db import connect, get_db_path
from scripts.state import create_plan
conn = connect(get_db_path('.'))
# For each finding, create a plan in the appropriate phase
# Wave assignment: S effort = wave 1, M effort = wave 2, L effort = wave 3
create_plan(conn, phase_id=<phase_id>, name='<finding_title>', description='<finding_description>', wave=<wave_from_effort>)
conn.close()
"
```

Assign waves based on effort: S → wave 1, M → wave 2, L → wave 3.

4. **Show the created structure**:
Run `/meridian:status` to display the new milestone, phases, and plans.

## Output

Final output should show:
- Audit report location: `.meridian/audit/REPORT.md`
- Summary table of findings
- If milestone created: milestone structure with phase/plan counts
- Next recommended action (e.g., "Run `/meridian:execute` to start Phase 1")
