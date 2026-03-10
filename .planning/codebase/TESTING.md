# Testing Patterns

**Analysis Date:** 2026-03-10

## Test Framework

**Runner:**
- pytest (no version pinned in `pyproject.toml` -- stdlib-only project, pytest is a dev dependency)
- Config: No `pytest.ini`, `conftest.py`, or `[tool.pytest]` section. Uses pytest defaults.

**Assertion Library:**
- pytest native assertions (plain `assert` statements)
- `pytest.raises` for exception testing

**Run Commands:**
```bash
pytest                     # Run all tests
pytest tests/test_state.py # Run single file
pytest -v                  # Verbose output
pytest -x                  # Stop on first failure
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)

**Naming:**
- Files: `test_{module}.py` mirroring `scripts/{module}.py`
- Classes: `Test{Entity}` grouping related tests: `TestProject`, `TestPhase`, `TestPlan`
- Methods: `test_{behavior}` describing what is tested: `test_create_and_get`, `test_valid_transitions`

**Structure:**
```
tests/
├── __init__.py          # Empty package marker
├── test_state.py        # Tests for scripts/state.py (CRUD, transitions, next action, status)
├── test_resume.py       # Tests for scripts/resume.py (prompt generation)
├── test_metrics.py      # Tests for scripts/metrics.py (velocity, cycle times, stalls, forecasts)
└── test_sync.py         # Tests for scripts/sync.py (Nero dispatch sync)
```

**Coverage Map:**
| Source Module | Test File | Tested |
|---|---|---|
| `scripts/state.py` | `tests/test_state.py` | Yes |
| `scripts/resume.py` | `tests/test_resume.py` | Yes |
| `scripts/metrics.py` | `tests/test_metrics.py` | Yes |
| `scripts/sync.py` | `tests/test_sync.py` | Yes |
| `scripts/db.py` | `tests/test_state.py` (indirectly) | Partial |
| `scripts/dispatch.py` | None | No |
| `scripts/export.py` | None | No |
| `scripts/context_window.py` | None | No |
| `scripts/axis_sync.py` | None | No |

## Test Structure

**Suite Organization:**
```python
# Each test file follows this pattern:

# 1. Imports with sys.path hack
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 2. Fixtures
@pytest.fixture
def db():
    """Create a temporary in-memory database with schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_schema(conn)
    yield conn
    conn.close()

@pytest.fixture
def seeded_db(db):
    """DB with a project, milestone, and phases."""
    create_project(db, name="Test Project", repo_path="/tmp/test")
    create_milestone(db, milestone_id="v1.0", name="Version 1.0")
    transition_milestone(db, "v1.0", "active")
    create_phase(db, milestone_id="v1.0", name="Foundation")
    create_phase(db, milestone_id="v1.0", name="Features")
    return db

# 3. Test classes grouped by entity/concern
class TestProject:
    def test_create_and_get(self, db):
        ...

class TestMilestone:
    def test_valid_transitions(self, db):
        ...
```

**Patterns:**
- **Setup:** Fixtures provide clean in-memory SQLite databases. Two tiers: `db` (empty schema) and `seeded_db` (with project/milestone/phases).
- **Teardown:** `yield` in fixtures handles `conn.close()`. No explicit teardown in tests.
- **Assertion:** Plain `assert` with direct value comparison. No assertion helpers or custom matchers.

## Fixtures

**Two standard fixtures used across all test files:**

**`db` fixture (base):**
- Creates in-memory SQLite connection
- Sets `row_factory` and `foreign_keys`
- Runs `init_schema()`
- Yields connection, closes on teardown
- Used when test needs to control all data setup

**`seeded_db` fixture (convenience):**
- Builds on `db` fixture
- Creates default project, active milestone, and 2 phases ("Foundation", "Features")
- Returns connection (not yielded -- relies on `db` fixture for cleanup)
- Used when test needs pre-existing entities

**`test_resume.py` uses a different `db` fixture:**
- Creates a real file-backed SQLite database in `tmp_path`
- Returns `(conn, project_dir)` tuple
- Required because `generate_resume_prompt()` takes a directory path and opens its own connection

**Important:** Each test file defines its own fixtures (no shared `conftest.py`). The `db` and `seeded_db` fixture patterns are duplicated across files with minor variations.

## Mocking

**Framework:** `unittest.mock.patch` (stdlib)

**Patterns:**
```python
from unittest.mock import patch

# Mock external HTTP calls to Nero
mock_response = {
    "status": "completed",
    "pr_url": "https://github.com/pr/1",
    "commit_sha": "abc123",
}

with patch("scripts.sync._nero_rpc", return_value=mock_response):
    results = pull_dispatch_status(seeded_db)
```

**What to Mock:**
- External HTTP calls (`_nero_rpc` in `scripts/sync.py`)
- Only the internal RPC helper is mocked, not `urllib` directly
- Mock at the narrowest boundary (private helper function)

**What NOT to Mock:**
- Database operations (use in-memory SQLite instead)
- State transitions (test real behavior)
- Internal function calls between modules

**Mock usage is limited to `tests/test_sync.py` only.** All other tests run against real (in-memory) databases with no mocks.

## Fixtures and Factories

**Test Data:**
- No factory library used
- Entities created via the same CRUD functions used in production code
- Consistent test data: project name "Test Project" or "TestApp", milestone "v1.0"/"Version 1.0", phases "Foundation"/"Features"

**Common setup pattern:**
```python
# Build up state through real transitions (no shortcuts)
phase = list_phases(seeded_db, "v1.0")[0]
transition_phase(seeded_db, phase["id"], "context_gathered")
transition_phase(seeded_db, phase["id"], "planned_out")
transition_phase(seeded_db, phase["id"], "executing")
p = create_plan(seeded_db, phase["id"], "Plan 1", "Do thing")
transition_plan(seeded_db, p["id"], "executing")
transition_plan(seeded_db, p["id"], "complete")
```

**Direct DB manipulation for time-based tests:**
```python
# Backdate timestamps to test time-dependent behavior
seeded_db.execute(
    "UPDATE plan SET started_at = datetime('now', '-30 hours') WHERE id = ?",
    (p["id"],),
)
seeded_db.commit()
```

**Location:**
- No separate fixtures directory. All fixtures are inline in test files.

## Coverage

**Requirements:** None enforced. No coverage configuration or thresholds.

**View Coverage:**
```bash
pytest --cov=scripts       # Requires pytest-cov (not currently configured)
```

## Test Types

**Unit Tests:**
- All tests are unit tests operating on in-memory SQLite
- Test individual functions in isolation
- State machine transitions tested exhaustively (valid paths and invalid paths)

**Integration Tests:**
- `tests/test_sync.py` tests integration between sync, state, and dispatch modules (with mocked HTTP)
- `tests/test_resume.py` tests the full resume prompt generation pipeline

**E2E Tests:**
- Not used. No end-to-end tests that exercise the CLI entry points.

## Common Patterns

**State Machine Testing:**
```python
# Test valid transition chain
def test_valid_transitions(self, db):
    create_project(db, name="App", repo_path="/dev/app")
    create_milestone(db, "v1.0", "V1")
    p = create_phase(db, "v1.0", "Phase 1")
    pid = p["id"]

    p = transition_phase(db, pid, "context_gathered")
    assert p["status"] == "context_gathered"
    p = transition_phase(db, pid, "planned_out")
    assert p["status"] == "planned_out"
    # ... continue through all valid states

# Test invalid transition
def test_invalid_transition(self, db):
    create_project(db, name="App", repo_path="/dev/app")
    create_milestone(db, "v1.0", "V1")
    p = create_phase(db, "v1.0", "Phase 1")
    with pytest.raises(ValueError, match="Invalid phase transition"):
        transition_phase(db, p["id"], "executing")  # can't skip
```

**Error Testing:**
```python
with pytest.raises(ValueError, match="Invalid transition"):
    transition_milestone(db, "v1.0", "complete")  # can't skip active
```

**Next Action / Decision Tree Testing:**
```python
# Test each branch of compute_next_action by building up specific states
class TestNextAction:
    def test_no_milestones(self, db):
        create_project(db, name="App", repo_path="/dev/app")
        action = compute_next_action(db)
        assert action["action"] == "create_milestone"

    def test_phase_needs_context(self, seeded_db):
        action = compute_next_action(seeded_db)
        assert action["action"] == "gather_context"
```

**Determinism Testing (in `test_resume.py`):**
```python
def test_deterministic(self, db):
    """Same state = same prompt (excluding git state which may change)."""
    conn, project_dir = db
    # ... setup state ...
    prompt1 = generate_resume_prompt(project_dir)
    prompt2 = generate_resume_prompt(project_dir)
    assert prompt1 == prompt2
```

## Adding New Tests

**For a new `scripts/{module}.py`:**
1. Create `tests/test_{module}.py`
2. Add the `sys.path` hack at top of file
3. Define `db` and optionally `seeded_db` fixtures (copy from existing test file)
4. Group tests in classes by entity/concern
5. Use real CRUD functions to set up state (no shortcuts around the state machine)
6. Mock only external I/O (HTTP, filesystem, subprocess)

**For a new state entity:**
1. Add CRUD tests in `tests/test_state.py` under a new `Test{Entity}` class
2. Test create, get, list, and transition functions
3. Test both valid and invalid transitions
4. Add next-action test cases in `TestNextAction` if the entity affects routing

---

*Testing analysis: 2026-03-10*
