#!/usr/bin/env python3
"""Tests for Axis PM ticket sync — _run_pm_command list args."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.axis_sync import (
    MERIDIAN_TO_AXIS,
    _run_pm_command,
    create_axis_tickets_for_phases,
    sync_phase_to_axis,
)
from scripts.db import open_project
from scripts.state import (
    create_milestone,
    create_phase,
    create_project,
    list_phases,
    transition_milestone,
    transition_phase,
    update_phase,
)


class TestRunPmCommand:
    """Tests for _run_pm_command with list-based args."""

    def test_builds_correct_subprocess_args(self):
        """_run_pm_command passes correct list to subprocess.run."""
        mock_result = MagicMock()
        mock_result.stdout = "OK\n"

        pm_path = Path.home() / "zeroclaw" / "skills" / "kanban" / "pm.sh"

        with (
            patch("scripts.axis_sync.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            result = _run_pm_command(["ticket", "move", "PROJ-1", "done"])

        assert result == "OK"
        mock_run.assert_called_once_with(
            ["bash", str(pm_path), "ticket", "move", "PROJ-1", "done"],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_handles_args_with_spaces(self):
        """_run_pm_command keeps values with spaces intact (no split)."""
        mock_result = MagicMock()
        mock_result.stdout = "Created ticket PROJ-42\n"

        pm_path = Path.home() / "zeroclaw" / "skills" / "kanban" / "pm.sh"

        with (
            patch("scripts.axis_sync.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
        ):
            result = _run_pm_command(
                ["ticket", "add", "PROJ", "Phase Name With Spaces", "--description", "A long description"]
            )

        assert result == "Created ticket PROJ-42"
        args_passed = mock_run.call_args[0][0]
        # The phase name with spaces should be a single arg, not split
        assert "Phase Name With Spaces" in args_passed
        assert "A long description" in args_passed

    def test_raises_on_missing_script(self):
        """Raises FileNotFoundError when pm.sh doesn't exist."""
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="PM script not found"):
                _run_pm_command(["ticket", "list"])

    def test_callers_pass_list(self):
        """sync_phase_to_axis passes list args to _run_pm_command."""
        from scripts.axis_sync import sync_phase_to_axis
        from scripts.db import open_project
        from scripts.state import (
            create_milestone,
            create_phase,
            create_project,
            list_phases,
            transition_milestone,
            update_phase,
        )

        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build base")
            phases = list_phases(conn, "v1.0")
            phase = phases[0]
            update_phase(conn, phase["id"], axis_ticket_id="AXIS-1")

            with patch("scripts.axis_sync._run_pm_command") as mock_cmd:
                mock_cmd.return_value = "OK"
                # Call via the actual function which uses open_project
                # We need to test the internal call, so patch at module level
                with patch("scripts.axis_sync.open_project") as mock_op:
                    mock_op.return_value.__enter__ = lambda s: conn
                    mock_op.return_value.__exit__ = MagicMock(return_value=False)
                    sync_phase_to_axis(project_dir="/tmp")

                # Verify _run_pm_command was called with a list, not a string
                if mock_cmd.called:
                    args = mock_cmd.call_args[0][0]
                    assert isinstance(args, list), f"Expected list args, got {type(args)}: {args}"


# ── Helper to build a seeded connection for axis sync tests ──────────────────


def _make_axis_conn(axis_project_id="AXIS"):
    """Create an in-memory DB seeded with a project, milestone, and 2 phases."""
    import contextlib

    conn_holder = {}

    @contextlib.contextmanager
    def _open():
        yield conn_holder["conn"]

    with open_project(":memory:") as conn:
        create_project(conn, name="Test", repo_path="/tmp", axis_project_id=axis_project_id)
        create_milestone(conn, "v1.0", "Version 1.0")
        transition_milestone(conn, "v1.0", "active")
        create_phase(conn, "v1.0", "Foundation", description="Build base")
        create_phase(conn, "v1.0", "Features", description="Add features")
        conn_holder["conn"] = conn
        yield conn, _open


# ── TestSyncPhaseToAxis ──────────────────────────────────────────────────────


class TestSyncPhaseToAxis:
    """Tests for sync_phase_to_axis."""

    def test_skipped_when_no_axis_project_id(self):
        """Returns skipped when project has no axis_project_id configured."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp")  # no axis_project_id
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")

            with patch("scripts.axis_sync.open_project") as mock_op:
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = sync_phase_to_axis(project_dir="/tmp")

        assert result["status"] == "skipped"

    def test_calls_run_pm_command_with_correct_args(self):
        """Calls _run_pm_command with ['ticket', 'move', ticket_id, axis_status]."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")
            update_phase(conn, phases[0]["id"], axis_ticket_id="AXIS-1")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="OK") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                sync_phase_to_axis(project_dir="/tmp")

            mock_cmd.assert_called_once_with(["ticket", "move", "AXIS-1", "backlog"])

    def test_maps_executing_to_in_progress(self):
        """Maps meridian 'executing' status to axis 'in_progress'."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")
            pid = phases[0]["id"]
            update_phase(conn, pid, axis_ticket_id="AXIS-1")
            # Transition phase to executing
            transition_phase(conn, pid, "context_gathered")
            transition_phase(conn, pid, "planned_out")
            transition_phase(conn, pid, "executing")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="OK") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                sync_phase_to_axis(project_dir="/tmp")

            mock_cmd.assert_called_once_with(["ticket", "move", "AXIS-1", "in_progress"])

    def test_skips_phases_without_axis_ticket_id(self):
        """Phases without axis_ticket_id are skipped (no _run_pm_command call)."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")  # no axis_ticket_id

            with (
                patch("scripts.axis_sync._run_pm_command") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = sync_phase_to_axis(project_dir="/tmp")

            mock_cmd.assert_not_called()
            assert result["status"] == "synced"
            assert result["results"] == []

    def test_only_syncs_specified_phase_id(self):
        """When phase_id is provided, only that phase is synced."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            create_phase(conn, "v1.0", "Features")
            phases = list_phases(conn, "v1.0")
            update_phase(conn, phases[0]["id"], axis_ticket_id="AXIS-1")
            update_phase(conn, phases[1]["id"], axis_ticket_id="AXIS-2")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="OK") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                # Only sync phase 2
                sync_phase_to_axis(project_dir="/tmp", phase_id=phases[1]["id"])

            # Only one call for AXIS-2
            assert mock_cmd.call_count == 1
            mock_cmd.assert_called_once_with(["ticket", "move", "AXIS-2", "backlog"])

    def test_status_mapping_complete(self):
        """Verify MERIDIAN_TO_AXIS has mappings for all expected statuses."""
        expected = {"planned", "context_gathered", "planned_out", "executing",
                    "verifying", "reviewing", "complete", "blocked"}
        assert set(MERIDIAN_TO_AXIS.keys()) == expected


# ── TestCreateAxisTickets ────────────────────────────────────────────────────


class TestCreateAxisTickets:
    """Tests for create_axis_tickets_for_phases."""

    def test_skipped_when_no_axis_project_id(self):
        """Returns skipped when project has no axis_project_id."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")

            with patch("scripts.axis_sync.open_project") as mock_op:
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = create_axis_tickets_for_phases(project_dir="/tmp")

        assert result[0]["status"] == "skipped"

    def test_creates_tickets_for_phases_without_axis_ticket_id(self):
        """Creates tickets for phases that lack axis_ticket_id."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build base")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="Created ticket AXIS-10") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = create_axis_tickets_for_phases(project_dir="/tmp")

            assert len(result) == 1  # Only Foundation phase exists
            assert result[0]["ticket_id"] == "AXIS-10"
            mock_cmd.assert_called_once()

    def test_skips_phases_with_existing_axis_ticket_id(self):
        """Phases with axis_ticket_id are skipped."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="AXIS")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation")
            phases = list_phases(conn, "v1.0")
            update_phase(conn, phases[0]["id"], axis_ticket_id="AXIS-1")

            with (
                patch("scripts.axis_sync._run_pm_command") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = create_axis_tickets_for_phases(project_dir="/tmp")

            mock_cmd.assert_not_called()
            assert result == []

    def test_parses_ticket_id_from_output(self):
        """Parses ticket ID from 'Created ticket PROJ-123' output."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="PROJ")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="Created ticket PROJ-123") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = create_axis_tickets_for_phases(project_dir="/tmp")

            assert result[0]["ticket_id"] == "PROJ-123"
            # Verify it was stored in the DB
            phases = list_phases(conn, "v1.0")
            assert phases[0]["axis_ticket_id"] == "PROJ-123"

    def test_records_error_when_ticket_id_unparseable(self):
        """Records error when ticket ID can't be parsed from output."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="PROJ")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="Something unexpected") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                result = create_axis_tickets_for_phases(project_dir="/tmp")

            assert "error" in result[0]
            assert "Could not parse ticket ID" in result[0]["error"]

    def test_calls_run_pm_command_with_ticket_add(self):
        """Calls _run_pm_command with ['ticket', 'add', project_id, name, ...]."""
        with open_project(":memory:") as conn:
            create_project(conn, name="Test", repo_path="/tmp", axis_project_id="PROJ")
            create_milestone(conn, "v1.0", "Version 1.0")
            transition_milestone(conn, "v1.0", "active")
            create_phase(conn, "v1.0", "Foundation", description="Build base")

            with (
                patch("scripts.axis_sync._run_pm_command", return_value="Created ticket PROJ-1") as mock_cmd,
                patch("scripts.axis_sync.open_project") as mock_op,
            ):
                mock_op.return_value.__enter__ = lambda s: conn
                mock_op.return_value.__exit__ = MagicMock(return_value=False)
                create_axis_tickets_for_phases(project_dir="/tmp")

            mock_cmd.assert_called_once_with(
                ["ticket", "add", "PROJ", "Foundation", "--description", "Build base"]
            )
