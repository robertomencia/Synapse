"""Aggregated cross-context state — the shared memory of the Rule Engine."""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DependencyInfo:
    name: str
    version: str
    ecosystem: str  # "npm" | "pip"
    source_file: str


@dataclass
class CVEEntry:
    id: str
    package: str
    severity: str  # "critical" | "high" | "medium" | "low" | "unknown"
    published: datetime
    description: str
    feed_url: str
    affected_versions: list[str] = field(default_factory=list)


@dataclass
class CalendarEvent:
    uid: str
    summary: str
    start: datetime
    tags: list[str] = field(default_factory=list)  # ["deploy", "meeting", "deadline"]
    end: datetime | None = None


@dataclass
class EngineState:
    # From DependencyCollector
    dependencies: dict[str, DependencyInfo] = field(default_factory=dict)  # key: "name@version"
    active_workspace: str | None = None

    # From RSSCollector
    cve_entries: list[CVEEntry] = field(default_factory=list)
    last_cve_check: datetime | None = None

    # From CalendarCollector
    upcoming_events: list[CalendarEvent] = field(default_factory=list)
    last_calendar_check: datetime | None = None

    # From FileWatcher (via event bus)
    last_changed_file: str | None = None
    last_changed_at: datetime | None = None

    # Extra context from any collector
    extra: dict[str, Any] = field(default_factory=dict)


class StateStore:
    """Thread-safe aggregated context store for the Rule Engine."""

    def __init__(self) -> None:
        self._state = EngineState()
        self._lock = asyncio.Lock()

    async def update_dependencies(self, deps: dict[str, DependencyInfo]) -> None:
        async with self._lock:
            self._state.dependencies = deps

    async def update_workspace(self, workspace: str) -> None:
        async with self._lock:
            self._state.active_workspace = workspace

    async def update_cves(self, entries: list[CVEEntry]) -> None:
        async with self._lock:
            self._state.cve_entries = entries
            self._state.last_cve_check = datetime.now(timezone.utc)

    async def update_calendar(self, events: list[CalendarEvent]) -> None:
        async with self._lock:
            self._state.upcoming_events = events
            self._state.last_calendar_check = datetime.now(timezone.utc)

    async def update_active_file(self, path: str) -> None:
        async with self._lock:
            self._state.last_changed_file = path
            self._state.last_changed_at = datetime.now(timezone.utc)

    async def set_extra(self, key: str, value: Any) -> None:
        async with self._lock:
            self._state.extra[key] = value

    async def snapshot(self) -> EngineState:
        """Return a deep copy of the current state (safe to read without lock)."""
        async with self._lock:
            return copy.deepcopy(self._state)
