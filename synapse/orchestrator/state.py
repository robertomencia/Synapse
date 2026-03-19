"""LangGraph state definition."""

from __future__ import annotations

from typing import Any, TypedDict


class SynapseState(TypedDict, total=False):
    event_type: str
    event_source: str
    event_payload: dict[str, Any]
    event_id: str
    routing_decision: str
    agent_outputs: list[dict]
    memory_context: list[dict]
    error: str | None
