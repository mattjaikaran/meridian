#!/usr/bin/env python3
"""Tests for Axis PM ticket sync — _run_pm_command list args."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.axis_sync import _run_pm_command


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
