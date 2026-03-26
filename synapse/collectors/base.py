"""Abstract base class for all Synapse context collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.rules.state_store import StateStore


class BaseCollector(ABC):
    """Collectors gather structured context and write it to the StateStore.

    Unlike perception Sensors (which emit events reactively), collectors feed
    the deterministic Rule Engine with cross-context state snapshots.
    """

    def __init__(self, state_store: "StateStore") -> None:
        self._store = state_store

    @abstractmethod
    async def start(self) -> None:
        """Start collecting. Should run indefinitely until stop() is called."""

    @abstractmethod
    async def stop(self) -> None:
        """Signal the collector to stop."""
