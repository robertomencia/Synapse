"""LangGraph orchestration graph."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Any

from langgraph.graph import END, StateGraph

from synapse.agents.base import BaseAgent
from synapse.event_bus import SynapseEvent, bus
from synapse.memory.memory_manager import MemoryManager
from synapse.orchestrator.state import SynapseState

logger = logging.getLogger(__name__)


def _build_graph(agents: list[BaseAgent], memory: MemoryManager) -> Any:
    """Build and compile the LangGraph StateGraph."""

    async def ingest_node(state: SynapseState) -> SynapseState:
        """Fetch recent memory context for the event."""
        try:
            recent = await memory.get_recent(minutes=10)
            state["memory_context"] = [
                {"text": e.text, "source": e.source, "ts": e.timestamp.isoformat()}
                for e in recent[:5]
            ]
        except Exception as e:
            logger.warning("Memory retrieval failed: %s", e)
            state["memory_context"] = []
        return state

    async def route_node(state: SynapseState) -> SynapseState:
        """Determine which agents should handle this event."""
        event_type = state.get("event_type", "")
        matched = [
            a.name
            for a in agents
            if any(fnmatch.fnmatch(event_type, p) for p in a.subscribes_to)
        ]
        state["routing_decision"] = ",".join(matched) if matched else "none"
        return state

    async def dispatch_node(state: SynapseState) -> SynapseState:
        """Dispatch event to matched agents concurrently."""
        routing = state.get("routing_decision", "none")
        if routing == "none":
            state["agent_outputs"] = []
            return state

        targeted_names = set(routing.split(","))
        targeted_agents = [a for a in agents if a.name in targeted_names]

        event = SynapseEvent(
            type=state["event_type"],
            source=state["event_source"],
            payload=state["event_payload"],
            id=state["event_id"],
        )

        results = await asyncio.gather(
            *[a.process(event) for a in targeted_agents],
            return_exceptions=True,
        )

        outputs = []
        for agent, result in zip(targeted_agents, results):
            if isinstance(result, Exception):
                logger.error("Agent %s failed: %s", agent.name, result)
            elif result.is_notable:
                outputs.append({
                    "agent": result.agent_name,
                    "status": result.status,
                    "summary": result.summary,
                    "detail": result.detail,
                    "confidence": result.confidence,
                    "suggested_actions": result.suggested_actions,
                })

        state["agent_outputs"] = outputs
        return state

    async def emit_node(state: SynapseState) -> SynapseState:
        """Emit agent outputs back to the event bus for HUD consumption."""
        for output in state.get("agent_outputs", []):
            out_event = SynapseEvent(
                type=f"agent.output.{output['agent']}",
                source="orchestrator",
                payload=output,
                priority=3,
            )
            await bus.publish(out_event)
        return state

    def should_dispatch(state: SynapseState) -> str:
        return "dispatch" if state.get("routing_decision", "none") != "none" else "emit"

    graph = StateGraph(SynapseState)
    graph.add_node("ingest", ingest_node)
    graph.add_node("route", route_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("emit", emit_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "route")
    graph.add_conditional_edges("route", should_dispatch, {"dispatch": "dispatch", "emit": "emit"})
    graph.add_edge("dispatch", "emit")
    graph.add_edge("emit", END)

    return graph.compile()


class Orchestrator:
    def __init__(self, agents: list[BaseAgent], memory: MemoryManager) -> None:
        self._graph = _build_graph(agents, memory)
        self._agents = agents

    async def handle(self, event: SynapseEvent) -> None:
        state: SynapseState = {
            "event_type": event.type,
            "event_source": event.source,
            "event_payload": event.payload,
            "event_id": event.id,
        }
        try:
            await self._graph.ainvoke(state)
        except Exception as e:
            logger.error("Orchestrator failed for event %s: %s", event.type, e)

    def subscribe_to_bus(self) -> None:
        """Subscribe the orchestrator to all relevant event patterns."""
        for pattern in ["file.*", "screen.*", "vscode.*", "system.*"]:
            bus.subscribe(pattern, self.handle)
