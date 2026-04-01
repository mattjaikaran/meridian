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
