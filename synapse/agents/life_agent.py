"""Life Agent — tracks focus, context switches, and productivity patterns."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime

from synapse.agents.base import AgentOutput, BaseAgent
from synapse.event_bus import SynapseEvent
from synapse.memory.models import Observation

logger = logging.getLogger(__name__)

FOCUS_THRESHOLD_SWITCHES = 10  # switches per hour = distraction alert


class LifeAgent(BaseAgent):
    name = "life"
    subscribes_to = ["screen.context"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._switches: list[tuple[datetime, str]] = []

    async def process(self, event: SynapseEvent) -> AgentOutput:
        app = event.payload.get("app", "other")
        title = event.payload.get("window_title", "")
        now = datetime.utcnow()

        self._switches.append((now, app))
        self._switches = [(t, a) for t, a in self._switches if (now - t).seconds < 3600]

        # Count switches in last hour
        if len(self._switches) > FOCUS_THRESHOLD_SWITCHES:
            apps = Counter(a for _, a in self._switches)
            top_app = apps.most_common(1)[0][0] if apps else "unknown"
            summary = f"High context switching detected ({len(self._switches)} switches/hr)"
            detail = (
                f"You've switched contexts {len(self._switches)} times in the last hour. "
                f"Most time in: {top_app}. Consider a focus session."
            )

            obs = Observation(
                text=summary,
                source=self.name,
                event_type=event.type,
                metadata={"switches": len(self._switches), "top_app": top_app},
            )
            await self._memory.store_observation(obs)

            return AgentOutput(
                agent_name=self.name,
                status="insight",
                summary=summary,
                detail=detail,
                confidence=0.85,
                suggested_actions=["Start a Pomodoro session", f"Stay in {top_app} for 25 min"],
                metadata={"app": app, "title": title},
            )

        # Just observe quietly
        obs = Observation(
            text=f"Active in {app}: {title[:80]}",
            source=self.name,
            event_type=event.type,
            metadata={"app": app},
        )
        await self._memory.store_observation(obs)

        return self._idle()
