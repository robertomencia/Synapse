"""PyQt6 application — runs in a daemon thread, bridges asyncio→Qt."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Callable

from PyQt6.QtCore import QMetaObject, Qt, Q_ARG
from PyQt6.QtWidgets import QApplication

from synapse.event_bus import SynapseEvent, bus
from synapse.hud.overlay import SynapseOverlay

logger = logging.getLogger(__name__)


class HUDApp:
    def __init__(self) -> None:
        self._app: QApplication | None = None
        self._overlay: SynapseOverlay | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start the Qt application in a daemon thread."""
        self._loop = loop
        self._thread = threading.Thread(target=self._run_qt, daemon=True, name="synapse-hud")
        self._thread.start()

    def _run_qt(self) -> None:
        self._app = QApplication(sys.argv[:1])
        self._overlay = SynapseOverlay()
        self._overlay.show()

        # Register event bus subscriber from Qt thread
        bus.subscribe("agent.output.*", self._on_agent_output_threadsafe)

        self._app.exec()

    def _on_agent_output_threadsafe(self, event: SynapseEvent) -> None:
        """Called from asyncio thread — dispatch to Qt thread safely."""
        if not self._overlay:
            return
        agent = event.payload.get("agent", "unknown")
        status = event.payload.get("status", "insight")
        summary = event.payload.get("summary", "")

        # This is a sync callback called from asyncio — use invokeMethod for Qt thread safety
        QMetaObject.invokeMethod(
            self._overlay,
            "show_notification",
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, agent),
            Q_ARG(str, status),
            Q_ARG(str, summary),
        )

    def stop(self) -> None:
        if self._app:
            self._app.quit()
