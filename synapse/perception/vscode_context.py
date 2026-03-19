"""VS Code context reader — detects active file and workspace."""

from __future__ import annotations

import asyncio
import json
import platform
from pathlib import Path

from synapse.event_bus import SynapseEvent, bus
from synapse.perception.base import Sensor


def _find_vscode_storage() -> Path | None:
    system = platform.system()
    if system == "Windows":
        base = Path.home() / "AppData" / "Roaming" / "Code" / "User"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "Code" / "User"
    else:
        base = Path.home() / ".config" / "Code" / "User"

    storage = base / "globalStorage" / "storage.json"
    return storage if storage.exists() else None


class VSCodeContext(Sensor):
    def __init__(self, interval: int = 10) -> None:
        self._interval = interval
        self._running = False
        self._last_workspace: str | None = None

    async def start(self) -> None:
        self._running = True
        while self._running:
            await self._poll()
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False

    async def _poll(self) -> None:
        storage = _find_vscode_storage()
        if not storage:
            return

        try:
            data = json.loads(storage.read_text(encoding="utf-8"))
            # Recent workspaces from VS Code storage
            workspaces = data.get("openedPathsList", {}).get("workspaces3", [])
            if not workspaces:
                return

            current = workspaces[0] if workspaces else None
            if not current or current == self._last_workspace:
                return

            self._last_workspace = current
            event = SynapseEvent(
                type="vscode.context",
                source="vscode_context",
                payload={"workspace": current, "recent_workspaces": workspaces[:5]},
                priority=7,
            )
            await bus.publish(event)
        except Exception:
            pass
