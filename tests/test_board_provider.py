"""Tests for BoardProvider protocol and registry."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.board.cli import CliProvider
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


class TestCliProvider:
    """Tests for the CLI-based board provider."""

    def test_satisfies_protocol(self):
        provider = CliProvider()
        assert isinstance(provider, BoardProvider)

    def test_create_ticket_calls_pm_sh(self):
        mock_result = MagicMock()
        mock_result.stdout = "Created ticket PROJ-42\n"
        pm_path = Path.home() / "bin" / "pm.sh"

        with (
            patch("scripts.board.cli.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
            patch("scripts.board.cli.PM_SCRIPT", pm_path),
        ):
            provider = CliProvider()
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
        pm_path = Path.home() / "bin" / "pm.sh"

        with (
            patch("scripts.board.cli.subprocess.run", return_value=mock_result) as mock_run,
            patch.object(Path, "exists", return_value=True),
            patch("scripts.board.cli.PM_SCRIPT", pm_path),
        ):
            provider = CliProvider()
            result = provider.move_ticket("PROJ-1", "done")

        assert result == "PROJ-1"
        mock_run.assert_called_once_with(
            ["bash", str(pm_path), "ticket", "move", "PROJ-1", "done"],
            capture_output=True, text=True, timeout=30,
        )

    def test_create_ticket_returns_none_when_script_missing(self):
        with patch.object(Path, "exists", return_value=False):
            provider = CliProvider()
            result = provider.create_ticket("PROJ", "Phase", "desc")
        assert result is None

    def test_move_ticket_returns_none_when_script_missing(self):
        with patch.object(Path, "exists", return_value=False):
            provider = CliProvider()
            result = provider.move_ticket("PROJ-1", "done")
        assert result is None

    def test_cli_registered_in_registry(self):
        provider = get_provider("cli")
        assert isinstance(provider, CliProvider)

    def test_axis_alias_registered(self):
        provider = get_provider("axis")
        assert isinstance(provider, CliProvider)
