# Pluggable Board Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the hardcoded Axis kanban integration with a provider-based plugin system so users can plug in their own board tools (Linear, Jira, GitHub Projects, etc.) or use Meridian standalone with no board at all.

**Architecture:** A `BoardProvider` protocol defines the contract (`create_ticket`, `move_ticket`). Providers are registered by name and resolved from a project setting (`board_provider`). The `transition_phase()` hook auto-syncs on status change. DB columns rename from `axis_*` to `board_*` via migration v7.

**Tech Stack:** Python 3.13, sqlite3, `typing.Protocol`, subprocess (for shell-based providers like Axis)

---

### Task 1: Define the BoardProvider Protocol

**Files:**
- Create: `scripts/board/__init__.py`
- Create: `scripts/board/provider.py`

**Step 1: Write the failing test**

Create `tests/test_board_provider.py`:

```python
"""Tests for BoardProvider protocol and registry."""

import pytest

from scripts.board.provider import (
    BoardProvider,
    NoopProvider,
    get_provider,
    register_provider,
)


class TestBoardProviderProtocol:
    """BoardProvider protocol enforces the contract."""

    def test_noop_provider_satisfies_protocol(self):
        provider = NoopProvider()
        assert isinstance(provider, BoardProvider)

    def test_noop_create_ticket_returns_none(self):
        provider = NoopProvider()
        result = provider.create_ticket(
            project_id="PROJ", name="Phase 1", description="desc"
        )
        assert result is None

    def test_noop_move_ticket_returns_none(self):
        provider = NoopProvider()
        result = provider.move_ticket(ticket_id="PROJ-1", status="done")
        assert result is None


class TestProviderRegistry:
    """Provider registration and lookup."""

    def test_register_and_get_provider(self):
        register_provider("noop", NoopProvider)
        provider = get_provider("noop")
        assert isinstance(provider, NoopProvider)

    def test_get_unknown_provider_raises(self):
        with pytest.raises(KeyError, match="Unknown board provider"):
            get_provider("nonexistent_provider_xyz")

    def test_noop_registered_by_default(self):
        provider = get_provider("noop")
        assert isinstance(provider, NoopProvider)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.board'`

**Step 3: Write minimal implementation**

Create `scripts/board/__init__.py`:
```python
"""Pluggable board sync — provider-based kanban integration."""
```

Create `scripts/board/provider.py`:
```python
"""BoardProvider protocol and registry."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BoardProvider(Protocol):
    """Contract for kanban board integrations.

    Providers sync Meridian phase status to external board tools.
    All methods return the external ticket ID on success, None on skip/noop.
    """

    def create_ticket(
        self,
        project_id: str,
        name: str,
        description: str = "",
    ) -> str | None: ...

    def move_ticket(
        self,
        ticket_id: str,
        status: str,
    ) -> str | None: ...


class NoopProvider:
    """Default provider — does nothing. Meridian works standalone."""

    def create_ticket(
        self,
        project_id: str,
        name: str,
        description: str = "",
    ) -> str | None:
        return None

    def move_ticket(
        self,
        ticket_id: str,
        status: str,
    ) -> str | None:
        return None


# ── Registry ─────────────────────────────────────────────────────────────────

_registry: dict[str, type[BoardProvider]] = {}


def register_provider(name: str, cls: type[BoardProvider]) -> None:
    """Register a board provider by name."""
    _registry[name] = cls


def get_provider(name: str) -> BoardProvider:
    """Instantiate a registered provider by name."""
    cls = _registry.get(name)
    if cls is None:
        raise KeyError(f"Unknown board provider: {name!r}. Registered: {list(_registry)}")
    return cls()


# Register built-in providers
register_provider("noop", NoopProvider)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_provider.py -v`
Expected: PASS (all 6 tests)

**Step 5: Commit**

```bash
git add scripts/board/__init__.py scripts/board/provider.py tests/test_board_provider.py
git commit -m "feat: add BoardProvider protocol and registry with noop default"
```

---

### Task 2: Axis Provider (migrate existing logic)

**Files:**
- Create: `scripts/board/axis.py`
- Modify: `tests/test_board_provider.py` (add Axis tests)

**Step 1: Write the failing test**

Append to `tests/test_board_provider.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.board.axis import AxisProvider


class TestAxisProvider:
    """Tests for the Axis PM provider."""

    def test_satisfies_protocol(self):
        provider = AxisProvider()
        assert isinstance(provider, BoardProvider)

    def test_create_ticket_calls_pm_sh(self):
        mock_result = MagicMock()
        mock_result.stdout = "Created ticket PROJ-42\n"
        pm_path = Path(os.environ.get("BOARD_PM_SCRIPT", str(Path.home() / "bin" / "pm.sh")))

        with (
            patch("scripts.board.axis.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            provider = AxisProvider()
            ticket_id = provider.create_ticket("PROJ", "Foundation", "Build base")

        assert ticket_id == "PROJ-42"
        mock_run.assert_called_once_with(
            ["bash", str(pm_path), "ticket", "add", "PROJ", "Foundation",
             "--description", "Build base"],
            capture_output=True, text=True, timeout=30,
        )

    def test_move_ticket_calls_pm_sh(self):
        mock_result = MagicMock()
        mock_result.stdout = "OK\n"
        pm_path = Path(os.environ.get("BOARD_PM_SCRIPT", str(Path.home() / "bin" / "pm.sh")))

        with (
            patch("scripts.board.axis.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            provider = AxisProvider()
            result = provider.move_ticket("PROJ-1", "done")

        assert result == "PROJ-1"
        mock_run.assert_called_once_with(
            ["bash", str(pm_path), "ticket", "move", "PROJ-1", "done"],
            capture_output=True, text=True, timeout=30,
        )

    def test_create_ticket_returns_none_when_script_missing(self):
        with patch.object(Path, "exists", return_value=False):
            provider = AxisProvider()
            result = provider.create_ticket("PROJ", "Phase", "desc")
        assert result is None

    def test_move_ticket_returns_none_when_script_missing(self):
        with patch.object(Path, "exists", return_value=False):
            provider = AxisProvider()
            result = provider.move_ticket("PROJ-1", "done")
        assert result is None

    def test_axis_registered_in_registry(self):
        provider = get_provider("axis")
        assert isinstance(provider, AxisProvider)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_provider.py::TestAxisProvider -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.board.axis'`

**Step 3: Write implementation**

Create `scripts/board/axis.py`:
```python
"""Axis PM kanban board provider."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from scripts.board.provider import register_provider

logger = logging.getLogger(__name__)

# Axis status ↔ Meridian phase status mapping
MERIDIAN_TO_AXIS = {
    "planned": "backlog",
    "context_gathered": "backlog",
    "planned_out": "todo",
    "executing": "in_progress",
    "verifying": "in_progress",
    "reviewing": "in_review",
    "complete": "done",
    "blocked": "blocked",
}

AXIS_TO_MERIDIAN = {
    "created": "planned",
    "backlog": "planned",
    "ready": "planned_out",
    "todo": "planned_out",
    "in_progress": "executing",
    "in_review": "reviewing",
    "done": "complete",
    "blocked": "blocked",
}

PM_SCRIPT = Path(os.environ.get("BOARD_PM_SCRIPT", str(Path.home() / "bin" / "pm.sh")))


def _run_pm_command(args: list[str]) -> str | None:
    """Run a pm.sh command. Returns stdout or None if script missing."""
    if not PM_SCRIPT.exists():
        logger.warning("PM script not found at %s — skipping", PM_SCRIPT)
        return None
    try:
        result = subprocess.run(
            ["bash", str(PM_SCRIPT)] + args,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError) as e:
        logger.error("PM command failed: %s", e)
        return None


def _parse_ticket_id(output: str) -> str | None:
    """Parse ticket ID from pm.sh output like 'Created ticket PROJ-123'."""
    for word in output.split():
        if "-" in word and any(c.isdigit() for c in word):
            return word
    return None


class AxisProvider:
    """Axis PM kanban board integration via pm.sh shell script."""

    def create_ticket(
        self,
        project_id: str,
        name: str,
        description: str = "",
    ) -> str | None:
        output = _run_pm_command(
            ["ticket", "add", project_id, name, "--description", description]
        )
        if output is None:
            return None
        return _parse_ticket_id(output)

    def move_ticket(
        self,
        ticket_id: str,
        status: str,
    ) -> str | None:
        output = _run_pm_command(["ticket", "move", ticket_id, status])
        if output is None:
            return None
        return ticket_id


register_provider("axis", AxisProvider)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_provider.py -v`
Expected: PASS (all 12 tests)

**Step 5: Commit**

```bash
git add scripts/board/axis.py tests/test_board_provider.py
git commit -m "feat: add Axis board provider wrapping pm.sh"
```

---

### Task 3: DB Migration — Rename axis_* to board_*

**Files:**
- Modify: `scripts/db.py` (add migration v7, update SCHEMA_SQL)
- Modify: `scripts/state.py` (rename column references)

**Step 1: Write the failing test**

Create `tests/test_board_migration.py`:

```python
"""Tests for board column migration (axis_* → board_*)."""

import sqlite3

from scripts.db import init_schema, get_schema_version, open_project


class TestBoardMigration:
    """Migration v7 renames axis_* columns to board_*."""

    def test_fresh_db_has_board_columns(self):
        """New databases get board_* columns directly."""
        with open_project(":memory:") as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(project)").fetchall()}
            assert "board_project_id" in cols
            assert "axis_project_id" not in cols

            cols = {row[1] for row in conn.execute("PRAGMA table_info(phase)").fetchall()}
            assert "board_ticket_id" in cols
            assert "axis_ticket_id" not in cols

    def test_migration_preserves_data(self):
        """Existing axis_* data is carried over to board_* columns."""
        with open_project(":memory:") as conn:
            # Simulate pre-migration state by inserting with axis columns
            # (the schema already has board_*, so we check the migration path
            # by verifying get_schema_version >= 7)
            version = get_schema_version(conn)
            assert version >= 7
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_migration.py -v`
Expected: FAIL — `assert 'board_project_id' in cols` (still `axis_project_id`)

**Step 3: Update SCHEMA_SQL and add migration**

In `scripts/db.py`, update `SCHEMA_SQL`:
- Change `axis_project_id TEXT` → `board_project_id TEXT` in project table
- Change `axis_ticket_id TEXT` → `board_ticket_id TEXT` in phase table

Add migration function:

```python
def _migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Rename axis_project_id → board_project_id, axis_ticket_id → board_ticket_id."""
    # SQLite doesn't support RENAME COLUMN before 3.25, but Python 3.13 ships 3.45+
    proj_cols = {row[1] for row in conn.execute("PRAGMA table_info(project)").fetchall()}
    if "axis_project_id" in proj_cols and "board_project_id" not in proj_cols:
        conn.execute("ALTER TABLE project RENAME COLUMN axis_project_id TO board_project_id")

    phase_cols = {row[1] for row in conn.execute("PRAGMA table_info(phase)").fetchall()}
    if "axis_ticket_id" in phase_cols and "board_ticket_id" not in phase_cols:
        conn.execute("ALTER TABLE phase RENAME COLUMN axis_ticket_id TO board_ticket_id")

    conn.execute("INSERT OR REPLACE INTO schema_version (version) VALUES (?)", (7,))
    conn.commit()
```

Wire it into `init_schema()`:
```python
    current_version = get_schema_version(conn)
    if current_version < 7:
        if db_path is not None and str(db_path) != ":memory:":
            backup_database(Path(db_path), max_backups=5)
        _migrate_v6_to_v7(conn)
```

Update `SCHEMA_VERSION = 7`.

In `scripts/state.py`, find-and-replace:
- `axis_project_id` → `board_project_id` (in ALLOWED_COLUMNS, create_project, update_project)
- `axis_ticket_id` → `board_ticket_id` (in ALLOWED_COLUMNS, create_phase, update_phase)

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_board_migration.py -v`
Expected: PASS

**Step 5: Run full test suite to check nothing broke**

Run: `python -m pytest tests/ -v`
Expected: PASS (axis_sync tests will fail — that's expected, we fix them next)

**Step 6: Commit**

```bash
git add scripts/db.py scripts/state.py tests/test_board_migration.py
git commit -m "refactor: rename axis_* columns to board_* with migration v7"
```

---

### Task 4: Board Sync Module — Wire Provider into Phase Transitions

**Files:**
- Create: `scripts/board/sync.py`
- Modify: `scripts/state.py` (add hook in `transition_phase`)

**Step 1: Write the failing test**

Create `tests/test_board_sync.py`:

```python
"""Tests for board sync — auto-sync on phase transitions."""

from unittest.mock import MagicMock, patch

import pytest

from scripts.board.provider import BoardProvider, get_provider, register_provider
from scripts.board.sync import sync_phase, create_tickets_for_phases
from scripts.db import open_project
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    list_phases,
    transition_milestone,
    transition_phase,
    update_phase,
    get_setting,
)


class FakeProvider:
    """Test provider that records calls."""

    def __init__(self):
        self.calls = []

    def create_ticket(self, project_id, name, description=""):
        self.calls.append(("create", project_id, name))
        return f"FAKE-{len(self.calls)}"

    def move_ticket(self, ticket_id, status):
        self.calls.append(("move", ticket_id, status))
        return ticket_id


class TestSyncPhase:
    """sync_phase uses the configured provider."""

    def test_skips_when_no_board_provider_setting(self):
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp")
            create_milestone(conn, "v1.0", "V1")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")

            result = sync_phase(conn, phases[0]["id"])
            assert result["status"] == "skipped"

    def test_syncs_with_configured_provider(self):
        fake = FakeProvider()
        register_provider("fake_test", lambda: None)  # placeholder

        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp",
                           board_project_id="PROJ")
            create_milestone(conn, "v1.0", "V1")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")
            update_phase(conn, phases[0]["id"], board_ticket_id="PROJ-1")

            from scripts.state import set_setting
            set_setting(conn, "board_provider", "axis")

            with patch("scripts.board.sync.get_provider", return_value=fake):
                result = sync_phase(conn, phases[0]["id"])

            assert result["status"] == "synced"
            assert fake.calls == [("move", "PROJ-1", "backlog")]


class TestCreateTickets:
    """create_tickets_for_phases creates tickets via provider."""

    def test_creates_tickets_and_stores_ids(self):
        fake = FakeProvider()

        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp",
                           board_project_id="PROJ")
            create_milestone(conn, "v1.0", "V1")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build base")

            from scripts.state import set_setting
            set_setting(conn, "board_provider", "axis")

            with patch("scripts.board.sync.get_provider", return_value=fake):
                result = create_tickets_for_phases(conn, "v1.0")

            assert len(result) == 1
            assert result[0]["ticket_id"] == "FAKE-1"
            # Verify stored in DB
            phases = list_phases(conn, "v1.0")
            assert phases[0]["board_ticket_id"] == "FAKE-1"


class TestTransitionPhaseHook:
    """transition_phase auto-syncs to board."""

    def test_transition_triggers_board_sync(self):
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp",
                           board_project_id="PROJ")
            create_milestone(conn, "v1.0", "V1")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")
            pid = phases[0]["id"]
            update_phase(conn, pid, board_ticket_id="PROJ-1")

            from scripts.state import set_setting
            set_setting(conn, "board_provider", "axis")

            with patch("scripts.state._board_sync_on_phase") as mock_sync:
                transition_phase(conn, pid, "context_gathered")
                mock_sync.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_board_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.board.sync'`

**Step 3: Write board/sync.py**

Create `scripts/board/sync.py`:
```python
"""Board sync — bridge between Meridian state and board providers."""

from __future__ import annotations

import logging
import sqlite3

from scripts.board.provider import get_provider

# Import axis to trigger its register_provider call
import scripts.board.axis  # noqa: F401

logger = logging.getLogger(__name__)

# Meridian status → generic board status
STATUS_MAP = {
    "planned": "backlog",
    "context_gathered": "backlog",
    "planned_out": "todo",
    "executing": "in_progress",
    "verifying": "in_progress",
    "reviewing": "in_review",
    "complete": "done",
    "blocked": "blocked",
}


def sync_phase(
    conn: sqlite3.Connection,
    phase_id: int,
    project_id: str = "default",
) -> dict:
    """Sync a single phase's status to its board ticket."""
    from scripts.state import get_phase, get_project, get_setting

    project = get_project(conn, project_id)
    if not project or not project.get("board_project_id"):
        return {"status": "skipped", "message": "No board project configured"}

    provider_name = get_setting(conn, "board_provider", project_id=project_id)
    if not provider_name:
        return {"status": "skipped", "message": "No board_provider setting"}

    phase = get_phase(conn, phase_id)
    if not phase or not phase.get("board_ticket_id"):
        return {"status": "skipped", "message": "Phase has no board ticket"}

    provider = get_provider(provider_name)
    board_status = STATUS_MAP.get(phase["status"], "backlog")

    try:
        provider.move_ticket(phase["board_ticket_id"], board_status)
        return {
            "status": "synced",
            "ticket": phase["board_ticket_id"],
            "board_status": board_status,
        }
    except Exception as e:
        logger.error("Board sync failed for phase %d: %s", phase_id, e)
        return {"status": "error", "error": str(e)}


def create_tickets_for_phases(
    conn: sqlite3.Connection,
    milestone_id: str,
    project_id: str = "default",
) -> list[dict]:
    """Create board tickets for phases that don't have them yet."""
    from scripts.state import get_project, get_setting, list_phases, update_phase

    project = get_project(conn, project_id)
    if not project or not project.get("board_project_id"):
        return [{"status": "skipped", "message": "No board project configured"}]

    provider_name = get_setting(conn, "board_provider", project_id=project_id)
    if not provider_name:
        return [{"status": "skipped", "message": "No board_provider setting"}]

    provider = get_provider(provider_name)
    board_project = project["board_project_id"]
    phases = list_phases(conn, milestone_id)
    created = []

    for phase in phases:
        if phase.get("board_ticket_id"):
            continue

        try:
            ticket_id = provider.create_ticket(
                board_project, phase["name"], phase.get("description", "")
            )
            if ticket_id:
                update_phase(conn, phase["id"], board_ticket_id=ticket_id)
                created.append({"phase": phase["name"], "ticket_id": ticket_id})
            else:
                created.append({"phase": phase["name"], "error": "Provider returned None"})
        except Exception as e:
            logger.error("Ticket creation failed for phase %s: %s", phase["name"], e)
            created.append({"phase": phase["name"], "error": str(e)})

    return created
```

**Step 4: Add hook in state.py's transition_phase**

In `scripts/state.py`, after the roadmap sync block in `transition_phase()`, add:

```python
    # Board sync (informational, non-blocking)
    _board_sync_on_phase(conn, phase_id)
```

And add the helper:

```python
def _board_sync_on_phase(conn: sqlite3.Connection, phase_id: int) -> None:
    """Sync phase status to board provider. Non-blocking — errors are logged."""
    try:
        from scripts.board.sync import sync_phase
        sync_phase(conn, phase_id)
    except Exception as e:
        logger.warning("Board sync skipped: %s", e)
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_board_sync.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add scripts/board/sync.py scripts/state.py tests/test_board_sync.py
git commit -m "feat: wire board sync into phase transitions with provider resolution"
```

---

### Task 5: Update axis_sync.py Tests and Remove Old Module

**Files:**
- Delete: `scripts/axis_sync.py`
- Modify: `tests/test_axis_sync.py` → rewrite to test `scripts/board/axis.py`
- Modify: `references/axis-integration.md` (update to reference new paths)

**Step 1: Update test imports and verify old tests still pass under new structure**

Rewrite `tests/test_axis_sync.py` to import from `scripts.board.axis` instead:

```python
"""Tests for Axis board provider — backward compat with pm.sh."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.board.axis import (
    MERIDIAN_TO_AXIS,
    AxisProvider,
    _run_pm_command,
    _parse_ticket_id,
)
from scripts.board.provider import BoardProvider, get_provider


class TestRunPmCommand:
    """Tests for _run_pm_command with list-based args."""

    def test_builds_correct_subprocess_args(self):
        mock_result = MagicMock()
        mock_result.stdout = "OK\n"
        pm_path = Path(os.environ.get("BOARD_PM_SCRIPT", str(Path.home() / "bin" / "pm.sh")))

        with (
            patch("scripts.board.axis.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            result = _run_pm_command(["ticket", "move", "PROJ-1", "done"])

        assert result == "OK"
        mock_run.assert_called_once_with(
            ["bash", str(pm_path), "ticket", "move", "PROJ-1", "done"],
            capture_output=True, text=True, timeout=30,
        )

    def test_returns_none_on_missing_script(self):
        with patch.object(Path, "exists", return_value=False):
            result = _run_pm_command(["ticket", "list"])
        assert result is None


class TestParseTicketId:
    """Tests for ticket ID parsing."""

    def test_parses_standard_format(self):
        assert _parse_ticket_id("Created ticket PROJ-123") == "PROJ-123"

    def test_returns_none_for_no_match(self):
        assert _parse_ticket_id("Something unexpected") is None


class TestAxisProviderProtocol:
    """Axis provider satisfies BoardProvider."""

    def test_satisfies_protocol(self):
        assert isinstance(AxisProvider(), BoardProvider)

    def test_registered_as_axis(self):
        provider = get_provider("axis")
        assert isinstance(provider, AxisProvider)


class TestStatusMapping:
    """Verify status mapping completeness."""

    def test_all_meridian_statuses_mapped(self):
        expected = {"planned", "context_gathered", "planned_out", "executing",
                    "verifying", "reviewing", "complete", "blocked"}
        assert set(MERIDIAN_TO_AXIS.keys()) == expected
```

**Step 2: Run the rewritten tests**

Run: `python -m pytest tests/test_axis_sync.py -v`
Expected: PASS

**Step 3: Delete old axis_sync.py**

```bash
git rm scripts/axis_sync.py
```

**Step 4: Update references/axis-integration.md**

Replace the Configuration section to reference the new paths:

```markdown
## Configuration
- Set `board_provider` setting to `"axis"` via `/meridian:init` or manually
- `board_project_id` set on project record
- Provider code at `scripts/board/axis.py`
- PM script at `$BOARD_PM_SCRIPT (or ~/bin/pm.sh default)`
- Axis auth handled by existing sync infrastructure

## Plugin System
- Axis is one of many possible board providers
- See `scripts/board/provider.py` for the `BoardProvider` protocol
- Custom providers: implement `create_ticket()` and `move_ticket()`, call `register_provider()`
```

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: PASS

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: remove standalone axis_sync, rewrite tests for board provider"
```

---

### Task 6: Update SKILL.md, README, and generate_commands

**Files:**
- Modify: `SKILL.md` (update file listing)
- Modify: `README.md` (update directory structure)
- Modify: `scripts/generate_commands.py` (update reference)

**Step 1: Update SKILL.md**

Replace `scripts/axis_sync.py -- Axis PM ticket sync` with:
```
scripts/board/          -- Pluggable board sync (kanban integration)
  provider.py           -- BoardProvider protocol and registry
  axis.py               -- Axis PM provider (pm.sh)
  sync.py               -- Sync bridge (called from phase transitions)
```

**Step 2: Update README.md directory listing**

Same replacement pattern as SKILL.md.

**Step 3: Update generate_commands.py**

Replace the `axis_sync.py` reference with `scripts/board/` description.

**Step 4: Commit**

```bash
git add SKILL.md README.md scripts/generate_commands.py
git commit -m "docs: update references for pluggable board sync module"
```

---

### Task 7: Integration Test — End-to-End Provider Flow

**Files:**
- Create: `tests/test_board_integration.py`

**Step 1: Write the integration test**

```python
"""Integration test — full provider lifecycle with in-memory DB."""

from scripts.board.provider import BoardProvider, register_provider, get_provider
from scripts.board.sync import create_tickets_for_phases, sync_phase
from scripts.db import open_project
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    get_phase,
    list_phases,
    set_setting,
    transition_milestone,
    transition_phase,
)


class InMemoryProvider:
    """Test provider that tracks state in a dict."""

    def __init__(self):
        self.tickets: dict[str, str] = {}  # ticket_id → status
        self._counter = 0

    def create_ticket(self, project_id, name, description=""):
        self._counter += 1
        tid = f"{project_id}-{self._counter}"
        self.tickets[tid] = "backlog"
        return tid

    def move_ticket(self, ticket_id, status):
        self.tickets[ticket_id] = status
        return ticket_id


class TestBoardIntegration:
    """End-to-end: create project → create tickets → transition → verify sync."""

    def test_full_lifecycle(self):
        provider = InMemoryProvider()
        # Register with a factory that returns our instance
        register_provider("inmemory", lambda: None)

        with open_project(":memory:") as conn:
            # Setup project
            create_project(conn, name="Test", repo_path="/tmp",
                           board_project_id="TEST")
            create_milestone(conn, "v1.0", "Version 1")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Base layer")
            create_phase(conn, "v1.0", "Features", description="Add features")
            set_setting(conn, "board_provider", "inmemory")

            # Create tickets
            from unittest.mock import patch
            with patch("scripts.board.sync.get_provider", return_value=provider):
                results = create_tickets_for_phases(conn, "v1.0")

            assert len(results) == 2
            assert all("ticket_id" in r for r in results)

            # Verify tickets stored in DB
            phases = list_phases(conn, "v1.0")
            assert phases[0]["board_ticket_id"] == "TEST-1"
            assert phases[1]["board_ticket_id"] == "TEST-2"

            # Verify provider state
            assert provider.tickets["TEST-1"] == "backlog"

            # Sync after transition
            pid = phases[0]["id"]
            transition_phase(conn, pid, "context_gathered")
            with patch("scripts.board.sync.get_provider", return_value=provider):
                sync_phase(conn, pid)

            assert provider.tickets["TEST-1"] == "backlog"  # context_gathered maps to backlog
```

**Step 2: Run it**

Run: `python -m pytest tests/test_board_integration.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_board_integration.py
git commit -m "test: add end-to-end board provider integration test"
```

---

Plan complete and saved to `docs/plans/2026-04-01-pluggable-board-sync.md`. Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?