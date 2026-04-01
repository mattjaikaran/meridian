"""Integration test — full provider lifecycle with in-memory DB."""

from unittest.mock import patch

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
