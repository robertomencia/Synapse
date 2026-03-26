"""Dependency collector — reads package.json / requirements.txt from active workspace."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from synapse.collectors.base import BaseCollector
from synapse.event_bus import SynapseEvent, bus
from synapse.rules.state_store import DependencyInfo

if TYPE_CHECKING:
    from synapse.rules.state_store import StateStore

logger = logging.getLogger(__name__)

# Strip semver operators: ^1.2.3, ~1.2.3, >=1.2.3, etc.
_SEMVER_PREFIX = re.compile(r"^[\^~>=<! ]+")

TARGET_FILES = {"package.json", "requirements.txt", "Pipfile", "pyproject.toml"}


def _strip_version(v: str) -> str:
    return _SEMVER_PREFIX.sub("", v).split(",")[0].strip()


class DependencyCollector(BaseCollector):
    """Event-driven collector: reacts to file.changed and vscode.context events."""

    def __init__(self, state_store: "StateStore", initial_workspace: Path | None = None) -> None:
        super().__init__(state_store)
        self._workspace = initial_workspace
        self._running = False

    async def start(self) -> None:
        self._running = True
        bus.subscribe("vscode.context", self._on_vscode_context)
        bus.subscribe("file.changed", self._on_file_changed)
        bus.subscribe("file.created", self._on_file_changed)
        if self._workspace and self._workspace.exists():
            await self._scan_workspace(self._workspace)
        logger.debug("DependencyCollector started")

    async def stop(self) -> None:
        self._running = False

    async def _on_vscode_context(self, event: SynapseEvent) -> None:
        workspace_str = event.payload.get("workspace", "")
        if workspace_str:
            workspace = Path(workspace_str)
            await self._store.update_workspace(str(workspace))
            self._workspace = workspace
            await self._scan_workspace(workspace)

    async def _on_file_changed(self, event: SynapseEvent) -> None:
        name = Path(event.payload.get("path", "")).name
        if name in TARGET_FILES:
            path = Path(event.payload.get("path", ""))
            await self._parse_dep_file(path)

    async def _scan_workspace(self, workspace: Path) -> None:
        deps: dict[str, DependencyInfo] = {}
        for filename in TARGET_FILES:
            candidate = workspace / filename
            if candidate.exists():
                found = await self._parse_dep_file(candidate)
                deps.update(found)
        if deps:
            await self._store.update_dependencies(deps)
            logger.info("DependencyCollector: found %d dependencies in %s", len(deps), workspace)

    async def _parse_dep_file(self, path: Path) -> dict[str, DependencyInfo]:
        try:
            if path.name == "package.json":
                return self._parse_package_json(path)
            elif path.name == "requirements.txt":
                return self._parse_requirements_txt(path)
            elif path.name == "pyproject.toml":
                return self._parse_pyproject_toml(path)
        except Exception as e:
            logger.warning("DependencyCollector: failed to parse %s: %s", path, e)
        return {}

    def _parse_package_json(self, path: Path) -> dict[str, DependencyInfo]:
        data = json.loads(path.read_text(encoding="utf-8"))
        deps: dict[str, DependencyInfo] = {}
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name, version_spec in data.get(section, {}).items():
                version = _strip_version(str(version_spec))
                key = f"{name}@{version}"
                deps[key] = DependencyInfo(
                    name=name,
                    version=version,
                    ecosystem="npm",
                    source_file=str(path),
                )
        if deps:
            # Update store immediately (don't wait for scan)
            import asyncio
            asyncio.create_task(self._store.update_dependencies(deps))
        return deps

    def _parse_requirements_txt(self, path: Path) -> dict[str, DependencyInfo]:
        deps: dict[str, DependencyInfo] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Handle: package==1.0, package>=1.0, package~=1.0
            match = re.split(r"[=><~!;@]", line, maxsplit=1)
            name = match[0].strip()
            version = _strip_version(line[len(name):]) if len(match) > 1 else "latest"
            key = f"{name}@{version}"
            deps[key] = DependencyInfo(
                name=name,
                version=version,
                ecosystem="pip",
                source_file=str(path),
            )
        return deps

    def _parse_pyproject_toml(self, path: Path) -> dict[str, DependencyInfo]:
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                logger.debug("tomllib/tomli not available, skipping pyproject.toml parsing")
                return {}

        data = tomllib.loads(path.read_text(encoding="utf-8"))
        deps: dict[str, DependencyInfo] = {}

        # PEP 621 format
        for dep_str in data.get("project", {}).get("dependencies", []):
            match = re.split(r"[=><~!;@\[ ]", dep_str, maxsplit=1)
            name = match[0].strip()
            version = _strip_version(dep_str[len(name):]) if len(match) > 1 else "latest"
            key = f"{name}@{version}"
            deps[key] = DependencyInfo(
                name=name,
                version=version,
                ecosystem="pip",
                source_file=str(path),
            )
        return deps
