"""Pytest fixtures."""

import pytest
import tempfile
from pathlib import Path

from synapse.memory.memory_manager import MemoryManager


@pytest.fixture
def tmp_memory(tmp_path: Path) -> MemoryManager:
    chroma = tmp_path / "chroma"
    sqlite = tmp_path / "test.db"
    manager = MemoryManager(chroma, sqlite)
    manager.connect()
    yield manager
    manager.close()
