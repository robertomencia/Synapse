"""Episodic/procedural memory backed by SQLite."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from synapse.memory.models import AgentAction, MemoryEntry, Observation


CREATE_OBSERVATIONS = """
CREATE TABLE IF NOT EXISTS observations (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL
)
"""

CREATE_AGENT_ACTIONS = """
CREATE TABLE IF NOT EXISTS agent_actions (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    detail TEXT NOT NULL,
    confidence REAL NOT NULL,
    suggested_actions TEXT NOT NULL DEFAULT '[]',
    metadata TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL,
    executed INTEGER NOT NULL DEFAULT 0
)
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_obs_timestamp ON observations(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_obs_source ON observations(source)",
    "CREATE INDEX IF NOT EXISTS idx_actions_timestamp ON agent_actions(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_actions_agent ON agent_actions(agent_name)",
]


class SQLiteStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._migrate()

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def _migrate(self) -> None:
        assert self._conn
        self._conn.execute(CREATE_OBSERVATIONS)
        self._conn.execute(CREATE_AGENT_ACTIONS)
        for idx in CREATE_INDEXES:
            self._conn.execute(idx)

    def _c(self) -> sqlite3.Connection:
        assert self._conn, "SQLiteStore not connected — call connect() first"
        return self._conn

    # --- Observations ---

    def insert_observation(self, obs: Observation) -> None:
        self._c().execute(
            "INSERT OR REPLACE INTO observations VALUES (?,?,?,?,?,?)",
            (
                obs.id,
                obs.text,
                obs.source,
                obs.event_type,
                json.dumps(obs.metadata),
                obs.timestamp.isoformat(),
            ),
        )

    def get_recent_observations(self, minutes: int = 30) -> list[MemoryEntry]:
        since = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        rows = self._c().execute(
            "SELECT id, text, source, metadata, timestamp FROM observations "
            "WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,),
        ).fetchall()
        return [
            MemoryEntry(
                id=r[0],
                text=r[1],
                source=r[2],
                entry_type="observation",
                metadata=json.loads(r[3]),
                timestamp=datetime.fromisoformat(r[4]),
            )
            for r in rows
        ]

    # --- Agent Actions ---

    def insert_action(self, action: AgentAction) -> None:
        self._c().execute(
            "INSERT OR REPLACE INTO agent_actions VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                action.id,
                action.agent_name,
                action.action_type,
                action.summary,
                action.detail,
                action.confidence,
                json.dumps(action.suggested_actions),
                json.dumps(action.metadata),
                action.timestamp.isoformat(),
                int(action.executed),
            ),
        )

    def get_recent_actions(self, minutes: int = 60) -> list[MemoryEntry]:
        since = (datetime.utcnow() - timedelta(minutes=minutes)).isoformat()
        rows = self._c().execute(
            "SELECT id, summary, agent_name, metadata, timestamp FROM agent_actions "
            "WHERE timestamp >= ? ORDER BY timestamp DESC",
            (since,),
        ).fetchall()
        return [
            MemoryEntry(
                id=r[0],
                text=r[1],
                source=r[2],
                entry_type="action",
                metadata=json.loads(r[3]),
                timestamp=datetime.fromisoformat(r[4]),
            )
            for r in rows
        ]

    def purge_old(self, retention_days: int) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
        c = self._c()
        c.execute("DELETE FROM observations WHERE timestamp < ?", (cutoff,))
        c.execute("DELETE FROM agent_actions WHERE timestamp < ?", (cutoff,))
        return c.execute("SELECT changes()").fetchone()[0]
