"""Unified facade over ChromaDB + SQLite memory stores."""

from __future__ import annotations

from pathlib import Path

from synapse.memory.chroma_store import ChromaStore
from synapse.memory.models import AgentAction, MemoryEntry, Observation
from synapse.memory.sqlite_store import SQLiteStore


class MemoryManager:
    def __init__(self, chroma_path: Path, sqlite_path: Path) -> None:
        self._chroma = ChromaStore(chroma_path)
        self._sqlite = SQLiteStore(sqlite_path)

    def connect(self) -> None:
        self._chroma.connect()
        self._sqlite.connect()

    def close(self) -> None:
        self._sqlite.close()

    async def store_observation(self, obs: Observation) -> str:
        """Store an observation in both stores (semantic + episodic)."""
        self._sqlite.insert_observation(obs)
        self._chroma.upsert(obs)
        return obs.id

    async def store_action(self, action: AgentAction) -> str:
        """Store an agent action in SQLite."""
        self._sqlite.insert_action(action)
        return action.id

    async def search_semantic(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """Vector similarity search — best for 'what was I working on?' queries."""
        return self._chroma.query(query, n=limit)

    async def get_recent(self, minutes: int = 30) -> list[MemoryEntry]:
        """Time-based retrieval of recent observations + actions."""
        obs = self._sqlite.get_recent_observations(minutes)
        actions = self._sqlite.get_recent_actions(minutes)
        combined = sorted(obs + actions, key=lambda e: e.timestamp, reverse=True)
        return combined

    async def purge_old(self, retention_days: int) -> int:
        return self._sqlite.purge_old(retention_days)

    @property
    def total_observations(self) -> int:
        return self._chroma.count()
