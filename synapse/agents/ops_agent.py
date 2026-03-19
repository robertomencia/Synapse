"""Ops Agent — monitors system resources and alerts on anomalies."""

from __future__ import annotations

import asyncio
import logging

import psutil

from synapse.agents.base import AgentOutput, BaseAgent
from synapse.event_bus import SynapseEvent, bus
from synapse.memory.models import AgentAction, Observation

logger = logging.getLogger(__name__)

CPU_THRESHOLD = 90.0  # %
MEMORY_THRESHOLD = 90.0  # %
DISK_THRESHOLD = 95.0  # %


class OpsAgent(BaseAgent):
    name = "ops"
    subscribes_to = ["system.check"]  # triggered by its own polling loop

    def __init__(self, *args, poll_interval: int = 60, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._poll_interval = poll_interval
        self._running = False

    async def start_polling(self) -> None:
        """Run as a background task — publishes system.check events."""
        self._running = True
        while self._running:
            await asyncio.sleep(self._poll_interval)
            metrics = self._collect_metrics()
            event = SynapseEvent(
                type="system.check",
                source=self.name,
                payload=metrics,
                priority=9,
            )
            await bus.publish(event)

    async def stop_polling(self) -> None:
        self._running = False

    async def process(self, event: SynapseEvent) -> AgentOutput:
        metrics = event.payload
        alerts: list[str] = []

        if metrics.get("cpu_percent", 0) > CPU_THRESHOLD:
            alerts.append(f"CPU at {metrics['cpu_percent']:.0f}%")
        if metrics.get("memory_percent", 0) > MEMORY_THRESHOLD:
            alerts.append(f"RAM at {metrics['memory_percent']:.0f}%")
        if metrics.get("disk_percent", 0) > DISK_THRESHOLD:
            alerts.append(f"Disk at {metrics['disk_percent']:.0f}%")

        if not alerts:
            return self._idle()

        summary = f"System pressure: {', '.join(alerts)}"
        detail = f"Resource thresholds exceeded. Metrics: {metrics}"

        obs = Observation(
            text=summary,
            source=self.name,
            event_type=event.type,
            metadata=metrics,
        )
        await self._memory.store_observation(obs)

        action_record = AgentAction(
            agent_name=self.name,
            action_type="alert",
            summary=summary,
            detail=detail,
            confidence=1.0,
            suggested_actions=["Check running processes", "Free up memory"],
            metadata=metrics,
        )
        await self._memory.store_action(action_record)

        return AgentOutput(
            agent_name=self.name,
            status="alert",
            summary=summary,
            detail=detail,
            confidence=1.0,
            metadata=metrics,
        )

    def _collect_metrics(self) -> dict:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "memory_available_gb": round(psutil.virtual_memory().available / 1e9, 1),
        }
