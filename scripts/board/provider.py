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
        raise KeyError(
            f"Unknown board provider: {name!r}. Registered: {list(_registry)}"
        )
    return cls()


# Register built-in providers
register_provider("noop", NoopProvider)
