"""Tests for CLI-based board provider internals."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.board.cli import (
    MERIDIAN_TO_BOARD,
    CliProvider,
    _run_pm_command,
    _parse_ticket_id,
)
from scripts.board.provider import BoardProvider, get_provider


class TestRunPmCommand:
    """Tests for _run_pm_command with list-based args."""

    def test_builds_correct_subprocess_args(self):
        mock_result = MagicMock()
        mock_result.stdout = "OK\n"
        pm_path = Path.home() / "bin" / "pm.sh"

        with (
            patch("scripts.board.cli.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
            patch("scripts.board.cli.PM_SCRIPT", pm_path),
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


class TestCliProviderProtocol:
    """CLI provider satisfies BoardProvider."""

    def test_satisfies_protocol(self):
        assert isinstance(CliProvider(), BoardProvider)

    def test_registered_as_cli(self):
        provider = get_provider("cli")
        assert isinstance(provider, CliProvider)

    def test_registered_as_axis_alias(self):
        provider = get_provider("axis")
        assert isinstance(provider, CliProvider)


class TestStatusMapping:
    """Verify status mapping completeness."""

    def test_all_meridian_statuses_mapped(self):
        expected = {"planned", "context_gathered", "planned_out", "executing",
                    "verifying", "reviewing", "complete", "blocked"}
        assert set(MERIDIAN_TO_BOARD.keys()) == expected
