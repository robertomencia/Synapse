"""Memory data models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Observation(BaseModel):
    """A raw observation from the perception layer or an agent insight."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    source: str  # "file_watcher" | "dev_agent" | "screen_capture" | etc.
    event_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentAction(BaseModel):
    """An action taken or proposed by an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str
    action_type: str  # "insight" | "alert" | "action_taken" | "suggestion"
    summary: str
    detail: str
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_actions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    executed: bool = False


class MemoryEntry(BaseModel):
    """Unified memory entry returned from queries."""

    id: str
    text: str
    source: str
    entry_type: Literal["observation", "action"]
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.0
