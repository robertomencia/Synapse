"""Base agent contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.event_bus import SynapseEvent
    from synapse.llm.ollama_client import OllamaClient
    from synapse.memory.memory_manager import MemoryManager


@dataclass
class AgentOutput:
    agent_name: str
    status: str  # "insight" | "alert" | "action" | "idle"
    summary: str  # One sentence — shown in HUD
    detail: str  # Full analysis — stored in memory
    confidence: float = 0.8
    suggested_actions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def is_notable(self) -> bool:
        return self.status in ("insight", "alert", "action")


class BaseAgent(ABC):
    name: str
    subscribes_to: list[str]  # event type patterns e.g. ["file.*", "screen.context"]

    def __init__(self, memory: "MemoryManager", llm: "OllamaClient") -> None:
        self._memory = memory
        self._llm = llm

    @abstractmethod
    async def process(self, event: "SynapseEvent") -> AgentOutput:
        """Process an event and return an output."""

    def _idle(self) -> AgentOutput:
        return AgentOutput(
            agent_name=self.name,
            status="idle",
            summary="",
            detail="",
            confidence=1.0,
        )
