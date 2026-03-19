"""Central asyncio event bus — the nervous system of Synapse."""

from __future__ import annotations

import asyncio
import fnmatch
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Coroutine


@dataclass
class SynapseEvent:
    type: str
    source: str
    payload: dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 5  # 1 (critical) → 10 (background)


Handler = Callable[[SynapseEvent], Coroutine[Any, Any, None]]


class EventBus:
    """Asyncio pub/sub bus with wildcard pattern support (fnmatch)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._queue: asyncio.Queue[SynapseEvent] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, pattern: str, handler: Handler) -> None:
        """Subscribe handler to events matching pattern (e.g. 'file.*', 'agent.output.dev')."""
        self._subscribers[pattern].append(handler)

    def unsubscribe(self, pattern: str, handler: Handler) -> None:
        if pattern in self._subscribers:
            self._subscribers[pattern].discard(handler)  # type: ignore[attr-defined]

    async def publish(self, event: SynapseEvent) -> None:
        await self._queue.put(event)

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._dispatch_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _dispatch_loop(self) -> None:
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            await self._dispatch(event)

    async def _dispatch(self, event: SynapseEvent) -> None:
        handlers: list[Handler] = []
        for pattern, pattern_handlers in self._subscribers.items():
            if fnmatch.fnmatch(event.type, pattern):
                handlers.extend(pattern_handlers)

        if not handlers:
            return

        await asyncio.gather(*[h(event) for h in handlers], return_exceptions=True)


# Global singleton — import and use directly
bus = EventBus()
