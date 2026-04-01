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
