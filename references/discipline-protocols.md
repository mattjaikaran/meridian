# Meridian Discipline Protocols

Engineering discipline rules enforced by Meridian's execution engine. These are embedded in subagent prompts and verified during review.

## 1. TDD Iron Law

**Rule**: No production code without a failing test first.

**Cycle**: RED → GREEN → REFACTOR

1. **RED**: Write a test that describes the desired behavior. Run it. It must fail.
2. **GREEN**: Write the minimum production code to make the test pass. No more.
3. **REFACTOR**: Clean up both test and production code. Tests must still pass.

**Enforcement**:
- Plans with `tdd_required = 1` must include test file paths in `files_to_create`
- Implementer subagent prompt requires test-first approach
- Review stage checks for test coverage of new code

**Exceptions**:
- Configuration files, templates, static assets
- Plans with `tdd_required = 0` (explicitly opted out)
- Quick tasks (`/meridian:quick`) — TDD optional

## 2. Systematic Debugging

**Rule**: 3+ failed fixes = architectural problem. Stop patching, re-think.

**Phases**:

### Phase 1: Investigation
- Read the error message completely
- Identify the exact file and line
- Understand the expected vs actual behavior
- Check recent changes (git log, git diff)

### Phase 2: Pattern Recognition
- Is this a known pattern? (null reference, race condition, wrong type, missing import)
- Has this error occurred before in this project?
- Search codebase for similar patterns

### Phase 3: Hypothesis
- Form a specific hypothesis: "The error occurs because X"
- Identify what evidence would confirm or refute the hypothesis
- Test the hypothesis with minimal changes

### Phase 4: Implementation
- Fix at the source, not the symptom
- Verify the fix resolves the original error
- Check for regression (run full test suite)
- Document the root cause as a decision

**Escalation**: After 3 failed fix attempts:
- Stop and create a decision entry with category "deviation"
- Re-examine assumptions
- Consider if the problem is architectural
- May need to re-plan the phase

## 3. Two-Stage Review

**Rule**: Never skip stage 1. Spec compliance before code quality.

### Stage 1: Spec Compliance Review
- Does the implementation match the plan description?
- Are all acceptance criteria met?
- Are all files listed in `files_to_create` / `files_to_modify` accounted for?
- Do tests cover the specified behavior?

### Stage 2: Code Quality Review
- Is the code clean and readable?
- Are there security concerns? (OWASP top 10)
- Is error handling appropriate?
- Are there performance concerns?
- Does it follow project conventions?

**Enforcement**:
- `/meridian:execute` runs both stages after each plan
- `/meridian:review` can be run independently
- Review failures transition phase back to `executing`

## 4. Verification Before Completion

**Rule**: Fresh evidence required. No claiming done without proving it works.

**Requirements before marking a plan complete**:
1. Tests pass (run `test_command` if specified)
2. No regressions (run project test suite)
3. Code compiles/imports without errors
4. Linter passes (ruff for Python, etc.)

**Requirements before marking a phase complete**:
1. All plans complete or skipped
2. All acceptance criteria verified with evidence
3. Two-stage review passed
4. Git state clean (committed)

## 5. Compressed Debugging (In Executors)

When a subagent encounters an error during execution:

1. **Read** the full error message and stack trace
2. **Trace** to the source file and line
3. **Fix** at the source (not by suppressing the error)
4. **Document** the root cause in a brief note

If the fix doesn't work after 2 attempts, the subagent should:
- Mark the plan as `failed` with the error message
- Let the coordinator handle escalation

## 6. Context Window Discipline

**Rule**: Checkpoint before context is lost.

- Track estimated token usage via `scripts/context_window.py`
- At 150k estimated tokens, trigger auto-checkpoint
- Subagents get scoped context (only what the plan needs) — never share context between them
- Resume prompt is always generated from SQLite, never from conversation history
