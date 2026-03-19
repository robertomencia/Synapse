"""Screen context sensor — captures active window title periodically."""

from __future__ import annotations

import asyncio
import platform

from synapse.event_bus import SynapseEvent, bus
from synapse.perception.base import Sensor


def _get_active_window() -> str | None:
    """Get active window title cross-platform."""
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or None
        elif system == "Darwin":
            from AppKit import NSWorkspace  # type: ignore
            app = NSWorkspace.sharedWorkspace().activeApplication()
            return app.get("NSApplicationName")
        else:  # Linux
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip() or None
    except Exception:
        return None


class ScreenCapture(Sensor):
    def __init__(self, interval: int = 5) -> None:
        self._interval = interval
        self._running = False
        self._last_title: str | None = None

    async def start(self) -> None:
        self._running = True
        while self._running:
            title = _get_active_window()
            if title and title != self._last_title:
                self._last_title = title
                event = SynapseEvent(
                    type="screen.context",
                    source="screen_capture",
                    payload={"window_title": title, "app": self._extract_app(title)},
                    priority=8,
                )
                await bus.publish(event)
            await asyncio.sleep(self._interval)

    async def stop(self) -> None:
        self._running = False

    def _extract_app(self, title: str) -> str:
        """Guess the app from the window title."""
        title_lower = title.lower()
        if "visual studio code" in title_lower or "vscode" in title_lower:
            return "vscode"
        if "chrome" in title_lower or "firefox" in title_lower or "edge" in title_lower:
            return "browser"
        if "terminal" in title_lower or "cmd" in title_lower or "powershell" in title_lower:
            return "terminal"
        if "slack" in title_lower:
            return "slack"
        if "outlook" in title_lower or "gmail" in title_lower:
            return "email"
        return "other"
