"""File system watcher using watchdog."""

from __future__ import annotations

import asyncio
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from synapse.event_bus import SynapseEvent, bus
from synapse.perception.base import Sensor

# Extensions that are worth monitoring
MONITORED_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".swift", ".kt",
    ".yaml", ".yml", ".toml", ".json", ".env", ".md", ".sql",
}


class _Handler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix not in MONITORED_EXTENSIONS:
            return
        self._emit("file.changed", path, "modified")

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix not in MONITORED_EXTENSIONS:
            return
        self._emit("file.created", path, "created")

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        self._emit("file.deleted", path, "deleted")

    def _emit(self, event_type: str, path: Path, action: str) -> None:
        payload = {
            "path": str(path),
            "name": path.name,
            "extension": path.suffix,
            "action": action,
        }
        if path.exists() and path.stat().st_size < 1_000_000:  # skip > 1MB
            try:
                payload["preview"] = path.read_text(encoding="utf-8", errors="ignore")[:500]
            except Exception:
                pass

        event = SynapseEvent(type=event_type, source="file_watcher", payload=payload)
        asyncio.run_coroutine_threadsafe(bus.publish(event), self._loop)


class FileWatcher(Sensor):
    def __init__(self, watch_paths: list[Path], warmup_delay: int = 5) -> None:
        self._paths = watch_paths
        self._warmup_delay = warmup_delay
        self._observer: Observer | None = None

    async def start(self) -> None:
        await asyncio.sleep(self._warmup_delay)  # avoid event storm on startup
        loop = asyncio.get_running_loop()
        handler = _Handler(loop)
        self._observer = Observer()
        for path in self._paths:
            if path.exists():
                self._observer.schedule(handler, str(path), recursive=True)
        self._observer.start()

    async def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join()
